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

    def _build_panel(self, dados_mercado, modelo_fatores) -> pd.DataFrame:
        """Constroi a METRICA (passos 1 e 2) como painel data x acao.

        O passo 3 (z-score entre acoes) fica a cargo do PanelSignal.compute().
        """
        params = self.params()
        dias_acumulo = int(params.get("accum_days", 60))    # J: janela do acumulo
        dias_janela_z = int(params.get("z_window", 252))    # W: janela da media/desvio

        # PASSO 1 -- retorno idiossincratico acumulado: soma dos residuos da janela.
        # Economicamente, e o afastamento do equilibrio de fatores que deve reverter.
        retorno_idio_acumulado = modelo_fatores.residuals.rolling(
            dias_acumulo, min_periods=int(dias_acumulo * 0.7)).sum()

        # PASSO 2 -- normaliza contra o historico da PROPRIA acao (cada uma e sua regua).
        # Atencao: media/desvio sao calculados sobre a serie de retorno_idio_acumulado,
        # nao sobre precos.
        media_propria = retorno_idio_acumulado.rolling(
            dias_janela_z, min_periods=dias_janela_z // 2).mean()
        desvio_proprio = retorno_idio_acumulado.rolling(
            dias_janela_z, min_periods=dias_janela_z // 2).std()

        # sinal negativo INVERTE: acumulo acima do normal dela => "cara" => short
        metrica = -(retorno_idio_acumulado - media_propria) / desvio_proprio
        return metrica.dropna(how="all")
