"""S&P 500 com composicao historica AS-OF (mata o vies de selecao) -- plano B v2.

Direcao do orientador (12/07): migrar o universo para o S&P 500 (dados yfinance
mais confiaveis), hedge com SPY, e construir a composicao historica do indice
para backtest as-of.

Fontes (gratuitas, verificadas):
  * Membership: dataset "S&P 500 Historical Components & Changes" (repo
    fja05680/sp500, construido do change log oficial mantido na Wikipedia) --
    composicao completa em cada data de mudanca desde 1996.
  * Precos/volume: yfinance (ajustados) para TODOS os tickers que ja foram
    membros na janela -- incluindo os que sairam depois.
  * Fatores: Ken French FF5+MOM (cache local).
  * Hedge: SPY (gravado no slot canonico etf_iwm.parquet -- o motor le como
    "ETF de hedge"; a semantica esta no meta.json).

VIES RESIDUAL (quantificado, nao ignorado): membership as-of resolve o vies de
SELECAO; resta o de DADOS -- tickers deslistados/renomeados sem historico no
yfinance. O script MEDE a cobertura (membros com preco / membros as-of, mes a
mes) e grava no meta.json. Esse numero vai no relatorio.

Uso:  python scripts/07_pull_sp500_asof.py [--start 2018-01-02]
Saida: data/processed_sp500/
"""

from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

OUT_SUBDIR = "processed_sp500"
DATASET = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
           "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
HEADERS = {"User-Agent": "Mozilla/5.0"}
BATCH = 250

# Renomeacoes de ticker (antigo -> atual no yfinance), resolvidas transitivamente
# (ex.: CBS -> VIAC -> PARA -> PSKY colapsa em CBS -> PSKY).
#
# POR QUE ISSO IMPORTA: quando so o SIMBOLO muda, a empresa continua no indice --
# mas o diff das listas de constituintes registra um par remove+add, e o ticker
# antigo vira um "nome sem preco nenhum" no painel. Cada renomeacao nao tratada
# apaga a empresa inteira do universo no periodo ANTERIOR a troca (ex.: sem o
# UTX -> RTX, a United Technologies some do painel de 2018 a abr/2020).
#
# O mapa e derivado por `scripts/13_membership_audit.py`: pares (rem X, add Y) na
# mesma data que aparecem no diff do fja05680 mas NAO no change log da Wikipedia
# -- mudanca real de indice a Wikipedia registra; troca de ticker, nao.
# Mantido explicito aqui (e nao baixado em runtime) para ser auditavel e estavel.
#
# RESSALVA: alguns pares combinam renomeacao com fusao (CBS/Viacom, Paramount/
# Skydance). Tratamos como continuidade do constituinte porque e assim que a
# Wikipedia -- e portanto a S&P -- os registra: sem evento de indice.
RENAMES = {
    "ABC": "COR",    "ANTM": "ELV",   "BBT": "TFC",    "BHGE": "BKR",
    "BK": "BNY",     "BLL": "BALL",   "CBS": "PSKY",   "COG": "CTRA",
    "CTL": "LUMN",   "FB": "META",    "FI": "FISV",    "HRS": "LHX",
    "JEC": "J",      "KORS": "CPRI",  "LB": "BBWI",    "MMC": "MRSH",
    "MYL": "VTRS",   "NLOK": "GEN",   "PARA": "PSKY",  "PEAK": "DOC",
    "PKI": "RVTY",   "SATS": "ECHO",  "TMK": "GL",     "UTX": "RTX",
    "VIAC": "PSKY",  "WRK": "SW",
}


def _arg(flag: str, default: str) -> str:
    args = sys.argv[1:]
    return args[args.index(flag) + 1] if flag in args else default


