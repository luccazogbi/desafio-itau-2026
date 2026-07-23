"""ANALISE DE CAPACIDADE: quanto alfa sobrevive em cada tamanho de book?

MOTIVACAO: no book oficial de $1 bi, os custos comem 63% do alfa bruto
(impacto de mercado = 62% do custo). Como o impacto cresce com o tamanho do
trade, um book menor deve reter muito mais alfa. Esta analise mede a curva
"Sharpe liquido x tamanho do book" RE-RODANDO o backtest completo em cada
tamanho -- o otimizador reage ao book (caps de liquidez e penalidade de
impacto mudam), entao escalar custos na mao subestimaria o efeito.

Janela: dev+val (2020-2023). O holdout (2024+) permanece TRANCADO.

Uso:    python scripts/11_capacity_analysis.py [--data processed_sp500]
Saida:  reports/capacity_analysis.md + capacity_curve.png + capacity_analysis.parquet
"""

from __future__ import annotations

import copy
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.backtest.engine import BacktestEngine
from statarb.backtest.metrics import compute_metrics
from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData
from statarb.factors.betas import FactorModel
from statarb.signals import build_signal

# Tamanhos de book testados (em USD). O oficial e $1 bi.
TAMANHOS_BOOK_USD = [100e6, 200e6, 300e6, 500e6, 1000e6]
FIM_DEV_VAL = "2023-12-31"          # tranca o holdout


def main() -> None:
    inicio = time.time()
    config = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:
        config["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]

    print("[1/3] Carregando painel + modelo de fatores (uma vez para todas as rodadas)...")
    dados_mercado = MarketData.from_dir(path_of(config, "data_processed"), config)
    modelo_fatores = FactorModel(config).fit(dados_mercado.returns, dados_mercado.factors)
    sinal = build_signal(config, "resid_ou")   # cache do painel e reaproveitado

    print(f"[2/3] Backtest completo em {len(TAMANHOS_BOOK_USD)} tamanhos de book...")
    linhas_curva = []
    for book_usd in TAMANHOS_BOOK_USD:
        config_rodada = copy.deepcopy(config)
        config_rodada["book"]["gross_usd"] = book_usd
        config_rodada["backtest"]["end"] = FIM_DEV_VAL

        t_rodada = time.time()
        saida = BacktestEngine(config_rodada).run(dados_mercado, modelo_fatores, sinal)
        metricas = compute_metrics(saida["results"], book_usd)

        linhas_curva.append({
            "book_usd_mm": book_usd / 1e6,
            "sharpe_bruto": metricas["sharpe_gross"],
            "sharpe_liquido": metricas["sharpe_net"],
            "ret_liquido_pct_aa": metricas["ann_return_net_pct"],
            "pnl_liquido_usd_mm": metricas["pnl_net_total_usd_mm"],
            "custos_bps_ano": metricas["costs_bps_of_gross_per_year"],
            "turnover_x_ano": metricas["ann_turnover_x"],
        })
        print(f"    book ${book_usd/1e6:>5.0f}mm: Sharpe liq {metricas['sharpe_net']:+.2f} "
              f"| ret liq {metricas['ann_return_net_pct']:+.2f}% "
              f"| custos {metricas['costs_bps_of_gross_per_year']:.0f}bps "
              f"({time.time()-t_rodada:.0f}s)")

    curva = pd.DataFrame(linhas_curva).set_index("book_usd_mm")

    print("[3/3] Gravando tabela, grafico e relatorio...")
    pasta_reports = path_of(config, "reports")
    curva.to_parquet(pasta_reports / "capacity_analysis.parquet")

    # grafico: Sharpe liquido e P&L liquido em funcao do tamanho do book
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from statarb.viz.style import PALETTE, apply_style
    apply_style()

    fig, eixos = plt.subplots(1, 2, figsize=(14, 5))
    curva["sharpe_liquido"].plot(ax=eixos[0], marker="o", color=PALETTE["strategy"],
                                 label="Sharpe liquido")
    curva["sharpe_bruto"].plot(ax=eixos[0], marker="o", color=PALETTE["gross"],
                               ls="--", label="Sharpe bruto")
    eixos[0].set_title("Capacidade: Sharpe vs tamanho do book (dev+val)")
    eixos[0].set_xlabel("book bruto (USD mm)"); eixos[0].legend()
    curva["pnl_liquido_usd_mm"].plot(ax=eixos[1], marker="o", color=PALETTE["cost"])
    eixos[1].set_title("P&L liquido acumulado 2020-23 (USD mm) -- o 'dinheiro no bolso'")
    eixos[1].set_xlabel("book bruto (USD mm)")
    fig.tight_layout()
    fig.savefig(pasta_reports / "capacity_curve.png", dpi=130)
    plt.close(fig)

    melhor = curva["sharpe_liquido"].idxmax()
    linhas_md = [
        "# Analise de capacidade -- resid_ou no S&P 500 as-of (dev+val)\n",
        "Backtest COMPLETO re-rodado em cada tamanho de book (nao e aproximacao).",
        f"Janela 2020-2023; holdout trancado. Rodado em {time.time()-inicio:.0f}s.\n",
        curva.round(3).to_markdown(), "",
        f"- Melhor Sharpe liquido: book de **${melhor:.0f}mm**",
        "- Leitura: o alfa do sinal e REAL mas tem capacidade finita; em books grandes",
        "  o impacto de mercado devora o retorno. O tamanho e uma decisao de desenho",
        "  da estrategia tao importante quanto o sinal.",
    ]
    (pasta_reports / "capacity_analysis.md").write_text("\n".join(linhas_md) + "\n",
                                                        encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(f"\nOK -> {pasta_reports / 'capacity_analysis.md'} | total {time.time()-inicio:.0f}s")


if __name__ == "__main__":
    main()
