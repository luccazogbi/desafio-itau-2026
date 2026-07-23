"""Extracao Bloomberg -> schema canonico (RODAR NA MAQUINA COM TERMINAL).

Requisitos (na maquina do terminal, com o Bloomberg aberto e logado):
    pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
    pip install xbbg

O script grava exatamente o mesmo schema que o gerador sintetico, entao o
resto do pipeline funciona sem NENHUMA alteracao -- basta trocar
data.source para 'bloomberg' no config.yaml e apontar o periodo.

ATENCAO ao limite mensal de consumo de dados do terminal:
  - rode UMA vez e guarde os parquets;
  - o membership e mensal (BMS), nao diario;
  - os campos de preco vem em lotes de 150 tickers.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

INDEX = "RTY Index"          # Russell 2000
ETF = "IWM US Equity"
BATCH = 150
FLD_TRI = "TOT_RETURN_INDEX_GROSS_DVDS"   # retorno total (dividendos reinvestidos)
FLD_PX = "PX_LAST"
FLD_VOL = "PX_VOLUME"
FLD_CAP = "CUR_MKT_CAP"


def month_starts(start: str, end: str) -> pd.DatetimeIndex:
    return pd.bdate_range(start, end, freq="BMS")


def pull_membership(blp, start: str, end: str) -> pd.DataFrame:
    """Constituintes point-in-time via INDX_MWEIGHT_HIST com override de data."""
    snaps = {}
    for d in month_starts(start, end):
        ds = d.strftime("%Y%m%d")
        try:
            mem = blp.bds(INDEX, "INDX_MWEIGHT_HIST", END_DATE_OVERRIDE=ds)
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {ds}: {e}")
            continue
        col = [c for c in mem.columns if "member" in c.lower() or "ticker" in c.lower()][0]
        tickers = sorted({f"{t.split()[0]} US Equity" for t in mem[col].astype(str)})
        snaps[d] = tickers
        print(f"  membership {ds}: {len(tickers)} nomes")
        time.sleep(0.2)

    all_tickers = sorted({t for lst in snaps.values() for t in lst})
    df = pd.DataFrame(False, index=pd.DatetimeIndex(sorted(snaps)), columns=all_tickers)
    for d, lst in snaps.items():
        df.loc[d, lst] = True
    return df


def pull_history(blp, tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    """BDH em lotes: TRI, preco, volume (acoes), market cap."""
    frames = {FLD_TRI: [], FLD_PX: [], FLD_VOL: [], FLD_CAP: []}
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i : i + BATCH]
        px = blp.bdh(chunk, [FLD_TRI, FLD_PX, FLD_VOL, FLD_CAP], start, end)
        for fld in frames:
            sub = px.xs(fld, axis=1, level=1)
            frames[fld].append(sub)
        print(f"  historico {i + len(chunk)}/{len(tickers)}")
        time.sleep(0.5)
    return {f: pd.concat(lst, axis=1) for f, lst in frames.items()}


def main() -> None:
    try:
        from xbbg import blp
    except ImportError:
        sys.exit("xbbg/blpapi nao instalados -- rodar na maquina com terminal Bloomberg.")

    cfg = load_config()
    start, end = cfg["data"]["start"], cfg["data"]["end"]
    out = path_of(cfg, "data_processed")

    print("[1/5] Membership point-in-time do Russell 2000...")
    member = pull_membership(blp, start, end)
    tickers = list(member.columns)

    print(f"[2/5] Historico de {len(tickers)} tickers...")
    h = pull_history(blp, tickers, start, end)
    tri, px = h[FLD_TRI], h[FLD_PX]
    dvol = (h[FLD_PX] * h[FLD_VOL]).astype(float)          # volume financeiro
    mcap = h[FLD_CAP].astype(float) * 1e6                  # CUR_MKT_CAP vem em mm

    print("[3/5] Setor GICS...")
    sec = blp.bdp(tickers, "GICS_SECTOR_NAME")
    sectors = sec.rename(columns=lambda c: "sector").rename_axis("ticker")

    print("[4/5] ETF de hedge (IWM)...")
    etf = blp.bdh(ETF, [FLD_TRI], start, end).droplevel(1, axis=1)
    etf.columns = ["tri"]
    etf["ret"] = etf["tri"].pct_change()

    print("[5/5] Fatores FF5+MOM (Ken French, gratuito)...")
    from statarb.factors.ff_loader import fetch_ff5_mom_daily
    factors = fetch_ff5_mom_daily(path_of(cfg, "data_raw")).loc[start:end]

    # normaliza nomes de colunas: 'ABC US Equity' -> 'ABC'
    strip = lambda df: df.rename(columns=lambda c: str(c).split()[0])
    for name, df in {
        "prices_tri": strip(tri), "prices_close": strip(px),
        "dollar_volume": strip(dvol), "market_cap": strip(mcap),
        "membership": strip(member), "factors": factors, "etf_iwm": etf,
    }.items():
        df.rename_axis("date").to_parquet(out / f"{name}.parquet")
    sectors.index = [str(t).split()[0] for t in sectors.index]
    sectors.to_parquet(out / "sectors.parquet")

    meta = {"universe": INDEX, "n_tickers": len(tickers), "start": start, "end": end}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
