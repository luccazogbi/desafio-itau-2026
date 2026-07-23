"""StatArb L/S no S&P 500 as-of - Desafio Quant AI 2026.

Pipeline: dados -> universo -> fatores -> sinal -> otimizador -> custos -> backtest.

Nota de nomenclatura: o universo migrou do Russell 2000 para o S&P 500 em 12/07
(ver considerações/). Restaram dois nomes legados no schema canonico, mantidos
para nao quebrar os parquets ja gravados:
    MarketData.iwm_ret  e  etf_iwm.parquet  contem o **SPY**, nao o IWM.
"""

__version__ = "0.1.0"
