"""Reversao de residuo com z-score temporal (Avellaneda & Lee 2010, versao parametrica).

Upgrade do placeholder idio_reversal: em vez de olhar a soma de residuos de 5
dias contra o cross-section, acumula o residuo por uma janela mais longa e
pergunta "o desvio ATUAL desta acao esta esticado vs o historico DELA?"
(tratamento Ornstein-Uhlenbeck simplificado):

    X_i(t)  = soma dos residuos FF5+MOM dos ultimos J dias   (desvio acumulado)
    z_i(t)  = -( X_i(t) - media_rolante(X_i) ) / desvio_rolante(X_i)

X muito acima da media propria => acao "cara" vs seus fatores => short (sinal
negativo); muito abaixo => long. A normalizacao temporal por nome remove
diferencas de escala entre acoes antes do z cross-sectional final.

Dados: apenas retornos (residuos do FactorModel). Zero dependencia extra.
"""

from __future__ import annotations

import pandas as pd

from .base import PanelSignal


class ResidOU(PanelSignal):
    name = "resid_ou"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        J = int(p.get("accum_days", 60))
        W = int(p.get("z_window", 252))

        X = fm.residuals.rolling(J, min_periods=int(J * 0.7)).sum()
        mu = X.rolling(W, min_periods=W // 2).mean()
        sd = X.rolling(W, min_periods=W // 2).std()
        raw = -(X - mu) / sd
        return raw.dropna(how="all")
