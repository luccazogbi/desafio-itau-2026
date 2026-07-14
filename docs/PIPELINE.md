# Pipeline StatArb Long-Short — Documentação de Funcionamento

**Projeto:** Desafio Itaú Asset Quant AI 2026
**Estratégia:** Arbitragem estatística long-short no Russell 2000, book de $1 bi dollar-neutral, neutra a fatores FF5+Momentum, com custos de execução Almgren-Chriss e hedge de beta residual via IWM.

---

## 1. O que é este pipeline (visão de 30 segundos)

Uma **linha de montagem de decisão de investimento**. Dados entram por um lado; do outro sai um P&L simulado com custos realistas e um tearsheet de métricas. No meio, cada etapa é um módulo independente com contrato de entrada/saída bem definido:

```mermaid
flowchart LR
    A[Dados brutos<br/>Bloomberg ou sintético] --> B[Universo investível<br/>point-in-time]
    B --> C[Modelo de fatores<br/>FF5+MOM rolling]
    C --> D[SINAL DE ALFA<br/>*** plug-in ***]
    D --> E[Otimizador convexo<br/>cvxpy]
    E --> F[Execução t+1<br/>custos Almgren-Chriss]
    F --> G[Hedge beta<br/>IWM]
    G --> H[P&L diário<br/>métricas + tearsheet]
```

A propriedade central: **o sinal (etapa D) é a única peça que falta decidir** — todas as outras já estão implementadas, testadas e são agnósticas a ele. Quando a pesquisa de sinais da equipe convergir, troca-se um módulo e roda-se tudo de novo.

---

## 2. Mapa do repositório

| Caminho | Papel |
|---|---|
| `config/config.yaml` | **Todos** os parâmetros (book, restrições, custos, janelas). Nada hard-coded. |
| `statarb/data/synthetic.py` | Gerador de painel sintético com reversão plantada (valida a esteira). |
| `statarb/data/loaders.py` | `MarketData`: carrega o *schema canônico* de `data/processed/`. |
| `statarb/data/universe.py` | Universo investível point-in-time (membership + filtros de liquidez). |
| `statarb/factors/betas.py` | `FactorModel`: betas rolling FF5+MOM, vol idio, resíduos diários. |
| `statarb/factors/ff_loader.py` | Download dos fatores reais (Ken French) p/ o modo Bloomberg. |
| `statarb/signals/` | **O plug-in.** `base.py` define o contrato; `reversal.py` é o placeholder. |
| `statarb/risk/covariance.py` | Covariância fatorada Σ = B·F·B′ + D (nunca N×N). |
| `statarb/costs/almgren_chriss.py` | Modelo de custo: spread + impacto temporário √ + permanente. |
| `statarb/portfolio/optimizer.py` | Otimização convexa (cvxpy) com todas as restrições do mandato. |
| `statarb/backtest/engine.py` | Motor de simulação diário (implementado pela equipe — exigência do edital). |
| `statarb/backtest/metrics.py` | Métricas + tearsheet (5 gráficos + tabela). |
| `scripts/00…03` | Entradas executáveis: sintético / Bloomberg / backtest / crosscheck bt. |
| `tests/test_pipeline.py` | 4 testes de sanidade (rodam em ~30s). |

---

## 3. As etapas, uma a uma

### Etapa 0 — Dados (schema canônico)

Tudo que o pipeline consome vive em `data/processed/` como parquet wide (index = data, colunas = tickers):

| Arquivo | Conteúdo |
|---|---|
| `prices_tri.parquet` | Índice de **retorno total** (dividendos reinvestidos — usar preço simples subestimaria o P&L). |
| `prices_close.parquet` | Preço de fechamento (filtros de universo). |
| `dollar_volume.parquet` | Volume financeiro diário (insumo do ADV → custos). |
| `market_cap.parquet` | Capitalização (contexto/filtros). |
| `membership.parquet` | Bool **mensal**: pertence ao índice naquela data (point-in-time). |
| `sectors.parquet` | Ticker → setor GICS. |
| `factors.parquet` | Retornos diários `mkt smb hml rmw cma mom` + `rf`. |
| `etf_iwm.parquet` | ETF de hedge (`tri`, `ret`). |

Duas fontes escrevem esse schema — e o resto do pipeline não sabe a diferença:

- `scripts/00_make_synthetic.py` — painel sintético: 300 ações, fatores + idiossincrático com **reversão plantada** (choque reverte 35% em 8 dias), 12% de deslistamentos, 10% de entradas tardias no índice. Serve para validar a esteira: se o pipeline não recupera um alfa que sabemos existir, tem bug.
- `scripts/01_pull_bloomberg.py` — extração real (rodar na máquina com terminal): membership point-in-time do `RTY Index` via `INDX_MWEIGHT_HIST` com override de data mensal, `TOT_RETURN_INDEX_GROSS_DVDS`, volume, market cap, GICS, IWM. Fatores reais vêm do Ken French (gratuito).

