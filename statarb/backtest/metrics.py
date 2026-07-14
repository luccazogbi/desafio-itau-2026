"""Metricas de desempenho e tearsheet grafico do backtest."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..viz.style import PALETTE, apply_style

ANN = 252


def compute_metrics(res: pd.DataFrame, gross_usd: float) -> dict:
    daily_net = res["pnl_net_usd"] / gross_usd
    daily_gross = res["pnl_gross_usd"] / gross_usd
    years = len(res) / ANN

    cum = daily_net.cumsum()
    dd = cum - cum.cummax()
    downside = daily_net[daily_net < 0].std(ddof=0)

    def _sh(x):
        s = x.std(ddof=0)
        return float(x.mean() / s * np.sqrt(ANN)) if s > 0 else np.nan

    m = {
        "period": f"{res.index[0]:%Y-%m-%d} a {res.index[-1]:%Y-%m-%d}",
        "ann_return_gross_pct": float(daily_gross.mean() * ANN * 100),
        "ann_return_net_pct": float(daily_net.mean() * ANN * 100),
        "ann_vol_pct": float(daily_net.std(ddof=0) * np.sqrt(ANN) * 100),
        "sharpe_gross": _sh(daily_gross),
        "sharpe_net": _sh(daily_net),
        "sortino_net": float(daily_net.mean() / downside * np.sqrt(ANN)) if downside > 0 else np.nan,
        "max_drawdown_pct": float(dd.min() * 100),
        "hit_rate_pct": float((daily_net > 0).mean() * 100),
        "avg_gross": float(res["gross"].mean()),
        "max_abs_net": float(res["net"].abs().max()),
        "ann_turnover_x": float(res["turnover"].mean() * ANN),
        "total_costs_usd_mm": float(res["cost_usd"].sum() / 1e6),
        "costs_bps_of_gross_per_year": float(res["cost_usd"].sum() / gross_usd / years * 1e4),
        "avg_n_positions": float(res["n_positions"].mean()),
        "max_abs_factor_expo": float(
            res[[c for c in res.columns if c.startswith("expo_")]].abs().max().max()
        ),
        "pnl_net_total_usd_mm": float(res["pnl_net_usd"].sum() / 1e6),
    }
    return m


def write_report(
    res: pd.DataFrame,
    m: dict,
    outdir: str | Path,
    gross_usd: float,
    benchmarks: pd.DataFrame | None = None,
) -> None:
    """Grava metricas + tearsheet. `benchmarks`: DataFrame de RETORNOS diarios
    (ex.: colunas 'Cash (RF)' e 'IWM') alinhado ao indice de `res`."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    apply_style()

    with open(out / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(m, fh, indent=2, ensure_ascii=False)

    lines = ["# Metricas do backtest\n", "| Metrica | Valor |", "|---|---:|"]
    fmt = {
        "period": ("Periodo", "{}"),
        "ann_return_gross_pct": ("Retorno anual bruto (% do gross)", "{:.2f}%"),
        "ann_return_net_pct": ("Retorno anual liquido (% do gross)", "{:.2f}%"),
        "ann_vol_pct": ("Vol anualizada (%)", "{:.2f}%"),
        "sharpe_gross": ("Sharpe bruto", "{:.2f}"),
        "sharpe_net": ("Sharpe liquido", "{:.2f}"),
        "sortino_net": ("Sortino liquido", "{:.2f}"),
        "max_drawdown_pct": ("Max drawdown (% do gross)", "{:.2f}%"),
        "hit_rate_pct": ("Hit rate diario", "{:.1f}%"),
        "avg_gross": ("Gross medio (fracao do book)", "{:.3f}"),
        "max_abs_net": ("Max |net| (fracao do book)", "{:.4f}"),
        "ann_turnover_x": ("Turnover anualizado (x gross)", "{:.1f}x"),
        "total_costs_usd_mm": ("Custos totais (USD mm)", "{:.1f}"),
        "costs_bps_of_gross_per_year": ("Custos (bps do gross/ano)", "{:.0f}"),
        "avg_n_positions": ("Numero medio de posicoes", "{:.0f}"),
        "max_abs_factor_expo": ("Max |exposicao a fator|", "{:.4f}"),
        "pnl_net_total_usd_mm": ("P&L liquido acumulado (USD mm)", "{:.1f}"),
    }
    for k, (label, f) in fmt.items():
        lines.append(f"| {label} | {f.format(m[k])} |")
    (out / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    _plots(res, out, gross_usd)
    if benchmarks is not None:
        _benchmark_plot(res, benchmarks, out, gross_usd)
        _ffn_stats(res, benchmarks, out, gross_usd)


def _equity(res: pd.DataFrame, G: float) -> pd.Series:
    """Curva de capital (base 1.0) da estrategia liquida sobre o gross."""
    return (1.0 + res["pnl_net_usd"] / G).cumprod()


def _benchmark_plot(res, benchmarks: pd.DataFrame, out: Path, G: float) -> None:
    """Curva de capital vs benchmarks, no estilo `res.plot()` do notebook."""
    eq = pd.DataFrame({"StatArb L/S (net)": _equity(res, G)})
    for col in benchmarks.columns:
        eq[col] = (1.0 + benchmarks[col].reindex(res.index).fillna(0.0)).cumprod()

    fig, ax = plt.subplots()
    colors = [PALETTE["strategy"], PALETTE["benchmark"], PALETTE["iwm"]]
    for i, col in enumerate(eq.columns):
        eq[col].plot(ax=ax, lw=1.6 if i == 0 else 1.0, color=colors[i % len(colors)],
                     alpha=1.0 if i == 0 else 0.8)
    ax.set_title("Curva de capital vs benchmarks (base 1.0)")
    ax.set_ylabel("Crescimento de $1")
    ax.legend(eq.columns)
    fig.tight_layout(); fig.savefig(out / "6_equity_vs_benchmarks.png", dpi=130); plt.close(fig)


def _ffn_stats(res, benchmarks: pd.DataFrame, out: Path, G: float) -> None:
    """Tabela de estatisticas estilo `res.display()` do notebook (via ffn)."""
    try:
        import contextlib
        import io

        import ffn

        prices = pd.DataFrame({"StatArb L/S (net)": _equity(res, G)})
        for col in benchmarks.columns:
            prices[col] = (1.0 + benchmarks[col].reindex(res.index).fillna(0.0)).cumprod()
        stats = ffn.core.calc_stats(prices * 100.0)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            stats.display()
        (out / "ffn_stats.txt").write_text(buf.getvalue(), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 - tabela e opcional, nunca derruba o report
        (out / "ffn_stats.txt").write_text(f"ffn stats indisponiveis: {exc}", encoding="utf-8")


def _plots(res: pd.DataFrame, out: Path, G: float) -> None:
    mm = 1e6

    fig, ax = plt.subplots(figsize=(10, 5))
    (res["pnl_net_usd"].cumsum() / mm).plot(ax=ax, label="Liquido (apos custos)", lw=1.6)
    (res["pnl_gross_usd"].cumsum() / mm).plot(ax=ax, label="Bruto", lw=1.0, alpha=0.6)
    ax.set_title("P&L acumulado (USD mm)"); ax.set_ylabel("USD mm"); ax.legend(); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "1_pnl.png", dpi=130); plt.close(fig)

    cum = res["pnl_net_usd"].cumsum() / G
    dd = (cum - cum.cummax()) * 100
    fig, ax = plt.subplots(figsize=(10, 3.2))
    dd.plot(ax=ax, color="firebrick"); ax.fill_between(dd.index, dd, 0, color="firebrick", alpha=0.25)
    ax.set_title("Drawdown (% do gross)"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "2_drawdown.png", dpi=130); plt.close(fig)

    expo_cols = [c for c in res.columns if c.startswith("expo_")]
    fig, ax = plt.subplots(figsize=(10, 4))
    res[expo_cols].rename(columns=lambda c: c[5:]).plot(ax=ax, lw=0.9)
    ax.set_title("Exposicao a fatores (beta x fracao do gross)"); ax.grid(alpha=0.3)
    ax.legend(ncol=6, fontsize=8)
    fig.tight_layout(); fig.savefig(out / "3_exposures.png", dpi=130); plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(10, 4))
    res["turnover"].rolling(21).mean().plot(ax=ax1, label="Turnover (21d mm)", color="tab:blue")
    ax1.set_ylabel("Turnover diario (x gross)", color="tab:blue"); ax1.grid(alpha=0.3)
    ax2 = ax1.twinx()
    (res["cost_usd"].rolling(21).mean() / 1e3).plot(ax=ax2, color="tab:orange", label="Custo (21d mm)")
    ax2.set_ylabel("Custo diario (USD mil)", color="tab:orange")
    ax1.set_title("Turnover e custos de execucao")
    fig.tight_layout(); fig.savefig(out / "4_turnover_costs.png", dpi=130); plt.close(fig)

    daily = res["pnl_net_usd"] / G
    roll_sh = daily.rolling(63).mean() / daily.rolling(63).std() * np.sqrt(252)
    fig, ax = plt.subplots(figsize=(10, 3.2))
    roll_sh.plot(ax=ax); ax.axhline(0, color="k", lw=0.7)
    ax.set_title("Sharpe liquido rolling 63d"); ax.grid(alpha=0.3)
    fig.tight_layout(); fig.savefig(out / "5_rolling_sharpe.png", dpi=130); plt.close(fig)
