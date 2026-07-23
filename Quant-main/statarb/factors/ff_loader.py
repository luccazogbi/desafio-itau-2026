"""Download dos fatores diarios FF5 + Momentum da biblioteca do Ken French.

Baixa os CSVs zipados DIRETO do site (o parser do pandas_datareader quebra na
linha de copyright do arquivo de Momentum). Valores vem em % -> convertidos
para decimal. Cache em parquet apos o primeiro download.
"""

from __future__ import annotations

import io
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
FILES = {
    "ff5": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
    "mom": "F-F_Momentum_Factor_daily_CSV.zip",
}
RENAME = {"Mkt-RF": "mkt", "SMB": "smb", "HML": "hml", "RMW": "rmw",
          "CMA": "cma", "Mom": "mom", "RF": "rf"}
UA = {"User-Agent": "Mozilla/5.0"}


def _fetch_csv_zip(url: str) -> pd.DataFrame:
    """Baixa um zip do Ken French e parseia o CSV diario de forma robusta."""
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=90).read()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    text = zf.read(zf.namelist()[0]).decode("latin-1")

    lines = text.splitlines()
    header_idx = None
    data = []
    for i, ln in enumerate(lines):
        if re.match(r"^\s*\d{8}\s*,", ln):        # linha de dados: YYYYMMDD,...
            if header_idx is None:
                header_idx = i - 1                 # a linha imediatamente anterior
            data.append(ln)
        elif header_idx is not None:
            break                                  # fim do bloco diario (copyright etc.)

    cols = [c.strip() for c in lines[header_idx].split(",")]
    cols[0] = "date"
    df = pd.read_csv(io.StringIO("\n".join([",".join(cols)] + data)))
    df["date"] = pd.to_datetime(df["date"].astype(str).str.strip(), format="%Y%m%d")
    df = df.set_index("date").apply(pd.to_numeric, errors="coerce")
    df = df.replace([-99.99, -999], pd.NA).astype(float) / 100.0
    return df


def fetch_ff5_mom_daily(cache_dir: str | Path) -> pd.DataFrame:
    """FF5 + Momentum diarios, em decimal, cacheados em parquet."""
    cache = Path(cache_dir) / "factors_ff.parquet"
    if cache.exists():
        return pd.read_parquet(cache)

    ff5 = _fetch_csv_zip(BASE + FILES["ff5"])
    mom = _fetch_csv_zip(BASE + FILES["mom"])
    mom.columns = [c.strip() for c in mom.columns]

    df = ff5.join(mom, how="inner").rename(columns=RENAME)
    df = df[["mkt", "smb", "hml", "rmw", "cma", "mom", "rf"]].dropna()
    df = df.rename_axis("date")

    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    return df
