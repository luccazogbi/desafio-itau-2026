"""Registro de sinais: para trocar o sinal, basta registrar aqui e apontar no config.

Biblioteca (shortlist do doc de sinais do colega -- todos so preco/volume,
sem dependencia de Bloomberg):
    idio_reversal   reversao idiossincratica curta (placeholder original)
    earnings_yield  E/P -- sinal de VALIDACAO da esteira (descartavel)
    trend_factor    Han-Zhou-Zhu 2016: MAs multi-horizonte com pesos aprendidos
    mad             Avramov 2021: MA(21)/MA(200) -- variante do modulo de tendencia
    str_turnover    Medhat-Schmeling 2022: reversao so no quantil de baixo turnover
    stm             Medhat-Schmeling 2022: MOMENTUM 1m so no quantil de ALTO turnover
    resid_ou        Avellaneda-Lee: desvio acumulado do residuo, z temporal (SINAL OFICIAL)
    left_tail       Atilgan 2020: momentum de cauda esquerda (VaR 1%)
    seasonality     Keloharju 2016/21: same-month menos outros meses
    overnight       Lou-Polk-Skouras 2019: persistencia do retorno overnight (close->open)
    salience        Cosemans-Frehen 2021: dias salientes vs mercado
    blend           combinador -- alfa unico a partir dos componentes do config
"""

from .base import PanelSignal, Signal
from .blend import BlendSignal
from .earnings_yield import EarningsYield
from .left_tail import LeftTail
from .overnight import Overnight
from .resid_ou import ResidOU
from .reversal import IdioReversal
from .salience import Salience
from .seasonality import Seasonality
from .str_turnover import STM, STRTurnover
from .trend_factor import MAD, TrendFactor

_REGISTRY = {
    cls.name: cls
    for cls in (
        IdioReversal, EarningsYield, TrendFactor, MAD, STRTurnover, STM,
        ResidOU, LeftTail, Seasonality, Overnight, Salience, BlendSignal,
    )
}


def build_signal(cfg: dict, name: str | None = None) -> Signal:
    name = name or cfg["signal"]["name"]
    if name not in _REGISTRY:
        raise KeyError(
            f"Sinal '{name}' nao registrado. Disponiveis: {list(_REGISTRY)}. "
            "Implemente uma subclasse de Signal e registre em statarb/signals/__init__.py"
        )
    return _REGISTRY[name](cfg)
