"""Aumenta o painel S&P 500 as-of com market cap (destrava o sinal str_turnover).

O painel de 07_pull_sp500_asof.py gravou market_cap = NaN (nao era preciso p/ a
reversao). O str_turnover precisa de turnover = volume$ / market cap. Aqui
construimos um market cap PROXY, coerente com o metodo ja usado no projeto
(script 06): market cap atual (screener Nasdaq) escalado pelo caminho do preco.
    market_cap_t = close_t * (market_cap_hoje / close_hoje)

Membros que ja sairam do indice e nao estao no screener de hoje ficam com NaN
(o str_turnover simplesmente os ignora naquele ranking -- minoria, aceitavel).
So sobrescreve market_cap.parquet; nao repuxa precos.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

SCREENER = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept": "application/json, text/plain, */*"}


def main() -> None:
    cfg = load_config()
    panel = path_of(cfg, "data_processed").parent / "processed_sp500"
    close = pd.read_parquet(panel / "prices_close.parquet")

    print("[1/2] Market cap atual via screener Nasdaq...")
    req = urllib.request.Request(SCREENER, headers=HEADERS)
    rows = json.loads(urllib.request.urlopen(req, timeout=60).read())["data"]["rows"]
    scr = pd.DataFrame(rows)
    scr["marketCap"] = pd.to_numeric(scr["marketCap"], errors="coerce")
    scr["sym"] = scr["symbol"].str.replace(".", "-", regex=False)
    mcap_now = scr.dropna(subset=["marketCap"]).set_index("sym")["marketCap"]
    mcap_now = mcap_now[mcap_now > 0]

    cols = close.columns
    have = mcap_now.reindex(cols).dropna()
    print(f"[2/2] Escalando pelo preco | {len(have)}/{len(cols)} tickers com market cap "
          f"({len(have)/len(cols):.0%})")

    px_now = close[have.index].ffill().iloc[-1]
    market_cap = pd.DataFrame(index=close.index, columns=cols, dtype=float)
    market_cap[have.index] = close[have.index].mul(have / px_now, axis=1)

    market_cap.rename_axis("date").to_parquet(panel / "market_cap.parquet")
    print(f"OK -> {panel / 'market_cap.parquet'} | cobertura {market_cap.iloc[-1].notna().mean():.0%}")


if __name__ == "__main__":
    main()
