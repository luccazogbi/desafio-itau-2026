"""Funil de avaliacao de sinais (protocolo anti-overfitting do doc de sinais, s.16).

Para cada sinal registrado, mede em cada split temporal (dev / validacao):
  coverage   fracao media do universo com score
  IC_h       correlacao de Spearman entre o z-score e o retorno RESIDUAL dos
             h dias apos a EXECUCAO (entrada no close de t+1 -- mesma convencao
             anti-lookahead do backtest); h em funnel.horizons
  t(IC)      t-stat da serie de ICs (media/desvio * raiz(n))
  AC5        autocorrelacao do score em 5 dias (proxy de turnover: 1 = lento)
  Q5-Q1      spread do quintil top vs bottom no retorno residual (bps/dia, h=5)

O HOLDOUT (apos funnel.val_end) fica trancado: so roda com --include-holdout,
e a regra do protocolo e UMA unica ida, como decisao final.

Uso:
    python scripts/04_signal_funnel.py                     # todos os sinais, dev+val
    python scripts/04_signal_funnel.py trend_factor mad    # subconjunto
    python scripts/04_signal_funnel.py --include-holdout   # decisao final (1x!)

NOTA (dados sinteticos): apenas reversao e mispricing (E/P) foram plantados.
Nos demais sinais o IC esperado aqui e ~0 -- o funil valida a MAQUINA;
a selecao de verdade acontece nos dados reais (plano B / Bloomberg).
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
from statarb.signals import _REGISTRY, build_signal


def evaluate_signal(name, cfg, md, fm, mask, splits) -> dict:
    sig = build_signal(cfg, name)
    horizons = list(cfg["funnel"]["horizons"])
    every = int(cfg["funnel"]["eval_every_days"])
    resid = fm.residuals
    idx = md.returns.index
    max_h = max(horizons)

    rows = []
    for split_name, (d0, d1) in splits.items():
        positions = [
            p for p in range(0, len(idx) - max_h - 2, every)
            if d0 <= idx[p] <= d1
        ]
        ics = {h: [] for h in horizons}
        spreads, coverages, scores_hist = [], [], {}
        for p in positions:
            d = idx[p]
            univ = list(mask.columns[mask.loc[d]])
            if len(univ) < 50:
                continue
            z = sig.compute(md, fm, d, univ)
            coverages.append(len(z) / len(univ))
            if len(z) < 30:
                continue
            scores_hist[d] = z
            for h in horizons:
                fwd = resid.iloc[p + 2 : p + 2 + h].sum(min_count=max(1, int(h * 0.7)))
                common = z.index.intersection(fwd.dropna().index)
                if len(common) >= 30:
                    ics[h].append(spearmanr(z[common], fwd[common])[0])
            # spread Q5-Q1 no horizonte de 5 dias
            fwd5 = resid.iloc[p + 2 : p + 7].sum(min_count=3)
            common = z.index.intersection(fwd5.dropna().index)
            if len(common) >= 50:
                q = pd.qcut(z[common].rank(method="first"), 5, labels=False)
                m = fwd5[common].groupby(q).mean()
                spreads.append((m.iloc[-1] - m.iloc[0]) / 5.0 * 1e4)  # bps/dia

        # autocorrelacao do score (5 dias) -- proxy de turnover do sinal
        acs = []
        ds = sorted(scores_hist)
        for a, b in zip(ds[:-1], ds[1:]):
            za, zb = scores_hist[a], scores_hist[b]
            common = za.index.intersection(zb.index)
            if len(common) >= 30:
                acs.append(np.corrcoef(za[common], zb[common])[0, 1])

        def _t(v):
            v = [x for x in v if np.isfinite(x)]
            return float(np.mean(v) / np.std(v) * np.sqrt(len(v))) if len(v) > 3 else np.nan

        row = {
            "signal": name, "split": split_name,
            "n_dates": len(scores_hist),
            "coverage": float(np.mean(coverages)) if coverages else 0.0,
            "AC5": float(np.nanmean(acs)) if acs else np.nan,
            "Q5-Q1_bps_d": float(np.nanmean(spreads)) if spreads else np.nan,
        }
        for h in horizons:
            v = [x for x in ics[h] if np.isfinite(x)]
            row[f"IC{h}"] = float(np.mean(v)) if v else np.nan
            row[f"t{h}"] = _t(ics[h])
        rows.append(row)
    return rows


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:      # ex.: --data processed_yf (painel real do plano B)
        cfg["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]
        argv = [a for i, a in enumerate(argv)
                if a != "--data" and (i == 0 or argv[i - 1] != "--data")]
    args = [a for a in argv if not a.startswith("--")]
    include_holdout = "--include-holdout" in argv

    names = args or [n for n in _REGISTRY if n != "blend"] + ["blend"]

    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    mask = tradable_mask(md, cfg)

    f = cfg["funnel"]
    start = pd.Timestamp(cfg["backtest"]["start"])
    splits = {
        "dev": (start, pd.Timestamp(f["dev_end"])),
        "val": (pd.Timestamp(f["dev_end"]), pd.Timestamp(f["val_end"])),
    }
    if include_holdout:
        print("[!] HOLDOUT INCLUIDO -- protocolo: esta e a unica ida. Registrar a decisao.")
        splits["HOLDOUT"] = (pd.Timestamp(f["val_end"]), md.returns.index[-1])

    all_rows = []
    for name in names:
        print(f"  avaliando {name}...")
        try:
            all_rows.extend(evaluate_signal(name, cfg, md, fm, mask, splits))
        except Exception as exc:  # noqa: BLE001
            print(f"    [erro] {name}: {exc}")

    table = pd.DataFrame(all_rows).set_index(["signal", "split"]).round(4)
    rep = path_of(cfg, "reports")
    table.to_parquet(rep / "funnel.parquet")
    with open(rep / "funnel.md", "w", encoding="utf-8") as fh:
        fh.write("# Funil de sinais\n\n" + table.to_markdown() + "\n")

    pd.set_option("display.width", 160)
    print("\n================== FUNIL DE SINAIS ==================")
    print(table.to_string())
    print("=====================================================")
    print(f"salvo em {rep / 'funnel.md'} | tempo: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
