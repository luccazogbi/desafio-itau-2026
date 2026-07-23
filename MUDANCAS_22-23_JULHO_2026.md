# Mudanças de 22–23/07/2026 — do estado inicial ao atual

> **Para quem está com a versão anterior do projeto.** Este documento descreve tudo que
> mudou: código, configuração, dados, resultados e documentação. Está escrito para ser lido
> por uma pessoa **e** por um assistente de código — cada mudança traz o arquivo, o motivo e
> o impacto.
>
> **Resumo em uma linha:** o Sharpe líquido caiu de **0,198 para 0,160** — e isso é uma
> melhora, porque o número anterior omitia um custo real e o painel tinha um bug que apagava
> 23 empresas do universo.

---

## 0. Como usar este documento

Se você vai pedir a um assistente para atualizar seu repositório:

1. **Não tente aplicar as mudanças por diff manual.** Leia as seções 3–6, entenda *o que*
   mudou e *por quê*, e refaça as alterações no seu código.
2. **Comece pela seção 2** (ambiente) — sem isso nada roda.
3. **A seção 9** lista o que ainda está aberto, para não refazer trabalho.
4. Os números da seção 7 são o gabarito: se você aplicar tudo e rodar, deve chegar neles
   (com a ressalva de reprodutibilidade da seção 5.3).

---

## 1. Ordem de leitura recomendada

