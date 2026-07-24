"""AUDITORIA DO DESLISTAMENTO: o backtest chega a viver algum?

MOTIVACAO: o motor tem um caminho de codigo para deslistamento -- quando o
retorno de um nome em carteira vira NaN, a posicao e liquidada, cobra-se o
spread e NAO se realiza perda terminal (o painel nao guarda o ultimo preco).
Essa aproximacao esta documentada como "otimista na perna long".

A pergunta que nunca havia sido feita: **esse caminho chega a ser executado?**

O QUE ESTE SCRIPT MEDE
  1. Nomes do painel que perdem preco NO MEIO da janela (morte observavel).
  2. Nomes que sao membros as-of mas nao tem preco NENHUM (o yfinance apagou
     o historico inteiro) -- esses nunca entram no universo.
  3. Saidas do indice durante dev+val, pelo membership as-of.
  4. Eventos de deslistagem REALMENTE processados pelo motor no backtest
     oficial (colunas delist_usd / delist_notional de results_daily.parquet).

A comparacao entre (3) e (4) e o resultado: se dezenas de empresas saem do
indice e o motor processa ZERO liquidacoes, entao a saida nao acontece por
deslistagem -- acontece porque a empresa simplesmente nunca esteve no painel.

HOLDOUT: le apenas metadados do painel (preco disponivel, membership) e o
resultado ja gravado do backtest dev+val. Nao calcula sinal, IC nem
desempenho, e nao passa de 2023-12-29. Nao toca no holdout.

Uso:   python scripts/17_delisting_audit.py [--data processed_sp500]
Saida: reports/delisting_audit.md
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of

DEV_VAL = ("2020-01-01", "2023-12-31")
TAG_BACKTEST = "sp500_dev_val"


def main() -> None:
    t0 = time.time()
    cfg = load_config()
    argv = sys.argv[1:]
    if "--data" in argv:
        cfg["paths"]["data_processed"] = "data/" + argv[argv.index("--data") + 1]
    painel = path_of(cfg, "data_processed")

    print("[1/4] Carregando painel...")
    close = pd.read_parquet(painel / "prices_close.parquet")
    member = pd.read_parquet(painel / "membership.parquet")
    fim_painel = close.index[-1]

    com_preco = [c for c in close.columns if close[c].notna().sum() > 0]
    sem_preco = [c for c in close.columns if close[c].notna().sum() == 0]

    print("[2/4] Nomes que perdem preco no meio do painel...")
    # ultima data com preco de cada nome; se for antes do fim do painel, o nome
    # "morre" de forma observavel -- e so ai o motor tem o que liquidar.
    ultimo = {c: close[c].dropna().index[-1] for c in com_preco}
    mortos = {c: d for c, d in ultimo.items() if d < fim_painel}
    mortos_dev_val = {c: d for c, d in mortos.items()
                      if pd.Timestamp(DEV_VAL[0]) <= d <= pd.Timestamp(DEV_VAL[1])}

    print("[3/4] Saidas do indice durante dev+val (membership as-of)...")
    mem_dv = member.loc[DEV_VAL[0]:DEV_VAL[1]]
    # saiu = era membro em algum momento da janela e nao era mais no fim dela
    era_membro = mem_dv.any()
    ainda_membro = mem_dv.iloc[-1]
    saidas = sorted(mem_dv.columns[era_membro & ~ainda_membro])
    saidas_sem_preco = [t for t in saidas if t in sem_preco]

    mm_total = int(mem_dv.sum().sum())
    mm_sem_preco = int(mem_dv[[c for c in sem_preco if c in mem_dv.columns]].sum().sum())

    print("[4/4] Eventos de deslistagem processados pelo motor...")
    rep = path_of(cfg, "reports")
    res_path = rep / TAG_BACKTEST / "results_daily.parquet"
    if res_path.exists():
        res = pd.read_parquet(res_path)
        n_dias = len(res)
        delist_usd = float(res["delist_usd"].sum())
        delist_notional = float(res["delist_notional"].sum())
        dias_com_evento = int((res["delist_notional"] > 0).sum())
        periodo = f"{res.index[0]:%Y-%m-%d} a {res.index[-1]:%Y-%m-%d}"
    else:
        n_dias = dias_com_evento = 0
        delist_usd = delist_notional = 0.0
        periodo = "backtest oficial nao encontrado -- rode scripts/02 --tag sp500_dev_val"

    L = [
        "# Auditoria do deslistamento: o backtest nunca vive um\n",
        f"> Painel: `{painel.name}` ({close.shape[1]} tickers x {close.shape[0]} dias) · "
        f"backtest oficial: {periodo}",
        "> Gerado por `scripts/17_delisting_audit.py`. Le apenas metadados do painel e o "
        "resultado ja gravado. **Nao toca no holdout.**\n",
        "## 1. O caminho de codigo que se quer testar\n",
        "O motor liquida uma posicao quando o retorno do nome vira `NaN` "
        "(`engine.py`, bloco 1): cobra o spread da saida e **nao realiza perda "
        "terminal**, porque o painel nao guarda o ultimo preco negociado. A "
        "limitacao esta documentada como *otimista na perna long*.\n",
        "A pergunta: **esse caminho e executado alguma vez?**\n",
        "## 2. Eventos de deslistagem processados pelo motor\n",
        "| | |",
        "|---|---:|",
        f"| Dias simulados | {n_dias} |",
        f"| Dias com liquidacao por deslistagem | **{dias_com_evento}** |",
        f"| Notional liquidado (fracao do gross, acumulada) | **{delist_notional:.4f}** |",
        f"| Custo de liquidacao cobrado | **US$ {delist_usd:,.2f}** |",
        "",
        "## 3. Por que zero: as empresas nao morrem, elas nunca nascem\n",
        "| Categoria | Nomes |",
        "|---|---:|",
        f"| Tickers no painel | {close.shape[1]} |",
        f"| — com algum preco | {len(com_preco)} |",
        f"| — **sem preco nenhum** (historico apagado pelo yfinance) | **{len(sem_preco)}** |",
        f"| Tickers que perdem preco no MEIO do painel | **{len(mortos)}** |",
        f"| — dentro de dev+val (2020-2023) | **{len(mortos_dev_val)}** |",
        "",
    ]

    if mortos:
        L += ["Os unicos nomes com morte observavel no painel:\n",
              "| Ticker | Ultimo preco |", "|---|---|"]
        for c, d in sorted(mortos.items(), key=lambda kv: kv[1]):
            dentro = " (dentro de dev+val)" if c in mortos_dev_val else ""
            L.append(f"| `{c}` | {d:%Y-%m-%d}{dentro} |")
        L.append("")

    L += [
        "## 4. O contraste que importa\n",
        "| | |",
        "|---|---:|",
        f"| Empresas que **sairam do indice** durante dev+val (membership as-of) | "
        f"**{len(saidas)}** |",
        f"| — destas, sem **nenhum** preco no painel | **{len(saidas_sem_preco)}** |",
        f"| Liquidacoes por deslistagem processadas pelo motor | **{dias_com_evento}** |",
        "",
        f"- Meses-membro em dev+val: **{mm_total}**",
        f"- Meses-membro pertencentes a nomes sem preco algum: **{mm_sem_preco}** "
        f"(**{mm_sem_preco/max(1,mm_total):.2%}**)\n",
        "## 5. Leitura\n",
        f"Durante 2020-2023, **{len(saidas)} empresas deixaram o S&P 500** pela composicao "
        f"as-of. O motor processou **{dias_com_evento} liquidacoes por deslistagem**.\n",
        "Isso nao e um bug do motor -- e a assinatura do problema de dados. Quando uma "
        "empresa e adquirida ou quebra, o yfinance apaga o historico **inteiro** dela. "
        "Ela nao *sai* do painel no meio do backtest: ela **nunca entra**. O filtro "
        "`md.returns.notna()` do universo a exclui desde o primeiro dia, anos antes do "
        "evento.\n",
        "Duas consequencias que precisam constar no relatorio:\n",
        "1. **A limitacao documentada esta vazia.** Dizer que o deslistamento e tratado "
        "*'a custo de spread, sem perda terminal, o que e otimista na perna long'* "
        "descreve um caminho que nunca e percorrido. O custo reportado e "
        f"**{'exatamente zero' if delist_usd == 0 else f'US$ {delist_usd:,.0f}'}**, e "
        "continuaria zero com qualquer premissa de perda terminal.\n",
        "2. **O vies e maior do que a cobertura sugere.** O numero usual "
        f"(**{mm_sem_preco/max(1,mm_total):.1%}** dos meses-membro sem preco) mede quanta "
        "*exposicao* se perde. Ele nao mostra que a amostra perdida e exatamente a "
        "populacao dos **eventos de saida** -- o backtest tem exposicao **zero** ao tipo "
        "de evento que a composicao as-of existe para capturar. O universo as-of resolve "
        "o vies de *selecao de membros*; nao resolve o de *selecao de desfechos*.\n",
        "> **Mitigacao possivel** (nao implementada): reter o ultimo preco negociado dos "
        "nomes que somem e impor um desfecho explicito na data de saida do indice "
        "(ex.: -100% em falencia, premio de aquisicao em M&A). Com dados gratuitos o "
        "desfecho teria de vir de outra fonte -- e a premissa passaria a ser declarada em "
        "vez de silenciosa. Bloomberg/CRSP resolvem direto.\n",
    ]

    (rep / "delisting_audit.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    sys.stdout.reconfigure(errors="replace")
    print()
    print(f"  sairam do indice em dev+val      : {len(saidas)}")
    print(f"  destes, sem preco nenhum         : {len(saidas_sem_preco)}")
    print(f"  mortes observaveis no painel     : {len(mortos)} (dev+val: {len(mortos_dev_val)})")
    print(f"  liquidacoes no motor             : {dias_com_evento} dias | US$ {delist_usd:,.2f}")
    print(f"  meses-membro sem preco (dev+val) : {mm_sem_preco}/{mm_total} "
          f"({mm_sem_preco/max(1,mm_total):.2%})")
    print(f"\nOK -> {rep / 'delisting_audit.md'} | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
