"""Mede a COBERTURA de precos de small caps deslistadas em fontes gratuitas.

Pergunta que decide se "small cap sem Bloomberg" e viavel: dos membros do
Russell 2000 que SAIRAM do indice, quantos ainda tem preco no yfinance?
Se a cobertura dos que sairam for baixa, o backtest small-cap gratuito
continua com survival bias (justamente os que sumiram sao os que importam).

Metodo:
  1. Holdings do IWM (iShares Russell 2000 ETF) via SEC EDGAR N-PORT, 2019 vs 2026.
  2. "Removidos" = no indice em 2019, fora em 2026 (mix de deslistados/adquiridos/
     graduados); "sobreviventes" = presentes nos dois -> grupo de controle.
  3. CUSIP -> ticker US via OpenFIGI (API gratuita, cobre deslistadas).
  4. yfinance: o ticker tem historico na janela 2018-2021 (quando era membro)?
  5. Reporta cobertura REMOVIDOS vs SOBREVIVENTES -> o tamanho do vies.

Saida: reports/delisted_coverage.md + .json
"""

from __future__ import annotations

import json
import pickle
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
H = {"User-Agent": "QuantAI2026 Research contact@example.com"}
FIGI_URL = "https://api.openfigi.com/v3/mapping"


def openfigi_map(cusips: list[str]) -> dict[str, str | None]:
    """CUSIP -> ticker US (batches de 10, throttled p/ o limite gratuito)."""
    out: dict[str, str | None] = {}
    for i in range(0, len(cusips), 10):
        chunk = cusips[i : i + 10]
        jobs = [{"idType": "ID_CUSIP", "idValue": c, "exchCode": "US"} for c in chunk]
        req = urllib.request.Request(
            FIGI_URL, data=json.dumps(jobs).encode(),
            headers={**H, "Content-Type": "application/json"})
        try:
            res = json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as e:  # rate limit / erro -> espera e tenta uma vez
            time.sleep(15)
            try:
                res = json.loads(urllib.request.urlopen(req, timeout=40).read())
            except Exception:
                res = [{} for _ in chunk]
                print(f"  [figi] batch {i} falhou: {str(e)[:50]}")
        for c, r in zip(chunk, res):
            data = r.get("data") if isinstance(r, dict) else None
            tk = None
            if data:
                # prefere ticker sem sufixo estranho (US common stock)
                for d in data:
                    cand = d.get("ticker", "")
                    if cand and cand.isalpha():
                        tk = cand; break
                tk = tk or data[0].get("ticker")
            out[c] = tk.replace("/", "-") if tk else None
        if (i // 10) % 10 == 0:
            print(f"  figi {min(i + 10, len(cusips))}/{len(cusips)}")
        time.sleep(3.0)  # ~20 req/min, dentro do limite sem API key
    return out


def yf_coverage(tickers: list[str]) -> dict[str, bool]:
    """True se o yfinance retorna historico utilizavel na janela 2018-2021."""
    import yfinance as yf

    cov: dict[str, bool] = {}
    uniq = sorted({t for t in tickers if t})
    for i in range(0, len(uniq), 200):
        chunk = uniq[i : i + 200]
        try:
            df = yf.download(chunk, start="2018-01-01", end="2021-12-31",
                             auto_adjust=True, progress=False, threads=True)
            close = df["Close"] if len(chunk) > 1 else df[["Close"]].set_axis(chunk, axis=1)
            valid = close.notna().sum()
            for t in chunk:
                cov[t] = bool(t in valid.index and valid[t] >= 30)
        except Exception as e:
            print(f"  [yf] batch {i} falhou: {str(e)[:50]}")
            for t in chunk:
                cov[t] = False
        print(f"  yf {min(i + 200, len(uniq))}/{len(uniq)}")
        time.sleep(1.0)
    return cov


def summarize(name: str, cusip_names: dict[str, str], figi: dict, cov: dict) -> dict:
    n = len(cusip_names)
    mapped = {c: figi[c] for c in cusip_names if figi.get(c)}
    priceable = {c: t for c, t in mapped.items() if cov.get(t)}
    r = {
        "grupo": name, "n_nomes": n,
        "mapeados_ticker": len(mapped), "pct_mapeados": round(len(mapped) / n, 4),
        "com_preco_yf": len(priceable), "pct_cobertura_total": round(len(priceable) / n, 4),
        "pct_cobertura_entre_mapeados": round(len(priceable) / max(1, len(mapped)), 4),
    }
    return r


def main() -> None:
    t0 = time.time()
    split = pickle.load(open(ROOT / "data" / "raw" / "iwm_2019_split.pkl", "rb"))
    removed, survivors = split["removed"], split["survivors"]

    # amostra de sobreviventes como controle (nao precisa dos 1000+)
    rng = np.random.default_rng(0)
    surv_keys = list(survivors)
    surv_sample = {k: survivors[k] for k in rng.choice(surv_keys, min(300, len(surv_keys)), replace=False)}

    all_cusips = list(removed) + list(surv_sample)
    print(f"[1/3] OpenFIGI: {len(removed)} removidos + {len(surv_sample)} sobreviventes (controle)...")
    figi = openfigi_map(all_cusips)

    print("[2/3] yfinance: cobertura de precos (janela 2018-2021)...")
    cov = yf_coverage([t for t in figi.values() if t])

    print("[3/3] Consolidando...")
    res_removed = summarize("removidos (sairam do indice)", removed, figi, cov)
    res_surv = summarize("sobreviventes (controle)", surv_sample, figi, cov)

    bias = res_surv["pct_cobertura_total"] - res_removed["pct_cobertura_total"]
    out = {
        "fonte_universo": "IWM holdings via SEC EDGAR N-PORT (2019-11 vs 2026-07)",
        "turnover_2019_2026": round(len(removed) / (len(removed) + len(survivors)), 4),
        "grupos": [res_removed, res_surv],
        "gap_de_cobertura_surv_menos_removidos": round(bias, 4),
        "leitura": ("cobertura dos REMOVIDOS << sobreviventes => survival bias residual "
                    "alto mesmo com membership as-of, porque o yfinance nao tem os precos "
                    "de quem sumiu. Numero que decide se small-cap gratuito e viavel."),
    }
    rep = ROOT / "reports"
    rep.mkdir(exist_ok=True)
    (rep / "delisted_coverage.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = ["# Cobertura de precos: deslistadas do Russell 2000 em fontes gratuitas\n",
             f"- Fonte do universo: {out['fonte_universo']}",
             f"- Turnover 2019->2026: **{out['turnover_2019_2026']:.0%}** dos membros sairam",
             "", "| Grupo | Nomes | Mapeados (ticker) | Com preco yfinance | Cobertura total |",
             "|---|---:|---:|---:|---:|"]
    for g in out["grupos"]:
        lines.append(f"| {g['grupo']} | {g['n_nomes']} | {g['pct_mapeados']:.0%} | "
                     f"{g['com_preco_yf']} | **{g['pct_cobertura_total']:.0%}** |")
    lines += ["", f"**Gap de cobertura (sobreviventes - removidos): {bias:+.0%}**", "",
              out["leitura"]]
    (rep / "delisted_coverage.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n================= COBERTURA DE DESLISTADAS =================")
    for g in out["grupos"]:
        print(f"  {g['grupo']:32s} cobertura total: {g['pct_cobertura_total']:.0%} "
              f"(mapeados {g['pct_mapeados']:.0%})")
    print(f"  GAP (survival bias residual): {bias:+.0%}")
    print(f"===========================================================\n{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
