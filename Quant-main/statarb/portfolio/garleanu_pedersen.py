"""Otimizacao MULTI-PERIODO de Garleanu & Pedersen (JF 2013).

O PROBLEMA COM O OTIMIZADOR DE 1 PERIODO: ele e miope. Compara o alfa de UM dia
contra o custo TOTAL de montar a posicao -- e conclui que nao vale a pena operar.
Nosso paliativo e a heuristica `horizon_days`: inflar o alfa por H=21 dias, como
se a posicao rendesse H dias antes de ser desmontada.

GP resolvem o problema de verdade. Com sinal que reverte e custo quadratico, a
politica otima e:

    x_t = x_{t-1} + D * (aim_t - x_{t-1})

ou seja: **nao va ate a carteira ideal, ande uma fracao D na direcao dela**. E o
alvo nao e a carteira de Markowitz -- e um "aim" que pondera o sinal pela sua
PERSISTENCIA: sinal que morre rapido merece menos posicao, porque nao ha tempo
de amortizar o custo de entrada.

-----------------------------------------------------------------------------
DERIVACAO (caso escalar; feita aqui em vez de citada, para poder ser conferida)

Bellman, com f_{t+1} = (1-phi) f_t + ruido:

    V(x,f) = max_{x'} [ x' b f - (g/2) x'^2 - (L/2)(x'-x)^2 + rho E V(x',f') ]

com g = gamma * sigma^2 (aversao a risco x variancia) e L = lambda (custo
quadratico). Chutando V(x,f) = -(A/2)x^2 + B x f + (...)f^2 + const, a condicao
de primeira ordem da:

    x' = [ L x + (b + rho B (1-phi)) f ] / K       com  K = g + L + rho A

Casando os coeficientes de x^2 e de x f:

    A = L (K - L) / K
    B = L b / (K - L rho (1-phi))

Substituindo A na definicao de K, sobra uma quadratica em K:

    K^2 - (g + L + rho L) K + rho L^2 = 0
    K = [ (g + L + rho L) + sqrt((g + L + rho L)^2 - 4 rho L^2) ] / 2

Dai saem as tres grandezas que interessam:

    taxa de trade      D    = (K - L) / K
    aim / Markowitz         = g K / [ (K - L rho (1-phi)) (K - L) ]
    H implicito             = (g + L) / (K - L rho (1-phi))

O "H implicito" e a ponte com a heuristica: e o valor de `horizon_days` que faz
o otimizador de 1 periodo REAGIR AO SINAL como o GP reage. Ver `comparar_com_heuristica`
para o que ele NAO consegue igualar.

RESSALVA CENTRAL: GP supoem custo QUADRATICO. O nosso Almgren-Chriss tem termo de
potencia 3/2 (lei da raiz). A forma fechada nao se aplica ao nosso custo -- por isso
este modulo serve para DIAGNOSTICAR a heuristica, com o custo aproximado localmente
por uma quadratica, e nao para substituir o otimizador convexo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SolucaoGP:
    """Solucao da politica otima multi-periodo (grandezas por periodo)."""

    K: float                  # denominador da FOC (g + L + rho*A)
    A: float                  # curvatura da funcao valor em x
    B: float                  # termo cruzado x*f da funcao valor
    taxa_de_trade: float      # D: fracao do gap ate o aim fechada por periodo
    aim_sobre_markowitz: float  # encolhimento do alvo vs carteira miope
    horizonte_implicito: float  # H que faz a heuristica reagir como o GP
    inercia_gp: float         # peso na posicao anterior sob GP  (L/K)
    inercia_heuristica: float  # peso na posicao anterior na heuristica (L/(g+L))


def resolver_gp(risco: float, custo: float, persistencia: float,
                desconto: float = 1.0) -> SolucaoGP:
    """Resolve a politica otima de Garleanu-Pedersen.

    Args:
        risco:        g = gamma * sigma^2, a penalidade marginal de risco.
        custo:        L = lambda, coeficiente do custo QUADRATICO de negociar.
        persistencia: phi em (0,1]. O sinal decai como (1-phi)^t.
                      phi -> 0: sinal permanente. phi -> 1: morre em 1 periodo.
        desconto:     rho <= 1. Praticamente 1 em horizonte diario.
    """
    g, L, phi, rho = float(risco), float(custo), float(persistencia), float(desconto)
    if g <= 0 or L < 0 or not (0.0 < phi <= 1.0):
        raise ValueError(f"parametros invalidos: risco={g}, custo={L}, persistencia={phi}")

    if L == 0.0:                       # sem custo: vai direto para Markowitz
        return SolucaoGP(K=g, A=0.0, B=0.0, taxa_de_trade=1.0,
                         aim_sobre_markowitz=1.0, horizonte_implicito=1.0,
                         inercia_gp=0.0, inercia_heuristica=0.0)

    b_quad = g + L + rho * L
    disc = b_quad**2 - 4.0 * rho * L**2
    K = (b_quad + np.sqrt(max(disc, 0.0))) / 2.0

    A = L * (K - L) / K
    denom_aim = K - L * rho * (1.0 - phi)
    B = L / denom_aim                          # por unidade de b (alfa por f)

    return SolucaoGP(
        K=float(K), A=float(A), B=float(B),
        taxa_de_trade=float((K - L) / K),
        aim_sobre_markowitz=float(g * K / (denom_aim * (K - L))),
        horizonte_implicito=float((g + L) / denom_aim),
        inercia_gp=float(L / K),
        inercia_heuristica=float(L / (g + L)),
    )


def politica_gp(x_anterior: float, sinal: float, b: float,
                risco: float, sol: SolucaoGP) -> float:
    """Posicao otima do proximo periodo sob GP: anda uma fracao rumo ao aim.

        markowitz = b*f / g          (carteira miope, sem custo)
        aim       = encolhimento * markowitz
        x'        = x + D * (aim - x)
    """
    markowitz = b * sinal / risco
    aim = sol.aim_sobre_markowitz * markowitz
    return x_anterior + sol.taxa_de_trade * (aim - x_anterior)


def politica_heuristica(x_anterior: float, sinal: float, b: float,
                        risco: float, custo: float, horizonte: float) -> float:
    """Otimizador de 1 periodo com alfa inflado por `horizonte` (o que fazemos hoje).

    max_x'  x' * (b*f*H) - (g/2) x'^2 - (L/2)(x'-x)^2
    """
    return (custo * x_anterior + b * sinal * horizonte) / (risco + custo)


def validar_por_simulacao(risco: float, custo: float, persistencia: float,
                          desconto: float = 1.0, b: float = 1.0,
                          n_passos: int = 200_000, semente: int = 0) -> dict:
    """Confere a otimalidade SIMULANDO: a politica GP deve bater qualquer
    perturbacao da taxa de trade e do encolhimento do aim.

    Esta e a validacao independente da algebra: se a derivacao estiver errada,
    alguma perturbacao rende mais.
    """
    sol = resolver_gp(risco, custo, persistencia, desconto)
    rng = np.random.default_rng(semente)

    # trajetoria do sinal: AR(1) com reversao `persistencia`
    ruido = rng.normal(0.0, 1.0, n_passos)
    f = np.empty(n_passos)
    f[0] = ruido[0]
    for t in range(1, n_passos):
        f[t] = (1.0 - persistencia) * f[t - 1] + ruido[t]

    def objetivo(taxa: float, encolhe: float) -> float:
        x = 0.0
        total = 0.0
        for t in range(n_passos):
            alvo = encolhe * b * f[t] / risco
            x_novo = x + taxa * (alvo - x)
            total += (x_novo * b * f[t] - 0.5 * risco * x_novo**2
                      - 0.5 * custo * (x_novo - x) ** 2)
            x = x_novo
        return total / n_passos

    base = objetivo(sol.taxa_de_trade, sol.aim_sobre_markowitz)
    grade = {
        "taxa -20%": (0.8, 1.0), "taxa +20%": (1.2, 1.0),
        "taxa -50%": (0.5, 1.0), "taxa +50%": (1.5, 1.0),
        "aim -20%": (1.0, 0.8), "aim +20%": (1.0, 1.2),
        # sem encolhimento do aim = mira direto na carteira miope de Markowitz
        "aim = markowitz": (1.0, 1.0 / max(sol.aim_sobre_markowitz, 1e-12)),
        # sem inercia = vai direto ao alvo todo periodo (otimizador sem custo)
        "taxa = 1 (sem inercia)": (1.0 / max(sol.taxa_de_trade, 1e-12), 1.0),
    }
    perturbacoes = {nome: objetivo(sol.taxa_de_trade * dt, sol.aim_sobre_markowitz * da)
                    for nome, (dt, da) in grade.items()}

    return {"solucao": sol, "objetivo_gp": base, "objetivo_perturbado": perturbacoes,
            "gp_e_otimo": all(base >= v - 1e-9 for v in perturbacoes.values())}
