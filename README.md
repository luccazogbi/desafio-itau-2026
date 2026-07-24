# StatArb L/S no S&P 500 as-of — Desafio Quant AI 2026 (Itaú Asset)

Arbitragem estatística *long-short* no **S&P 500 com composição histórica as-of**
(sem viés de sobrevivência): book de **$1 bi dollar-neutral** (~$500mm por perna),
neutro aos fatores **FF5+Momentum** e a **setores**, otimização convexa (**cvxpy**),
custos de execução **Almgren-Chriss**, hedge de beta com **SPY**.

**Sinal oficial:** `resid_ou` — reversão à média do resíduo idiossincrático
(Avellaneda & Lee, 2010), escolhido por evidência num funil de 11 candidatos
com splits dev/validação/holdout.

> 📓 **Documento vivo do projeto**: [notebooks/pipeline_walkthrough.ipynb](notebooks/pipeline_walkthrough.ipynb)
> (passo a passo com gráficos; kernel "Python (QuantAI 2026)"; dúvidas em `notebooks/doubts.md`)
> 📋 Tarefas: [roadmap.md](roadmap.md) · 🤖 Log de GenAI (15% da nota): [docs/genai_log.md](docs/genai_log.md)
> 📤 Enviar para o GitHub: [COMO_ENVIAR_GITHUB.md](COMO_ENVIAR_GITHUB.md)
> ⚖️ Por que S&P 500 e não Russell 2000: [considerações/](considerações/)

## Ambiente

Venv **fora** da pasta do projeto (evita corrupção por sync):

```powershell
$py = "$env:USERPROFILE\.venvs\quant_ai_2026\Scripts\python.exe"
# setup (uma vez): python -m venv $env:USERPROFILE\.venvs\quant_ai_2026
#                  & $py -m pip install -r requirements.txt
```

## Fluxo de trabalho (dados reais, S&P 500 as-of)

```powershell
# dados: composicao as-of + precos/volume/abertura/max-min + mcap/setor (uma vez)
& $py scripts\07_pull_sp500_asof.py
& $py scripts\07b_add_marketcap_sp500.py
& $py scripts\07c_add_open_sp500.py
& $py scripts\07d_add_highlow_sp500.py

# CONGELA o painel: sem isso, repuxar muda o universo historico e o backtest
# deixa de ser reproduzivel entre execucoes (ver results/04)
& $py scripts\16_snapshot_panel.py

# auditoria do painel: cruza 2 fontes de membership e classifica o gap de precos
& $py scripts\13_membership_audit.py

# auditoria do deslistamento: o backtest chega a viver algum? (roda apos o 02)
& $py scripts\17_delisting_audit.py

# calibracao do modelo de custo com ADV/vol reais (spread por Corwin-Schultz)
& $py scripts\14_cost_calibration.py

# pesquisa de sinais: funil (IC/quintis, splits dev/val) e correlacoes p/ blend
& $py scripts\04_signal_funnel.py resid_ou
& $py scripts\09_blend_analysis.py

# BACKTEST OFICIAL (dev+val 2020-2023). O holdout e trancado PELO CONFIG:
# backtest.end = 2023-12-31 e o motor RECUSA passar de holdout_start sem flag.
& $py scripts\02_run_backtest.py --tag sp500_dev_val

# notebook explicativo (gera + executa com graficos)
& $py scripts\05_build_walkthrough.py

# testes de sanidade (20: anti-lookahead de 9 sinais, neutralidades, custos,
#                     trava do holdout, aluguel do short, Newey-West,
#                     Garleanu-Pedersen, snapshot)
& $py -m pytest tests -q
```

## Resultado atual (dev+val 2020-2023, holdout trancado)

| | |
|---|---:|
| Sharpe bruto / líquido | **+0,51 / +0,16** |
| Retorno líquido | +0,96% a.a. (sobre o gross) |
| Custos | 211 bps/ano (impacto 60% · spread 30% · aluguel do short 9%) |
| Turnover | 15,6× /ano (one-way) |
| Max drawdown | −11,3% |
| Snapshot do painel | `2026-07-23` |

