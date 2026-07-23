"""Seasonality cross-sectional same-month (Keloharju, Linnainmaa & Nyberg,
JF 2016 e JFE 2021).

Fato: acoes que historicamente vao bem em determinado mes-calendario tendem a
repetir o padrao naquele mes. Versao refinada (2021): subtrair a media dos
OUTROS meses expurga o nivel de retorno da acao e isola o padrao sazonal puro.

No fim do mes m (decidindo a carteira que vale para o mes m+1):

    score_i = media[ retornos da acao i no MESMO mes-calendario de (m+1),
                     ultimos N anos ]  -  media[ retornos nos outros meses ]

Exige historico longo (>= min_years observacoes do mesmo mes). No painel
sintetico de 7 anos a cobertura comeca reduzida -- em dados reais, puxar
historico desde ~2012. Dados: apenas retornos mensais.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import PanelSignal
from .trend_factor import _month_ends


class Seasonality(PanelSignal):
    name = "seasonality"

    def _build_panel(self, md, fm) -> pd.DataFrame:
        p = self.params()
        min_years = int(p.get("min_years", 3))
        max_years = int(p.get("max_years", 10))

        me = _month_ends(md.tri.index)
        rm = md.tri.loc[me].pct_change(fill_method=None)

        panel = pd.DataFrame(np.nan, index=me, columns=md.tri.columns)
        for i, t in enumerate(me):
            hist = rm.iloc[: i + 1].tail(max_years * 12)
            if len(hist) < min_years * 12:
                continue
            target_month = (t.month % 12) + 1        # mes que esta para comecar
            same = hist[hist.index.month == target_month]
            other = hist[hist.index.month != target_month]
            if len(same) < min_years:
                continue
            mean_same = same.mean()
            n_same = same.notna().sum()
            raw = mean_same - other.mean()
            raw[n_same < min_years] = np.nan
            panel.iloc[i] = raw
        return panel.dropna(how="all")
