"""Gera o painel sintetico no schema canonico (data/processed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from statarb.config import load_config, path_of
from statarb.data.synthetic import generate

if __name__ == "__main__":
    cfg = load_config()
    generate(
        outdir=path_of(cfg, "data_processed"),
        n_stocks=300,
        start=cfg["data"]["start"],
        end=cfg["data"]["end"],
        seed=42,
    )
