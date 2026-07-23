"""AUDITORIA DA COMPOSICAO AS-OF: cruza duas fontes e mede a cobertura de precos.

MOTIVACAO: o painel as-of resolve o vies de SELECAO, mas dois riscos sobram e
nunca haviam sido medidos separadamente:
  (a) a composicao esta CORRETA? (datas exatas de entrada/saida)
  (b) o gap de cobertura de precos e DADO INDISPONIVEL ou BUG NOSSO?

METODO
  1. Log de eventos A -- fja05680/sp500: diff das listas de constituintes entre
     datas de mudanca consecutivas => (ticker, data, add|rem).
  2. Log de eventos B -- tabela "changes" da Wikipedia: log de eventos ja
     explicito (Effective Date | Added | Removed | Reason).
  3. Cross-check A x B com tolerancia de data, reportando concordancia exata,
     divergencia de data e eventos exclusivos de cada fonte.
  4. RENOMEACOES: par (rem X, add Y) na mesma data em A que NAO aparece em B.
     Mudanca real de indice aparece na Wikipedia; troca de ticker, nao.
     Resolvido transitivamente (CBS -> VIAC -> PARA -> PSKY).
  5. Cobertura: para cada nome que ja foi membro, dias com preco vs membership,
     separando o gap RECUPERAVEL (renomeacao) do PERDIDO (deslistagem real).

RESSALVA DE INDEPENDENCIA: o dataset fja05680 e construido A PARTIR do change
log da Wikipedia. O cross-check valida a DERIVACAO (parsing, datas, diffs), nao
e confronto de fontes independentes. Os press releases oficiais da S&P Global
bloqueiam acesso automatizado (HTTP 403), o que esta registrado no relatorio.

HOLDOUT: este script le apenas METADADOS (membership e disponibilidade de
preco). Nao calcula retorno, sinal, IC nem desempenho. Nao toca no holdout.

Uso:   python scripts/13_membership_audit.py [--data processed_sp500]
Saida: reports/membership_audit.md + membership_events.csv + rename_map.csv
"""

from __future__ import annotations

import io
import re
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

HEADERS = {"User-Agent": "QuantAI2026-Research/1.0 (academic project)"}
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FJA_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
           "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
SPGLOBAL_URL = "https://www.spglobal.com/spdji/en/documents/indexnews/announcements/"

JANELA_INI = pd.Timestamp("2018-01-01")
JANELA_FIM = pd.Timestamp("2026-12-31")
TOL_DIAS = 7          # tolerancia de data no casamento entre fontes


def normaliza(ticker: str) -> str:
    """Padroniza o ticker para comparacao entre fontes (padrao yfinance)."""
    t = re.sub(r"\[.*?\]", "", str(ticker)).strip().upper()
    t = re.sub(r"-\d{6}$", "", t)          # sufixo de deslistagem do dataset antigo
    return t.replace(".", "-")             # BRK.B -> BRK-B


