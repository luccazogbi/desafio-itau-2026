"""ANALISE DE REGIME DE VOLATILIDADE: quando a estrategia ganha e quando ela some?

MOTIVACAO: no backtest dev+val, 2020 foi otimo (Sharpe liq +0,52) e 2023 foi
negativo (-0,70). Duas leituras possiveis: (a) o alfa DEPENDE DO REGIME --
reversao paga quando ha estresse e demanda por liquidez, some na calmaria;
(b) o alfa esta decaindo/arbitrado. Esta analise separa as hipoteses medindo
desempenho E qualidade do sinal (IC) por regime de volatilidade do mercado.

Proxy de regime: volatilidade realizada de 21 dias do SPY, DEFASADA em 1 dia
(so usamos a vol que ja era conhecida ao entrar no dia -- sem contemporaneidade).
Regimes = tercis da vol dentro do periodo analisado (baixa / media / alta).

Uso:    python scripts/12_regime_analysis.py [--data processed_sp500]
Saida:  reports/regime_analysis.md + regime_analysis.png
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

HORIZONTE_IC_DIAS = 21     # mesmo horizonte do sinal
PASSO_GRADE_DIAS = 5       # grade de datas p/ o IC (evita sobreposicao excessiva)


def main() -> None:
    inicio = time.time()
    config = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:
        config["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]

    print("[1/4] Carregando resultados oficiais + painel...")
    pasta_backtest = path_of(config, "reports") / "sp500_dev_val"
    resultado_diario = pd.read_parquet(pasta_backtest / "results_daily.parquet")
    book_usd = float(config["book"]["gross_usd"])

    dados_mercado = MarketData.from_dir(path_of(config, "data_processed"), config)
    modelo_fatores = FactorModel(config).fit(dados_mercado.returns, dados_mercado.factors)
    universo_negociavel = tradable_mask(dados_mercado, config)
    sinal = build_signal(config, "resid_ou")

    print("[2/4] Definindo regimes: tercis da vol realizada 21d do SPY (defasada 1 dia)...")
    vol_spy_21d = dados_mercado.iwm_ret.rolling(21).std() * np.sqrt(252)   # anualizada
    vol_conhecida = vol_spy_21d.shift(1)                # so o que ja se sabia no dia
    vol_no_periodo = vol_conhecida.reindex(resultado_diario.index).dropna()

    limites_tercis = vol_no_periodo.quantile([1 / 3, 2 / 3]).values
    def classifica_regime(vol: float) -> str:
        if vol <= limites_tercis[0]:
            return "1-vol baixa"
        return "2-vol media" if vol <= limites_tercis[1] else "3-vol ALTA"
    regime_diario = vol_no_periodo.map(classifica_regime)

    print("[3/4] Desempenho e IC por regime...")
    retorno_liq_diario = (resultado_diario["pnl_net_usd"] / book_usd).reindex(regime_diario.index)
    retorno_bruto_diario = (resultado_diario["pnl_gross_usd"] / book_usd).reindex(regime_diario.index)

    def resume(grupo_retornos: pd.Series) -> tuple[float, float]:
        ann = grupo_retornos.mean() * 252 * 100
        sharpe = grupo_retornos.mean() / grupo_retornos.std() * np.sqrt(252)
        return ann, sharpe

    linhas_pnl = []
    for nome_regime, retornos_do_regime in retorno_liq_diario.groupby(regime_diario):
        ann_liq, sharpe_liq = resume(retornos_do_regime)
        ann_bru, sharpe_bru = resume(retorno_bruto_diario.loc[retornos_do_regime.index])
        vol_media = vol_no_periodo.loc[retornos_do_regime.index].mean()
        linhas_pnl.append({"regime": nome_regime, "n_dias": len(retornos_do_regime),
                           "vol_spy_media": f"{vol_media:.0%}",
                           "ret_bruto_aa": round(ann_bru, 2), "sharpe_bruto": round(sharpe_bru, 2),
                           "ret_liq_aa": round(ann_liq, 2), "sharpe_liq": round(sharpe_liq, 2)})
    tabela_pnl = pd.DataFrame(linhas_pnl).set_index("regime")

    # IC por regime: qualidade PURA do sinal, sem otimizador/custos
    datas_painel = dados_mercado.returns.index
    pos_inicio = datas_painel.searchsorted(resultado_diario.index[0])
    pos_fim = datas_painel.searchsorted(resultado_diario.index[-1])
    ic_com_regime = []
    for pos in range(pos_inicio, pos_fim - HORIZONTE_IC_DIAS - 2, PASSO_GRADE_DIAS):
        data = datas_painel[pos]
        if data not in regime_diario.index:
            continue
        acoes_hoje = list(universo_negociavel.columns[universo_negociavel.loc[data]])
        zscores_hoje = sinal.compute(dados_mercado, modelo_fatores, data, acoes_hoje)
        if len(zscores_hoje) < 200:
            continue
        retorno_futuro = modelo_fatores.residuals.iloc[
            pos + 2 : pos + 2 + HORIZONTE_IC_DIAS].sum(min_count=int(HORIZONTE_IC_DIAS * 0.7))
        acoes_validas = zscores_hoje.index.intersection(retorno_futuro.dropna().index)
        ic_com_regime.append({"regime": regime_diario.loc[data],
                              "ic": spearmanr(zscores_hoje[acoes_validas],
                                              retorno_futuro[acoes_validas])[0]})
    ic_df = pd.DataFrame(ic_com_regime)
    tabela_ic = ic_df.groupby("regime")["ic"].agg(
        ic_medio="mean",
        t_stat=lambda v: v.mean() / v.std() * np.sqrt(len(v)),
        n_datas="count").round(4)

    # contexto anual: vol media de cada ano (explica 2020 vs 2023)
    vol_por_ano = vol_no_periodo.groupby(vol_no_periodo.index.year).mean()

    print("[4/4] Gravando relatorio e grafico...")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from statarb.viz.style import PALETTE, apply_style
    apply_style()

    fig, eixos = plt.subplots(1, 2, figsize=(14, 5))
    tabela_pnl[["sharpe_bruto", "sharpe_liq"]].plot(
        kind="bar", ax=eixos[0], color=[PALETTE["gross"], PALETTE["strategy"]], alpha=0.9)
    eixos[0].axhline(0, color="k", lw=0.8)
    eixos[0].set_title("Sharpe por regime de vol do SPY (dev+val)")
    tabela_ic["ic_medio"].plot(kind="bar", ax=eixos[1], color=PALETTE["iwm"], alpha=0.9)
    eixos[1].axhline(0, color="k", lw=0.8)
    eixos[1].set_title("IC do sinal por regime (qualidade pura, sem custos)")
    fig.tight_layout()
    pasta_reports = path_of(config, "reports")
    fig.savefig(pasta_reports / "regime_analysis.png", dpi=130)
    plt.close(fig)

    # tabelas em parquet para o notebook ler sem recomputar
    tabela_pnl.to_parquet(pasta_reports / "regime_pnl.parquet")
    tabela_ic.to_parquet(pasta_reports / "regime_ic.parquet")

    linhas_md = [
        "# Analise de regime de volatilidade -- resid_ou (dev+val 2020-2023)\n",
        "Regime = tercil da vol realizada 21d do SPY, defasada 1 dia (conhecida ao entrar no dia).\n",
        "## Desempenho da estrategia por regime\n", tabela_pnl.to_markdown(), "",
        "## Qualidade do sinal (IC, fwd 21d) por regime\n", tabela_ic.to_markdown(), "",
        "## Vol media do SPY por ano (contexto)\n",
        vol_por_ano.map(lambda v: f"{v:.0%}").to_markdown(), "",
        "Leitura: se Sharpe e IC concentram no regime de vol ALTA, o resultado fraco de",
        "2023 (ano de vol baixa) e DEPENDENCIA DE REGIME -- caracteristica da tese de",
        "provisao de liquidez (ganhamos quando o mercado precisa de liquidez) -- e nao",
        "necessariamente decaimento do alfa.",
    ]
    (pasta_reports / "regime_analysis.md").write_text("\n".join(linhas_md) + "\n",
                                                      encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(tabela_pnl.to_string())
    print(); print(tabela_ic.to_string())
    print(); print("vol media por ano:", {int(a): f"{v:.0%}" for a, v in vol_por_ano.items()})
    print(f"\nOK -> {pasta_reports / 'regime_analysis.md'} | {time.time()-inicio:.0f}s")


if __name__ == "__main__":
    main()
