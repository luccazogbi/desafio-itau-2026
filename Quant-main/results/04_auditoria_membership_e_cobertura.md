# Auditoria da composição as-of — o universo estava perdendo empresas vivas

> **Pergunta que motivou:** o painel as-of resolve o viés de *seleção*. Mas a composição
> está **correta**? E o gap de cobertura de preços é **dado indisponível** ou **bug nosso**?
> As duas perguntas nunca haviam sido separadas — os 8,3% eram tratados como um número só.
> **Método:** dois logs de eventos independentes, cruzados evento a evento; depois,
> classificação de cada nome sem preço.
> **Artefatos:** `reports/membership_audit.md` · `reports/rename_map.csv` ·
> `reports/membership_events.csv` · script `scripts/13_membership_audit.py`
> **Holdout:** este trabalho lê apenas *metadados* (membership e disponibilidade de preço).
> Não calcula retorno, sinal, IC nem desempenho — **não toca no holdout**.

---

## 1. As fontes e o que cada uma vale

| Fonte | Papel | Status |
|---|---|---|
| `fja05680/sp500` | listas de constituintes por data de mudança | ✅ usada no painel |
| Wikipedia *changes* | log de eventos explícito (add/rem + motivo) | ✅ cruzada |
| S&P Global (press releases) | fonte oficial | ❌ **HTTP 403** — bloqueia acesso automatizado |

**Ressalva que precisa constar no relatório:** o `fja05680` é *construído a partir* do change
log da Wikipedia. Cruzar os dois valida a **derivação** (parsing, datas, diffs) — não é
confronto de fontes independentes. A validação verdadeiramente independente continua **em
aberto**, porque a fonte oficial da S&P não permite acesso programático. Rota possível para
o futuro: holdings do **IVV** via SEC EDGAR N-PORT (mesmo método já usado para o IWM no
`scripts/08`).

---

## 2. A composição está correta

Cross-check dos **382 eventos** do `fja05680` contra os **332** da Wikipedia (2018–2026):

| Resultado | Eventos |
|---|---:|
| Casados | 320 |
| — com data **idêntica** | **303 (94,7%)** |
| — com data divergente (≤ 7 dias) | 17 |
| Só na Wikipedia | 12 |
| Só no `fja05680` | 62 |

**94,7% de concordância exata de data** é um bom resultado: as datas de entrada e saída que
o painel usa estão certas. Os 12 eventos exclusivos da Wikipedia são casos de borda de
cisão/fusão (FOX/FOXA no mesmo dia, BMS/Amcor, MBC).

---

## 3. O achado: 62 "eventos" que não eram eventos

Os 62 exclusivos do `fja05680` seguem um padrão único — **trocas de ticker**:

```
PX→LIN   HRS→LHX   TMK→GL    BHGE→BKR  SYMC→NLOK  HCP→PEAK
CBS→VIAC BBT→TFC   JEC→J     UTX→RTX   CTL→LUMN   MYL→VTRS
LB→BBWI  COG→CTRA  VIAC→PARA BLL→BALL  ABC→COR    PKI→RVTY
WRK→SW   PEAK→DOC  MMC→MRSH  BK→BNY    SATS→ECHO  ...
```

A empresa **continuou no índice**; só o símbolo mudou. O diff de listas registra isso como
um par remove+add; a Wikipedia — e portanto a S&P — corretamente **não** registra como
evento de índice.

**Por que isso quebrava o painel:** `07_pull_sp500_asof.py` tratava apenas **3** renomeações
(`FB`, `ANTM`, `KORS`). Para as outras 23, o ticker antigo virava uma coluna sem **nenhum**
preço — e a empresa sumia do universo em **todo o período anterior à troca**.

O caso mais caro: sem `UTX→RTX`, a **United Technologies desaparece do painel de 2018 a
abr/2020** — uma das maiores industriais do índice, ausente de metade da janela de
desenvolvimento.

---

## 4. Quanto do "viés de dados" era bug

| | Antes | Depois |
|---|---:|---:|
| Tickers no painel | 688 | **665** |
| Cobertura média dos membros as-of | 91,7% | **92,8%** |
| Cobertura **mínima** | 83,8% | **86,1%** |
| Gap total (meses-membro) | 7,80% | **6,76%** |
| — recuperável (renomeação) | 840 meses (20% do gap) | **0** |
| — perdido (deslistagem real) | 3.171 meses | 3.477 meses |

**Um quinto do que era reportado como "viés irredutível de dados gratuitos" era um bug de
mapeamento de ticker.** Corrigido em `scripts/07_pull_sp500_asof.py`; o mapa completo vive
lá, explícito e auditável, e é derivado por `scripts/13_membership_audit.py`.

---

## 5. O que sobra é real — e **cresce com o tempo**

Os 6,76% restantes são deslistagens genuínas: quando a empresa é adquirida, o yfinance
apaga o histórico **inteiro** dela, inclusive os anos em que ela era constituinte saudável.

| | |
|---|---:|
| Meses-membro em 2020–2023 (dev+val) | 24.202 |
| Perdidos por nomes que saíram **depois** de 2023 | **834 (3,45%)** |

Ou seja: **o universo de 2020–2023 é condicionado por aquisições de 2024–2026.** Empresas
como Hologic, Kellanova, Interpublic, Ansys, Hess e Juniper foram constituintes durante
todo o backtest e não têm um único dia de preço no painel.

Três consequências que precisam estar no relatório:

1. **O painel não é estável entre execuções.** Cada aquisição futura apaga mais um nome do
   passado. A cobertura reportada é medição **daquela data**, não propriedade fixa.
2. **A direção do viés é desfavorável ao rigor**: o universo é sistematicamente depletado de
   alvos futuros de M&A — informação do futuro condicionando a amostra histórica.
3. **O exemplo do SVB no notebook está errado.** `SIVB` tem 60 meses de membership e **zero
   preços**; `FRC` (First Republic), 52 meses e zero preços. As duas quebras bancárias de
   2023 — os casos canônicos de viés de sobrevivência — **não entram no backtest**. A
   ilustração da seção 1.1 do `pipeline_walkthrough` descreve algo que o painel não faz e
   precisa ser reescrita.

---

## 6. Mitigação honesta (proposta, não implementada)

Não há como recuperar preços de empresas adquiridas em fontes gratuitas. O que dá para fazer:

1. **Reportar a erosão como número datado**, com a data do pull ao lado — e não como "8,3%".
   Já implementado: `reports/membership_audit.md` carrega a data.
2. ✅ **Congelar o painel — IMPLEMENTADO em 23/07** (`scripts/16_snapshot_panel.py`).
   O painel é fotografado numa pasta datada, com SHA-256 de cada arquivo num manifesto
   versionado; o backtest grava em qual snapshot rodou e **avisa** quando o painel não
   corresponde a nenhum. `--diff A B` mede a erosão entre duas versões em meses-membro.
   **Snapshot inicial: `2026-07-23`** (665 tickers, 77 sem preço, gap de 7,04% em dev+val).
   A partir daqui, quando um resultado mudar, a causa é o código — o dado está parado.
3. **Medir a sensibilidade**: rodar o backtest só com os nomes que têm cobertura completa vs.
   o universo inteiro. Se o resultado não se mover, o viés é tolerável; se mover, é material.
4. **Bloomberg/CRSP resolvem** — é exatamente isto que se paga ao comprar esses dados.
