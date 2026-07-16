"""Analise de blend: correlacao entre candidatos e o sinal oficial (resid_ou).

O funil (04) diz se cada sinal PREVE (IC). Este script diz se eles se SOMAM:
  * correlacao media dos SCORES cross-sectional (sobreposicao de informacao);
  * correlacao das series de spread Q5-Q1 (proxy do P&L de cada sinal).

Regra do blend (formula K/rho): um segundo sinal agrega se tem IC>0 E
correlacao de P&L baixa/negativa com o nucleo. IC alto + corr alta = redundante.

Uso: python scripts/09_blend_analysis.py [sinais...] [--data processed_sp500]
     (default: resid_ou stm overnight salience)
Saida: reports/blend_analysis.md
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

H_SPREAD = 5   # horizonte (dias) do spread Q5-Q1 usado como proxy de P&L


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:
        cfg["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]
        argv = [a for i, a in enumerate(argv)
                if a != "--data" and (i == 0 or argv[i - 1] != "--data")]
    names = [a for a in argv if not a.startswith("--")] or [
        "resid_ou", "stm", "overnight", "salience"]

    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    mask = tradable_mask(md, cfg)
    sigs = {n: build_signal(cfg, n) for n in names}

    idx = md.returns.index
    start = idx.searchsorted(pd.Timestamp(cfg["backtest"]["start"]))
    val_end = pd.Timestamp(cfg["funnel"]["val_end"])
    every = int(cfg["funnel"]["eval_every_days"])

    spreads: dict[str, dict] = {n: {} for n in names}
    score_corr_acc: dict[tuple, list] = {}

    for p in range(start, len(idx) - H_SPREAD - 2, every):
        d = idx[p]
        if d > val_end:
            break
        univ = list(mask.columns[mask.loc[d]])
        if len(univ) < 200:
            continue
        zs = {}
        for n in names:
            z = sigs[n].compute(md, fm, d, univ)
            if len(z) >= 50:
                zs[n] = z

        fwd = fm.residuals.iloc[p + 2 : p + 2 + H_SPREAD].sum(min_count=3)
        for n, z in zs.items():
            common = z.index.intersection(fwd.dropna().index)
            if len(common) >= 50:
                q = pd.qcut(z[common].rank(method="first"), 5, labels=False)
                mq = fwd[common].groupby(q).mean()
                spreads[n][d] = (mq.iloc[-1] - mq.iloc[0]) / H_SPREAD * 1e4  # bps/dia

        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if a in zs and b in zs:
                    common = zs[a].index.intersection(zs[b].index)
                    if len(common) >= 50:
                        score_corr_acc.setdefault((a, b), []).append(
                            spearmanr(zs[a][common], zs[b][common])[0])

    # matrizes
    spread_df = pd.DataFrame({n: pd.Series(v) for n, v in spreads.items()})
    pnl_corr = spread_df.corr()
    score_corr = pd.DataFrame(np.eye(len(names)), index=names, columns=names)
    for (a, b), v in score_corr_acc.items():
        score_corr.loc[a, b] = score_corr.loc[b, a] = float(np.nanmean(v))

    stats = pd.DataFrame({
        "spread_medio_bps_d": spread_df.mean(),
        "t_stat": spread_df.mean() / spread_df.std() * np.sqrt(spread_df.notna().sum()),
        "n_datas": spread_df.notna().sum(),
    }).round(3)

    lines = ["# Analise de blend (dev+val, holdout trancado)\n",
             f"Painel: {cfg['paths']['data_processed']} | grade a cada {every}d | "
             f"spread Q5-Q1 fwd {H_SPREAD}d sobre retorno RESIDUAL\n",
             "## Spread por sinal (proxy de P&L gross)\n", stats.to_markdown(), "",
             "## Correlacao dos SCORES (sobreposicao de informacao)\n",
             score_corr.round(3).to_markdown(), "",
             "## Correlacao das series de spread (proxy de P&L)\n",
             pnl_corr.round(3).to_markdown(), "",
             "Leitura: candidato agrega ao blend se spread>0 (com t razoavel) E "
             "correlacao de P&L com resid_ou baixa/negativa."]
    rep = path_of(cfg, "reports")
    (rep / "blend_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("=== SPREADS (bps/dia, gross) ==="); print(stats.to_string())
    print("\n=== CORRELACAO DOS SCORES ==="); print(score_corr.round(3).to_string())
    print("\n=== CORRELACAO DO P&L (spreads) ==="); print(pnl_corr.round(3).to_string())
    print(f"\nsalvo em {rep / 'blend_analysis.md'} | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
