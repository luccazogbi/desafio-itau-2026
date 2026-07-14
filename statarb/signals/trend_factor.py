"""Trend factor (Han, Zhou & Zhu, JFE 2016) + variante MAD (Avramov et al. 2021).

TREND FACTOR -- um unico sinal que combina reversao curta, momentum medio e
reversao longa, aprendendo o peso de cada horizonte nos dados:

  1. No fim de cada mes t, para cada acao i e cada janela L da grade:
         A(i,L,t) = MA_L(preco) / preco_t     (normalizar pelo preco e essencial)
  2. Regressao cross-sectional mensal: r_i(t) = sum_L beta_L(t) * A(i,L,t-1) + e
  3. Suavizar: E[beta_L] = media dos beta_L dos ultimos 12 meses (sem isso e ruido)
  4. Score(t) = sum_L E[beta_L] * A(i,L,t)  -> previsao do retorno do mes t+1

Grade truncada em 400 dias (paper vai a 1000; small caps jovens nao tem
historico -- decisao documentada, recomendacao do doc de sinais do colega).

MAD -- Moving Average Distance: MA(21)/MA(200). Ancoragem: investidores
subreagem a informacao que afasta o preco da media longa. Implementada como
variante do modulo de tendencia (mesma familia; medir alfa incremental no funil).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PanelSignal


def _month_ends(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.Series(idx, index=idx).groupby(idx.to_period("M")).last())


class TrendFactor(PanelSignal):
    name = "trend_factor"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        grid = list(p.get("ma_grid", [3, 5, 10, 20, 50, 100, 200, 400]))
        smooth = int(p.get("smooth_months", 12))
        min_names = int(p.get("min_names", 50))

        tri = md.tri
        me = _month_ends(tri.index)

        # A(:, L) nos fins de mes -- rolling diario, depois subamostra (backward)
        A = {L: (tri.rolling(L).mean() / tri).loc[me] for L in grid}
        rm = tri.loc[me].pct_change(fill_method=None)

        # regressoes cross-sectional mensais: retorno do mes t sobre A de t-1
        betas = pd.DataFrame(np.nan, index=me, columns=grid, dtype=float)
        for i in range(1, len(me)):
            y = rm.iloc[i]
            X = pd.DataFrame({L: A[L].iloc[i - 1] for L in grid})
            valid = X.notna().all(axis=1) & y.notna()
            if int(valid.sum()) < min_names:
                continue
            Xc = np.column_stack([np.ones(int(valid.sum())), X[valid].values])
            coef, *_ = np.linalg.lstsq(Xc, y[valid].values, rcond=None)
            betas.iloc[i] = coef[1:]

        eb = betas.rolling(smooth, min_periods=max(3, smooth // 2)).mean()

        # score no fim do mes t: E[beta] (conhecido em t) x A em t  -> preve t+1
        panel = pd.DataFrame(np.nan, index=me, columns=tri.columns)
        for i, t in enumerate(me):
            if eb.iloc[i].isna().any():
                continue
            score = sum(eb.iloc[i][L] * A[L].iloc[i] for L in grid)
            panel.iloc[i] = score
        return panel.dropna(how="all")


class MAD(PanelSignal):
    name = "mad"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        short, long = int(p.get("short_ma", 21)), int(p.get("long_ma", 200))
        tri = md.tri
        return (tri.rolling(short).mean() / tri.rolling(long).mean()).dropna(how="all")
