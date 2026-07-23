"""Estilo unico de plotagem do projeto.

Segue as convencoes do notebook de referencia
(Aprendizado/Pesquisa de Alfa/alpha_signal_research_tutorial.ipynb):
    plt.rcParams["figure.figsize"] = (12, 5)
    plt.rcParams["axes.grid"] = True
mais alguns refinamentos discretos (grid suave, sem spines superiores).
Todo modulo/notebook que plota deve chamar apply_style() uma vez no inicio.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

# paleta consistente entre figuras (estrategia, benchmark, custos, pernas)
PALETTE = {
    "strategy": "#1f77b4",   # azul  - estrategia (net)
    "gross": "#8ab4d8",      # azul claro - bruto
    "benchmark": "#7f7f7f",  # cinza - benchmark/cash
    "iwm": "#2ca02c",        # verde - IWM
    "cost": "#ff7f0e",       # laranja - custos
    "drawdown": "#b22222",   # vermelho - drawdown
    "long": "#2ca02c",
    "short": "#d62728",
}


def apply_style() -> None:
    """Aplica os rcParams do notebook de referencia a sessao atual."""
    plt.rcParams.update({
        "figure.figsize": (12, 5),
        "axes.grid": True,
        "grid.alpha": 0.30,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titleweight": "bold",
        "legend.frameon": False,
        "figure.dpi": 100,
    })