Diagnóstico completo em [`results/01`](results/01_analise_backtest_dev_val.md). A curva de
capacidade ([`results/02`](results/02_analise_capacidade.md)) mostra **0,33 em $100mm** —
o mandato de $1 bi opera acima do tamanho ótimo da estratégia.

## Estrutura

```
config/config.yaml    <- TODOS os parametros (sinal ativo, mandato, custos, splits)
statarb/              <- pacote: data, factors, signals (11 plug-ins), risk, costs,
                         portfolio (otimizador), backtest (motor proprio), stats
scripts/              <- 00 sintetico | 02 backtest | 04 funil | 05 notebook
                         07x painel S&P500 as-of | 08 estudo deslistadas | 09 blend
                         10 kappa | 11 capacidade | 12 regime | 13 auditoria as-of
                         14 calibracao de custos | 15 Garleanu-Pedersen
                         16 snapshot do painel | 17 auditoria de deslistamento
                         legados: 01 Bloomberg (aguarda acesso) | 03 crosscheck bt
                                  06 proxy R2000 (substituido pelo 07)
snapshots/            <- manifestos (hash SHA-256 de cada parquet) -- VERSIONADOS.
                         As copias dos dados ficam em data/snapshots/ (fora do git)
notebooks/            <- pipeline_walkthrough.ipynb (documento vivo) + doubts.md
results/              <- analises interpretadas (01 backtest | 02 capacidade
                         03 regime | 04 auditoria de membership | 05 custos
                         06 multi-periodo GP vs heuristica | 07 elevar o Sharpe
                         08 deslistamento ausente no backtest)
docs/                 <- genai_log.md | arquivo/ (documentos historicos)
considerações/        <- justificativas metodologicas (universo, vieses)
data/ reports/        <- gerados pelos scripts (fora do git)
```

## Decisões-chave (não reabrir sem motivo novo)

1. **Universo S&P 500 as-of** — R2000 gratuito tem survival bias muito mais severo: das
   ações **removidas** do índice, só **18%** têm preço no R2000 contra **46%** no S&P 500;
   ver `considerações/`.
2. **Sinal único `resid_ou`** — funil de 11 candidatos: é o melhor, com IC positivo e
   consistente nos dois splits (IC21 0,051 dev / 0,036 val). Com t-stat corrigido por
   Newey-West: **t = 2,50 dev / 1,66 val** — o dev é significativo, a validação não
   chega a 2. Blend testado 2× e descartado (não agrega).
3. **Sem Bloomberg** até etapas futuras do desafio — fontes: Wikipedia/fja05680
   (membership), yfinance (preços), Ken French (fatores), Nasdaq screener (mcap/setor).

## Limitações conhecidas (medidas, não escondidas)

| Limitação | Tamanho | Onde está documentada |
|---|---|---|
| Deslistadas sem preço no yfinance | **6,8%** dos meses-membro | `results/04` |
| Universo de 2020-23 erodido por M&A de 2024-26 | **3,5%** e **crescendo** | `results/04` |
| **Viés de DESFECHO** — o backtest processa **zero** deslistamentos; 36 das 68 saídas do índice em 2020-23 não têm preço algum | **não corrigível** no gratuito | **`results/08`** |
| Reprodutibilidade entre execuções | resolvida por **snapshot** (`scripts/16`) | `results/04` §6 |
| Setor e market cap vêm do screener de **hoje** | look-ahead brando | `scripts/07b` |
| Deslistagem sem perda terminal | limitação **vazia**: o caminho nunca é executado | `results/08` |
| Validação independente da composição | **em aberto** (S&P bloqueia acesso) | `results/04` |
| Números 18%/46% do estudo de deslistadas | **não re-deriváveis** hoje (`scripts/08` depende de um pickle que nenhum script gera) | `considerações/` |
| `horizon_days = 21` não é validado pela meia-vida medida | a medição não é independente (janela de 60d) | `results/06` §2 |
