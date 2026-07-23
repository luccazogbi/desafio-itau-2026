"""Inferencia estatistica para series com JANELAS SOBREPOSTAS.

O PROBLEMA: medimos o IC contra o retorno residual de `h` dias a frente, numa
grade que avanca `every` dias. Com h=21 e every=5, duas medicoes consecutivas
compartilham 16 dos 21 dias -- os ICs NAO sao independentes. O t-stat ingenuo

    t = media / desvio * raiz(n)

assume independencia e superestima a evidencia por um fator da ordem de
raiz(h/every) -- com h=21 e every=5, cerca de 2x. Um "t = 4" vira "t = 2".

A CORRECAO (Newey-West, 1987): usa a variancia de longo prazo da media, que
soma as autocovariancias ate o lag onde a sobreposicao morre:

    var_NW = [gamma_0 + 2 * soma_l ( 1 - l/(L+1) ) * gamma_l] / n
    t_NW   = media / raiz(var_NW)

Os pesos de Bartlett (1 - l/(L+1)) garantem variancia nao-negativa. O lag L
natural aqui e o numero de medicoes que ainda se sobrepoem: ceil(h/every) - 1.

Isso NAO muda o IC medio -- muda apenas a confianca que se pode ter nele.
"""

from __future__ import annotations

import numpy as np


def overlap_lag(horizon_days: int, every_days: int) -> int:
    """Lag de truncamento implicado pela sobreposicao das janelas.

    Duas medicoes separadas por `every` dias compartilham dias enquanto a
    distancia entre elas for menor que o horizonte `h`. Logo o numero de
    vizinhos correlacionados de cada lado e ceil(h/every) - 1.
    """
    if every_days <= 0 or horizon_days <= 0:
        return 0
    return max(0, int(np.ceil(horizon_days / every_days)) - 1)


def newey_west_tstat(valores, lag: int) -> float:
    """t-stat da media de `valores`, robusto a autocorrelacao ate `lag`.

    Com lag=0 devolve exatamente o t-stat classico (media/desvio*raiz(n)).
    """
    x = np.asarray([v for v in np.asarray(valores, dtype=float).ravel()
                    if np.isfinite(v)], dtype=float)
    n = len(x)
    if n < 5:
        return float("nan")

    desvios = x - x.mean()
    gamma0 = float(desvios @ desvios) / n
    if gamma0 <= 0:
        return float("nan")

    var_longo_prazo = gamma0
    for l in range(1, min(int(lag), n - 1) + 1):
        gamma_l = float(desvios[l:] @ desvios[:-l]) / n
        peso_bartlett = 1.0 - l / (lag + 1.0)
        var_longo_prazo += 2.0 * peso_bartlett * gamma_l

    if var_longo_prazo <= 0:                 # autocovariancias negativas dominaram
        return float("nan")
    return float(x.mean() / np.sqrt(var_longo_prazo / n))


def tstat_com_e_sem_correcao(valores, horizon_days: int, every_days: int) -> dict:
    """Devolve os dois t-stats lado a lado -- util em relatorio, para mostrar
    o tamanho do efeito da sobreposicao em vez de so trocar o numero."""
    lag = overlap_lag(horizon_days, every_days)
    return {
        "t_ingenuo": newey_west_tstat(valores, 0),
        "t_newey_west": newey_west_tstat(valores, lag),
        "lag": lag,
    }
