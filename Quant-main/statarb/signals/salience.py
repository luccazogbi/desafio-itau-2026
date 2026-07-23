"""Sinal de saliencia (Cosemans & Frehen, JFE 2021; teoria: Bordalo et al.).

Investidores sobreponderam os dias de retorno mais "salientes" (mais distantes
do mercado) ao formar expectativas. Upside saliente atrai demanda -> acao fica
sobrevalorizada -> retorno futuro baixo (e vice-versa).

    saliencia do dia d:  sig_d = |r_i,d - r_m,d| / (|r_i,d| + |r_m,d| + theta)
    pesos distorcidos:   w_d ~ delta^rank(sig_d),  normalizados na janela
    ST_i = media ponderada pelos pesos distorcidos - media simples
    score = -ST   (upside saliente = caro = short)

theta=0.1 e delta=0.7 sao os valores do paper -- FIXOS (otimiza-los seria
fabricar backtest). Mercado = ETF de hedge do painel (SPY). Expectativa honesta
em large caps: fraca (o efeito mora em limits-to-arbitrage) -- teste barato.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PanelSignal


class Salience(PanelSignal):
    name = "salience"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        theta = float(p.get("theta", 0.1))
        delta = float(p.get("delta", 0.7))
        W = int(p.get("window", 21))
        every = int(p.get("refresh_days", 5))

        rets = md.returns
        m = md.iwm_ret.reindex(rets.index)
        idx = rets.index

        rows, dates = [], []
        for pos in range(W - 1, len(idx), every):
            R = rets.iloc[pos - W + 1 : pos + 1].values          # W x N
            mm = m.iloc[pos - W + 1 : pos + 1].values[:, None]   # W x 1
            bad = np.isnan(R).any(axis=0) | np.isnan(mm).any()

            sig = np.abs(R - mm) / (np.abs(R) + np.abs(mm) + theta)
            sig = np.nan_to_num(sig, nan=-1.0)
            order = np.argsort(-sig, axis=0)                     # rank 0 = mais saliente
            ranks = np.empty_like(order)
            np.put_along_axis(ranks, order, np.arange(W)[:, None].repeat(R.shape[1], 1), axis=0)
            w = delta ** ranks
            w /= w.sum(axis=0, keepdims=True)

            ST = (w * np.nan_to_num(R)).sum(axis=0) - np.nanmean(R, axis=0)
            row = pd.Series(-ST, index=rets.columns)
            row[bad] = np.nan
            rows.append(row)
            dates.append(idx[pos])
        return pd.DataFrame(rows, index=pd.DatetimeIndex(dates)).dropna(how="all")
