"""Testes de sanidade do pipeline (rapidos, painel sintetico pequeno)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config
from statarb.costs.almgren_chriss import ACCostModel
from statarb.data.loaders import MarketData
from statarb.data.synthetic import generate
from statarb.factors.betas import FactorModel
from statarb.portfolio.optimizer import optimize_weights
from statarb.risk.covariance import factor_cov_chol, total_vol
from statarb.signals import build_signal


# --------------------------------------------------------------- fixtures
@pytest.fixture(scope="session")
def cfg(tmp_path_factory):
    cfg = load_config()
    cfg["data"]["start"], cfg["data"]["end"] = "2021-01-04", "2022-12-30"
    cfg["backtest"]["start"], cfg["backtest"]["end"] = "2021-10-01", "2022-12-30"
    cfg["factors"]["beta_window"] = 126
    cfg["factors"]["beta_min_obs"] = 80
    cfg["universe"]["min_history_days"] = 130
    cfg["risk"]["cov_window"] = 126
    return cfg


@pytest.fixture(scope="session")
def md(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("panel")
    # mispricing mais forte que o default p/ o teste de IC do E/P ser estavel
    generate(d, n_stocks=80, start=cfg["data"]["start"], end=cfg["data"]["end"],
             seed=7, mispricing_phi=0.994, mispricing_sigma=0.15)
    return MarketData.from_dir(d, cfg)


@pytest.fixture(scope="session")
def fm(cfg, md):
    return FactorModel(cfg).fit(md.returns, md.factors)


def _opt_inputs(cfg, md, fm, date):
    B_df = fm.betas_asof(date)
    ivol_s = fm.idio_asof(date)
    names = sorted(set(B_df.index) & set(ivol_s.index))[:60]
    rng = np.random.default_rng(0)
    alpha = rng.normal(0, 8e-4, len(names))
    B = B_df.reindex(names).values
    ivol = ivol_s.reindex(names).values
    F_chol = factor_cov_chol(md.factors, date, cfg["risk"]["cov_window"])
    sigma = total_vol(B, F_chol, ivol)
    adv = md.adv.loc[date].reindex(names).fillna(5e6).values
    return names, alpha, B, F_chol, ivol, sigma, adv


# ------------------------------------------------------------------ testes
def test_optimizer_neutrality_and_caps(cfg, md, fm):
    date = md.returns.index[-5]
    names, alpha, B, F_chol, ivol, sigma, adv = _opt_inputs(cfg, md, fm, date)
    w = optimize_weights(alpha, B, F_chol, ivol, sigma, adv,
                         np.zeros(len(names)), ACCostModel(cfg), cfg)
    assert w is not None, "otimizador nao encontrou solucao"
    r = cfg["risk"]
    assert abs(w.sum()) <= r["net_tolerance"] + 1e-6          # dollar-neutral
    assert np.abs(w).sum() <= 1.0 + 1e-6                      # orcamento bruto
    expo = np.abs(B.T @ w)
    assert (expo <= r["factor_exposure_bound"] + 1e-6).all()  # neutralidade de fatores
    G = float(cfg["book"]["gross_usd"])
    t_cap = r["participation_cap"] * np.maximum(adv, 1e5) / G
    assert (np.abs(w) <= t_cap + 1e-8).all()                  # participacao (w_prev=0)


def test_cost_model_convex_and_monotone(cfg):
    ac = ACCostModel(cfg)
    sigma = np.full(4, 0.02)
    adv = np.full(4, 1e7)
    small = ac.realized_cost_usd(np.full(4, 1e-3), sigma, adv)["total_usd"]
    big = ac.realized_cost_usd(np.full(4, 4e-3), sigma, adv)["total_usd"]
    assert 0 < small < big
    assert big > 4 * small  # superlinear (impacto convexo)


@pytest.fixture(scope="session")
def trunc(cfg, md):
    """Painel truncado em idx[-40] + FactorModel refitado (compartilhado)."""
    date = md.returns.index[-40]
    md_trunc = MarketData(
        tri=md.tri.loc[:date], close=md.close.loc[:date],
        returns=md.returns.loc[:date], dollar_volume=md.dollar_volume.loc[:date],
        adv=md.adv.loc[:date], market_cap=md.market_cap.loc[:date],
        membership_daily=md.membership_daily.loc[:date], sectors=md.sectors,
        factors=md.factors.loc[:date], rf=md.rf.loc[:date],
        iwm_ret=md.iwm_ret.loc[:date],
        earnings=None if md.earnings is None else md.earnings.loc[:date],
    )
    fm_trunc = FactorModel(cfg).fit(md_trunc.returns, md_trunc.factors)
    return md_trunc, fm_trunc, date


@pytest.mark.parametrize("signal_name", [
    "idio_reversal", "earnings_yield", "mad", "str_turnover", "left_tail", "resid_ou",
])
def test_signal_no_lookahead(cfg, md, fm, trunc, signal_name):
    """Scores na data t nao mudam se o futuro for removido do painel."""
    from statarb.signals import _REGISTRY

    md_trunc, fm_trunc, date = trunc
    univ = list(md.returns.columns[:70])

    z_full = _REGISTRY[signal_name](cfg).compute(md, fm, date, univ)
    z_trunc = _REGISTRY[signal_name](cfg).compute(md_trunc, fm_trunc, date, univ)

    common = z_full.index.intersection(z_trunc.index)
    assert len(common) > 15, f"{signal_name}: cobertura insuficiente ({len(common)})"
    # betas re-estimados em painel truncado podem diferir em datas de borda;
    # o contrato exige correlacao ~1 entre os scores
    corr = np.corrcoef(z_full[common], z_trunc[common])[0, 1]
    assert corr > 0.999, f"possivel lookahead em {signal_name}: corr={corr:.4f}"


def test_blend_combines_components(cfg, md, fm):
    """O combinador agrega z-scores e devolve um alfa normalizado."""
    from statarb.signals import build_signal

    blend = build_signal(cfg, "blend")
    date = md.returns.index[-40]
    univ = list(md.returns.columns)
    z = blend.compute(md, fm, date, univ)
    assert len(z) > 30
    assert np.isfinite(z).all()
    assert z.abs().max() <= float(cfg["signal"]["zscore_cap"]) + 1e-9


def test_earnings_yield_ic_positive(cfg, md, fm):
    """O E/P recupera o mispricing plantado: IC medio (fwd 21d) > 0 com folga."""
    from scipy.stats import spearmanr

    from statarb.signals.earnings_yield import EarningsYield

    sig = EarningsYield(cfg)
    idx = md.returns.index
    H = 21
    ics = []
    for p in range(len(idx) - 300, len(idx) - H - 2, 10):
        d = idx[p]
        univ = list(md.returns.columns[md.returns.loc[d].notna()])
        z = sig.compute(md, fm, d, univ)
        if len(z) < 30:
            continue
        fwd = (1.0 + md.returns.iloc[p + 2 : p + 2 + H]).prod() - 1.0
        common = z.index.intersection(fwd.dropna().index)
        if len(common) >= 30:
            ics.append(spearmanr(z[common], fwd[common])[0])
    assert len(ics) >= 15
    ic = float(np.mean(ics))
    assert ic > 0.03, f"IC medio do E/P fraco demais: {ic:.4f}"


def test_engine_smoke(cfg, md, fm):
    from statarb.backtest.engine import BacktestEngine

    sig = build_signal(cfg)
    out = BacktestEngine(cfg).run(md, fm, sig)
    res = out["results"]
    assert len(res) > 100
    assert np.isfinite(res["pnl_net_usd"]).all()
    assert (res["gross"] <= 1.0 + 1e-6).all()
    assert res["cost_usd"].sum() > 0
    assert res["n_positions"].max() > 20
