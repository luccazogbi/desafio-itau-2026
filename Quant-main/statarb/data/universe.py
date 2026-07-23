"""Construcao do universo investivel point-in-time.

Um nome e negociavel no dia t se, USANDO APENAS INFORMACAO ATE t:
  1. pertence ao indice (snapshot de membership mais recente <= t);
  2. preco >= min_price (sem penny stocks);
  3. ADV >= min_adv_usd (liquidez minima p/ um book de $1bi);
  4. tem historico suficiente p/ estimar beta e vol;
  5. tem retorno valido no dia (nao deslistada).

Todas as mascaras usam operacoes backward-looking (rolling/shift),
portanto nao ha lookahead por construcao.
"""

from __future__ import annotations

import pandas as pd


def tradable_mask(md, cfg: dict) -> pd.DataFrame:
    u = cfg["universe"]
    has_history = md.tri.notna() & md.tri.shift(int(u["min_history_days"])).notna()
    mask = (
        md.membership_daily
        & (md.close >= float(u["min_price"]))
        & (md.adv >= float(u["min_adv_usd"]))
        & has_history
        & md.returns.notna()
    )
    return mask.fillna(False)
