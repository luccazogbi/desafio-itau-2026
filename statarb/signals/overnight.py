"""Sinal overnight "tug of war" (Lou, Polk & Skouras, JFE 2019).

Fato do paper: o componente OVERNIGHT do retorno (close de ontem -> abertura de
hoje) exibe CONTINUACAO firme no cross-section -- quem tem overnight alto segue
com overnight alto -- por efeito de clientelas/sentimento, nao de fatores.

    on_ret_i(d) = Open_i(d) / Close_i(d-1) - 1
    score_i(t)  = soma[ log(1+on_ret) ] dos ultimos W dias   (long = overnight alto)

Requer precos de ABERTURA ajustados na MESMA base dos closes (auto_adjust do
yfinance) -- inconsistencia de ajuste criaria "alfa" falso em toda ex-date.
Painel: prices_open.parquet (scripts/07c_add_open_sp500.py).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PanelSignal


class Overnight(PanelSignal):
    name = "overnight"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        if getattr(md, "open_", None) is None:
            return pd.DataFrame()          # painel sem abertura -> sinal indisponivel
        p = self.params()
        W = int(p.get("window", 21))
        mo = int(p.get("min_obs", 15))

        on = (md.open_ / md.close.shift(1) - 1.0).clip(-0.5, 0.5)
        raw = np.log1p(on).rolling(W, min_periods=mo).sum()
        return raw.dropna(how="all")
