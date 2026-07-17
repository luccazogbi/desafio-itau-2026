"""Motor de backtest event-driven (implementado pela equipe, exigencia do edital).

Convencao temporal ANTI-LOOKAHEAD (lag_days = 1):
  close de t   : sinal calculado com dados <= t; otimizador gera pesos-alvo
  close de t+1 : ordens MOC executadas; custos AC debitados no preco de t+1
  t+1 -> t+2   : posicao nova comeca a acruar P&L

Loop diario, por data d:
  1. P&L dos pesos carregados de d-1 para d (por perna + hedge);
  2. se ha execucao agendada p/ d: transiciona w -> alvo, debita custos,
     re-hedgeia o beta residual de mercado com IWM;
  3. decisao no close de d: universo(d) -> sinal(d) -> otimizador -> alvo
     agendado para d + lag.

Nomes deslistados enquanto carregados: retorno NaN => posicao encerrada
a custo zero (aproximacao conservadora documentada; na Bloomberg o TRI
ja embute o ultimo preco de negociacao).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..costs.almgren_chriss import ACCostModel
from ..data.universe import tradable_mask
from ..portfolio.optimizer import optimize_weights, to_series
from ..risk.covariance import factor_cov_chol, total_vol


class BacktestEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.G = float(cfg["book"]["gross_usd"])
        self.lag = int(cfg["execution"]["lag_days"])
        self.cost_model = ACCostModel(cfg)
        self.hedge_on = bool(cfg["hedge"]["enabled"])

    # ------------------------------------------------------------------ run
    def run(self, md, fm, signal) -> dict:
        cfg = self.cfg
        mask = tradable_mask(md, cfg)

        all_dates = md.returns.index
        start = pd.Timestamp(cfg["backtest"]["start"])
        end = pd.Timestamp(cfg["backtest"]["end"])
        dates = all_dates[(all_dates >= start) & (all_dates <= end)]
        if fm.betas_asof(dates[0]) is None:
            raise ValueError("Backtest comeca antes da primeira estimacao de betas.")

        w = pd.Series(dtype=float)       # pesos correntes (fracao do gross)
        hedge = 0.0                      # peso no ETF de hedge
        pending: dict[pd.Timestamp, pd.Series] = {}
        rows, targets_hist = [], {}
        n_fail = 0
        # sinais lentos nao precisam de decisao diaria: reduz giro/custo sem
        # perder informacao (ex.: resid_ou tem autocorrelacao de score ~0.9)
        every = int(cfg["execution"].get("rebalance_every_days", 1))

        for i, d in enumerate(dates):
            # ---------- 1) P&L do dia com os pesos carregados
            r = md.returns.loc[d]
            r_h = r.reindex(w.index)
            dead = r_h.isna()
            if dead.any():
                w = w[~dead]                      # deslistou: fecha a custo zero
                r_h = r_h[~dead]
            pnl_long = float((w[w > 0] * r_h[w > 0]).sum())
            pnl_short = float((w[w < 0] * r_h[w < 0]).sum())
            pnl_hedge = float(hedge * md.iwm_ret.get(d, 0.0))
            pnl_gross = pnl_long + pnl_short + pnl_hedge

            # ---------- 2) execucao agendada para hoje
            cost_usd = spread_usd = impact_usd = turnover = 0.0
            if d in pending:
                target = pending.pop(d)
                union = w.index.union(target.index)
                trades = target.reindex(union).fillna(0.0) - w.reindex(union).fillna(0.0)

                ivol_d = fm.idio_asof(d)
                sigma_tr = ivol_d.reindex(union).fillna(0.02).values if ivol_d is not None else np.full(len(union), 0.02)
                adv_tr = md.adv.loc[d].reindex(union).values
                cost = self.cost_model.realized_cost_usd(trades.values, sigma_tr, adv_tr)
                cost_usd, spread_usd, impact_usd = cost["total_usd"], cost["spread_usd"], cost["impact_usd"]
                turnover = float(trades.abs().sum())

                w = target[target != 0.0]
                hedge = self._rehedge(fm, d, w) if self.hedge_on else 0.0

            # ---------- 3) decisao no close de d p/ execucao em d+lag
            if i % every == 0 and i + self.lag < len(dates):
                tgt = self._decide(md, fm, signal, mask, d, w)
                if tgt is not None:
                    exec_date = dates[i + self.lag]
                    pending[exec_date] = tgt
                    targets_hist[exec_date] = tgt
                else:
                    n_fail += 1

            expo = self._exposures(fm, d, w)
            rows.append({
                "date": d,
                "pnl_gross_usd": pnl_gross * self.G,
                "cost_usd": cost_usd, "spread_usd": spread_usd, "impact_usd": impact_usd,
                "pnl_net_usd": pnl_gross * self.G - cost_usd,
                "pnl_long_usd": pnl_long * self.G, "pnl_short_usd": pnl_short * self.G,
                "pnl_hedge_usd": pnl_hedge * self.G,
                "gross": float(w.abs().sum()), "net": float(w.sum()),
                "turnover": turnover, "n_positions": int((w != 0).sum()),
                "hedge_w": hedge,
                "max_sector_net": self._max_sector_net(md, w),
                **{f"expo_{k}": v for k, v in expo.items()},
            })

        res = pd.DataFrame(rows).set_index("date")
        weights = pd.DataFrame(targets_hist).T.sort_index().fillna(0.0)
        weights.index.name = "date"
        return {"results": res, "target_weights": weights, "n_opt_failures": n_fail}

    # ------------------------------------------------------------- decisao
    def _decide(self, md, fm, signal, mask, d, w_cur) -> pd.Series | None:
        univ_row = mask.loc[d]
        universe = list(univ_row.index[univ_row])
        if len(universe) < 50:
            return None

        z = signal.compute(md, fm, d, universe)
        B_df = fm.betas_asof(d)
        ivol_s = fm.idio_asof(d)
        if z is None or len(z) < 50 or B_df is None:
            return None

        names = sorted(set(z.index) & set(B_df.index) & set(ivol_s.index))
        adv_row = md.adv.loc[d].reindex(names)
        names = [n for n, ok in zip(names, adv_row.notna().values) if ok]
        if len(names) < 50:
            return None

        # alfa esperado ao longo do horizonte de manutencao (anti-miopia):
        # a posicao rende ~alpha_diario x horizon ate ser desmontada, e e esse
        # total que compete com o custo de execucao pago uma unica vez na entrada
        alpha_scale = (
            float(self.cfg["signal"]["alpha_bps_per_z"]) * 1e-4
            * float(self.cfg["signal"].get("horizon_days", 1))
        )
        alpha = z.reindex(names).values * alpha_scale
        B = B_df.reindex(names).values
        ivol = ivol_s.reindex(names).values
        F_chol = factor_cov_chol(md.factors, d, int(self.cfg["risk"]["cov_window"]))
        sigma = total_vol(B, F_chol, ivol)
        adv = md.adv.loc[d].reindex(names).values
        w_prev = w_cur.reindex(names).fillna(0.0).values

        sectors = md.sectors.reindex(names).fillna("Unknown").values

        w_new = optimize_weights(
            alpha=alpha, B=B, F_chol=F_chol, ivol=ivol, sigma_total=sigma,
            adv=adv, w_prev=w_prev, cost_model=self.cost_model, cfg=self.cfg,
            sectors=sectors,
        )
        if w_new is None:
            return None
        return to_series(w_new, names)

    # --------------------------------------------------------------- hedge
    def _rehedge(self, fm, d, w) -> float:
        """Peso em IWM que zera o beta de mercado residual do book."""
        B = fm.betas_asof(d)
        if B is None or len(w) == 0:
            return 0.0
        common = w.index.intersection(B.index)
        beta_mkt = float((w.reindex(common) * B.loc[common, "mkt"]).sum())
        return -beta_mkt

    def _exposures(self, fm, d, w) -> dict:
        B = fm.betas_asof(d)
        if B is None or len(w) == 0:
            return {k: 0.0 for k in self.cfg["factors"]["names"]}
        common = w.index.intersection(B.index)
        expo = B.loc[common].mul(w.reindex(common), axis=0).sum()
        return expo.to_dict()

    def _max_sector_net(self, md, w) -> float:
        """Maior |exposicao liquida| a um setor no book corrente (monitoracao)."""
        if len(w) == 0:
            return 0.0
        sec = md.sectors.reindex(w.index).fillna("Unknown")
        return float(w.groupby(sec).sum().abs().max())
