"""Roda o pipeline completo: dados -> fatores -> sinal -> otimizador -> backtest -> tearsheet.

Uso:
    python scripts/02_run_backtest.py
    python scripts/02_run_backtest.py --signal blend --alpha-bps 6 --horizon 8 --tag blend

--tag sufixa os arquivos de saida (results_daily_<tag>.parquet etc.), permitindo
comparar rodadas de sinais diferentes sem sobrescrever o tearsheet oficial.
"""

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.backtest.engine import BacktestEngine
from statarb.backtest.metrics import compute_metrics, write_report
from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData
from statarb.factors.betas import FactorModel
from statarb.signals import build_signal


def _cli_overrides(cfg) -> tuple[str, bool]:
    """Aplica overrides de CLI ao config.

    Devolve (tag dos artefatos, permissao explicita de rodar no holdout).
    """
    args = sys.argv[1:]
    tag = ""
    allow_holdout = "--allow-holdout" in args
    # o painel default (data.panel) ja e resolvido em load_config(); aqui so o
    # override explicito de --data
    for i, a in enumerate(args):
        if a == "--signal":
            cfg["signal"]["name"] = args[i + 1]
        elif a == "--alpha-bps":
            cfg["signal"]["alpha_bps_per_z"] = float(args[i + 1])
        elif a == "--horizon":
            cfg["signal"]["horizon_days"] = int(args[i + 1])
        elif a == "--rebalance":   # dias uteis entre decisoes (default 3 no config)
            cfg["execution"]["rebalance_every_days"] = int(args[i + 1])
        elif a == "--tag":
            tag = "_" + args[i + 1]
        elif a == "--data":       # ex.: --data processed_yf  (painel real do plano B)
            cfg["paths"]["data_processed"] = "data/" + args[i + 1]
        elif a == "--bt-start":
            cfg["backtest"]["start"] = args[i + 1]
        elif a == "--bt-end":     # ex.: --bt-end 2023-12-31 (tranca o holdout)
            cfg["backtest"]["end"] = args[i + 1]
    return tag, allow_holdout


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    tag, allow_holdout = _cli_overrides(cfg)
    if allow_holdout:
        print("[!] --allow-holdout ATIVO: esta rodada PODE entrar no holdout (2024+).")
        print("[!] O protocolo permite UMA unica ida. Registre a decisao no roadmap.")

    print("[1/4] Carregando painel de dados...")
    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    print(f"      {md.returns.shape[1]} tickers x {md.returns.shape[0]} dias "
          f"| painel: {Path(cfg['paths']['data_processed']).name}")

    print("[2/4] Estimando modelo de fatores (betas rolling + residuos)...")
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    print(f"      {len(fm.est_index)} datas de estimacao")

    print(f"[3/4] Backtest diario com sinal '{cfg['signal']['name']}'...")
    signal = build_signal(cfg)
    engine = BacktestEngine(cfg, allow_holdout=allow_holdout)
    out = engine.run(md, fm, signal)
    res = out["results"]
    if out["n_opt_failures"]:
        print(f"      [warn] otimizador sem solucao em {out['n_opt_failures']} datas (manteve pesos)")

    print("[4/4] Metricas e tearsheet...")
    m = compute_metrics(res, float(cfg["book"]["gross_usd"]))

    # RASTREABILIDADE: amarra este resultado ao estado exato dos dados. Sem isso,
    # comparar duas rodadas nao distingue mudanca de codigo de mudanca de painel.
    from statarb.snapshot import identifica_snapshot
    snap = identifica_snapshot(path_of(cfg, "data_processed"),
                               Path(cfg["_root"]) / "snapshots")
    m["snapshot"] = snap or "NAO_RASTREAVEL"
    if snap:
        print(f"      painel = snapshot {snap}")
    else:
        print("      [warn] painel nao corresponde a nenhum snapshot: resultado NAO "
              "rastreavel. Congele com scripts/16_snapshot_panel.py")
    rep = path_of(cfg, "reports")
    if tag:
        rep = rep / tag.lstrip("_")
        rep.mkdir(parents=True, exist_ok=True)
    benchmarks = pd.DataFrame({"Cash (RF)": md.rf, "IWM": md.iwm_ret}).reindex(res.index)
    write_report(res, m, rep, float(cfg["book"]["gross_usd"]), benchmarks=benchmarks)
    res.to_parquet(rep / "results_daily.parquet")
    out["target_weights"].to_parquet(rep / "target_weights.parquet")

    print("\n================= RESUMO =================")
    for k in ("period", "ann_return_gross_pct", "ann_return_net_pct", "ann_vol_pct",
              "sharpe_gross", "sharpe_net", "max_drawdown_pct", "ann_turnover_x",
              "costs_bps_of_gross_per_year", "avg_gross", "max_abs_net",
              "max_abs_factor_expo", "avg_n_positions", "pnl_net_total_usd_mm"):
        v = m[k]
        print(f"  {k:32s} {v:>12.3f}" if isinstance(v, float) else f"  {k:32s} {v:>12s}")
    print("==========================================")
    print(f"Relatorios em: {rep}  |  tempo total: {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
