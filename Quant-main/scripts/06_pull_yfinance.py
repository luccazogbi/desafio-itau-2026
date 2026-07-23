"""PLANO B de dados reais (sem Bloomberg): universo proxy Russell 2000 via
Nasdaq screener + precos/volume via yfinance. Grava o schema canonico em
data/processed_yf/ -- o pipeline inteiro roda em cima sem NENHUMA alteracao.

Metodo do universo (transparente e defensavel):
  o Russell 2000 e, por definicao, os ranks ~1001-3000 do mercado americano
  por capitalizacao. O screener da Nasdaq da o snapshot de TODAS as acoes US
  com market cap; ranqueamos e tomamos os ranks 1001-3000 = proxy do indice.

VIESES DOCUMENTADOS (aceitos p/ validacao; conserto = Bloomberg/N-PORT, roadmap 1b):
  * SOBREVIVENCIA: a lista e a de HOJE -- empresas deslistadas no meio do
    caminho nao aparecem; membership e estatico (sem point-in-time).
  * MCAP PROXY: market cap historico ~ mcap_hoje x (preco_t / preco_hoje).
  * TRI: close ajustado do yfinance (auto_adjust embute dividendos+splits).

Uso:  python scripts/06_pull_yfinance.py [--start 2018-01-02] [--top-from 1000] [--top-to 3000]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

OUT_SUBDIR = "processed_yf"
SCREENER = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
           "Accept": "application/json, text/plain, */*"}
BATCH = 250


def _arg(flag: str, default: str) -> str:
    args = sys.argv[1:]
    return args[args.index(flag) + 1] if flag in args else default


def build_universe(rank_from: int, rank_to: int) -> pd.DataFrame:
    """Snapshot do screener Nasdaq -> ranks [rank_from, rank_to) por market cap."""
    req = urllib.request.Request(SCREENER, headers=HEADERS)
    rows = json.loads(urllib.request.urlopen(req, timeout=60).read())["data"]["rows"]
    df = pd.DataFrame(rows)
    df["marketCap"] = pd.to_numeric(df["marketCap"], errors="coerce")
    df = df.dropna(subset=["marketCap"])
    df = df[df["marketCap"] > 0]

    # tickers problematicos p/ yfinance: unidades/warrants/direitos e simbolos com ^ /
    bad = df["symbol"].str.contains(r"[\^/]| ", regex=True)
    df = df[~bad]
    df["yf_symbol"] = df["symbol"].str.replace(".", "-", regex=False)

    df = df.sort_values("marketCap", ascending=False).reset_index(drop=True)
    uni = df.iloc[rank_from:rank_to].copy()
    print(f"[universo] screener: {len(df)} acoes US | proxy R2000 = ranks "
          f"{rank_from + 1}..{rank_to} | mcap: ${uni['marketCap'].min()/1e6:.0f}mm a "
          f"${uni['marketCap'].max()/1e9:.2f}bi")
    return uni


def download_prices(symbols: list[str], start: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    import yfinance as yf

    closes, volumes = [], []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i : i + BATCH]
        df = yf.download(chunk, start=start, auto_adjust=True, progress=False,
                         threads=True, group_by="column")
        closes.append(df["Close"] if len(chunk) > 1 else df[["Close"]].set_axis(chunk, axis=1))
        volumes.append(df["Volume"] if len(chunk) > 1 else df[["Volume"]].set_axis(chunk, axis=1))
        print(f"  precos {min(i + BATCH, len(symbols))}/{len(symbols)}")
        time.sleep(1.0)
    close = pd.concat(closes, axis=1).sort_index()
    volume = pd.concat(volumes, axis=1).sort_index()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    volume.index = pd.to_datetime(volume.index).tz_localize(None)
    return close, volume


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    start = _arg("--start", cfg["data"]["start"])
    rank_from = int(_arg("--top-from", "1000"))
    rank_to = int(_arg("--top-to", "3000"))
    out = path_of(cfg, "data_processed").parent / OUT_SUBDIR
    out.mkdir(parents=True, exist_ok=True)

    print("[1/5] Universo proxy via Nasdaq screener...")
    uni = build_universe(rank_from, rank_to)

    print(f"[2/5] Precos/volume de {len(uni)} tickers via yfinance (desde {start})...")
    close, volume = download_prices(list(uni["yf_symbol"]), start)

    # cobertura minima: >= 70% de closes validos desde o ano seguinte ao inicio
    cov_start = (pd.Timestamp(start) + pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    cov = close.loc[cov_start:].notna().mean()
    keep = cov[cov >= 0.70].index
    close, volume = close[keep], volume[keep]
    print(f"[3/5] Cobertura: {len(keep)}/{len(uni)} tickers com >=70% de dados validos")

    # fatores reais (Ken French) -- publicados com defasagem: truncar o painel
    # inteiro na ultima data com fatores (senao os betas quebram com NaN)
    from statarb.factors.ff_loader import fetch_ff5_mom_daily
    factors_all = fetch_ff5_mom_daily(path_of(cfg, "data_raw"))
    last_f = factors_all.index[-1]
    close, volume = close.loc[:last_f], volume.loc[:last_f]
    print(f"    painel truncado em {last_f.date()} (ultima data dos fatores FF)")

    dollar_volume = (close * volume).astype(float)

    # mcap proxy: snapshot de hoje escalado pelo caminho do preco
    mcap_now = uni.set_index("yf_symbol")["marketCap"].reindex(keep)
    px_now = close.ffill().iloc[-1]
    market_cap = close.mul(mcap_now / px_now, axis=1)

    # membership estatico mensal (VIES DE SOBREVIVENCIA -- documentado no meta.json)
    snap = pd.bdate_range(close.index[0], close.index[-1], freq="BMS")
    membership = pd.DataFrame(True, index=snap, columns=list(keep))

    sectors = (uni.set_index("yf_symbol")["sector"].reindex(keep).fillna("Unknown")
               .rename("sector").to_frame())
    sectors.index.name = "ticker"

    print("[4/5] Alinhando fatores + IWM...")
    factors = factors_all.reindex(close.index).ffill(limit=3)

    import yfinance as yf
    iwm_px = yf.download("IWM", start=start, auto_adjust=True, progress=False)["Close"]
    iwm_px.index = pd.to_datetime(iwm_px.index).tz_localize(None)
    iwm_px = iwm_px.reindex(close.index).ffill()
    iwm_ret = iwm_px.pct_change(fill_method=None).squeeze()
    iwm = pd.DataFrame({"tri": iwm_px.squeeze(), "ret": iwm_ret})

    print("[5/5] Gravando schema canonico...")
    panels = {
        "prices_tri": close,           # close ajustado = proxy de retorno total
        "prices_close": close,
        "dollar_volume": dollar_volume,
        "market_cap": market_cap,
        "membership": membership,
        "factors": factors,
        "etf_iwm": iwm,
    }
    for name, df in panels.items():
        df.rename_axis("date").to_parquet(out / f"{name}.parquet")
    sectors.to_parquet(out / "sectors.parquet")

    meta = {
        "fonte": "Nasdaq screener (universo) + yfinance (precos) + Ken French (fatores)",
        "metodo_universo": f"ranks {rank_from + 1}-{rank_to} por market cap (definicao do R2000)",
        "asof": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "n_tickers": int(len(keep)),
        "start": str(close.index[0].date()), "end": str(close.index[-1].date()),
        "vieses_documentados": [
            "SOBREVIVENCIA: lista de hoje; sem deslistadas; membership estatico",
            "MCAP historico = proxy (snapshot escalado pelo preco)",
            "TRI = close ajustado (auto_adjust); dollar volume usa close ajustado",
        ],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK -> {out} | {len(keep)} tickers x {len(close)} dias | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
