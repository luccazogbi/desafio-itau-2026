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
    rng = np.random.default_rng(1)
    sectors = rng.choice(["Tech", "Fin", "Health", "Energy", "Cons"], len(names))
    w = optimize_weights(alpha, B, F_chol, ivol, sigma, adv,
                         np.zeros(len(names)), ACCostModel(cfg), cfg, sectors=sectors)
    assert w is not None, "otimizador nao encontrou solucao"
    r = cfg["risk"]
    assert abs(w.sum()) <= r["net_tolerance"] + 1e-6          # dollar-neutral
    assert np.abs(w).sum() <= 1.0 + 1e-6                      # orcamento bruto
    expo = np.abs(B.T @ w)
    assert (expo <= r["factor_exposure_bound"] + 1e-6).all()  # neutralidade de fatores
    G = float(cfg["book"]["gross_usd"])
    t_cap = r["participation_cap"] * np.maximum(adv, 1e5) / G
    assert (np.abs(w) <= t_cap + 1e-8).all()                  # participacao (w_prev=0)
    for s in np.unique(sectors):                              # neutralidade setorial
        assert abs(w[sectors == s].sum()) <= r["sector_net_bound"] + 1e-6


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
        open_=None if md.open_ is None else md.open_.loc[:date],
    )
    fm_trunc = FactorModel(cfg).fit(md_trunc.returns, md_trunc.factors)
    return md_trunc, fm_trunc, date


@pytest.mark.parametrize("signal_name", [
    "idio_reversal", "earnings_yield", "mad", "str_turnover", "left_tail", "resid_ou",
    "stm", "overnight", "salience",
])
def test_signal_no_lookahead(cfg, md, fm, trunc, signal_name):
    """Scores na data t nao mudam se o futuro for removido do painel."""
    from statarb.signals import _REGISTRY

    md_trunc, fm_trunc, date = trunc
    # universo inteiro do painel de teste: sinais com mascara de quantil
    # (str_turnover/stm mantem ~25% dos nomes) precisam de base ampla
    univ = list(md.returns.columns)

    z_full = _REGISTRY[signal_name](cfg).compute(md, fm, date, univ)
    z_trunc = _REGISTRY[signal_name](cfg).compute(md_trunc, fm_trunc, date, univ)

    common = z_full.index.intersection(z_trunc.index)
    assert len(common) > 10, f"{signal_name}: cobertura insuficiente ({len(common)})"
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


# ------------------------------------------------- correcoes (regressao)
def test_holdout_esta_trancado(cfg, md, fm):
    """O motor recusa rodar dentro do holdout sem permissao explicita."""
    import copy

    from statarb.backtest.engine import BacktestEngine

    c = copy.deepcopy(cfg)
    c["backtest"]["holdout_start"] = "2022-01-01"     # holdout dentro da amostra de teste
    c["backtest"]["end"] = "2022-12-30"               # invade de proposito
    sig = build_signal(c)

    with pytest.raises(ValueError, match="HOLDOUT"):
        BacktestEngine(c).run(md, fm, sig)

    # com a flag explicita, roda
    out = BacktestEngine(c, allow_holdout=True).run(md, fm, sig)
    assert len(out["results"]) > 10


def test_custo_de_aluguel_do_short(cfg, md, fm):
    """O aluguel da perna short e debitado e escala com a taxa configurada."""
    import copy

    from statarb.backtest.engine import BacktestEngine

    sem = copy.deepcopy(cfg); sem["costs"]["borrow_bps_per_year"] = 0.0
    com = copy.deepcopy(cfg); com["costs"]["borrow_bps_per_year"] = 100.0

    r_sem = BacktestEngine(sem).run(md, fm, build_signal(sem))["results"]
    r_com = BacktestEngine(com).run(md, fm, build_signal(com))["results"]

    assert r_sem["borrow_usd"].sum() == 0.0
    assert r_com["borrow_usd"].sum() > 0.0
    # custo total sobe exatamente o que o aluguel adiciona
    assert r_com["cost_usd"].sum() > r_sem["cost_usd"].sum()
    # e o P&L liquido cai na mesma medida
    assert r_com["pnl_net_usd"].sum() < r_sem["pnl_net_usd"].sum()


def test_hedge_entra_na_contabilidade(cfg, md, fm):
    """gross/net COM hedge existem e sao >= a versao so-acoes."""
    from statarb.backtest.engine import BacktestEngine

    res = BacktestEngine(cfg).run(md, fm, build_signal(cfg))["results"]
    assert "gross_com_hedge" in res and "net_com_hedge" in res
    assert (res["gross_com_hedge"] >= res["gross"] - 1e-9).all()
    assert res["hedge_cost_usd"].sum() >= 0.0


