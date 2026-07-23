"""Adiciona MAXIMA e MINIMA diarias ao painel S&P 500 as-of (p/ calibrar o spread).

Os estimadores de spread que funcionam so com dado diario (Corwin-Schultz 2012,
Abdi-Ranaldo 2017) precisam de High/Low. Sem eles o `costs.spread_bps` fica
sendo um chute de literatura -- com eles, vira medicao no proprio universo.

yfinance com auto_adjust=True devolve High/Low na MESMA base do Close ajustado.
Como os estimadores usam apenas RAZOES dentro do dia (H/L, C vs ponto medio),
o fator de ajuste se cancela -- entao a base ajustada nao introduz vies.

Grava prices_high.parquet e prices_low.parquet alinhados ao indice do painel.
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
    painel = path_of(cfg, "data_processed").parent / "processed_sp500"
    close = pd.read_parquet(painel / "prices_close.parquet")
    simbolos = list(close.columns)

    import yfinance as yf

    altas, baixas = [], []
    for i in range(0, len(simbolos), BATCH):
        lote = simbolos[i : i + BATCH]
        df = yf.download(lote, start=str(close.index[0].date()), auto_adjust=True,
                         progress=False, threads=True, group_by="column")
        for campo, acumulador in (("High", altas), ("Low", baixas)):
            bloco = df[campo] if len(lote) > 1 else df[[campo]].set_axis(lote, axis=1)
            acumulador.append(bloco)
        print(f"  high/low {min(i + BATCH, len(simbolos))}/{len(simbolos)}")
        time.sleep(1.0)

    def consolida(blocos: list[pd.DataFrame]) -> pd.DataFrame:
        px = pd.concat(blocos, axis=1).sort_index()
        px.index = pd.to_datetime(px.index).tz_localize(None)
        px = px.loc[:, ~px.columns.duplicated()]
        px = px.reindex(index=close.index, columns=close.columns)
        return px.where(close.notna())          # respeita deslistamentos

    high, low = consolida(altas), consolida(baixas)
    high.rename_axis("date").to_parquet(painel / "prices_high.parquet")
    low.rename_axis("date").to_parquet(painel / "prices_low.parquet")

    validos = (high.notna() & low.notna() & (high >= low)).sum().sum()
    cobertura = validos / max(1, int(close.notna().sum().sum()))
    print(f"OK -> prices_high/low.parquet | cobertura vs close: {cobertura:.1%} "
          f"| {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
