"""Congelamento e rastreamento do painel de dados.

O PROBLEMA: repuxar os dados MUDA o universo historico. Quando uma empresa e
adquirida, o yfinance apaga o historico INTEIRO dela -- inclusive os anos em que
ela era constituinte saudavel. Medido no painel atual: 3,45% dos meses-membro de
2020-2023 pertencem a empresas que sairam do indice DEPOIS de 2023.

Consequencia pratica: o mesmo script, o mesmo codigo e a mesma config, rodados
com meses de diferenca, produzem universos historicos diferentes. Quando um
resultado muda, nao da para saber se foi o codigo ou o dado se mexendo -- e um
experimento sem grupo de controle. Aconteceu de fato em 23/07: o Sharpe bruto
caiu de 0,532 para 0,511 e a causa nao pode ser atribuida.

A SOLUCAO: fotografar o painel, guardar a copia com data e registrar a impressao
digital (SHA-256) de cada arquivo. A partir dai o dado fica parado, e toda
mudanca de resultado e atribuivel ao codigo.

ONDE FICA O QUE:
    data/snapshots/<id>/        copias dos parquets  (fora do git -- ~150 MB)
    snapshots/<id>.json         manifesto com hashes (NO git -- alguns KB)

O manifesto e pequeno e versionado: e ele que amarra um numero do relatorio a um
estado de dados identificavel.

O QUE ISTO NAO RESOLVE: as empresas ja perdidas continuam perdidas. Congelar
impede que piore, nao desfaz.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

DEV_VAL = ("2020-01-01", "2023-12-31")
BLOCO = 1 << 20          # 1 MB por leitura ao hashear


def hash_arquivo(caminho: Path) -> str:
    """SHA-256 do arquivo, lido em blocos (os parquets tem dezenas de MB)."""
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(BLOCO), b""):
            h.update(bloco)
    return h.hexdigest()


def impressao_digital(painel: Path) -> dict[str, dict]:
    """Hash + tamanho de cada arquivo do painel, ordenado por nome."""
    return {
        f.name: {"sha256": hash_arquivo(f), "bytes": f.stat().st_size}
        for f in sorted(painel.iterdir())
        if f.is_file() and f.suffix in (".parquet", ".json")
    }


def _resumo_painel(painel: Path) -> dict:
    """Metricas que tornam o manifesto legivel sem abrir os parquets."""
    close = pd.read_parquet(painel / "prices_close.parquet")
    member = pd.read_parquet(painel / "membership.parquet")

    sem_preco = [c for c in close.columns if close[c].notna().sum() == 0]
    mm_dev_val = int(member.loc[DEV_VAL[0]:DEV_VAL[1]].sum().sum())
    perdidos_dev_val = int(
        member.loc[DEV_VAL[0]:DEV_VAL[1], [c for c in sem_preco if c in member.columns]]
        .sum().sum()
    ) if sem_preco else 0

    return {
        "n_tickers": int(close.shape[1]),
        "n_dias": int(close.shape[0]),
        "periodo": [str(close.index[0].date()), str(close.index[-1].date())],
        "tickers_sem_preco": len(sem_preco),
        "meses_membro_dev_val": mm_dev_val,
        "meses_membro_perdidos_dev_val": perdidos_dev_val,
        "gap_dev_val": round(perdidos_dev_val / max(1, mm_dev_val), 4),
        "tickers": sorted(close.columns),
    }


def criar_snapshot(painel: Path, dir_dados: Path, dir_manifestos: Path,
                   rotulo: str | None = None) -> tuple[str, dict]:
    """Copia o painel para uma pasta datada e grava o manifesto versionavel."""
    base = rotulo or datetime.now().strftime("%Y-%m-%d")
    snapshot_id, n = base, 2
    while (dir_dados / snapshot_id).exists():       # ja existe hoje: sufixa
        snapshot_id, n = f"{base}-{n}", n + 1

    destino = dir_dados / snapshot_id
    destino.mkdir(parents=True)
    for f in sorted(painel.iterdir()):
        if f.is_file():
            shutil.copy2(f, destino / f.name)

    manifesto = {
        "snapshot_id": snapshot_id,
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "painel": painel.name,
        **_resumo_painel(painel),
        "arquivos": impressao_digital(painel),
    }
    dir_manifestos.mkdir(parents=True, exist_ok=True)
    (dir_manifestos / f"{snapshot_id}.json").write_text(
        json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot_id, manifesto


def carrega_manifestos(dir_manifestos: Path) -> dict[str, dict]:
    """Todos os manifestos disponiveis, por id."""
    if not dir_manifestos.exists():
        return {}
    return {f.stem: json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(dir_manifestos.glob("*.json"))}


def identifica_snapshot(painel: Path, dir_manifestos: Path) -> str | None:
    """A qual snapshot o painel de trabalho corresponde HOJE?

    Compara os hashes. Devolve None se o painel foi repuxado ou editado e nao
    bate com nenhum snapshot conhecido -- e essa e a informacao que interessa:
    um resultado gerado a partir de um painel nao identificado nao e rastreavel.
    """
    if not painel.exists():
        return None
    atual = impressao_digital(painel)
    for sid, man in carrega_manifestos(dir_manifestos).items():
        if man.get("arquivos") == atual:
            return sid
    return None


def compara(antes: dict, depois: dict) -> dict:
    """O que mudou entre dois snapshots -- em especial, quanto do passado sumiu."""
    t_antes, t_depois = set(antes.get("tickers", [])), set(depois.get("tickers", []))
    arq_a, arq_d = antes.get("arquivos", {}), depois.get("arquivos", {})

    return {
        "tickers_removidos": sorted(t_antes - t_depois),
        "tickers_adicionados": sorted(t_depois - t_antes),
        "arquivos_alterados": sorted(
            n for n in set(arq_a) & set(arq_d)
            if arq_a[n]["sha256"] != arq_d[n]["sha256"]),
        "delta_sem_preco": depois.get("tickers_sem_preco", 0) - antes.get("tickers_sem_preco", 0),
        "delta_meses_perdidos_dev_val": (depois.get("meses_membro_perdidos_dev_val", 0)
                                         - antes.get("meses_membro_perdidos_dev_val", 0)),
        "gap_dev_val_antes": antes.get("gap_dev_val"),
        "gap_dev_val_depois": depois.get("gap_dev_val"),
    }