### Etapa 1 — Universo investível (`universe.py`)

No dia *t*, um nome é negociável se (usando **apenas informação ≤ t**): pertence ao índice no snapshot mais recente; preço ≥ $1; ADV ≥ $1mm; ≥ 260 dias de histórico; retorno válido no dia. Point-in-time de verdade: nomes deslistados saem do universo quando morrem, nomes que entram no índice só aparecem quando entram — **sem viés de sobrevivência de membership**.

### Etapa 2 — Modelo de fatores (`factors/betas.py`)

Regressão OLS rolling de 252 dias de cada ação nos 6 fatores, re-estimada a cada 21 dias (betas movem devagar; re-estimar diariamente só adiciona ruído):

- **Betas** B (N×6): usados como restrição de neutralidade no otimizador e no hedge;
- **Vol idiossincrática**: escala o sinal e o termo de risco;
- **Resíduos diários** r − B·f: a matéria-prima do sinal de reversão. O resíduo do dia *s* usa somente betas estimados **antes** de *s* (anti-lookahead estrutural).

### Etapa 3 — Sinal de alfa (`signals/` — O PLUG-IN)

Contrato (`signals/base.py`): receber `(dados, modelo_de_fatores, data, universo)` e devolver uma **Series de scores cross-sectional** (z-score winsorizado; maior = comprar, menor = vender), usando só informação ≤ data.

Placeholder atual (`reversal.py`) — reversão idiossincrática de 5 dias:

```
score_i = − Σ(resíduos últimos 5d) / (ivol_i · √5)   →   z-score cross-sectional, cap ±3
```

Tese: em small caps, fluxo não-informacional gera sobre-reação; o resíduo (movimento **não explicado por fatores**) tende a reverter. Quem provê liquidez é pago pela reversão.

**Para trocar o sinal:** criar `statarb/signals/meu_sinal.py` subclasseando `Signal` (ou `PanelSignal`, se o score cru puder ser pré-computado como painel com operações backward-looking), registrar em `signals/__init__.py`, apontar `signal.name` no config. Fim — nada mais muda.

#### A biblioteca de sinais (roadmap 3b) — todos só preço/volume, sem Bloomberg

| Sinal | Paper | Ideia em uma linha |
|---|---|---|
| `idio_reversal` | — (placeholder) | resíduo de 5d reverte |
| `earnings_yield` | Basu 1977 | E/P alto = barata (VALIDAÇÃO da esteira; descartável) |
| `trend_factor` | Han-Zhou-Zhu 2016 | MAs multi-horizonte com pesos aprendidos em regressão mensal |
| `mad` | Avramov 2021 | MA(21)/MA(200) — ancoragem (variante do módulo de tendência) |
| `str_turnover` | Medhat-Schmeling 2022 | reversão só no quantil de baixo turnover (provisão de liquidez limpa) |
| `resid_ou` | Avellaneda-Lee 2010 | desvio acumulado do resíduo, z contra o próprio histórico |
| `left_tail` | Atilgan et al. 2020 | cauda esquerda pesada persiste → short; turnover baixíssimo |
| `seasonality` | Keloharju et al. 2016/21 | same-month menos outros meses (exige história longa) |
| `blend` | — (combinador) | alfa único = Σ w_k·z_k dos componentes do config (FAQ 20 do edital) |

#### O funil (`scripts/04_signal_funnel.py`, roadmap 3c)

Mede por sinal e por split temporal (dev ≤2022 / val 2023 / **holdout 2024+ trancado** — uma ida só, com `--include-holdout`): cobertura, IC de Spearman contra o retorno **residual** de 1/5/21 dias *após a execução em t+1*, t-stats, autocorrelação do score (proxy de turnover) e spread Q5−Q1. Resultado da rodada sintética (validação da máquina): detecta os dois alfas plantados (reversão IC5≈0,15; E/P IC21≈0,11), mostra ~0 onde nada existe (left_tail, seasonality), fica **negativo** no MAD (sinal de continuação num mundo de reversão) e o **blend supera os componentes** (t5 = 37 vs 33/20) com autocorrelação menor — a diversificação K/ρ observada na prática. **Números do sintético não são expectativa real; a seleção acontece nos dados reais.**

