"""Congela o painel de dados e mede a erosao entre versoes.

POR QUE: repuxar os dados muda o universo HISTORICO -- o yfinance apaga o
historico inteiro de empresas adquiridas, inclusive os anos em que elas eram
constituintes saudaveis. Sem congelar, o mesmo codigo rodado em datas diferentes
da resultados diferentes, e nao se sabe se a causa foi o codigo ou o dado.

Uso:
    python scripts/16_snapshot_panel.py                  # fotografa o painel atual
    python scripts/16_snapshot_panel.py --pull           # repuxa os dados ANTES
    python scripts/16_snapshot_panel.py --list           # lista snapshots
    python scripts/16_snapshot_panel.py --check          # o painel bate com qual?
    python scripts/16_snapshot_panel.py --diff A B       # o que mudou entre dois

Saida:
    data/snapshots/<id>/     copias dos parquets (fora do git, ~150 MB)
    snapshots/<id>.json      manifesto com hashes (versionado, alguns KB)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of
from statarb.snapshot import (
    carrega_manifestos, compara, criar_snapshot, identifica_snapshot,
)

RAIZ = Path(__file__).resolve().parents[1]
DIR_MANIFESTOS = RAIZ / "snapshots"
SCRIPTS_PULL = ["07_pull_sp500_asof.py", "07b_add_marketcap_sp500.py",
                "07c_add_open_sp500.py", "07d_add_highlow_sp500.py"]


def repuxa() -> bool:
    """Roda os 07x em ordem. Para no primeiro erro -- painel meio-atualizado e
    pior que painel velho (foi assim que a restricao setorial ficou inativa)."""
    for nome in SCRIPTS_PULL:
        print(f"  -> {nome}")
        r = subprocess.run([sys.executable, str(RAIZ / "scripts" / nome)],
                           cwd=RAIZ, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [ERRO] {nome} falhou:\n{r.stdout[-800:]}\n{r.stderr[-800:]}")
            return False
    return True


def main() -> None:
    t0 = time.time()
    argv = sys.argv[1:]
    cfg = load_config()
    painel = path_of(cfg, "data_processed")
    dir_dados = painel.parent / "snapshots"

    # ---------------------------------------------------------------- listar
    if "--list" in argv:
        mans = carrega_manifestos(DIR_MANIFESTOS)
        if not mans:
            print("nenhum snapshot ainda. crie um com: python scripts/16_snapshot_panel.py")
            return
        print(f"{'snapshot':<14s} {'criado':<20s} {'tickers':>8s} {'s/preco':>8s} "
              f"{'gap dev+val':>12s}")
        for sid, m in mans.items():
            print(f"{sid:<14s} {m['criado_em'][:19]:<20s} {m['n_tickers']:>8d} "
                  f"{m['tickers_sem_preco']:>8d} {m['gap_dev_val']:>11.2%}")
        atual = identifica_snapshot(painel, DIR_MANIFESTOS)
        print(f"\npainel de trabalho corresponde a: {atual or 'NENHUM (foi repuxado/editado)'}")
        return

    # ---------------------------------------------------------------- checar
    if "--check" in argv:
        atual = identifica_snapshot(painel, DIR_MANIFESTOS)
        if atual:
            print(f"OK: o painel de trabalho corresponde ao snapshot {atual}")
        else:
            print("ATENCAO: o painel NAO corresponde a nenhum snapshot conhecido.")
            print("Resultados gerados a partir dele nao sao rastreaveis.")
            print("Congele com: python scripts/16_snapshot_panel.py")
        return

    # ----------------------------------------------------------------- diff
    if "--diff" in argv:
        i = argv.index("--diff")
        try:
            a, b = argv[i + 1], argv[i + 2]
        except IndexError:
            sys.exit("uso: --diff <snapshot_antes> <snapshot_depois>")
        mans = carrega_manifestos(DIR_MANIFESTOS)
        faltando = [x for x in (a, b) if x not in mans]
        if faltando:
            sys.exit(f"snapshot(s) nao encontrado(s): {faltando} | "
                     f"disponiveis: {list(mans)}")
        d = compara(mans[a], mans[b])
        print(f"=== {a}  ->  {b} ===")
        print(f"  tickers removidos   : {len(d['tickers_removidos'])} "
              f"{d['tickers_removidos'][:12]}")
        print(f"  tickers adicionados : {len(d['tickers_adicionados'])} "
              f"{d['tickers_adicionados'][:12]}")
        print(f"  arquivos alterados  : {len(d['arquivos_alterados'])}")
        print(f"  nomes sem preco     : {d['delta_sem_preco']:+d}")
        print(f"  EROSAO em 2020-2023 : {d['delta_meses_perdidos_dev_val']:+d} meses-membro"
              f"  ({d['gap_dev_val_antes']:.2%} -> {d['gap_dev_val_depois']:.2%})")
        return

    # ---------------------------------------------------------------- criar
    if "--pull" in argv:
        print("[1/2] Repuxando os dados (07 -> 07b -> 07c -> 07d)...")
        if not repuxa():
            sys.exit("pull falhou; snapshot NAO criado (painel pode estar inconsistente)")
    else:
        print("[1/2] Usando o painel como esta (sem repuxar).")

    print("[2/2] Congelando o painel e gravando o manifesto...")
    anterior = list(carrega_manifestos(DIR_MANIFESTOS))
    sid, man = criar_snapshot(painel, dir_dados, DIR_MANIFESTOS)

    print(f"\nsnapshot {sid} criado")
    print(f"  {man['n_tickers']} tickers x {man['n_dias']} dias "
          f"({man['periodo'][0]} a {man['periodo'][1]})")
    print(f"  sem preco: {man['tickers_sem_preco']} nomes | "
          f"gap em 2020-2023: {man['gap_dev_val']:.2%}")
    print(f"  dados    : {dir_dados / sid}")
    print(f"  manifesto: {DIR_MANIFESTOS / sid}.json  (este vai para o git)")

    if anterior:
        d = compara(carrega_manifestos(DIR_MANIFESTOS)[anterior[-1]], man)
        print(f"\nvs {anterior[-1]}:")
        print(f"  tickers: -{len(d['tickers_removidos'])} / "
              f"+{len(d['tickers_adicionados'])}")
        print(f"  EROSAO em 2020-2023: {d['delta_meses_perdidos_dev_val']:+d} meses-membro")
        if d["tickers_removidos"]:
            print(f"  sairam: {', '.join(d['tickers_removidos'][:15])}")

    print(f"\nOK | {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
