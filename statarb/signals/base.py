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

    def _zscore(self, raw: pd.Series) -> pd.Series:
        """Normalizacao padrao: z-score cross-sectional winsorizado em +-cap."""
        raw = raw.replace([np.inf, -np.inf], np.nan).dropna()
        if len(raw) < 5:
            return pd.Series(dtype=float)
        z = (raw - raw.mean()) / (raw.std(ddof=0) + 1e-12)
        return z.clip(-self.cap, self.cap)

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

    def _build_panel(self, md, fm) -> pd.DataFrame:
        raise NotImplementedError

    def compute(self, md, fm, date, universe) -> pd.Series:
        key = (id(md.returns), len(md.returns))
        if getattr(self, "_panel_key", None) != key:
            self._panel = self._build_panel(md, fm)
            self._panel_key = key

        sub = self._panel.loc[:date]
        if len(sub) == 0:
            return pd.Series(dtype=float)
        last = sub.index[-1]
        if (pd.Timestamp(date) - last).days > self.max_staleness_days:
            return pd.Series(dtype=float)

        raw = sub.iloc[-1].reindex(universe)
        return self._zscore(raw)
