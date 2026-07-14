"""Reversao de curto prazo condicional em turnover (Medhat & Schmeling, RFS 2022).

Fato do paper: o retorno do ultimo mes REVERTE nas acoes de baixo turnover e
CONTINUA nas de alto turnover. A reversao classica e remuneracao por prover
liquidez -- e so existe onde o movimento NAO foi validado por volume.

Implementacao (produto final sugerido pelo doc do colega): operar apenas a
perna limpa -- reversao dentro do quantil de MENOR turnover:

    turnover_21d = soma(volume $ 21d) / market cap
    score = -retorno_21d   APENAS nos nomes com turnover <= quantil q (demais: fora)

Dados: preco/volume/market cap -- ja no schema canonico, sem dependencia extra.
"""

from __future__ import annotations

import pandas as pd

from .base import PanelSignal


class STRTurnover(PanelSignal):
    name = "str_turnover"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        rw = int(p.get("ret_window", 21))
        tw = int(p.get("to_window", 21))
        q = float(p.get("low_to_quantile", 0.25))

        ret = md.tri.pct_change(rw, fill_method=None)
        turnover = md.dollar_volume.rolling(tw, min_periods=tw // 2).sum() / md.market_cap
        to_rank = turnover.rank(axis=1, pct=True)

        raw = (-ret).where(to_rank <= q)   # reversao so onde o volume nao validou
        return raw.dropna(how="all")
