"""Left-tail momentum (Atilgan, Bali, Demirtas & Gunaydin, JFE 2020).

Fato do paper: risco de cauda esquerda e PERSISTENTE e os investidores
subestimam essa persistencia -- seguram acoes que acabaram de sofrer perdas
grandes, que ficam sobrevalorizadas e continuam caindo.

    VaR1_i(t) = -(1o percentil dos retornos diarios dos ultimos 250 pregoes)
    score     = -z(VaR1)      (cauda pesada -> short; cauda leve -> long)

Turnover baixissimo (o VaR de 250 dias muda devagar) -- e o ponto forte:
mesmo um alfa modesto sobrevive aos custos. Dados: apenas retornos.
Refresh a cada 21 dias por eficiencia (a medida quase nao muda no meio-tempo).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PanelSignal


class LeftTail(PanelSignal):
    name = "left_tail"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        W = int(p.get("window", 250))
        min_obs = int(p.get("min_obs", 200))
        q = float(p.get("quantile", 0.01))
        every = int(p.get("refresh_days", 21))

        rets = md.returns
        idx = rets.index
        rows, dates = [], []
        for pos in range(W - 1, len(idx), every):
            win = rets.iloc[pos - W + 1 : pos + 1]
            counts = win.notna().sum()
            with np.errstate(all="ignore"):
                var1 = -np.nanpercentile(win.values, q * 100.0, axis=0)
            row = pd.Series(var1, index=rets.columns)
            row[counts < min_obs] = np.nan
            rows.append(-row)             # cauda pesada (VaR alto) => score baixo
            dates.append(idx[pos])
        return pd.DataFrame(rows, index=pd.DatetimeIndex(dates))
