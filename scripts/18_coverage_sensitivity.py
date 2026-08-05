"""Teste de sensibilidade a COBERTURA de precos (results/08 s.4.2).

Pergunta: o resultado do backtest depende dos nomes que so temos PELA METADE?

O painel tem nomes cuja serie de precos cobre integralmente o periodo em que eles
foram membros do indice, e nomes cuja serie tem buracos (ou some no meio). A mascara
do universo ja exige `returns.notna()` no dia, entao um nome de cobertura parcial e
negociado nos dias em que existe e some silenciosamente nos outros -- e essas ausencias
NAO sao aleatorias: correlacionam com desfecho ruim (aquisicao, quebra).

O teste: re-rodar o backtest restrito aos nomes de cobertura >= limiar e comparar.
  - se o resultado nao se move, a contaminacao por cobertura parcial e toleravel;
  - se se move muito, o numero oficial depende de nomes que mal enxergamos.

LIMITE DO TESTE (importante para o relatorio): ele NAO mede o vies das empresas que
nao tem preco NENHUM -- essas nunca entram no painel e nao ha o que restringir.
Mede apenas a parcela do vies que e observavel. Ver results/08 s.3.2.

Uso:  python scripts/18_coverage_sensitivity.py [limiar1 limiar2 ...]   (default: 1.0 0.99 0.95)
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.backtest.engine import BacktestEngine
from statarb.backtest.metrics import compute_metrics
from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData
from statarb.factors.betas import FactorModel
from statarb.signals import build_signal

CHAVES = ["sharpe_gross", "sharpe_net", "ann_return_net_pct", "ann_vol_pct",
          "max_drawdown_pct", "ann_turnover_x", "costs_bps_of_gross_per_year",
          "avg_n_positions", "pnl_net_total_usd_mm"]


def cobertura_por_nome(md, ini, fim) -> pd.Series:
    """Fracao dos dias-membro em que o nome tem retorno valido, dentro da janela."""
    mem = md.membership_daily.loc[ini:fim]
    ret = md.returns.loc[ini:fim].reindex(columns=mem.columns)
    dias_membro = mem.sum()
    dias_com_preco = (mem & ret.notna()).sum()
    vale = dias_membro > 0
    return (dias_com_preco[vale] / dias_membro[vale]).astype(float)


def roda(cfg, md, fm, excluidos: list[str] | None) -> dict:
    """Roda o backtest, opcionalmente zerando a membership dos nomes excluidos."""
    original = None
    if excluidos:
        original = md.membership_daily[excluidos].copy()
        md.membership_daily[excluidos] = False
    try:
        out = BacktestEngine(cfg).run(md, fm, build_signal(cfg))
        return compute_metrics(out["results"], float(cfg["book"]["gross_usd"]))
    finally:
        if original is not None:
            md.membership_daily[excluidos] = original


def main() -> None:
    t0 = time.time()
    limiares = [float(a) for a in sys.argv[1:]] or [1.0, 0.99, 0.95]
    cfg = load_config()
    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    ini, fim = pd.Timestamp(cfg["backtest"]["start"]), pd.Timestamp(cfg["backtest"]["end"])

    cob = cobertura_por_nome(md, ini, fim)
    print(f"{len(cob)} nomes com ao menos 1 dia de membership em {ini.date()}..{fim.date()}")
    print("distribuicao da cobertura:")
    for q in [0.01, 0.05, 0.10, 0.25, 0.50]:
        print(f"  p{int(q*100):02d} = {cob.quantile(q):.3f}")
    print(f"  cobertura == 1,000 : {int((cob >= 0.9999).sum())} nomes")
    print()

    print("[baseline] rodando com o universo completo...")
    base = roda(cfg, md, fm, None)
    linhas = [("baseline (todos)", len(cob), base)]

    for lim in limiares:
        fora = sorted(cob.index[cob < lim])
        print(f"[limiar {lim:.2f}] excluindo {len(fora)} nomes "
              f"({100*len(fora)/len(cob):.1f}% do universo)...")
        linhas.append((f"cobertura >= {lim:.2f}", len(cob) - len(fora), roda(cfg, md, fm, fora)))

    # ---------------------------------------------------------------- relatorio
    cab = "| Cenario | Nomes | " + " | ".join(k.replace("_", " ") for k in CHAVES) + " |"
    sep = "|---" * (2 + len(CHAVES)) + "|"
    corpo = [f"| {nome} | {n} | " + " | ".join(f"{m[k]:.3f}" for k in CHAVES) + " |"
             for nome, n, m in linhas]

    print("\n" + cab + "\n" + sep)
    for l in corpo:
        print(l)

    delta = "\nDelta vs baseline (Sharpe liquido):"
    for nome, _, m in linhas[1:]:
        d = m["sharpe_net"] - base["sharpe_net"]
        delta += f"\n  {nome:22} {m['sharpe_net']:+.3f}  ({d:+.3f})"
    print(delta)

    rep = path_of(cfg, "reports")
    txt = ["# Sensibilidade a cobertura de precos", "",
           f"Janela {ini.date()} a {fim.date()} | sinal `{cfg['signal']['name']}` | "
           f"rebalance {cfg['execution']['rebalance_every_days']}d", "",
           "> Mede a parcela OBSERVAVEL do vies de desfecho: quanto o resultado depende de",
           "> nomes cuja serie de precos nao cobre todo o periodo de membership. NAO mede as",
           "> empresas sem preco algum -- essas nunca entram no painel (ver `results/08`).", "",
           cab, sep, *corpo, "", "## Distribuicao da cobertura", "",
           *[f"- p{int(q*100):02d} = {cob.quantile(q):.3f}" for q in [0.01, 0.05, 0.10, 0.25, 0.50]],
           f"- cobertura == 1,000: **{int((cob >= 0.9999).sum())}** de {len(cob)} nomes", ""]
    (rep / "coverage_sensitivity.md").write_text("\n".join(txt), encoding="utf-8")
    print(f"\nRelatorio: {rep / 'coverage_sensitivity.md'}  |  {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
