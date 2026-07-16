"""Adiciona precos de ABERTURA ao painel S&P 500 as-of (p/ o sinal overnight).

O sinal overnight (Lou-Polk-Skouras, JFE 2019) usa o retorno close->open.
yfinance com auto_adjust=True da o Open AJUSTADO consistente com o Close
ajustado do painel (mesma base de proventos -- sem "alfa" falso em ex-dates).
Grava prices_open.parquet alinhado ao indice do painel existente.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

BATCH = 250


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    panel = path_of(cfg, "data_processed").parent / "processed_sp500"
    close = pd.read_parquet(panel / "prices_close.parquet")
    symbols = list(close.columns)

    import yfinance as yf

    opens = []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i : i + BATCH]
        df = yf.download(chunk, start=str(close.index[0].date()), auto_adjust=True,
                         progress=False, threads=True, group_by="column")
        opens.append(df["Open"] if len(chunk) > 1 else df[["Open"]].set_axis(chunk, axis=1))
        print(f"  open {min(i + BATCH, len(symbols))}/{len(symbols)}")
        time.sleep(1.0)

    open_px = pd.concat(opens, axis=1).sort_index()
    open_px.index = pd.to_datetime(open_px.index).tz_localize(None)
    open_px = open_px.loc[:, ~open_px.columns.duplicated()]
    open_px = open_px.reindex(index=close.index, columns=close.columns)
    open_px = open_px.where(close.notna())          # respeita deslistamentos

    open_px.rename_axis("date").to_parquet(panel / "prices_open.parquet")
    cov = open_px.notna().sum().sum() / max(1, close.notna().sum().sum())
    print(f"OK -> prices_open.parquet | cobertura vs close: {cov:.1%} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
