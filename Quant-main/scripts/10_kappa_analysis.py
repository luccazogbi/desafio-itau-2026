"""Analise da VELOCIDADE DE REVERSAO (kappa) -- o filtro do Avellaneda-Lee que nao temos.

MOTIVACAO: nossa tese diz "o afastamento reverte". Mas nem toda acao tem residuo
que reverte -- algumas se comportam como passeio aleatorio. O A&L estima kappa
(velocidade de reversao) por acao e DESCARTA as lentas demais. Nos operamos todas.
Hipotese testavel: o IC e maior entre as acoes de reversao rapida?

METODO (fiel ao paper): dentro de uma janela de J=60 dias, constroi-se o caminho
CUMULATIVO dos residuos Y(k) = soma dos k primeiros residuos, e ajusta-se AR(1):
        Y(k) = a + b*Y(k-1) + ruido
    b em (0,1)  -> reverte;  kappa = -ln(b) * 252 (anualizado); tau = 1/kappa (anos)
    b >= 1      -> NAO reverte (passeio aleatorio ou explosivo) -> A&L descartaria

NOTA: o AR(1) e ajustado ao caminho cumulativo DENTRO da janela (como no paper),
e nao a nossa serie X (media movel de 60d), que e autocorrelacionada por
construcao -- janelas sobrepostas dariam b~0.98 mecanicamente, sem significado.

Saida: reports/kappa_analysis.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of
from statarb.data.loaders import MarketData
from statarb.data.universe import tradable_mask
from statarb.factors.betas import FactorModel
from statarb.stats import newey_west_tstat, overlap_lag

J = 60        # janela de estimacao do AR(1) (dias) -- igual ao acumulo do sinal
H = 21        # horizonte do IC (dias uteis a frente, apos execucao em t+1)
EVERY = 10    # grade de datas


def fit_ar1_kappa(R: np.ndarray) -> np.ndarray:
    """AR(1) vetorizado no caminho cumulativo. R = (J x N) residuos -> kappa (N,)."""
    Y = np.nancumsum(np.nan_to_num(R), axis=0)          # caminho cumulativo
    y0, y1 = Y[:-1], Y[1:]                               # lag e atual
    y0c = y0 - y0.mean(axis=0)
    y1c = y1 - y1.mean(axis=0)
    var = (y0c ** 2).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        b = (y0c * y1c).sum(axis=0) / var
        kappa = -np.log(b) * 252.0                       # anualizado
    kappa[~np.isfinite(kappa)] = np.nan
    kappa[(b <= 0) | (b >= 1)] = np.nan                  # nao reverte -> A&L descarta
    kappa[R.shape[0] - np.isnan(R).sum(axis=0) < J * 0.8] = np.nan   # dados insuficientes
    return kappa


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:
        cfg["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]

    md = MarketData.from_dir(path_of(cfg, "data_processed"), cfg)
    fm = FactorModel(cfg).fit(md.returns, md.factors)
    mask = tradable_mask(md, cfg)
    resid = fm.residuals
    idx = md.returns.index

    from statarb.signals import build_signal
    sig = build_signal(cfg, "resid_ou")

    start = idx.searchsorted(pd.Timestamp(cfg["backtest"]["start"]))
    val_end = pd.Timestamp(cfg["funnel"]["val_end"])

    frac_no_rev, taus = [], []
    ic_fast, ic_slow, ic_all = [], [], []
    ic_q = {q: [] for q in range(4)}

    for p in range(start, len(idx) - H - 2, EVERY):
        d = idx[p]
        if d > val_end:
            break
        univ = list(mask.columns[mask.loc[d]])
        if len(univ) < 200:
            continue

        z = sig.compute(md, fm, d, univ)
        if len(z) < 200:
            continue

        R = resid.iloc[p - J + 1 : p + 1][z.index].values
        kappa = pd.Series(fit_ar1_kappa(R), index=z.index)
        frac_no_rev.append(kappa.isna().mean())
        taus.append((1.0 / kappa.dropna() * 252).median())      # tau em dias uteis

        fwd = resid.iloc[p + 2 : p + 2 + H].sum(min_count=int(H * 0.7))
        common = z.index.intersection(fwd.dropna().index)
        if len(common) < 150:
            continue
        ic_all.append(spearmanr(z[common], fwd[common])[0])

        k = kappa.reindex(common)
        ok = k.dropna()
        if len(ok) < 100:
            continue
        med = ok.median()
        fast = ok[ok >= med].index                     # reverte rapido
        slow = ok[ok < med].index
        if len(fast) >= 50:
            ic_fast.append(spearmanr(z[fast], fwd[fast])[0])
        if len(slow) >= 50:
            ic_slow.append(spearmanr(z[slow], fwd[slow])[0])

        qs = pd.qcut(ok.rank(method="first"), 4, labels=False)
        for q in range(4):
            names = ok.index[qs == q]
            if len(names) >= 40:
                ic_q[q].append(spearmanr(z[names], fwd[names])[0])

    # t-stat corrigido para SOBREPOSICAO: o IC olha H=21 dias a frente numa grade
    # de EVERY=10 dias, entao medicoes vizinhas compartilham 11 dias. O t ingenuo
    # assume independencia e infla. Mesma correcao aplicada nos scripts 04 e 12.
    lag_ic = overlap_lag(H, EVERY)

    def stat(v):
        v = [x for x in v if np.isfinite(x)]
        if len(v) < 5:
            return np.nan, np.nan, 0
        return float(np.mean(v)), newey_west_tstat(v, lag_ic), len(v)

    ic_a, t_a, n_a = stat(ic_all)
    ic_f, t_f, _ = stat(ic_fast)
    ic_s, t_s, _ = stat(ic_slow)

    lines = [
        "# Velocidade de reversão (kappa): o filtro do Avellaneda-Lee\n",
        f"Janela AR(1): {J}d · horizonte do IC: {H}d · {n_a} datas (dev+val, holdout trancado)\n",
        "## 1. Quantas ações realmente revertem?\n",
        f"- Ações **sem reversão** (AR(1) com b>=1 → passeio aleatório/explosivo): "
        f"**{np.mean(frac_no_rev):.0%}** do universo, em média",
        f"- Entre as que revertem, meia-vida típica (tau): **{np.nanmedian(taus):.0f} dias úteis**\n",
        "> O A&L **descartaria** essa fatia sem reversão. Nós operamos todas.\n",
        "## 2. O sinal funciona melhor onde há reversão?\n",
        "| Grupo | IC (21d) | t-stat |",
        "|---|---:|---:|",
        f"| Todas as ações (como fazemos hoje) | {ic_a:+.4f} | {t_a:+.2f} |",
        f"| **Reversão rápida** (kappa acima da mediana) | **{ic_f:+.4f}** | **{t_f:+.2f}** |",
        f"| Reversão lenta (kappa abaixo da mediana) | {ic_s:+.4f} | {t_s:+.2f} |",
        "",
        "### Por quartil de velocidade (Q4 = mais rápido)\n",
        "| Quartil | IC (21d) | t-stat |",
        "|---|---:|---:|",
    ]
    for q in range(4):
        i_, t_, _ = stat(ic_q[q])
        lines.append(f"| Q{q+1} | {i_:+.4f} | {t_:+.2f} |")

    ganho = (ic_f - ic_a) / abs(ic_a) * 100 if np.isfinite(ic_a) and ic_a != 0 else np.nan
    veredito = ("FILTRAR AJUDA: o IC sobe materialmente entre as de reversão rápida."
                if np.isfinite(ic_f) and np.isfinite(ic_a) and ic_f > ic_a * 1.2 else
                "Filtrar NÃO ajuda de forma clara neste universo/período.")
    lines += ["", "## 3. Veredito\n",
              f"- IC entre rápidas vs todas: **{ganho:+.0f}%** de variação",
              f"- **{veredito}**", "",
              "> Se o filtro ajuda, implementá-lo NÃO é overfitting: é implementar a",
              "> referência (Avellaneda-Lee) de forma mais fiel — a justificativa é teórica,",
              "> anterior ao dado."]

    rep = path_of(cfg, "reports")
    (rep / "kappa_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # console do Windows e cp1252: nao encoda setas/acentos -> imprime tolerante
    sys.stdout.reconfigure(errors="replace")
    print("\n".join(lines))
    print(f"\nsalvo em {rep / 'kappa_analysis.md'} | {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
