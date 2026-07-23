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
# dados: composicao as-of + precos/volume/abertura + mcap/setor (uma vez)
& $py scripts\07_pull_sp500_asof.py
& $py scripts\07b_add_marketcap_sp500.py
& $py scripts\07c_add_open_sp500.py

# pesquisa de sinais: funil (IC/quintis, splits dev/val) e correlacoes p/ blend
& $py scripts\04_signal_funnel.py resid_ou --data processed_sp500
& $py scripts\09_blend_analysis.py --data processed_sp500

# BACKTEST OFICIAL (dev+val 2020-2023; holdout 2024+ trancado)
& $py scripts\02_run_backtest.py --data processed_sp500 --bt-end 2023-12-31 --tag sp500_dev_val

# notebook explicativo (gera + executa com graficos)
& $py scripts\05_build_walkthrough.py

# testes de sanidade (anti-lookahead de 9 sinais, neutralidades, custos)
& $py -m pytest tests -q
```

## Estrutura

```
config/config.yaml    <- TODOS os parametros (sinal ativo, mandato, custos, splits)
statarb/              <- pacote: data, factors, signals (11 plug-ins), risk, costs,
                         portfolio (otimizador), backtest (motor proprio)
scripts/              <- 00 sintetico | 02 backtest | 04 funil | 05 notebook
                         07x painel S&P500 as-of | 08 estudo deslistadas | 09 blend
notebooks/            <- pipeline_walkthrough.ipynb (documento vivo) + doubts.md
docs/                 <- genai_log.md | arquivo/ (documentos historicos)
considerações/        <- justificativas metodologicas (universo, vieses)
data/ reports/        <- gerados pelos scripts (fora do git)
```

## Decisões-chave (não reabrir sem motivo novo)

1. **Universo S&P 500 as-of** — R2000 gratuito tem survival bias severo (medido:
   18% de cobertura das deslistadas vs 92%); ver `considerações/`.
2. **Sinal único `resid_ou`** — funil de 11 candidatos: é o único com IC robusto
   nos dois splits; blend testado 2× e descartado (não agrega).
3. **Sem Bloomberg** até etapas futuras do desafio — fontes: Wikipedia/fja05680
   (membership), yfinance (preços), Ken French (fatores), Nasdaq screener (mcap/setor).
