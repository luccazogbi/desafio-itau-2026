"""Validacao cruzada do P&L com a biblioteca bt (pmorissette/bt).

Replay dos MESMOS pesos-alvo do nosso motor dentro do bt (WeighTarget +
Rebalance, comissao linear = spread). Se as curvas brutas-de-impacto
baterem, o P&L do nosso motor esta correto -- e um teste independente
de contabilidade, nao um segundo backtest.

Diferencas esperadas (pequenas): o bt nao modela impacto AC (por isso
comparamos contra gross - spread) e trata caixa/fracionamento de cotas
de forma propria.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData


def main() -> None:
    import bt

    cfg = load_config()
    rep = path_of(cfg, "reports")
    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)

    weights = pd.read_parquet(rep / "target_weights.parquet")
    res_eng = pd.read_parquet(rep / "results_daily.parquet")

    cols = list(weights.columns)
    prices = md.tri[cols].reindex(res_eng.index)
    prices = prices.ffill().bfill()            # bt exige painel denso (delistadas ficam flat)

    wdf = weights.reindex(prices.index).ffill().fillna(0.0)

    spread = float(cfg["costs"]["spread_bps"]) * 1e-4
    strat = bt.Strategy("replay", [bt.algos.WeighTarget(wdf), bt.algos.Rebalance()])
    test = bt.Backtest(
        strat, prices, integer_positions=False,
        commissions=lambda q, p: abs(q) * p * spread,
        progress_bar=False,
    )
    r = bt.run(test)

    bt_ret = r["replay"].prices.pct_change(fill_method=None).dropna()
    G = float(cfg["book"]["gross_usd"])
    eng_ret = ((res_eng["pnl_gross_usd"] - res_eng["spread_usd"]) / G).reindex(bt_ret.index)

    corr = float(np.corrcoef(bt_ret, eng_ret)[0, 1])
    diff_bps = float((bt_ret - eng_ret).abs().mean() * 1e4)
    print("=========== CROSSCHECK bt vs motor proprio ===========")
    print(f"  correlacao dos retornos diarios : {corr:.4f}")
    print(f"  |dif| media diaria              : {diff_bps:.2f} bps")
    print(f"  ann ret bt                      : {bt_ret.mean() * 252 * 100:.2f}%")
    print(f"  ann ret motor (gross - spread)  : {eng_ret.mean() * 252 * 100:.2f}%")
    print("=======================================================")
    if corr < 0.95:
        print("  [ALERTA] correlacao baixa -- investigar contabilidade!")


if __name__ == "__main__":
    main()
