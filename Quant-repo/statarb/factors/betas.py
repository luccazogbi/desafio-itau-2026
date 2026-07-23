"""Modelo de fatores FF5 + Momentum: betas rolling, vol idiossincratica e residuos.

As cargas (betas) sao estimadas por OLS em janela rolling e RE-USADAS ate a
proxima data de estimacao (betas movem devagar; re-estimar diariamente so
adiciona ruido e custo computacional).

Anti-lookahead: o residuo do dia s usa exclusivamente betas estimados em
t < s (a ultima data de estimacao anterior ao segmento).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class FactorModel:
    def __init__(self, cfg: dict):
        f = cfg["factors"]
        self.window = int(f["beta_window"])
        self.min_obs = int(f["beta_min_obs"])
        self.every = int(f["estimation_every_days"])
        self.factor_names: list[str] = list(f["names"])
        self._B: dict[pd.Timestamp, pd.DataFrame] = {}
        self._ivol: dict[pd.Timestamp, pd.Series] = {}
        self.est_index: pd.DatetimeIndex | None = None
        self.residuals: pd.DataFrame | None = None

    # ------------------------------------------------------------------ fit
    def fit(self, returns: pd.DataFrame, factors: pd.DataFrame) -> "FactorModel":
        idx = returns.index
        F = factors.reindex(idx)[self.factor_names]

        for p in range(self.window - 1, len(idx), self.every):
            t = idx[p]
            sl = slice(p - self.window + 1, p + 1)
            R = returns.iloc[sl]
            X = F.iloc[sl].values
            Xc = np.column_stack([np.ones(len(X)), X])

            count = R.notna().sum()
            cols = count[count >= self.min_obs].index
            if len(cols) < 5:
                continue
            R0 = R[cols].fillna(0.0).values

            coef, *_ = np.linalg.lstsq(Xc, R0, rcond=None)
            resid = R0 - Xc @ coef
            k = coef.shape[0]
            self._B[t] = pd.DataFrame(coef[1:].T, index=cols, columns=self.factor_names)
            self._ivol[t] = pd.Series(
                resid.std(axis=0, ddof=min(k, len(R0) - 1)), index=cols
            ).clip(lower=1e-4)

        self.est_index = pd.DatetimeIndex(sorted(self._B))
        self._build_residuals(returns, F)
        return self

    def _build_residuals(self, returns: pd.DataFrame, F: pd.DataFrame) -> None:
        """Painel diario de residuos r - B f, usando o beta vigente (passado)."""
        idx = returns.index
        resid = pd.DataFrame(np.nan, index=idx, columns=returns.columns)
        ei = self.est_index
        for i, t in enumerate(ei):
            t_next = ei[i + 1] if i + 1 < len(ei) else idx[-1]
            seg = idx[(idx > t) & (idx <= t_next)]
            if len(seg) == 0:
                continue
            B = self._B[t]
            pred = F.loc[seg].values @ B.values.T
            resid.loc[seg, B.index] = returns.loc[seg, B.index].values - pred
        self.residuals = resid

    # ---------------------------------------------------------------- as-of
    def _asof(self, store: dict, date: pd.Timestamp):
        pos = self.est_index.searchsorted(date, side="right") - 1
        return None if pos < 0 else store[self.est_index[pos]]

    def betas_asof(self, date) -> pd.DataFrame | None:
        """Betas vigentes na data (ultima estimacao <= date)."""
        return self._asof(self._B, pd.Timestamp(date))

    def idio_asof(self, date) -> pd.Series | None:
        """Vol idiossincratica diaria vigente na data."""
        return self._asof(self._ivol, pd.Timestamp(date))
