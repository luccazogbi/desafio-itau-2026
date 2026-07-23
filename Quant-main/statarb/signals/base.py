"""Interface do sinal de alfa -- o PONTO DE ENCAIXE do pipeline.

Contrato:
  compute(md, fm, date, universe) -> pd.Series de scores cross-sectional
  (maior = mais atrativo p/ comprar; menor = mais atrativo p/ vender),
  tipicamente um z-score winsorizado, indexada por ticker (subconjunto
  do universo). REGRA DE OURO: usar somente informacao <= date.

O teste tests/test_pipeline.py::test_signal_no_lookahead verifica esse
contrato truncando o painel e comparando os scores.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class Signal(ABC):
    name: str = "base"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.cap = float(cfg["signal"]["zscore_cap"])

    @abstractmethod
    def compute(self, md, fm, date: pd.Timestamp, universe: list[str]) -> pd.Series:
        """Scores cross-sectional na data, usando apenas dados <= date."""
        raise NotImplementedError

    def _zscore(self, metrica: pd.Series) -> pd.Series:
        """PASSO 3: transforma a METRICA (uma por acao) no SINAL final.

        Padroniza no CORTE TRANSVERSAL -- a media e o desvio sao calculados
        entre as acoes daquele dia, nao ao longo do tempo:
            z_i = (metrica_i - media_do_dia) / desvio_do_dia
        Centrar importa: um book dollar-neutral so monetiza diferencas
        RELATIVAS; o nivel comum a todas as acoes nao e operavel.
        """
        metrica = metrica.replace([np.inf, -np.inf], np.nan).dropna()
        if len(metrica) < 5:
            return pd.Series(dtype=float)
        media_do_dia = metrica.mean()
        desvio_do_dia = metrica.std(ddof=0)
        zscore = (metrica - media_do_dia) / (desvio_do_dia + 1e-12)
        return zscore.clip(-self.cap, self.cap)   # winsoriza: outlier nao domina o book

    def params(self) -> dict:
        """Parametros do sinal declarados em cfg['signal_params'][name]."""
        return self.cfg.get("signal_params", {}).get(self.name, {})


class PanelSignal(Signal):
    """Sinal cujo score cru pode ser pre-computado como um PAINEL inteiro
    (data x ticker) usando SOMENTE operacoes backward-looking (rolling/shift).

    O painel e construido uma vez por objeto de dados (cache) e o compute()
    apenas pega a ultima linha <= date, restringe ao universo e normaliza.
    Anti-lookahead por construcao: como toda transformacao e backward-looking,
    a linha da data t e identica com ou sem o futuro no painel (verificado
    pelos testes de truncamento).
    """

    max_staleness_days: int = 45   # sinais mensais valem ate ~1 mes + folga

    def _build_panel(self, dados_mercado, modelo_fatores) -> pd.DataFrame:
        """Cada sinal implementa aqui a sua METRICA como painel (data x acao)."""
        raise NotImplementedError

    def compute(self, dados_mercado, modelo_fatores, data, universo) -> pd.Series:
        # Cache: o painel inteiro e caro de construir, mas so muda se os dados mudarem
        chave_cache = (id(dados_mercado.returns), len(dados_mercado.returns))
        if getattr(self, "_panel_key", None) != chave_cache:
            self._panel = self._build_panel(dados_mercado, modelo_fatores)
            self._panel_key = chave_cache

        # Corta o painel ate a data (nunca depois: anti-lookahead) e pega a ultima linha
        painel_ate_hoje = self._panel.loc[:data]
        if len(painel_ate_hoje) == 0:
            return pd.Series(dtype=float)

        ultima_data_disponivel = painel_ate_hoje.index[-1]
        dias_desatualizado = (pd.Timestamp(data) - ultima_data_disponivel).days
        if dias_desatualizado > self.max_staleness_days:
            return pd.Series(dtype=float)      # sinal velho demais: melhor nao operar

        metrica_hoje = painel_ate_hoje.iloc[-1].reindex(universo)
        return self._zscore(metrica_hoje)      # PASSO 3 -> sinal final
