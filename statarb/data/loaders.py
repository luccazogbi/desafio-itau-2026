"""Carregamento do painel canonico em um objeto unico de dados de mercado.

Qualquer fonte (sintetica ou Bloomberg) que grave o schema canonico em
data/processed/ e lida aqui do mesmo jeito -- o resto do pipeline nao sabe
(nem precisa saber) de onde os dados vieram.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class MarketData:
    """Painel de mercado alinhado em dias uteis (index comum = returns.index)."""

    tri: pd.DataFrame            # indice de retorno total
    close: pd.DataFrame          # preco de fechamento
    returns: pd.DataFrame        # retornos diarios totais (pct_change do TRI)
    dollar_volume: pd.DataFrame  # volume financeiro diario
    adv: pd.DataFrame            # ADV mediano rolling (USD)
    market_cap: pd.DataFrame
    membership_daily: pd.DataFrame  # bool diario (ffill do snapshot mensal)
    sectors: pd.Series           # ticker -> setor GICS
    factors: pd.DataFrame        # retornos diarios dos fatores (sem rf)
    rf: pd.Series                # taxa livre de risco diaria
    iwm_ret: pd.Series           # retorno diario do ETF de hedge
    earnings: pd.DataFrame | None = None  # EPS trailing (degraus trimestrais); opcional
    open_: pd.DataFrame | None = None     # abertura ajustada; opcional (sinal overnight)

    @classmethod
    def from_dir(cls, processed: str | Path, cfg: dict) -> "MarketData":
        processed = Path(processed)
        read = lambda n: pd.read_parquet(processed / f"{n}.parquet")

        tri = read("prices_tri").sort_index()
        returns = tri.pct_change(fill_method=None)
        idx = returns.index

        close = read("prices_close").reindex(idx)
        dvol = read("dollar_volume").reindex(idx)
        adv_w = int(cfg["costs"]["adv_window"])
        adv = dvol.rolling(adv_w, min_periods=max(5, adv_w // 2)).median()

        member_m = read("membership")
        limit = int(cfg["universe"]["membership_ffill_limit_days"])
        member_d = (
            member_m.astype(float).reindex(idx.union(member_m.index))
            .ffill(limit=limit).reindex(idx).fillna(0.0) > 0.5
        )

        fac_all = read("factors").reindex(idx)
        fac_names = list(cfg["factors"]["names"])
        iwm = read("etf_iwm").reindex(idx)

        earn_path = processed / "earnings.parquet"
        earnings = pd.read_parquet(earn_path).reindex(idx) if earn_path.exists() else None

        open_path = processed / "prices_open.parquet"
        open_ = pd.read_parquet(open_path).reindex(idx) if open_path.exists() else None

        return cls(
            tri=tri, close=close, returns=returns, dollar_volume=dvol, adv=adv,
            market_cap=read("market_cap").reindex(idx),
            membership_daily=member_d,
            sectors=read("sectors")["sector"],
            factors=fac_all[fac_names],
            rf=fac_all["rf"],
            iwm_ret=iwm["ret"],
            earnings=earnings,
            open_=open_,
        )
