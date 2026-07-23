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
    sectors: np.ndarray | None = None,  # (n,) rotulos de setor (str); None = sem restricao
    horizon_days: int = 1,              # dias de manutencao -- ver nota de unidades
) -> np.ndarray | None:
    import cvxpy as cp

    limites = cfg["risk"]              # bloco 'risk' do config: todos os limites do mandato
    n_acoes = len(alpha)
    if n_acoes < 10:
        return None

    book_usd = float(cfg["book"]["gross_usd"])                     # $1 bi
    adv_seguro = np.maximum(np.nan_to_num(adv, nan=0.0), 1e5)      # evita divisao por ~0

    # --- Limites por acao (em fracao do book) ---
    # cap_posicao: nao concentrar demais NEM passar da liquidez do nome
    cap_posicao = np.minimum(float(limites["max_weight"]),
                             float(limites["liquidity_cap_adv_mult"]) * adv_seguro / book_usd)
    # cap_trade: nao negociar mais que X% do volume diario daquela acao
    cap_trade = float(limites["participation_cap"]) * adv_seguro / book_usd

    # --- Tolerancias adaptativas: garantem que exista solucao mesmo se a carteira
    # atual (w_prev) tiver degradado. LIMITADAS por um teto: sem ele, uma solucao
    # ruim relaxaria as tolerancias do dia seguinte e o erro cresceria em cascata
    # (bug real pego na validacao com E/P: o gross chegou a 6,9x o orcamento).
    net_atual = abs(float(w_prev.sum()))
    alcance_de_ajuste = float(cap_trade.sum())        # quanto da p/ corrigir em 1 dia
    tol_net = min(max(float(limites["net_tolerance"]),
                      net_atual - 0.8 * alcance_de_ajuste), 0.05)

    exposicao_atual = np.abs(B.T @ w_prev)
    tol_fator = np.minimum(
        np.maximum(float(limites["factor_exposure_bound"]), 0.5 * exposicao_atual), 0.10)

    # --- Variavel de decisao e funcao objetivo ---
    pesos = cp.Variable(n_acoes)          # o que queremos descobrir
    trades = pesos - w_prev               # quanto e preciso negociar para chegar la

    # risco = variancia do book na forma fatorada (B F B' + D), nunca a matriz N x N
    risco_diario = (cp.sum_squares(F_chol.T @ (B.T @ pesos))    # parte dos fatores
                    + cp.sum_squares(cp.multiply(ivol, pesos)))  # parte idiossincratica

    # COERENCIA DE UNIDADES: `alpha` chega ja amortizado pelo horizonte de
    # manutencao (alpha_diario x horizon_days), porque o custo de entrada e pago
    # UMA vez e compete com o alfa acumulado ate a posicao ser desmontada.
    # O risco tem de viver no MESMO horizonte -- senao o objetivo compara
    # 21 dias de retorno contra 1 dia de variancia e subpenaliza risco em 21x.
    # Sob incrementos iid, Var(H dias) ~ H x Var(1 dia).
    risco = float(max(1, horizon_days)) * risco_diario
    custo = cost_model.cvxpy_cost(trades, sigma_total, adv_seguro)

    objetivo = cp.Maximize(
        OBJ_SCALE * (alpha @ pesos - float(limites["risk_aversion"]) * risco - custo))

    restricoes = [
        cp.abs(cp.sum(pesos)) <= tol_net,        # dollar-neutral: soma dos pesos ~ 0
        cp.norm1(pesos) <= 1.0,                  # orcamento bruto: soma |pesos| <= book
        cp.abs(B.T @ pesos) <= tol_fator,        # neutro a cada fator FF5+MOM
        cp.abs(pesos) <= cap_posicao,            # concentracao + liquidez por acao
        cp.abs(trades) <= cap_trade,             # participacao maxima no volume do dia
    ]

    # --- NEUTRALIDADE SETORIAL: o residuo FF5+MOM nao remove comovimento de
    # industria; sem este limite o book poderia virar aposta setorial disfarcada.
    matriz_setores = tol_setor = None
    if sectors is not None:
        # matriz_setores: (n_acoes x n_setores), 1 na coluna do setor da acao.
        # Assim, matriz_setores.T @ pesos = soma dos pesos DENTRO de cada setor.
        _, indice_setor = np.unique(np.asarray(sectors), return_inverse=True)
        matriz_setores = np.zeros((n_acoes, indice_setor.max() + 1))
        matriz_setores[np.arange(n_acoes), indice_setor] = 1.0

        limite_setor = float(limites.get("sector_net_bound", 0.05))
        exposicao_setorial_atual = np.abs(matriz_setores.T @ w_prev)
        tol_setor = np.minimum(
            np.maximum(limite_setor, 0.5 * exposicao_setorial_atual), 0.15)
        restricoes.append(cp.abs(matriz_setores.T @ pesos) <= tol_setor)

    prob = cp.Problem(objetivo, restricoes)
    # Tenta os solvers em cascata: o primeiro que devolver solucao VIAVEL ganha
    for nome_solver in SOLVERS:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # avisos de solucao imprecisa
                prob.solve(solver=getattr(cp, nome_solver))
        except (cp.SolverError, Exception):
            continue

        if prob.status in ("optimal", "optimal_inaccurate") and pesos.value is not None:
            pesos_resultado = np.asarray(pesos.value).ravel()
            pesos_resultado[np.abs(pesos_resultado) < 1e-6] = 0.0   # limpa poeira numerica

            # PORTAO DE VIABILIDADE: o status 'inaccurate' pode devolver solucao que
            # viola as restricoes de verdade. Nunca deixar isso entrar no book.
            if _respeita_mandato(pesos_resultado, w_prev, B, tol_fator, cap_posicao,
                                 cap_trade, tol_net, matriz_setores, tol_setor):
                return pesos_resultado

    return None  # nenhum solver deu solucao viavel -> o motor mantem a carteira atual


def _respeita_mandato(
    pesos: np.ndarray, pesos_anteriores: np.ndarray, betas: np.ndarray,
    tol_fator: np.ndarray | float, cap_posicao: np.ndarray, cap_trade: np.ndarray,
    tol_net: float, matriz_setores: np.ndarray | None = None,
    tol_setor: np.ndarray | None = None, folga: float = 5e-3,
) -> bool:
    """Confere TODAS as restricoes do mandato, com pequena folga numerica."""
    if not np.all(np.isfinite(pesos)):
        return False
    if matriz_setores is not None and not np.all(
            np.abs(matriz_setores.T @ pesos) <= tol_setor + folga):
        return False

    dollar_neutral = abs(pesos.sum()) <= tol_net + folga
    dentro_do_book = np.abs(pesos).sum() <= 1.0 + folga
    neutro_a_fatores = np.all(np.abs(betas.T @ pesos) <= np.asarray(tol_fator) + folga)
    respeita_concentracao = np.all(np.abs(pesos) <= cap_posicao + folga)
    respeita_participacao = np.all(np.abs(pesos - pesos_anteriores) <= cap_trade + folga)

    return bool(dollar_neutral and dentro_do_book and neutro_a_fatores
                and respeita_concentracao and respeita_participacao)


def to_series(pesos: np.ndarray, nomes_acoes: list[str]) -> pd.Series:
    """Converte o vetor de pesos em Series (acao -> peso), sem as posicoes zeradas."""
    serie_pesos = pd.Series(pesos, index=nomes_acoes)
    return serie_pesos[serie_pesos != 0.0]