| # | Seção | Por quê |
|---|---|---|
| 1 | [Ambiente](#2-ambiente-o-venv-do-readme-não-existia) | pré-requisito |
| 2 | [Correções de código](#3-correções-de-código-6-defeitos) | o que mudou de comportamento |
| 3 | [Configuração](#4-mudanças-em-configconfigyaml) | parâmetros novos e alterados |
| 4 | [Achados nos dados](#5-achados-nos-dados-o-mais-importante) | o mais importante |
| 5 | [Análises novas](#6-análises-novas) | 4 estudos inéditos |
| 6 | [Números](#7-números-antes--depois) | antes → depois |

---

## 2. Ambiente: o venv do README não existia

O `README` mandava usar `~/.venvs/quant_ai_2026`, que nunca havia sido criado nesta máquina.
Nada rodava.

```bash
python -m venv "$env:USERPROFILE\.venvs\quant_ai_2026"
```
```bash
& "$env:USERPROFILE\.venvs\quant_ai_2026\Scripts\python.exe" -m pip install -r requirements.txt
```

Python 3.11.9 funcionou sem ajuste. Note que `requirements.txt` só tem limites inferiores,
então uma instalação limpa hoje traz **pandas 3.0.3**, **scipy 1.17**, **cvxpy 1.7.5**.
Testamos: **não quebrou nada**.

---

## 3. Correções de código (6 defeitos)

### 3.1 t-stats inflados ~2× por janelas sobrepostas 🔴

**Arquivo novo:** `statarb/stats.py`
**Alterados:** `scripts/04_signal_funnel.py`, `scripts/10_kappa_analysis.py`, `scripts/12_regime_analysis.py`

O IC é medido contra retorno de **21 dias** numa grade de **5 dias** — medições vizinhas
compartilham ~16 dias e **não são independentes**. A fórmula `média/desvio·√n` assume que
são, e infla o t-stat.

Implementamos Newey-West com pesos de Bartlett e lag = `ceil(h/every) − 1`.

**Impacto — este é o item que mais muda a narrativa do projeto:**

| Afirmação | t antigo (ingênuo) | **t Newey-West** |
|---|---:|---:|
| Funil, split **dev** | 4,20 | **2,50** |
| Funil, split **val** | 2,26 | **1,66** |
| IC em vol alta (regime) | 4,08 | **2,78** |
| IC em vol média (regime) | 3,47 | **2,51** |

O `resid_ou` continua sendo a melhor escolha entre os 11 candidatos e o IC segue positivo
nos dois splits (0,051 dev / 0,036 val) — mas **a validação fica abaixo de t = 2**. A frase
"único com IC robusto nos dois splits" foi corrigida em todos os documentos por ser forte
demais.

### 3.2 O holdout estava desprotegido 🔴

**Arquivos:** `statarb/backtest/engine.py`, `config/config.yaml`, `scripts/02_run_backtest.py`

`config.yaml` tinha `backtest.end: 2024-12-31`. Rodar `02_run_backtest.py` **sem flags**
entrava no holdout em silêncio.

Agora:
- `backtest.end: 2023-12-31` (default deliberado)
- `backtest.holdout_start: 2024-01-01` (novo)
- o motor **levanta `ValueError`** se `end >= holdout_start` sem `allow_holdout=True`
- CLI: `--allow-holdout` (com aviso em tela)

### 3.3 Aluguel da perna short não era cobrado 🔴

**Arquivos:** `config/config.yaml`, `statarb/backtest/engine.py`

O modelo de custo tinha só spread + impacto. O aluguel das ações vendidas —
**~20 bps/ano sobre o gross** — nunca entrou. A limitação estava documentada apenas no
`docs/arquivo/PIPELINE_v1_historico.md` e sumiu quando os docs foram reescritos em 15/07.

Novo: `costs.borrow_bps_per_year: 40.0`, debitado diariamente sobre `|posições vendidas|`.

### 3.4 Hedge, deslistagem e rebalance do ETF eram gratuitos 🟠

**Arquivos:** `statarb/backtest/engine.py`, `statarb/backtest/metrics.py`

Três buracos na contabilidade:

| Buraco | Correção |
|---|---|
| Hedge SPY fora de `gross`/`net` | colunas novas `gross_com_hedge`, `net_com_hedge` |
| Rebalance do hedge sem custo | cobra spread do ETF |
| Deslistagem "a custo zero" | cobra spread da liquidação |

O mais revelador: `|net|` reportado era **0,002**, mas o livro completo (com o ETF) carrega
até **0,0223** — $22mm num book de $1 bi. A neutralidade reportada era melhor que a efetiva.

> Sobre a deslistagem: o docstring dizia "aproximação **conservadora**". É o contrário —
> a perda terminal de uma empresa que quebra nunca é realizada, o que é **otimista na perna
> long**. Corrigido no docstring.

### 3.5 Unidades incoerentes no otimizador 🟠

**Arquivos:** `statarb/portfolio/optimizer.py`, `statarb/backtest/engine.py`, `config/config.yaml`

O objetivo comparava **21 dias** de alfa (`alpha × horizon_days`) contra **1 dia** de
variância. O risco era subpenalizado em 21×, e `risk_aversion: 150` não significava o que o
nome sugeria.

Corrigido: o termo de risco é escalado por `horizon_days`, e λ passou de **150 → 7,143**
(= 150/21). **Isso resolve exatamente o mesmo problema** — é correção de unidade, não
recalibragem. Os resultados não se movem.

### 3.6 Scripts rodavam no painel errado em silêncio 🟠

**Arquivo:** `statarb/config.py`

Os scripts 11, 12 e 15 não honravam a chave `data.panel` e caíam no default
`data/processed` — o painel **sintético**. Rodariam sobre dados falsos achando que estavam
nos reais.

A resolução foi para `load_config()`, então **todo script** herda. `--data` continua
sobrescrevendo.

---

## 4. Mudanças em `config/config.yaml`

| Chave | Antes | Depois | Motivo |
|---|---|---|---|
| `data.panel` | — | `processed_sp500` | **nova** — evita rodar no sintético por engano |
| `backtest.end` | `2024-12-31` | `2023-12-31` | não invadir o holdout por default |
| `backtest.holdout_start` | — | `2024-01-01` | **nova** — trava no motor |
| `costs.spread_bps` | `5.0` | `4.0` | **medido** (Corwin-Schultz) |
| `costs.borrow_bps_per_year` | — | `40.0` | **nova** — aluguel do short |
| `risk.risk_aversion` | `150.0` | `7.143` | correção de unidade (=150/21) |
| `execution.rebalance_every_days` | `3` | `3` | **mantido** (ver §6.4) |

---

## 5. Achados nos dados (o mais importante)

### 5.1 26 renomeações de ticker — o painel apagava empresas vivas 🔴

**Arquivos:** `scripts/13_membership_audit.py` (novo), `scripts/07_pull_sp500_asof.py`

Cruzamos duas fontes de eventos do índice (`fja05680` × change log da Wikipedia). Resultado:
**94,7% de concordância exata de data** nos 320 eventos casados — a composição as-of está
correta.

Mas 62 eventos apareciam só numa fonte. Investigando: eram **trocas de ticker**.

```
UTX→RTX   MMC→MRSH   BK→BNY    ABC→COR   WRK→SW    PKI→RVTY
CBS→PSKY  BBT→TFC    JEC→J     CTL→LUMN  MYL→VTRS  BLL→BALL
PEAK→DOC  NLOK→GEN   BHGE→BKR  TMK→GL    HRS→LHX   ...
```

A empresa **continuou no índice**; só o símbolo mudou. `07_pull_sp500_asof.py` tratava
apenas **3** (`FB`, `ANTM`, `KORS`). Para as outras 23, o ticker antigo virava uma coluna
sem **nenhum** preço, e a empresa sumia do universo em **todo o período anterior à troca**.

> Caso mais caro: sem `UTX→RTX`, a **United Technologies desaparece do painel de 2018 a
> abr/2020** — uma das maiores industriais do índice, ausente de metade do dev.

| | Antes | Depois |
|---|---:|---:|
| Tickers no painel | 688 | **665** |
| Cobertura média dos membros as-of | 91,7% | **92,8%** |
| Cobertura mínima | 83,8% | **86,1%** |
| Gap recuperável (bug) | 840 meses-membro | **0** |

**Um quinto do que era reportado como "viés irredutível de dados gratuitos" era bug de
mapeamento.** O mapa completo está explícito em `scripts/07_pull_sp500_asof.py`.

### 5.2 O universo de 2020-23 é erodido por M&A de 2024-26 🔴

Quando uma empresa é adquirida, o yfinance **apaga o histórico inteiro** dela — inclusive os
anos em que era constituinte saudável.

Medido: **24 empresas** foram membros durante todo o dev+val e saíram do índice só depois de
2023. Somam **834 meses-membro = 3,45%** da janela. Entre elas: Hologic, Kellanova,
Interpublic, Ansys, Hess, Juniper, Discover, Walgreens, Marathon Oil, Comerica.

**E o número cresce a cada nova aquisição.** O painel **não é estável entre execuções**.

> **O exemplo do SVB no notebook estava factualmente errado.** `SIVB` tem 60 meses de
> membership e **zero preços**; `FRC` idem. As duas quebras bancárias de 2023 — os casos
> canônicos de viés de sobrevivência — **não entram no backtest**. O texto da seção 1.1 foi
> reescrito usando `UTX→RTX`, que é verificável.

### 5.3 Congelamento do painel (snapshot) 🟠

**Arquivos novos:** `statarb/snapshot.py`, `scripts/16_snapshot_panel.py`

O problema de §5.2 tem consequência prática: o mesmo código rodado em datas diferentes dá
resultados diferentes. Isso **custou uma atribuição de causa** nesta sessão — o Sharpe bruto
caiu de 0,532 para 0,511 e não foi possível dizer se foi o código ou o painel, porque o
painel antigo não fora salvo.

Agora:

```
data/snapshots/<id>/     cópias dos parquets  (70 MB, fora do git)
snapshots/<id>.json      manifesto com SHA-256 (10 KB, VERSIONADO)
```

- o backtest grava `snapshot` no `metrics.json`
- **avisa** quando o painel não corresponde a nenhum snapshot (resultado não rastreável)
- `--diff A B` mede a erosão entre versões em meses-membro
- **Snapshot inicial: `2026-07-23`** (665 tickers, 77 sem preço)

Rotina no dia a dia: **nenhuma**. Só um comando (`--pull`) quando quiser dados novos.

### 5.4 A restrição setorial estava inativa 🔴

Descoberto durante a re-execução: `07_pull_sp500_asof.py` grava `sectors.parquet` com todos
os nomes como `"Unknown"`; é o `07b` que traz os setores reais. Sem rodar o `07b`, a
restrição de neutralidade setorial **colapsa num balde único** e vira equivalente à de
dollar-neutrality.

Custo medido do controle de risco quando ativo: **−0,06 de Sharpe** (0,220 → 0,160).

⚠️ **Rode sempre `07` → `07b` → `07c` → `07d` na sequência.** O `scripts/16 --pull` faz isso
e para no primeiro erro justamente por causa deste caso.

---

## 6. Análises novas

### 6.1 Calibração do modelo de custo — `results/05`

**Novos:** `scripts/07d_add_highlow_sp500.py`, `scripts/14_cost_calibration.py`

Dos três parâmetros, **só um era estimável** — e os outros dois foram *demonstrados*
não-identificáveis, não assumidos:

| Parâmetro | Veredito |
|---|---|
| `spread_bps` | ✅ **medido**: Corwin-Schultz dá 5,55 bps round-trip, monotônico na liquidez (D1 8,1 → D10 3,8). **5,0 → 4,0** |
| `ac_gamma` | ❌ a rota do Amihud **degenera**: `ILLIQ × ADV ≈ E\|r\|`, logo `γ ≈ E\|r\|/σ ≈ 0,66` para qualquer ação (idêntico nos 10 decis). Mantido em 0,05 |
| `ac_eta` | ❌ exige dados de execução (Almgren 2005 usou base do Citi). Passou no teste de plausibilidade: 10,2 bps a 1% do ADV, faixa publicada 5–15. Mantido em 0,5 |

> **Armadilha:** a primeira implementação do Corwin-Schultz deu **55 bps** — 10× o correto.
> Faltavam duas coisas do paper original: o **ajuste de gap overnight** e truncar negativos
> **depois** da agregação mensal, não em cada observação.

### 6.2 Gârleanu-Pedersen vs. heurística — `results/06`

**Novos:** `statarb/portfolio/garleanu_pedersen.py`, `scripts/15_gp_vs_heuristica.py`

Forma fechada **derivada** (resolvendo o Bellman e casando coeficientes) e **validada por
simulação** — a política GP domina todas as perturbações dela.

**Achado colateral valioso:** a autocorrelação do z-score decai de 0,842 (5d) a 0,243 (40d)
→ **meia-vida de 21,7 dias úteis**. O `horizon_days = 21` foi escolhido *a priori*, sem olhar
dado. **Validação independente.**

**Veredito:** a heurística **reage ~4× demais** ao sinal (`H` ótimo ≈ 5,5, não 21) e
**rebalanceia devagar demais** (2% do gap por período vs 13% do ótimo). Os dois erros se
cancelam em parte — compensação acidental, frágil.

*Ressalva:* GP supõem custo quadrático; o nosso tem spread linear (11%) e potência 3/2. É
diagnóstico, não substituição. `horizon_days` **não foi alterado**.

### 6.3 Filtro de κ (Avellaneda-Lee) — **rejeitado** — `results/07`

`scripts/10_kappa_analysis.py` **existia e nunca fora executado nem documentado**. Rodado
pela primeira vez:

| Quartil de velocidade | IC (21d) |
|---|---:|
| Q1 (mais **lento**) | **+0,050** |
| Q4 (mais **rápido**) | +0,024 |

Só **4%** do universo não reverte, e o IC é **maior nas de reversão lenta**. Filtrar
derrubaria o IC em 25%. Coerente: o sinal acumula 60 dias e tem meia-vida de 21,7 — é feito
para reversão lenta.

### 6.4 Reduzir giro — funciona, mas menos do que parecia — `results/07`

A leitura ingênua sugeria rebalance de 10 dias dando **+0,11** de Sharpe. Dois alertas
impediram aceitar: a curva não era monotônica (5 e 8 dias *piores* que 3) e o Sharpe **bruto**
oscilava 40%.

**Teste de fase** (mesmo intervalo, deslocando só a data inicial):

```
2020-01-03  →  0,341
2020-01-09  →  0,077
```

A dispersão (0,26) é **maior** que a suposta melhora (0,106). Média entre fases:

| rebalance | bruto | **líquido** | custos |
|---:|---:|---:|---:|
| 3 | 0,499 | **0,141** | 211 |
| 5 | 0,509 | 0,172 | 191 |
| 10 | 0,516 | **0,205** | 168 |

Ganho real **+0,06**, sustentado pelo mecanismo (bruto constante + custos caindo).
**`rebalance_every_days` mantido em 3** — a mudança é decisão de calibração e move todos os
números do relatório.

> **Fragilidade descoberta:** a dependência de fase (±0,09) é estrutural — giramos 100% do
> book de uma vez. A correção de mesa é **tranching** (girar ~10% todo dia). Não
> implementado.

---

## 7. Números: antes → depois

### Backtest oficial (dev+val 2020-2023)

| Métrica | 15/07 | **23/07** |
|---|---:|---:|
| Sharpe bruto | 0,532 | **0,511** |
| Sharpe líquido | 0,198 | **0,160** |
| Retorno líquido | 1,18% a.a. | **0,96%** a.a. |
| Custos | 198 bps | **211 bps** |
| P&L líquido | $47,2mm | **$38,3mm** |
| Turnover | 15,1× | 15,6× |
| Max drawdown | −10,9% | −11,3% |

**Decomposição da queda** — duas causas de tamanho parecido:

| Causa | Δ Sharpe | Decomponível? |
|---|---:|---|
| Alfa **bruto** caiu (painel mudou) | −0,021 | ❌ não isolado (painel antigo não fora salvo) |
| Custos subiram 12,5 bps/ano | −0,021 | ✅ exato |

Custos em detalhe: spread **−13,1** (calibração), impacto +4,3, **aluguel +20,0**, hedge +1,3.

> **Metade da queda é custo que sempre existiu e não estava sendo cobrado.** Não é o
> resultado piorando — é o resultado ficando correto.

### Curva de capacidade

| Book | Sharpe líq. antes | **depois** |
|---:|---:|---:|
| $100mm | 0,37 | **0,33** |
| $300mm | 0,30 | 0,26 |
| $1.000mm | 0,20 | **0,16** |

A **forma** monotônica — que é a conclusão — não mudou.

### Neutralidade (colunas novas)

| | Só ações | **Com hedge** |
|---|---:|---:|
| Gross médio | 0,999 | 1,012 |
| \|Net\| máximo | 0,0020 | **0,0223** |

---

## 8. Documentação atualizada

| Arquivo | O que mudou |
|---|---|
| `README.md` | fluxo com 07d/13/14/16; bloco de **resultado atual**; tabela de limitações; scripts legados |
| `roadmap.md` | 20 testes (era 11/18), 11 candidatos (era 8), 665 tickers, capacidade 0,33→0,16, t-stats corrigidos, 4 itens novos concluídos |
| `results/01` | regerado; decomposição correta da queda; benchmark SPY medido |
| `results/02` | curva regerada; conexão com `results/06` |
| `results/03` | t-stats Newey-West **medidos** |
| `results/04` a `07` | **novos** |
| `considerações/` | cobertura 92,8%; ressalva de que a premissa "aquisição mantém histórico" é falsa no yfinance |
| `docs/genai_log.md` | 8 entradas novas (5h a 5o) |
| `notebooks/doubts.md` | 4 dúvidas respondidas |
| `notebooks/pipeline_walkthrough.ipynb` | regenerado; exemplo do SVB corrigido; α lido do config (estava fixo em 5 bps, divergindo dos 3 oficiais) |

### Correções de consistência encontradas na auditoria final

1. **Cobertura 92,9% → 92,8%** — o `meta.json` tem 0,9285; o script de pull imprimia 92,9%
   por arredondamento e o valor errado se propagou por 6 arquivos.
2. **Comparação R2000 × S&P 500 estava trocada** — "18% vs 92%" comparava deslistadas do
   R2000 com **sobreviventes do R2000**. O correto entre deslistadas é **18% (R2000) vs
   46% (S&P 500)**.
3. **Dois números-chave não são reproduzíveis** ⚠️ — `scripts/08` carrega
   `data/raw/iwm_2019_split.pkl`, que **nenhum script gera**; e
   `reports/delisted_coverage_sp500.md` é citado mas nada o produz. São justamente os números
   que justificam a escolha do universo. Ficam marcados como **medição de 14/07, não
   re-derivável**. Métrica equivalente reprodutível hoje: `scripts/13` mede 77 de 665
   membros sem preço.

---

## 9. O que ficou pendente

| Item | Situação |
|---|---|
| `rebalance_every_days` 3 → 10 | **decisão do usuário** — vale ~+0,06, move todos os números |
| Implementar *tranching* | proposto — elimina a dependência de fase |
| Crosscheck `bt` nos dados reais | o 0,996 documentado é do painel **sintético** |
| Validação independente da composição | S&P Global bloqueia (HTTP 403); rota: IVV via SEC EDGAR |
| Tornar `scripts/08` reproduzível | falta o passo de download N-PORT |
| Condicionar exposição ao regime de vol | só vale se **pré-registrado** e testado no holdout |
| **Ida ao holdout (2024+)** | **NÃO FEITO** — segue trancado |

---

## 10. Estado final verificado

```
20 testes passando
backtest oficial: Sharpe 0,160 · snapshot 2026-07-23 · 2020-01-02 a 2023-12-29
665 tickers × 2113 dias · cobertura 92,8%
16/16 números dos .md conferidos contra os artefatos
```

**O holdout nunca foi tocado.** Nenhum backtest, IC, sinal ou métrica de desempenho passou
de 2023-12-29, e o motor agora recusa fazê-lo sem flag explícita.

---

## 11. Nota de método

Vale registrar o padrão que se repetiu, porque é a parte reaproveitável:

- **Três resultados favoráveis foram rejeitados** após verificação — o rebalance de 10 dias
  (+0,11 era ruído de fase), o filtro de κ (piorava) e o spread de 55 bps (bug de
  implementação).
- **Dois números que sustentavam decisões centrais não resistiram ao escrutínio** — o
  "t≈4" do funil (era o t ingênuo) e os 18%/46% do estudo de deslistadas (não reproduzíveis).
- **O resultado piorou de 0,198 para 0,160** — e é mais defensável agora do que antes.

Nenhuma restrição de risco foi afrouxada, nenhum parâmetro foi ajustado para melhorar o
Sharpe, e o holdout segue intacto.
