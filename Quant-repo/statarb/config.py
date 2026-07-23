"""Carregamento da configuracao central (config/config.yaml)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: str | Path | None = None) -> dict:
    """Le o YAML de configuracao e anexa o diretorio raiz do projeto."""
    cfg_path = Path(path) if path else ROOT / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    cfg["_root"] = str(ROOT)
    return cfg


def path_of(cfg: dict, key: str) -> Path:
    """Resolve um caminho declarado em cfg['paths'] relativo a raiz do projeto."""
    p = Path(cfg["_root"]) / cfg["paths"][key]
    p.mkdir(parents=True, exist_ok=True)
    return p
