"""Gerador de dados sinteticos no schema canonico do pipeline.

Objetivo: validar a esteira de ponta a ponta ANTES dos dados Bloomberg.
O gerador planta uma reversao de curto prazo no componente idiossincratico
(AR(1) com coeficiente negativo), de modo que o sinal placeholder tem um
alfa real a recuperar -- isso serve de teste de sanidade do pipeline inteiro.

Schema canonico gravado em data/processed/ (tudo parquet, wide, index=date):
    prices_tri.parquet     indice de retorno total por ticker (dividendos inclusos)
    prices_close.parquet   preco de fechamento (para filtros de universo)
    dollar_volume.parquet  volume financeiro diario (USD)
    market_cap.parquet     capitalizacao de mercado (USD)
    membership.parquet     bool mensal: pertence ao indice na data (point-in-time)
    sectors.parquet        ticker -> setor GICS (coluna unica 'sector')
    factors.parquet        retornos diarios dos fatores [mkt smb hml rmw cma mom] + rf
    etf_iwm.parquet        ETF de hedge: colunas ['tri', 'ret']
    earnings.parquet       EPS trailing por acao, em degraus trimestrais (p/ sinal E/P)

Dois alfas plantados, independentes entre si e ortogonais aos fatores:
  1. REVERSAO curta (MA): choque idio reverte `reversal_rho` em `reversal_horizon` dias
     -> capturada pelo sinal idio_reversal.
  2. MISPRICING lento (AR(1)): o preco oscila em torno do valor justo EPS x multiplo
     com meia-vida de meses; E/P alto = barato = drift positivo a frente
     -> capturado pelo sinal earnings_yield.
Ressalva de mundo real (documentar no relatorio): E/P de verdade carrega value/HML
e seria parcialmente neutralizado pelas constraints de fator do otimizador. Aqui ele
e ortogonal por construcao, porque o objetivo e VALIDAR a esteira, nao propor E/P
como sinal final.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import lfilter

GICS = [
    "Energy", "Materials", "Industrials", "Cons. Discretionary", "Cons. Staples",
    "Health Care", "Financials", "Info Tech", "Comm. Services", "Utilities", "Real Estate",
]

# vol anual / retorno anual dos fatores sinteticos (aproximacao dos momentos FF)
FACTOR_MOMENTS = {
    "mkt": (0.07, 0.18),
    "smb": (0.01, 0.10),
    "hml": (0.01, 0.10),
    "rmw": (0.015, 0.08),
    "cma": (0.01, 0.07),
    "mom": (0.04, 0.14),
}


def generate(
    outdir: str | Path,
    n_stocks: int = 300,
    start: str = "2018-01-02",
    end: str = "2024-12-31",
    seed: int = 42,
    reversal_rho: float = 0.35,
    reversal_horizon: int = 8,
    mispricing_phi: float = 0.996,
    mispricing_sigma: float = 0.10,
    fair_multiple_mean: float = 15.0,
    fair_multiple_std: float = 0.75,
) -> None:
    """Gera o painel sintetico completo e grava no schema canonico.

    Reversao plantada como MA: um choque idiossincratico ε reverte
    `reversal_rho` (35%) de si mesmo distribuido pelos `reversal_horizon`
    dias seguintes. Estrutura deliberadamente LENTA: com execucao em t+1,
    um AR(1) de 1 dia nao deixaria alfa capturavel (licao registrada no
    genai_log) -- reversao real de small caps decai ao longo de dias.
    """
    rng = np.random.default_rng(seed)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    dates = pd.bdate_range(start, end)
    T = len(dates)
    tickers = [f"SYN{i:04d}" for i in range(n_stocks)]

    # --- fatores diarios (iid; correlacao entre fatores ignorada por simplicidade)
    fac = {}
    for name, (mu, vol) in FACTOR_MOMENTS.items():
        fac[name] = rng.normal(mu / 252.0, vol / np.sqrt(252.0), T)
    factors = pd.DataFrame(fac, index=dates)
    factors["rf"] = 0.045 / 252.0

    # --- cargas de fator por acao (small caps: beta mkt ~ 1, resto disperso)
    K = len(FACTOR_MOMENTS)
    B = np.column_stack([
        rng.normal(1.00, 0.25, n_stocks),   # mkt
        rng.normal(0.60, 0.35, n_stocks),   # smb (small caps carregam SMB)
        rng.normal(0.00, 0.40, n_stocks),   # hml
        rng.normal(0.00, 0.30, n_stocks),   # rmw
        rng.normal(0.00, 0.30, n_stocks),   # cma
        rng.normal(0.00, 0.30, n_stocks),   # mom
    ])

    # --- idiossincratico MA(H) com cauda negativa ==> REVERSAO PLANTADA
    # idio[t] = eps[t] - (rho/H) * (eps[t-1] + ... + eps[t-H])
    ivol_ann = rng.uniform(0.20, 0.45, n_stocks)
    eps = rng.normal(0.0, 1.0, (T, n_stocks)) * (ivol_ann / np.sqrt(252.0))
    ma = np.r_[1.0, -np.full(reversal_horizon, reversal_rho / reversal_horizon)]
    idio = lfilter(ma, [1.0], eps, axis=0)

    # --- mispricing AR(1) lento ==> ALFA DO E/P PLANTADO
    # m = log(preco/valor justo); reverte a 0 com meia-vida ln(2)/(1-phi) dias.
    # O retorno diario ganha dm (a correcao do desvio); quem compra E/P alto
    # (m negativo) captura o drift de volta ao valor justo.
    burn = 1000
    u = rng.normal(0.0, mispricing_sigma * np.sqrt(1.0 - mispricing_phi**2),
                   (T + burn, n_stocks))
    m = lfilter([1.0], [1.0, -mispricing_phi], u, axis=0)[burn:]
    dm = np.diff(m, axis=0, prepend=m[:1])

    rets = np.clip(factors[list(FACTOR_MOMENTS)].values @ B.T + idio + dm, -0.35, 0.35)
    rets_df = pd.DataFrame(rets, index=dates, columns=tickers)

    tri = 100.0 * (1.0 + rets_df).cumprod()
    px0 = rng.uniform(3.0, 60.0, n_stocks)
    close = (1.0 + rets_df).cumprod() * px0

    # --- abertura sintetica: ~35% do retorno do dia acontece overnight + ruido
    # (p/ testar o sinal overnight; sem alfa overnight plantado)
    on_noise = rng.normal(0.0, 0.3, (T, n_stocks)) * (ivol_ann / np.sqrt(252.0))
    open_px = close.shift(1) * (1.0 + 0.35 * rets_df + on_noise)

    # --- EPS trailing em degraus trimestrais, coerente com o mispricing:
    # no inicio de cada trimestre, EPS = preco_justo / multiplo = close*exp(-m)/mult.
    # Entre trimestres o EPS fica FIXO e so o preco varia -> E/P = EPS/close se move
    # com o preco, exatamente a construcao do notebook de referencia.
    mult = rng.normal(fair_multiple_mean, fair_multiple_std, n_stocks).clip(min=8.0)
    m_df = pd.DataFrame(m, index=dates, columns=tickers)
    q_dates = pd.DatetimeIndex([dates[0]]).union(
        pd.bdate_range(start, end, freq="BQS").intersection(dates)
    )
    eps_daily = pd.DataFrame(np.nan, index=dates, columns=tickers)
    eps_daily.loc[q_dates] = (
        close.loc[q_dates].values * np.exp(-m_df.loc[q_dates].values) / mult[None, :]
    )
    eps_daily = eps_daily.ffill()

    # --- volume financeiro: base lognormal persistente + ruido diario
    base_adv = np.clip(np.exp(rng.normal(np.log(8e6), 1.0, n_stocks)), 7e5, 3e8)
    dvol = pd.DataFrame(
        base_adv[None, :] * np.exp(rng.normal(0.0, 0.30, (T, n_stocks))),
        index=dates, columns=tickers,
    )

    # --- market cap coerente com small caps ($150mm a $3bi no inicio)
    cap0 = rng.uniform(1.5e8, 3.0e9, n_stocks)
    mcap = close / close.iloc[0] * cap0

    # --- membership mensal point-in-time com churn e DESLISTAMENTOS
    snap = pd.bdate_range(start, end, freq="BMS")
    member = pd.DataFrame(True, index=snap, columns=tickers)

    n_delist = int(0.12 * n_stocks)          # ~12% morrem no meio da amostra
    n_late = int(0.10 * n_stocks)            # ~10% entram no indice depois
    delisted = rng.choice(n_stocks, n_delist, replace=False)
    late_pool = np.setdiff1d(np.arange(n_stocks), delisted)
    late = rng.choice(late_pool, n_late, replace=False)

    for j in delisted:
        cut = int(rng.uniform(0.35, 0.90) * len(snap))
        member.iloc[cut:, j] = False
        dcut = snap[cut]
        # apos o deslistamento a acao simplesmente deixa de existir no painel
        tri.loc[tri.index > dcut, tickers[j]] = np.nan
        close.loc[close.index > dcut, tickers[j]] = np.nan
        dvol.loc[dvol.index > dcut, tickers[j]] = np.nan
        mcap.loc[mcap.index > dcut, tickers[j]] = np.nan
    for j in late:
        entry = int(rng.uniform(0.10, 0.50) * len(snap))
        member.iloc[:entry, j] = False

    sectors = pd.DataFrame(
        {"sector": rng.choice(GICS, n_stocks)}, index=pd.Index(tickers, name="ticker")
    )

    # --- ETF de hedge (IWM sintetico ~ fator de mercado + ruido pequeno)
    iwm_ret = pd.Series(factors["mkt"].values + rng.normal(0, 5e-4, T), index=dates)
    iwm = pd.DataFrame({"tri": 100.0 * (1.0 + iwm_ret).cumprod(), "ret": iwm_ret})

    # EPS e abertura deixam de existir junto com o preco (deslistamentos)
    eps_daily = eps_daily.where(close.notna())
    open_px = open_px.where(close.notna())

    # --- grava schema canonico
    for name, df in {
        "prices_tri": tri, "prices_close": close, "dollar_volume": dvol,
        "market_cap": mcap, "membership": member, "factors": factors, "etf_iwm": iwm,
        "earnings": eps_daily, "prices_open": open_px,
    }.items():
        df.rename_axis("date").to_parquet(outdir / f"{name}.parquet")
    sectors.to_parquet(outdir / "sectors.parquet")

    half_life = int(np.log(2) / (1.0 - mispricing_phi))
    print(f"[synthetic] {n_stocks} acoes x {T} dias | delistadas={n_delist} "
          f"| entradas tardias={n_late} | reversao MA rho={reversal_rho} "
          f"H={reversal_horizon}d | mispricing sigma={mispricing_sigma} "
          f"meia-vida~{half_life}d -> {outdir}")
