"""Modelo de custo de execucao no estilo Almgren-Chriss.

Custo por nome, como fracao do book bruto G, para um trade dw (fracao de G):

  custo(dw) = spread * |dw|                                (spread/taxas)
            + eta   * sigma * sqrt(G/ADV) * |dw|^(3/2)     (impacto TEMPORARIO, sqrt-law)
            + 0.5 * gamma * sigma * (G/ADV) * dw^2         (impacto PERMANENTE, linear)

Derivacao do termo temporario: impacto por unidade ~ eta*sigma*sqrt(Q/ADV)
com Q = |dw|*G; custo total = impacto * Q => eta*sigma*sqrt(G/ADV)*|dw|^1.5.

Todos os termos sao CONVEXOS em dw => o mesmo modelo entra (i) como
penalidade dentro do otimizador cvxpy e (ii) como debito realizado no
backtest. Essa consistencia otimizador<->simulacao e deliberada: o
portfolio ja nasce ciente do proprio footprint.
"""

from __future__ import annotations

import numpy as np


class ACCostModel:
    def __init__(self, cfg: dict):
        c = cfg["costs"]
        self.spread = float(c["spread_bps"]) * 1e-4
        self.eta = float(c["ac_eta"])
        self.gamma = float(c["ac_gamma"])
        self.G = float(cfg["book"]["gross_usd"])

    # ---------------------------------------------------------- coeficientes
    def _coeffs(self, sigma: np.ndarray, adv: np.ndarray):
        adv = np.maximum(np.nan_to_num(adv, nan=1e5), 1e5)
        sigma = np.clip(np.nan_to_num(sigma, nan=0.02), 1e-4, 0.20)
        k_temp = self.eta * sigma * np.sqrt(self.G / adv)
        k_perm = 0.5 * self.gamma * sigma * (self.G / adv)
        return k_temp, k_perm

    # ------------------------------------------------------------- realizado
    def realized_cost_usd(self, dw: np.ndarray, sigma: np.ndarray, adv: np.ndarray) -> dict:
        """Custo em USD de um vetor de trades dw (fracoes do gross)."""
        dw = np.nan_to_num(dw)
        k_temp, k_perm = self._coeffs(sigma, adv)
        spread = self.spread * np.abs(dw)
        impact = k_temp * np.abs(dw) ** 1.5 + k_perm * dw**2
        return {
            "spread_usd": float(spread.sum() * self.G),
            "impact_usd": float(impact.sum() * self.G),
            "total_usd": float((spread + impact).sum() * self.G),
        }

    # ----------------------------------------------------------- p/ o cvxpy
    def cvxpy_cost(self, dw, sigma: np.ndarray, adv: np.ndarray):
        """Expressao cvxpy convexa do custo total (fracao do gross)."""
        import cvxpy as cp

        k_temp, k_perm = self._coeffs(sigma, adv)
        return (
            self.spread * cp.norm1(dw)
            + cp.sum(cp.multiply(k_temp, cp.power(cp.abs(dw), 1.5)))
            + cp.sum(cp.multiply(k_perm, cp.square(dw)))
        )
