"""Combinador (blend): agrega os z-scores de varios sinais num UNICO alfa.

    alpha_i = sum_k  w_k * z_{k,i}     ->  re-normalizado (z-score) e winsorizado

E o "sexto sinal" da arquitetura: o modelo final consolidado que o edital pede
(FAQ 20 -- submodulos sao permitidos, a avaliacao e sobre o modelo global).
Racional: sinais modestos e DESCORRELACIONADOS somam Sharpe --
Sharpe_blend = S * sqrt(K / (1 + (K-1)*rho)). Os componentes e pesos vivem no
config (blend.components); o funil decide QUEM entra apos os dados reais.

Convencao de alinhamento: cada z e reindexado a uniao dos nomes; ausencia num
sinal = contribuicao zero daquele sinal (nao exclui o nome do book).
"""

from __future__ import annotations

import pandas as pd

from .base import Signal


class BlendSignal(Signal):
    name = "blend"

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        from . import _REGISTRY  # import tardio (registro completo na chamada)

        comps: dict[str, float] = dict(cfg["blend"]["components"])
        if not comps:
            raise ValueError("blend.components vazio no config")
        self._subs = [(name, float(w), _REGISTRY[name](cfg)) for name, w in comps.items()]

    def compute(self, md, fm, date, universe) -> pd.Series:
        zs = []
        for name, w, sig in self._subs:
            z = sig.compute(md, fm, date, universe)
            if len(z):
                zs.append(w * z)
        if not zs:
            return pd.Series(dtype=float)

        union = zs[0].index
        for z in zs[1:]:
            union = union.union(z.index)
        acc = sum(z.reindex(union).fillna(0.0) for z in zs)
        return self._zscore(acc)
