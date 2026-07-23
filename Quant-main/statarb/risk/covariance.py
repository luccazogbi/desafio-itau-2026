"""Covariancia estruturada por modelo de fatores.

Sigma = B F B' + D, onde F = cov dos fatores (K x K) e D = diag(ivol^2).

Nunca formamos a matriz N x N: com N ~ 2000 e T ~ 252 a covariancia
amostral e singular e ruidosa (T < N). A forma fatorada e a pratica
padrao da industria e mantem o problema de otimizacao pequeno:
o termo de risco vira ||chol(F)' B' w||^2 + ||ivol .* w||^2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def factor_cov_chol(factors: pd.DataFrame, date, window: int) -> np.ndarray:
    """Cholesky da covariancia diaria dos fatores usando dados <= date."""
    F = factors.loc[:date].tail(window).cov().values
    K = F.shape[0]
    return np.linalg.cholesky(F + 1e-12 * np.eye(K))


def total_vol(B: np.ndarray, F_chol: np.ndarray, ivol: np.ndarray) -> np.ndarray:
    """Vol total diaria por nome: sqrt(diag(B F B') + ivol^2). Usada no custo."""
    sys_var = np.sum((B @ F_chol) ** 2, axis=1)
    return np.sqrt(np.maximum(sys_var, 0.0) + ivol**2)
