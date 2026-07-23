"""Sinal placeholder: reversao de curto prazo IDIOSSINCRATICA.

Tese: em small caps, choques de fluxo nao-informacional geram sobre-reacao
de precos; o componente do retorno NAO explicado pelos fatores tende a
reverter em poucos dias. Quem prove liquidez captura essa reversao.

score_i = - (soma dos residuos dos ultimos L dias) / (ivol_i * sqrt(L))

Normalizacao: z-score cross-sectional winsorizado em +/- cap.
Usa apenas residuos <= date (residuos ja sao anti-lookahead por construcao
no FactorModel).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Signal


class IdioReversal(Signal):
    name = "idio_reversal"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        s = cfg["signal"]
        self.lookback = int(s["lookback_days"])
        self.cap = float(s["zscore_cap"])

    def compute(self, md, fm, date, universe) -> pd.Series:
        resid = fm.residuals.loc[:date]
        if len(resid) < self.lookback:
            return pd.Series(dtype=float)
        window = resid.tail(self.lookback)

        cols = [c for c in universe if c in window.columns]
        ivol = fm.idio_asof(date)
        if ivol is None or not cols:
            return pd.Series(dtype=float)

        cum = window[cols].sum(min_count=max(1, self.lookback - 2))
        raw = -cum / (ivol.reindex(cols) * np.sqrt(self.lookback))
        raw = raw.replace([np.inf, -np.inf], np.nan).dropna()
        if len(raw) < 5:
            return pd.Series(dtype=float)

        z = (raw - raw.mean()) / (raw.std(ddof=0) + 1e-12)
        return z.clip(-self.cap, self.cap)
