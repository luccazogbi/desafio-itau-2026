"""Construcao de portfolio por otimizacao convexa (cvxpy).

Problema resolvido a cada rebalanceamento (w em fracoes do book bruto G):

  max_w   alpha'w  -  lambda * (||F_chol' B'w||^2 + ||ivol .* w||^2)  -  custo_AC(w - w_prev)

  s.a.    |1'w|      <= net_tol          (dollar-neutral: ~$500mm por perna)
          ||w||_1    <= 1                (orcamento bruto: $1 bi)
          |B'w|      <= eps  (por fator) (neutralidade FF5+MOM => alfa idiossincratico)
          |w_i|      <= min(w_max, liq_mult * ADV_i / G)   (concentracao + liquidez)
          |w_i-wp_i| <= part_cap * ADV_i / G               (participacao diaria no volume)

Tudo convexo => solucao global unica. O custo AC dentro do objetivo faz o
otimizador negociar devagar por conta propria (impacto e a restricao economica
dominante num book de $1bi em small caps).

Robustez: se o universo mudou e w_prev ficou fora das bandas (ex.: nomes
deslistados), as tolerancias de net e de fator relaxam ate o alcancavel
dentro do limite de participacao -- o problema permanece sempre factivel.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

SOLVERS = ["CLARABEL", "ECOS", "SCS"]

# reescala o objetivo: alfa/risco/custo vivem em ~1e-4..1e-3 enquanto as
# restricoes vivem em ~1.0; sem isso o solver opera perto da tolerancia
# numerica e degrada para 'optimal_inaccurate'
OBJ_SCALE = 1e3


def optimize_weights(
    alpha: np.ndarray,       # (n,) retorno esperado diario (decimal)
    B: np.ndarray,           # (n, K) betas
    F_chol: np.ndarray,      # (K, K) cholesky da cov dos fatores
    ivol: np.ndarray,        # (n,) vol idio diaria
    sigma_total: np.ndarray, # (n,) vol total diaria (p/ custo)
    adv: np.ndarray,         # (n,) ADV em USD
    w_prev: np.ndarray,      # (n,) pesos atuais (fracao do gross)
    cost_model,
    cfg: dict,
) -> np.ndarray | None:
    import cvxpy as cp

    r = cfg["risk"]
    n = len(alpha)
    if n < 10:
        return None

    G = float(cfg["book"]["gross_usd"])
    adv_safe = np.maximum(np.nan_to_num(adv, nan=0.0), 1e5)

    w_cap = np.minimum(float(r["max_weight"]), float(r["liquidity_cap_adv_mult"]) * adv_safe / G)
    t_cap = float(r["participation_cap"]) * adv_safe / G

    # tolerancias adaptativas: garantem factibilidade mesmo se w_prev degradou.
    # LIMITADAS (min): sem o teto, uma solucao ruim que escapasse relaxaria as
    # tolerancias do dia seguinte e o erro cresceria em cascata (bug pego na
    # validacao com E/P: gross chegou a 6.9x o orcamento).
    net_prev = abs(float(w_prev.sum()))
    reach = float(t_cap.sum())
    net_tol = min(max(float(r["net_tolerance"]), net_prev - 0.8 * reach), 0.05)

    expo_prev = np.abs(B.T @ w_prev)
    eps = np.minimum(
        np.maximum(float(r["factor_exposure_bound"]), 0.5 * expo_prev), 0.10
    )

    w = cp.Variable(n)
    dw = w - w_prev

    risk = cp.sum_squares(F_chol.T @ (B.T @ w)) + cp.sum_squares(cp.multiply(ivol, w))
    cost = cost_model.cvxpy_cost(dw, sigma_total, adv_safe)
    objective = cp.Maximize(
        OBJ_SCALE * (alpha @ w - float(r["risk_aversion"]) * risk - cost)
    )

    constraints = [
        cp.abs(cp.sum(w)) <= net_tol,
        cp.norm1(w) <= 1.0,
        cp.abs(B.T @ w) <= eps,
        cp.abs(w) <= np.maximum(w_cap, np.abs(w_prev) * 0.0),  # cap fixo (>=0)
        cp.abs(dw) <= t_cap,
    ]

    prob = cp.Problem(objective, constraints)
    for solver in SOLVERS:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # inaccurate-solution warnings
                prob.solve(solver=getattr(cp, solver))
        except (cp.SolverError, Exception):
            continue
        if prob.status in ("optimal", "optimal_inaccurate") and w.value is not None:
            out = np.asarray(w.value).ravel()
            out[np.abs(out) < 1e-6] = 0.0
            # PORTAO DE VIABILIDADE: status 'inaccurate' pode devolver solucao
            # que viola as restricoes de verdade. Nunca deixar isso entrar no book.
            if _is_feasible(out, w_prev, B, eps, w_cap, t_cap, net_tol):
                return out
    return None  # caller mantem w_prev


def _is_feasible(
    w: np.ndarray, w_prev: np.ndarray, B: np.ndarray, eps: np.ndarray | float,
    w_cap: np.ndarray, t_cap: np.ndarray, net_tol: float, tol: float = 5e-3,
) -> bool:
    """Confere as restricoes do mandato com folga numerica pequena."""
    if not np.all(np.isfinite(w)):
        return False
    checks = (
        abs(w.sum()) <= net_tol + tol
        and np.abs(w).sum() <= 1.0 + tol
        and np.all(np.abs(B.T @ w) <= np.asarray(eps) + tol)
        and np.all(np.abs(w) <= w_cap + tol)
        and np.all(np.abs(w - w_prev) <= t_cap + tol)
    )
    return bool(checks)


def to_series(w: np.ndarray, names: list[str]) -> pd.Series:
    s = pd.Series(w, index=names)
    return s[s != 0.0]
