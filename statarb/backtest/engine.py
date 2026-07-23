"""Motor de backtest event-driven (implementado pela equipe, exigencia do edital).

Convencao temporal ANTI-LOOKAHEAD (lag_days = 1):
  close de t   : sinal calculado com dados <= t; otimizador gera pesos-alvo
  close de t+1 : ordens MOC executadas; custos AC debitados no preco de t+1
  t+1 -> t+2   : posicao nova comeca a acruar P&L

Loop diario, por data d:
  1. P&L dos pesos carregados de d-1 para d (por perna + hedge);
  2. se ha execucao agendada p/ d: transiciona w -> alvo, debita custos,
     re-hedgeia o beta residual de mercado com o ETF (SPY);
  3. decisao no close de d: universo(d) -> sinal(d) -> otimizador -> alvo
     agendado para d + lag.

CUSTOS DEBITADOS (todos em cost_usd, decompostos nas colunas do resultado):
  spread + impacto  execucao Almgren-Chriss dos trades de acoes;
  borrow            aluguel da perna short, diario sobre |posicoes vendidas|;
  hedge             spread do rebalanceamento do ETF (antes era gratuito);
  delist            spread da liquidacao de nome deslistado (antes era gratuito).

LIMITACAO DOCUMENTADA -- deslistamento: quando o retorno vira NaN o nome sai do
painel e nos cobramos o spread da saida, mas NAO ha perda terminal, porque o
painel nao guarda o ultimo preco negociado. Para uma falencia isso e OTIMISTA
na perna long (a perda final nunca e realizada) e conservador na short. Com TRI
da Bloomberg o ultimo preco vem embutido e a aproximacao cai.

TRAVA DO HOLDOUT: o motor RECUSA rodar alem de backtest.holdout_start sem
allow_holdout=True explicito. O protocolo reserva 2024+ para uma unica ida.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..costs.almgren_chriss import ACCostModel
from ..data.universe import tradable_mask
from ..portfolio.optimizer import optimize_weights, to_series
from ..risk.covariance import factor_cov_chol, total_vol


class BacktestEngine:
    def __init__(self, cfg: dict, allow_holdout: bool = False):
        self.cfg = cfg
        self.G = float(cfg["book"]["gross_usd"])
        self.lag = int(cfg["execution"]["lag_days"])
        self.cost_model = ACCostModel(cfg)
        self.hedge_on = bool(cfg["hedge"]["enabled"])
        self.allow_holdout = bool(allow_holdout)
        # aluguel da perna short, convertido para taxa diaria
        self.borrow_daily = float(cfg["costs"].get("borrow_bps_per_year", 0.0)) * 1e-4 / 252.0

    # ------------------------------------------------------------------ run
    def run(self, md, fm, signal) -> dict:
        cfg = self.cfg
        mask = tradable_mask(md, cfg)

        all_dates = md.returns.index
        start = pd.Timestamp(cfg["backtest"]["start"])
        end = pd.Timestamp(cfg["backtest"]["end"])

        # ---------- TRAVA DO HOLDOUT ----------
        # O protocolo anti-overfitting reserva 2024+ para UMA unica ida. Sem esta
        # guarda, bastava esquecer o --bt-end para queimar o holdout em silencio.
        holdout = cfg["backtest"].get("holdout_start")
        if holdout is not None and not self.allow_holdout:
            h0 = pd.Timestamp(holdout)
            if end >= h0:
                raise ValueError(
                    f"backtest.end={end:%Y-%m-%d} invade o HOLDOUT (inicia em "
                    f"{h0:%Y-%m-%d}). O protocolo permite UMA unica ida. Se e mesmo "
                    f"a decisao final, passe allow_holdout=True (CLI: --allow-holdout) "
                    f"e registre a rodada. Caso contrario, use --bt-end "
                    f"{h0 - pd.Timedelta(days=1):%Y-%m-%d}."
                )

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
            # DESLISTAMENTO: o nome sai do painel (retorno NaN). Antes a posicao era
            # encerrada a custo ZERO, o que nao e conservador -- e uma saida gratuita.
            # Agora cobramos ao menos o spread da liquidacao. Nao inventamos perda
            # terminal (nao temos o ultimo preco); a limitacao fica documentada.
            delist_usd, delist_notional = 0.0, 0.0
            if dead.any():
                delist_notional = float(w[dead].abs().sum())
                delist_usd = self.cost_model.spread * delist_notional * self.G
                w = w[~dead]
                r_h = r_h[~dead]
            pnl_long = float((w[w > 0] * r_h[w > 0]).sum())
            pnl_short = float((w[w < 0] * r_h[w < 0]).sum())
            pnl_hedge = float(hedge * md.iwm_ret.get(d, 0.0))
            pnl_gross = pnl_long + pnl_short + pnl_hedge

            # ALUGUEL da perna short: cobrado todo dia sobre o notional vendido.
            borrow_usd = self.borrow_daily * float(w[w < 0].abs().sum()) * self.G

            # ---------- 2) execucao agendada para hoje
            cost_usd = spread_usd = impact_usd = turnover = hedge_usd = 0.0
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
                # O hedge tambem NEGOCIA: antes era rebalanceado de graca. ETF de
                # ADV enorme => so spread, sem impacto relevante.
                hedge_novo = self._rehedge(fm, d, w) if self.hedge_on else 0.0
                hedge_usd = self.cost_model.spread * abs(hedge_novo - hedge) * self.G
                hedge = hedge_novo

            cost_usd += borrow_usd + delist_usd + hedge_usd

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
                "borrow_usd": borrow_usd, "delist_usd": delist_usd, "hedge_cost_usd": hedge_usd,
                "delist_notional": delist_notional,
                "pnl_net_usd": pnl_gross * self.G - cost_usd,
                "pnl_long_usd": pnl_long * self.G, "pnl_short_usd": pnl_short * self.G,
                "pnl_hedge_usd": pnl_hedge * self.G,
                # 'gross'/'net' = so a carteira de ACOES -- e sobre ela que o mandato
                # do otimizador incide. As colunas *_com_hedge mostram o livro REAL,
                # incluindo a posicao no ETF (antes o hedge ficava fora da conta e a
                # neutralidade reportada era melhor do que a efetiva).
                "gross": float(w.abs().sum()), "net": float(w.sum()),
                "gross_com_hedge": float(w.abs().sum()) + abs(hedge),
                "net_com_hedge": float(w.sum()) + hedge,
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
            horizon_days=int(self.cfg["signal"].get("horizon_days", 1)),
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