O score vira retorno esperado via `alpha = z · alpha_bps_per_z · horizon_days`. O `horizon_days` corrige a **miopia do otimizador de 1 período**: a posição rende alfa por ~4 dias até ser desmontada, e é esse acumulado que compete com o custo de entrada (pago uma vez). Sem isso, o otimizador compara 1 dia de alfa com o custo cheio do trade e simplesmente não opera (constatado empiricamente: gross de 10% vs. ~50% do book).

### Etapa 4 — Risco (`risk/covariance.py`)

Covariância **fatorada**: Σ = B·F·B′ + D (F = cov 252d dos 6 fatores; D = diag das vols idio). Nunca formamos a matriz N×N: com N ≈ 2000 e T = 252, a covariância amostral é singular e ruidosa (T < N). No otimizador o risco entra como `‖chol(F)′·B′·w‖² + ‖ivol ∘ w‖²` — compacto e bem-condicionado.

### Etapa 5 — Otimizador (`portfolio/optimizer.py`)

A cada rebalanceamento, resolve-se (w em frações do book bruto G = $1 bi):

```
max_w   α′w  −  λ·(‖F½B′w‖² + ‖ivol∘w‖²)  −  custo_AC(w − w_prev)

s.a.    |Σw|      ≤ 0.002        dollar-neutral (~$500mm por perna)
        ‖w‖₁     ≤ 1             orçamento bruto ($1 bi)
        |B′w|     ≤ 0.02          neutralidade por fator (FF5+MOM)
        |w_i|     ≤ min(0.5%, 1×ADVᵢ/G)     concentração + liquidez
        |Δw_i|    ≤ 5%·ADVᵢ/G     participação diária no volume
```

Tudo convexo ⇒ solução global única (cvxpy; solvers Clarabel → ECOS → SCS em cascata). Detalhes de robustez: objetivo reescalado ×1000 (alfa ~1e-3 vs. restrições ~1.0 degradava a precisão numérica); tolerâncias adaptativas de net/fator garantem factibilidade quando o universo muda (deslistamentos); se nenhum solver converge, mantém-se o portfólio anterior.

**As restrições de fator são a tese de risco do projeto**: não queremos ser pagos por carregar mercado, size, value ou momentum — queremos alfa idiossincrático puro. O book resultante é ~zero-beta em tudo.

### Etapa 6 — Custos de execução (`costs/almgren_chriss.py`)

Custo de negociar `dw` (fração de G) em um nome, no espírito de Almgren-Chriss:

```
custo(dw) = spread·|dw|                                  (5 bps: meio-spread + taxas)
          + η·σ·√(G/ADV)·|dw|^1.5                        (impacto TEMPORÁRIO, lei da √)
          + ½·γ·σ·(G/ADV)·dw²                            (impacto PERMANENTE)
```

O mesmo modelo aparece **duas vezes**: como penalidade dentro do otimizador (o portfólio nasce ciente do próprio footprint e negocia devagar por conta própria) e como débito realizado no backtest. Essa consistência é deliberada — num book de $1 bi em small caps, impacto é a restrição econômica dominante, não um detalhe.

### Etapa 7 — Execução e convenção temporal (anti-lookahead)

```
close de t   : sinal calculado com dados ≤ t → otimizador → pesos-alvo
close de t+1 : ordens MOC executadas; custos debitados
t+1 → t+2    : nova posição começa a acruar P&L
```

Sinal calculado com o close de *t* e executado no close de *t* seria lookahead (o sinal usa o próprio preço de execução). O lag de 1 dia é conservador e defensável perante a banca. *Lição registrada:* essa convenção interage com a velocidade do alfa — um sinal cuja previsibilidade morre em 1 dia não sobrevive ao lag (descoberto na primeira versão do gerador sintético e corrigido: reversão real de small caps decai ao longo de dias, não horas).

### Etapa 8 — Hedge (`engine._rehedge`)

Dollar-neutral ≠ beta-neutral. Após cada rebalanceamento, o beta de mercado residual do book (já limitado a ±0.02 pelo otimizador) é zerado com uma posição em IWM (ETF do próprio Russell 2000, ADV enorme ⇒ custo desprezível). Cinto e suspensório: a restrição controla, o hedge apara o resíduo.

### Etapa 9 — Motor de backtest (`backtest/engine.py`)

Loop diário event-driven **implementado pela equipe** (exigência expressa do edital — FAQ 15): P&L por perna (long/short/hedge) → execuções agendadas → decisão do dia. Nomes deslistados com posição aberta são encerrados a custo zero (aproximação documentada). Saídas: série diária de P&L bruto/líquido, custos decompostos (spread × impacto), gross/net, turnover, nº de posições, exposições a fatores, e o histórico de pesos-alvo (usado no crosscheck).