# --------------------------------------------------------------- fonte A
def eventos_fja() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Log de eventos por diff das listas consecutivas de constituintes."""
    raw = urllib.request.urlopen(
        urllib.request.Request(FJA_URL, headers=HEADERS), timeout=90).read()
    df = pd.read_csv(io.StringIO(raw.decode("utf-8", errors="replace")))
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["members"] = df["tickers"].apply(
        lambda s: {normaliza(t) for t in str(s).split(",") if t.strip()})

    linhas = []
    for i in range(1, len(df)):
        antes, agora, d = df.loc[i - 1, "members"], df.loc[i, "members"], df.loc[i, "date"]
        linhas += [{"data": d, "ticker": t, "evento": "add"} for t in sorted(agora - antes)]
        linhas += [{"data": d, "ticker": t, "evento": "rem"} for t in sorted(antes - agora)]
    return pd.DataFrame(linhas), df


# --------------------------------------------------------------- fonte B
def eventos_wikipedia() -> pd.DataFrame:
    """Log de eventos da tabela 'changes' da Wikipedia (ja explicito)."""
    from bs4 import BeautifulSoup

    html = urllib.request.urlopen(
        urllib.request.Request(WIKI_URL, headers=HEADERS), timeout=90).read()
    tabela = BeautifulSoup(html, "html.parser").find_all("table", class_="wikitable")[1]

    linhas, data_pendente, repeticoes = [], None, 0
    for tr in tabela.find_all("tr"):
        celulas = tr.find_all("td")
        if not celulas:
            continue
        valores = [c.get_text(" ", strip=True) for c in celulas]
        if repeticoes > 0 and len(valores) == 5:      # linha sob rowspan da data
            data, resto = data_pendente, valores
            repeticoes -= 1
        else:
            rowspan = int(celulas[0].get("rowspan", 1))
            if rowspan > 1:
                data_pendente, repeticoes = valores[0], rowspan - 1
            data, resto = valores[0], valores[1:]
        if len(resto) < 5:
            continue
        add_tk, _, rem_tk, _, motivo = resto[:5]
        motivo = re.sub(r"\[.*?\]", "", motivo).strip()
        if add_tk:
            linhas.append({"data": data, "ticker": normaliza(add_tk),
                           "evento": "add", "motivo": motivo})
        if rem_tk:
            linhas.append({"data": data, "ticker": normaliza(rem_tk),
                           "evento": "rem", "motivo": motivo})

    df = pd.DataFrame(linhas)
    df["data"] = pd.to_datetime(df["data"], format="mixed", errors="coerce")
    return df.dropna(subset=["data"]).sort_values("data").reset_index(drop=True)


# --------------------------------------------------------------- cross-check
def cruza(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    """Casa eventos por (ticker, direcao) com tolerancia de data."""
    usados, pares, so_b = set(), [], []
    for _, rb in b.iterrows():
        cand = a[(a["ticker"] == rb["ticker"]) & (a["evento"] == rb["evento"])
                 & (~a.index.isin(usados))]
        cand = cand[(cand["data"] - rb["data"]).abs().dt.days <= TOL_DIAS]
        if len(cand):
            j = (cand["data"] - rb["data"]).abs().idxmin()
            usados.add(j)
            pares.append({"ticker": rb["ticker"], "evento": rb["evento"],
                          "data_wiki": rb["data"], "data_fja": a.loc[j, "data"],
                          "dif_dias": int((a.loc[j, "data"] - rb["data"]).days)})
        else:
            so_b.append(rb)
    return {"pares": pd.DataFrame(pares), "so_wiki": pd.DataFrame(so_b),
            "so_fja": a[~a.index.isin(usados)]}


def detecta_renomeacoes(so_fja: pd.DataFrame, com_dado: set[str]) -> dict[str, str]:
    """Par (rem X, add Y) na mesma data ausente da Wikipedia => renomeacao.

    Resolve cadeias transitivamente (CBS -> VIAC -> PARA -> PSKY) e desfaz
    ciclos (FISV -> FI -> FISV, a Fiserv trocou de simbolo e voltou atras)
    escolhendo, entre os tickers do ciclo, o que realmente tem preco.
    """
    bruto = {}
    for _, g in so_fja.groupby("data"):
        rems = sorted(g[g["evento"] == "rem"]["ticker"])
        adds = sorted(g[g["evento"] == "add"]["ticker"])
        if len(rems) == 1 and len(adds) == 1:          # so o par 1:1 e inequivoco
            bruto[rems[0]] = adds[0]

    def resolve(tk: str) -> str:
        caminho = [tk]
        while tk in bruto:
            prox = bruto[tk]
            if prox in caminho:                        # ciclo detectado
                ciclo = caminho[caminho.index(prox):]
                vivos = [c for c in ciclo if c in com_dado]
                return vivos[0] if vivos else ciclo[-1]
            caminho.append(prox)
            tk = prox
        return tk

    return {antigo: resolve(antigo) for antigo in bruto}


# --------------------------------------------------------------- cobertura
def audita_cobertura(painel: Path, mapa: dict[str, str]) -> dict:
    """Dias com preco vs meses de membership, separando gap recuperavel."""
    close = pd.read_parquet(painel / "prices_close.parquet")
    member = pd.read_parquet(painel / "membership.parquet")
    mm_total = int(member.sum().sum())

    recuperaveis, perdidos = [], []
    for t in close.columns:
        if close[t].notna().sum() > 0:
            continue
        meses = int(member[t].sum()) if t in member.columns else 0
        if meses == 0:
            continue
        destino = mapa.get(t)
        vivo = destino and destino in close.columns and close[destino].notna().sum() > 0
        (recuperaveis if vivo else perdidos).append(
            {"ticker": t, "meses_membro": meses, "destino": destino or ""})

    # depois do mapa de renomeacoes entrar no pull, `recuperaveis` fica VAZIO --
    # o DataFrame sem colunas quebraria o sort, entao fixamos o schema.
    COLS = ["ticker", "meses_membro", "destino"]
    ordena = lambda regs: (pd.DataFrame(regs, columns=COLS)
                           .sort_values("meses_membro", ascending=False))
    rec, per = ordena(recuperaveis), ordena(perdidos)
    mm_rec = int(rec["meses_membro"].sum()) if len(rec) else 0
    mm_per = int(per["meses_membro"].sum()) if len(per) else 0

    # erosao retroativa: nomes vivos durante TODO o dev+val que sumiram depois
    dev_val_fim = pd.Timestamp("2023-12-31")
    mm_dev_val = int(member.loc["2020-01-01":dev_val_fim].sum().sum())
    erosao = 0
    for _, r in per.iterrows():
        s = member[r["ticker"]]
        datas = s.index[s]
        if len(datas) and datas[-1] > dev_val_fim:
            erosao += int(((datas >= "2020-01-01") & (datas <= dev_val_fim)).sum())

    return {"recuperaveis": rec, "perdidos": per, "mm_total": mm_total,
            "mm_rec": mm_rec, "mm_per": mm_per,
            "mm_dev_val": mm_dev_val, "erosao_dev_val": erosao,
            "n_tickers": close.shape[1], "n_dias": close.shape[0]}


def testa_spglobal() -> str:
    """Registra se a fonte oficial da S&P permite acesso automatizado."""
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(SPGLOBAL_URL, headers=HEADERS), timeout=30)
        return f"acessivel (HTTP {r.status})"
    except Exception as exc:
        return f"INACESSIVEL ({str(exc)[:60]})"


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    argv = sys.argv[1:]
    sub = argv[argv.index("--data") + 1] if "--data" in argv else "processed_sp500"
    painel = path_of(cfg, "data_processed").parent / sub

    print("[1/5] Log de eventos A -- fja05680 (diff das listas)...")
    ev_fja, snaps = eventos_fja()
    print(f"      {len(ev_fja)} eventos | {len(snaps)} datas de mudanca no arquivo")

    print("[2/5] Log de eventos B -- change log da Wikipedia...")
    ev_wiki = eventos_wikipedia()
    print(f"      {len(ev_wiki)} eventos")

    janela = lambda df: df[(df["data"] >= JANELA_INI) & (df["data"] <= JANELA_FIM)].reset_index(drop=True)
    a, b = janela(ev_fja), janela(ev_wiki)
    print(f"      janela {JANELA_INI:%Y-%m} a {JANELA_FIM:%Y-%m}: fja={len(a)} | wiki={len(b)}")

    print("[3/5] Cross-check evento a evento...")
    cc = cruza(a, b)
    pares = cc["pares"]
    exatos = int((pares["dif_dias"] == 0).sum()) if len(pares) else 0
    print(f"      casados {len(pares)} | data identica {exatos} "
          f"({exatos/max(1,len(pares)):.1%}) | so wiki {len(cc['so_wiki'])} "
          f"| so fja {len(cc['so_fja'])}")

    print("[4/5] Detectando renomeacoes de ticker...")
    close_cols = pd.read_parquet(painel / "prices_close.parquet")
    com_dado = {c for c in close_cols.columns if close_cols[c].notna().sum() > 0}
    mapa = detecta_renomeacoes(cc["so_fja"], com_dado)
    print(f"      {len(mapa)} renomeacoes (resolvidas transitivamente)")

    print("[5/5] Auditoria de cobertura de precos...")
    cob = audita_cobertura(painel, mapa)
    print(f"      recuperaveis {len(cob['recuperaveis'])} ({cob['mm_rec']} meses-membro) "
          f"| perdidos {len(cob['perdidos'])} ({cob['mm_per']} meses-membro)")

    status_sp = testa_spglobal()
    rep = path_of(cfg, "reports")
    a.assign(fonte="fja05680").to_csv(rep / "membership_events.csv", index=False)
    pd.Series(mapa, name="ticker_atual").rename_axis("ticker_antigo").to_csv(rep / "rename_map.csv")

    gap_atual = (cob["mm_rec"] + cob["mm_per"]) / cob["mm_total"]
    gap_pos = cob["mm_per"] / cob["mm_total"]
    linhas = [
        "# Auditoria da composicao as-of do S&P 500 (2018-2026)\n",
        f"> Painel: `{sub}` ({cob['n_tickers']} tickers x {cob['n_dias']} dias) · "
        f"gerado por `scripts/13_membership_audit.py`",
        "> Le apenas METADADOS (membership + disponibilidade de preco). "
        "Nao calcula retorno nem desempenho: **nao toca no holdout**.\n",
        "## 1. Fontes\n",
        "| Fonte | Papel | Status |",
        "|---|---|---|",
        "| `fja05680/sp500` | listas de constituintes por data de mudanca | OK |",
        "| Wikipedia *changes* | log de eventos explicito (add/rem + motivo) | OK |",
        f"| S&P Global (press releases) | fonte oficial | {status_sp} |",
        "",
        "**Ressalva de independencia:** o `fja05680` e derivado do change log da "
        "Wikipedia. O cross-check valida a DERIVACAO (parsing, datas, diffs), nao e "
        "confronto de fontes independentes. A fonte oficial da S&P bloqueia acesso "
        "automatizado, entao a validacao independente de verdade continua em aberto.\n",
        "## 2. Cross-check dos eventos (2018-2026)\n",
        "| Resultado | Eventos |",
        "|---|---:|",
        f"| Casados | {len(pares)} |",
        f"| — com data **identica** | **{exatos}** ({exatos/max(1,len(pares)):.1%}) |",
        f"| — com data divergente (<= {TOL_DIAS}d) | {len(pares)-exatos} |",
        f"| So na Wikipedia | {len(cc['so_wiki'])} |",
        f"| So no fja05680 | {len(cc['so_fja'])} |",
        "",
        "Os eventos exclusivos do `fja05680` sao, na esmagadora maioria, **trocas de "
        "ticker**: a empresa continuou no indice e so o simbolo mudou. O diff de listas "
        "registra isso como um par remove+add; a Wikipedia, corretamente, nao registra "
        "como evento de indice.\n",
        "## 3. Renomeacoes detectadas\n",
        f"**{len(mapa)} renomeacoes** no periodo. O painel tratava apenas 3 "
        "(`FB`, `ANTM`, `KORS`) — as demais viravam nomes sem preco nenhum.\n",
        "| Ticker antigo | Ticker atual |",
        "|---|---|",
    ]
    for antigo in sorted(mapa):
        linhas.append(f"| `{antigo}` | `{mapa[antigo]}` |")

    linhas += [
        "",
        "## 4. Cobertura de precos dos ex-membros\n",
        "| Categoria | Nomes | Meses-membro | % do painel |",
        "|---|---:|---:|---:|",
        f"| **Recuperavel** (renomeacao nao tratada) | {len(cob['recuperaveis'])} | "
        f"{cob['mm_rec']} | {cob['mm_rec']/cob['mm_total']:.2%} |",
        f"| **Perdido** (deslistagem real) | {len(cob['perdidos'])} | "
        f"{cob['mm_per']} | {cob['mm_per']/cob['mm_total']:.2%} |",
        f"| **Gap total** | {len(cob['recuperaveis'])+len(cob['perdidos'])} | "
        f"{cob['mm_rec']+cob['mm_per']} | **{gap_atual:.2%}** |",
        "",
        (
            "O mapa de renomeacoes **ja esta aplicado** em `scripts/07_pull_sp500_asof.py`, "
            "entao o gap recuperavel remanescente e zero: o que sobra e ausencia real de "
            "dado. Medido antes da correcao (mapa com apenas 3 renomeacoes): 688 tickers, "
            "cobertura media 91,7% (min 83,8%), gap de 7,80% -- dos quais 840 meses-membro "
            "(20% do gap) eram renomeacoes nao tratadas. Depois: 665 tickers, cobertura "
            f"media 92,8% (min 86,1%), gap de {gap_atual:.2%}.\n"
            if cob["mm_rec"] == 0 else
            f"Tratando as renomeacoes, o gap cai de **{gap_atual:.2%}** para "
            f"**{gap_pos:.2%}** — ou seja, "
            f"**{cob['mm_rec']/max(1, cob['mm_rec']+cob['mm_per']):.0%} do gap e bug, "
            "nao indisponibilidade de dado**.\n"
        ),
        "## 5. Erosao retroativa (o risco que cresce)\n",
        f"Quando uma empresa e adquirida, o yfinance apaga o historico INTEIRO dela. "
        f"Resultado: nomes que foram constituintes saudaveis durante todo o dev+val "
        f"(2020-2023) e sairam do indice **depois** desaparecem retroativamente da "
        f"janela de desenvolvimento.\n",
        f"- Meses-membro em 2020-2023: **{cob['mm_dev_val']}**",
        f"- Perdidos por nomes que sairam **depois** de 2023: **{cob['erosao_dev_val']}** "
        f"({cob['erosao_dev_val']/cob['mm_dev_val']:.2%})\n",
        "Este numero **cresce com o tempo**: cada aquisicao futura apaga mais um nome "
        "do passado. O painel nao e estavel entre execucoes — e a cobertura reportada "
        "deve ser lida como medicao **daquela data**, nao como propriedade fixa.\n",
        "## 6. Deslistagens reais com maior exposicao perdida\n",
        "| Ticker | Meses no indice |",
        "|---|---:|",
    ]
    for _, r in cob["perdidos"].head(15).iterrows():
        linhas.append(f"| `{r['ticker']}` | {r['meses_membro']} |")

    (rep / "membership_audit.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(f"\nOK -> {rep / 'membership_audit.md'} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
