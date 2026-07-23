"""Carregamento da configuracao central (config/config.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path | None = None) -> dict:
    """Le o YAML de configuracao e anexa o diretorio raiz do projeto.

    Resolve `paths.data_processed` a partir de `data.panel`, se declarado. Sem
    isso cada script precisava receber `--data processed_sp500` na mao -- e quem
    esquecesse rodava, em silencio, sobre o painel SINTETICO de `data/processed`
    achando que estava nos dados reais. Bug real: pego quando os scripts 11/12
    ficaram fora da mudanca que introduziu `data.panel` no script 02.

    O `--data` do CLI continua valendo: os scripts sobrescrevem
    `cfg["paths"]["data_processed"]` DEPOIS desta funcao.
    """
    cfg_path = Path(path) if path else ROOT / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_root"] = str(ROOT)

    painel = cfg.get("data", {}).get("panel")
    if painel:
        cfg["paths"]["data_processed"] = f"data/{painel}"
    return cfg


def path_of(cfg: dict, key: str) -> Path:
    """Resolve um caminho declarado em cfg['paths'] relativo a raiz do projeto."""
    p = Path(cfg["_root"]) / cfg["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p