**Validação independente** (`scripts/03_bt_crosscheck.py`): os mesmos pesos-alvo são reproduzidos dentro da biblioteca `bt` (pmorissette/bt, indicada pelo orientador) com custo linear. Resultado: correlação **0.9964** entre os retornos diários, diferença média de **0.42 bps/dia** — a contabilidade do motor está certa por verificação externa.

### Etapa 10 — Métricas e tearsheet (`backtest/metrics.py`)

`reports/`: `metrics.md`/`.json` (Sharpe bruto/líquido, Sortino, max drawdown, turnover, custos em bps/ano, hit rate, exposições máximas...) e 5 gráficos: P&L acumulado bruto×líquido, drawdown, exposição a fatores no tempo (a prova visual da neutralidade), turnover×custos, Sharpe rolling 63d.

---

## 4. Resultado da validação de ponta a ponta (dados sintéticos)

Rodada 2020–2024, 300 ações, sinal placeholder sobre reversão plantada:

| Métrica | Valor | Leitura |
|---|---:|---|
| Sharpe bruto / líquido | 12.4 / 10.0 | Pipeline **recupera o alfa plantado** (nº de laboratório, não expectativa real!) |
| Retorno bruto / líquido | 14.9% / 12.0% a.a. | Custos comem 288 bps/ano — realismo do AC funcionando |
| Gross médio | 49% do book | Equilíbrio alfa × custo × risco emerge da otimização |
| |Net| máximo | 0.2% | Dollar-neutrality efetiva |
| Exposição máx. a fator | 0.022 | Neutralidade FF5+MOM efetiva |
| Turnover | 12.8× /ano | Coerente com reversão de ~4 dias de horizonte |
| Testes de sanidade | 4/4 | Neutralidade, convexidade de custos, anti-lookahead, smoke |
| Crosscheck bt | corr 0.9964 | Contabilidade validada por biblioteca externa |

**Interpretação honesta:** esses números provam que a *esteira* funciona (captura alfa conhecido, respeita mandato, debita custos, hedgeia). Não dizem nada sobre desempenho em dados reais — isso depende do sinal que será plugado.

---

## 5. Passagem para dados reais (Bloomberg) — checklist

1. Na máquina com terminal: `pip install blpapi xbbg` (índice pip da Bloomberg — instruções no `requirements.txt`);
2. Rodar `scripts/01_pull_bloomberg.py` **uma vez** (atenção ao limite mensal de dados do terminal; tudo fica cacheado em parquet);
3. `config.yaml`: `data.source: bloomberg`, ajustar `data.start/end` e `backtest.start/end`;
4. Rodar `scripts/02_run_backtest.py` e `03_bt_crosscheck.py`;
5. Sanidade nos dados reais: cobertura de tickers deslistados, buracos de TRI, ADV zero — o `universe.py` filtra, mas medir a cobertura é parte da análise de vieses do relatório.

## 6. Limitações conhecidas (material para o relatório)

- **Financiamento não modelado**: custo de aluguel das pontas short e rebate de caixa ignorados (típico 25–50 bps/ano em small caps líquidas; hard-to-borrow pode ser mais). Próximo passo natural.
- **Deslistamento a custo zero**: aproximação; com TRI da Bloomberg o último preço negociado é capturado, mas o dia exato da saída pode carregar gap.
- **Betas mensais**: entre re-estimações, a exposição real deriva um pouco do limite de ±0.02 (observado máx. 0.022) — o hedge IWM apara o resíduo de mercado, os demais fatores ficam ~0.02.
- **Custos calibrados por literatura** (η=0.5, γ=0.05, spread 5 bps): calibração fina com dados reais de spread/ADV do universo é próximo passo.
- **Otimizador míope com correção heurística** (`horizon_days`): a solução rigorosa é otimização multi-período (Gârleanu-Pedersen) — bom "próximos passos" para o relatório.

## 7. Mapa pipeline → critérios de avaliação do desafio

| Critério (peso) | Onde o pipeline entrega |
|---|---|
| Conceito (20%) | Tese de provisão de liquidez + neutralidade fatorial (seções 3.3, 3.5) |
| Modelagem (20%) | Formulação convexa completa com mandato explícito (seção 3.5) |
| Backtest (15%) | Motor próprio + point-in-time + anti-lookahead + crosscheck externo (3.7, 3.9) |
| Análise (15%) | Tearsheet com decomposição de custos e prova de neutralidade (3.10) |
| Conclusão (10%) | Limitações documentadas + evoluções concretas (seção 6) |
| GenAI (15%) | `docs/genai_log.md` — usos concretos com impacto prático |
| Robô (5%) | Pendente — branding na fase de relatório |