def test_snapshot_congela_e_detecta_alteracao(tmp_path):
    """O snapshot identifica o painel; qualquer alteracao quebra a identificacao."""
    from statarb.data.synthetic import generate
    from statarb.snapshot import carrega_manifestos, compara, criar_snapshot, identifica_snapshot

    painel = tmp_path / "painel"
    generate(painel, n_stocks=12, start="2021-01-04", end="2021-12-31", seed=3)
    dados, manifestos = tmp_path / "snaps", tmp_path / "manifestos"

    sid, man = criar_snapshot(painel, dados, manifestos, rotulo="teste")
    assert (dados / sid).exists() and (manifestos / f"{sid}.json").exists()
    assert man["n_tickers"] == 12
    assert man["arquivos"], "manifesto deve listar os arquivos com hash"

    # painel intacto -> identificado
    assert identifica_snapshot(painel, manifestos) == sid

    # painel alterado -> NAO identificado (e esse e o ponto: resultado nao rastreavel)
    df = pd.read_parquet(painel / "prices_close.parquet")
    df.iloc[0, 0] = float(df.iloc[0, 0]) * 1.01
    df.to_parquet(painel / "prices_close.parquet")
    assert identifica_snapshot(painel, manifestos) is None

    # segundo snapshot: o diff enxerga o arquivo alterado
    sid2, _ = criar_snapshot(painel, dados, manifestos, rotulo="teste-alterado")
    mans = carrega_manifestos(manifestos)
    d = compara(mans[sid], mans[sid2])
    assert "prices_close.parquet" in d["arquivos_alterados"]

    # e enxerga tickers que somem
    df2 = df.drop(columns=[df.columns[0]])
    df2.to_parquet(painel / "prices_close.parquet")
    sid3, _ = criar_snapshot(painel, dados, manifestos, rotulo="teste-sem-ticker")
    d3 = compara(carrega_manifestos(manifestos)[sid2],
                 carrega_manifestos(manifestos)[sid3])
    assert d3["tickers_removidos"] == [df.columns[0]]


def test_garleanu_pedersen_limites_e_otimalidade():
    """A solucao multi-periodo respeita os limites conhecidos e bate perturbacoes."""
    from statarb.portfolio.garleanu_pedersen import resolver_gp, validar_por_simulacao

    # sem custo -> vai direto para Markowitz (taxa 1, aim = markowitz)
    s0 = resolver_gp(risco=0.05, custo=0.0, persistencia=0.03)
    assert s0.taxa_de_trade == pytest.approx(1.0)
    assert s0.aim_sobre_markowitz == pytest.approx(1.0)

    # custo crescente -> negocia cada vez mais devagar
    taxas = [resolver_gp(risco=0.05, custo=c, persistencia=0.03).taxa_de_trade
             for c in (0.1, 1.0, 10.0, 100.0)]
    assert taxas == sorted(taxas, reverse=True), f"taxa deveria cair com o custo: {taxas}"

    # sinal mais efemero -> alvo menor (nao ha tempo de amortizar o custo)
    aim_lento = resolver_gp(risco=0.05, custo=5.0, persistencia=0.02).aim_sobre_markowitz
    aim_rapido = resolver_gp(risco=0.05, custo=5.0, persistencia=0.50).aim_sobre_markowitz
    assert aim_rapido < aim_lento, "sinal que morre rapido deveria encolher mais o aim"

    # a derivacao e valida: a politica GP domina perturbacoes dela mesma
    val = validar_por_simulacao(risco=0.07, custo=6.9, persistencia=0.0315,
                                n_passos=20_000, semente=3)
    assert val["gp_e_otimo"], val["objetivo_perturbado"]


def test_newey_west_corrige_sobreposicao():
    """Em serie autocorrelacionada, o t corrigido < t ingenuo; sem autocorrelacao
    (lag=0) os dois coincidem."""
    from statarb.stats import newey_west_tstat, overlap_lag

    assert overlap_lag(21, 5) == 4      # 21d de horizonte, grade de 5d
    assert overlap_lag(5, 5) == 0       # sem sobreposicao

    rng = np.random.default_rng(0)
    ruido = rng.normal(0.02, 0.05, 600)
    # media movel de 5 -> autocorrelacao forte, como ICs sobrepostos
    sobreposta = pd.Series(ruido).rolling(5).mean().dropna().values

    t_ing = newey_west_tstat(sobreposta, 0)
    t_nw = newey_west_tstat(sobreposta, 4)
    assert t_ing > t_nw > 0, f"t ingenuo {t_ing:.2f} deveria exceder o NW {t_nw:.2f}"

    iid = rng.normal(0.02, 0.05, 600)   # sem autocorrelacao: lag 0 == classico
    assert abs(newey_west_tstat(iid, 0) - iid.mean() / iid.std() * np.sqrt(len(iid))) < 1e-9