def load_membership_asof(start: str) -> tuple[pd.DataFrame, dict]:
    """Snapshots mensais (BMS) da composicao as-of a partir do change log."""
    req = urllib.request.Request(DATASET, headers=HEADERS)
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
    df = pd.read_csv(io.StringIO(raw))
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    def clean(tk: str) -> str:
        tk = tk.strip()
        tk = re.sub(r"-\d{6}$", "", tk)          # sufixo de deslistagem do dataset antigo
        tk = RENAMES.get(tk, tk)
        return tk.replace(".", "-")               # BRK.B -> BRK-B (padrao yfinance)

    df["members"] = df["tickers"].apply(lambda s: sorted({clean(t) for t in str(s).split(",") if t.strip()}))

    snaps = pd.bdate_range(start, pd.Timestamp.today(), freq="BMS")
    all_members: set[str] = set()
    rows = {}
    for d in snaps:
        prev = df[df["date"] <= d]
        if prev.empty:
            continue
        members = prev.iloc[-1]["members"]
        rows[d] = members
        all_members.update(members)

    cols = sorted(all_members)
    member = pd.DataFrame(False, index=pd.DatetimeIndex(sorted(rows)), columns=cols)
    for d, members in rows.items():
        member.loc[d, members] = True

    meta = {
        "dataset_first_change": str(df["date"].iloc[0].date()),
        "dataset_last_change": str(df["date"].iloc[-1].date()),
        "n_change_dates": int(len(df)),
        "n_members_ever_in_window": len(cols),
        "avg_members_per_month": float(member.sum(axis=1).mean()),
    }
    print(f"[membership] change log: {meta['n_change_dates']} datas "
          f"({meta['dataset_first_change']} a {meta['dataset_last_change']}) | "
          f"janela: {len(cols)} tickers distintos | ~{meta['avg_members_per_month']:.0f} membros/mes")
    return member, meta


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
    # remove colunas duplicadas (renames que colidem) e 100% vazias
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]
    return close, volume


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    start = _arg("--start", cfg["data"]["start"])
    out = path_of(cfg, "data_processed").parent / OUT_SUBDIR
    out.mkdir(parents=True, exist_ok=True)

    print("[1/6] Composicao historica as-of (fja05680/sp500 <- Wikipedia change log)...")
    member, meta_m = load_membership_asof(start)

    print(f"[2/6] Precos/volume de {member.shape[1]} membros historicos via yfinance...")
    close, volume = download_prices(list(member.columns), start)

    print("[3/6] Fatores FF5+MOM (cache) + truncamento na ultima data com fatores...")
    from statarb.factors.ff_loader import fetch_ff5_mom_daily
    factors_all = fetch_ff5_mom_daily(path_of(cfg, "data_raw"))
    last_f = factors_all.index[-1]
    close, volume = close.loc[:last_f], volume.loc[:last_f]
    factors = factors_all.reindex(close.index).ffill(limit=3)

    print("[4/6] COBERTURA: membros as-of com preco disponivel, mes a mes...")
    cov_rows = {}
    for d in member.index:
        members_d = member.columns[member.loc[d]]
        if d > close.index[-1] or d < close.index[0]:
            continue
        pos = close.index.searchsorted(d)
        window = close.iloc[max(0, pos - 5) : pos + 1]          # preco valido na semana da data
        have = window[members_d.intersection(close.columns)].notna().any()
        cov_rows[d] = float(have.sum() / len(members_d))
    coverage = pd.Series(cov_rows).sort_index()
    print(f"    cobertura media: {coverage.mean():.1%} | min: {coverage.min():.1%} "
          f"({coverage.idxmin():%Y-%m}) | max: {coverage.max():.1%}")

    print("[5/6] SPY (hedge) + paineis derivados...")
    import yfinance as yf
    spy_px = yf.download("SPY", start=start, auto_adjust=True, progress=False)["Close"]
    spy_px.index = pd.to_datetime(spy_px.index).tz_localize(None)
    spy_px = spy_px.reindex(close.index).ffill()
    spy_ret = spy_px.pct_change(fill_method=None).squeeze()
    etf = pd.DataFrame({"tri": spy_px.squeeze(), "ret": spy_ret})

    dollar_volume = (close * volume).astype(float)
    market_cap = pd.DataFrame(np.nan, index=close.index, columns=close.columns)  # nao usado p/ reversao
    sectors = pd.DataFrame({"sector": "Unknown"}, index=pd.Index(close.columns, name="ticker"))
    member_out = member.reindex(columns=close.columns).fillna(False)

    print("[6/6] Gravando schema canonico...")
    for name, df in {
        "prices_tri": close, "prices_close": close, "dollar_volume": dollar_volume,
        "market_cap": market_cap, "membership": member_out, "factors": factors, "etf_iwm": etf,
    }.items():
        df.rename_axis("date").to_parquet(out / f"{name}.parquet")
    sectors.to_parquet(out / "sectors.parquet")

    meta = {
        "universo": "S&P 500 com composicao historica AS-OF",
        "hedge_etf": "SPY (gravado no slot etf_iwm.parquet)",
        "fontes": {"membership": "fja05680/sp500 (Wikipedia change log)",
                   "precos": "yfinance (ajustados)", "fatores": "Ken French FF5+MOM"},
        **meta_m,
        "asof_pull": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "janela": [str(close.index[0].date()), str(close.index[-1].date())],
        "cobertura_membros_asof": {
            "media": round(float(coverage.mean()), 4),
            "minima": round(float(coverage.min()), 4),
            "mes_minimo": str(coverage.idxmin().date()),
            "serie_mensal": {str(k.date()): round(v, 4) for k, v in coverage.items()},
        },
        "vieses_documentados": [
            "SELECAO: RESOLVIDO -- membership as-of por data (inclui quem saiu depois)",
            f"DADOS: residual -- {1 - coverage.mean():.1%} dos membros as-of (media) sem "
            "historico no yfinance (deslistados/renomeados); direcao: tende a INFLAR "
            "levemente resultados, quantificado acima",
            "market_cap: nao disponivel historicamente (NaN; nao usado pela reversao)",
        ],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK -> {out} | {close.shape[1]} tickers x {len(close)} dias | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
