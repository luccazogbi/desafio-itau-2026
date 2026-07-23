"""Sinal de validacao: Earnings Yield (E/P), como no notebook de referencia.

E/P_i(t) = EPS_i (ultimo conhecido ate t) / preco_i(t)

Tese (Basu 1977): acoes "baratas" em lucro (E/P alto) rendem mais que as
"caras" (E/P baixo). EPS negativo -> E/P negativo -> lado short, o que e
sensato. Normalizacao: z-score cross-sectional winsorizado.

PAPEL NO PROJETO: sinal DESCARTAVEL de validacao da esteira com um sinal
fundamentalista lento (turnover baixo), antes de plugar os 5 sinais reais.
No sintetico, o alfa do E/P foi plantado ortogonal aos fatores; no mundo
real, E/P carrega value/HML e seria parcialmente neutralizado pelas
constraints do otimizador -- licao a documentar no relatorio.

Anti-lookahead: o painel de earnings ja vem em degraus (o EPS so muda no
inicio de cada trimestre), entao o valor na linha t e o ultimo CONHECIDO em t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Signal


class EarningsYield(Signal):
    name = "earnings_yield"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.cap = float(cfg["signal"]["zscore_cap"])

    def compute(self, md, fm, date, universe) -> pd.Series:
        if getattr(md, "earnings", None) is None:
            return pd.Series(dtype=float)

        eps = md.earnings.loc[:date]
        if len(eps) == 0:
            return pd.Series(dtype=float)
        eps = eps.iloc[-1].reindex(universe)
        px = md.close.loc[:date].iloc[-1].reindex(universe)

        raw = (eps / px).replace([np.inf, -np.inf], np.nan).dropna()
        raw = raw[px.reindex(raw.index) > 0]
        if len(raw) < 5:
            return pd.Series(dtype=float)

        z = (raw - raw.mean()) / (raw.std(ddof=0) + 1e-12)
        return z.clip(-self.cap, self.cap)
