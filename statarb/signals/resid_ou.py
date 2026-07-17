"""Reversao do RETORNO IDIOSSINCRATICO ACUMULADO (Avellaneda & Lee 2010, versao parametrica).

TESE: um movimento proprio da acao (nao explicado pelos fatores) anormalmente
grande costuma ser sobre-reacao a fluxo, nao informacao -> reverte em ~1 mes.

METRICA (numero por acao) em 2 passos:
    X_i(t)  = soma dos residuos FF5+MOM dos ultimos J dias  (retorno idiossincratico
              acumulado; economicamente, o afastamento do equilibrio de fatores)
    s_i(t)  = -( X_i(t) - media_rolante(X_i) ) / desvio_padrao_rolante(X_i)
              -> "esse acumulo e grande PARA ESTA acao?" (cada acao e sua propria regua)

SINAL: s_i padronizado no cross-section (z-score, cap +-3) -> ranking do universo.
X muito acima do normal dela => esticada p/ cima => "cara" => short; abaixo => long.

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
