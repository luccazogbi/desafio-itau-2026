"""DIAGNOSTICO DO HOLDOUT: o alfa morreu, ou o regime nao apareceu?

CONTEXTO: a ida unica ao holdout (2024-01-02 a 2026-05-29) foi feita em
04/08/2026 com autorizacao explicita. Resultado: Sharpe liquido -1,15 e,
o que mais importa, Sharpe BRUTO -0,77 e IC21 -0,030. O sinal nao apenas
parou de funcionar -- ele INVERTEU.

A tese do projeto (results/03) diz que o alfa depende do REGIME: aparece em
vol alta (provisao de liquidez e cara quando ha pressa) e some em vol baixa.
Se o holdout foi um periodo calmo, a tese preveria IC ~ 0 -- nao IC < 0.

ESTE SCRIPT SEPARA AS DUAS HIPOTESES:
  H1 REGIME  : o holdout foi calmo; nos dias de vol ALTA o sinal ainda funciona.
  H2 DECAIMENTO: o sinal falha inclusive em vol alta -> o alfa acabou.

METODO: aplica ao holdout os MESMOS limiares ABSOLUTOS de vol do dev+val
(nao tercis do proprio holdout -- isso mudaria a definicao de "vol alta" e
tornaria a comparacao invalida). Mede IC e desempenho por regime e por ano.

HOLDOUT: este script LE o holdout. So deve ser executado depois da ida unica.

Uso:   python scripts/19_holdout_diagnostico.py
Saida: reports/holdout_diagnostico.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData
from statarb.data.universe import tradable_mask
from statarb.factors.betas import FactorModel
from statarb.signals import build_signal
from statarb.stats import newey_west_tstat, overlap_lag

H, EVERY = 21, 5
DEV_VAL = ("2020-01-02", "2023-12-29")


def ic_series(md, fm, mask, sig, datas, regime=None):
    """IC do sinal contra o retorno residual de H dias, na grade EVERY."""
    idx = md.returns.index
    out = []
    p0, p1 = idx.searchsorted(datas[0]), idx.searchsorted(datas[1])
    for p in range(p0, min(p1, len(idx) - H - 2), EVERY):
        d = idx[p]
        univ = list(mask.columns[mask.loc[d]])
        if len(univ) < 200:
            continue
        z = sig.compute(md, fm, d, univ)
        if len(z) < 200:
            continue
        fwd = fm.residuals.iloc[p + 2 : p + 2 + H].sum(min_count=int(H * 0.7))
        com = z.index.intersection(fwd.dropna().index)
        if len(com) < 150:
            continue
        out.append({"data": d, "ic": spearmanr(z[com], fwd[com])[0],
                    "regime": regime.get(d) if regime is not None else None})
    return pd.DataFrame(out)


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    rep = path_of(cfg, "reports")

    print("[1/4] Painel + modelo de fatores...")
    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    mask = tradable_mask(md, cfg)
    sig = build_signal(cfg, "resid_ou")

    print("[2/4] Limiares de vol do DEV+VAL (definicao de regime congelada)...")
    vol = (md.iwm_ret.rolling(21).std() * np.sqrt(252)).shift(1)
    vol_dv = vol.loc[DEV_VAL[0]:DEV_VAL[1]].dropna()
    lo, hi = vol_dv.quantile([1 / 3, 2 / 3]).values
    print(f"      vol baixa < {lo:.1%} <= media <= {hi:.1%} < alta")

    classifica = lambda v: "1-baixa" if v <= lo else ("2-media" if v <= hi else "3-ALTA")
    reg = vol.dropna().map(classifica)

    print("[3/4] IC por regime: dev+val vs HOLDOUT...")
    ho_ini = cfg["backtest"]["holdout_start"]
    ho_fim = str(md.returns.index[-1].date())
    ic_dv = ic_series(md, fm, mask, sig, DEV_VAL, reg)
    ic_ho = ic_series(md, fm, mask, sig, (ho_ini, ho_fim), reg)
    lag = overlap_lag(H, EVERY)

    def resume(df, nome):
        linhas = []
        for r_ in ["1-baixa", "2-media", "3-ALTA"]:
            v = df[df["regime"] == r_]["ic"].dropna().values
            linhas.append({"periodo": nome, "regime": r_, "n": len(v),
                           "ic": float(np.mean(v)) if len(v) else np.nan,
                           "t_nw": newey_west_tstat(v, lag) if len(v) >= 5 else np.nan})
        v = df["ic"].dropna().values
        linhas.append({"periodo": nome, "regime": "TOTAL", "n": len(v),
                       "ic": float(np.mean(v)), "t_nw": newey_west_tstat(v, lag)})
        return linhas

    tab = pd.DataFrame(resume(ic_dv, "dev+val") + resume(ic_ho, "HOLDOUT"))

    # fracao de dias em cada regime
    mix = {}
    for nome, (a, b) in [("dev+val", DEV_VAL), ("HOLDOUT", (ho_ini, ho_fim))]:
        r_ = reg.loc[a:b]
        mix[nome] = (r_.value_counts(normalize=True).reindex(["1-baixa", "2-media", "3-ALTA"])
                     .fillna(0.0))
    mix = pd.DataFrame(mix)

    print("[4/4] Desempenho ano a ano no holdout...")
    ho_path = rep / "holdout" / "results_daily.parquet"
    anos = []
    if ho_path.exists():
        rr = pd.read_parquet(ho_path)
        Gv = float(cfg["book"]["gross_usd"])
        n_, g_ = rr["pnl_net_usd"] / Gv, rr["pnl_gross_usd"] / Gv
        for y, gr in n_.groupby(n_.index.year):
            gg = g_.loc[gr.index]
            anos.append({"ano": int(y), "dias": len(gr),
                         "vol_spy": f"{vol.reindex(gr.index).mean():.0%}",
                         "sharpe_bruto": round(gg.mean() / gg.std() * np.sqrt(252), 2),
                         "sharpe_liq": round(gr.mean() / gr.std() * np.sqrt(252), 2),
                         "ret_liq_aa": round(gr.mean() * 252 * 100, 2)})
    anos = pd.DataFrame(anos)

    ic_alta_ho = tab[(tab.periodo == "HOLDOUT") & (tab.regime == "3-ALTA")]["ic"].iloc[0]
    veredito = ("H1 REGIME sobrevive em parte: em vol ALTA o IC do holdout continua POSITIVO."
                if ic_alta_ho > 0.01 else
                "H2 DECAIMENTO: o sinal falha INCLUSIVE em vol alta. A defesa por regime NAO se sustenta.")

    L = ["# Diagnostico do holdout: o alfa morreu ou o regime nao apareceu?\n",
         f"> Holdout: {ho_ini} a {ho_fim} · gerado por `scripts/19_holdout_diagnostico.py`",
         "> Limiares de regime **congelados no dev+val** para que 'vol alta' signifique a mesma "
         "coisa nos dois periodos.\n",
         f"Vol baixa < **{lo:.1%}** <= media <= **{hi:.1%}** < alta\n",
         "## 1. Composicao de regimes: o holdout foi mais calmo?\n",
         (mix * 100).round(1).to_markdown() + "\n",
         "## 2. IC do sinal por regime — dev+val vs holdout\n",
         tab.round(4).to_markdown(index=False) + "\n",
         "## 3. Desempenho ano a ano no holdout\n",
         (anos.to_markdown(index=False) if len(anos) else "_backtest do holdout nao encontrado_") + "\n",
         "## 4. Veredito\n", f"**{veredito}**\n"]
    (rep / "holdout_diagnostico.md").write_text("\n".join(L), encoding="utf-8")

    sys.stdout.reconfigure(errors="replace")
    print("\n=== MIX DE REGIMES (% dos dias) ===");  print((mix * 100).round(1).to_string())
    print("\n=== IC POR REGIME ===");                print(tab.round(4).to_string(index=False))
    if len(anos):
        print("\n=== ANO A ANO (holdout) ===");      print(anos.to_string(index=False))
    print(f"\n>>> {veredito}")
    print(f"\nOK -> {rep / 'holdout_diagnostico.md'} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
