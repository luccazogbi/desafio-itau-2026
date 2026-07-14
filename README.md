# StatArb L/S Russell 2000 — Desafio Quant AI 2026 (Itaú Asset)

Estratégia de arbitragem estatística long-short em small caps americanas:
book de **$1 bi** dollar-neutral ($500mm por perna), neutro aos fatores
**FF5 + Momentum**, com otimização convexa (**cvxpy**), custos de execução
**Almgren-Chriss** e hedge de beta residual com **IWM**.

> Documentação completa do funcionamento: [docs/PIPELINE.md](docs/PIPELINE.md)
> **Walkthrough didático com gráficos**: [notebooks/pipeline_walkthrough.ipynb](notebooks/pipeline_walkthrough.ipynb)
>   (gerado por `scripts/05_build_walkthrough.py`; abrir com o kernel "Python (QuantAI 2026)")
> Log de uso de IA Generativa (critério de 15% do desafio): [docs/genai_log.md](docs/genai_log.md)
> Lista de tarefas viva: [roadmap.md](roadmap.md)

## Ambiente (importante)

O projeto vive em pasta sincronizada pelo OneDrive; o venv fica **fora** dela
(`C:\Users\<user>\.venvs\quant_ai_2026`) — venv dentro de pasta sincronizada
corrompe (o OneDrive mexe nos milhares de arquivos do ambiente).

```powershell
# atalho usado nos comandos abaixo
$py = "$env:USERPROFILE\.venvs\quant_ai_2026\Scripts\python.exe"

# 1. ambiente (uma vez)
python -m venv $env:USERPROFILE\.venvs\quant_ai_2026
& $py -m pip install -r requirements.txt

# 2. dados sinteticos (validacao do pipeline; Bloomberg vem depois)
& $py scripts\00_make_synthetic.py

# 3. backtest completo + tearsheet em reports/  (~4 min)
& $py scripts\02_run_backtest.py

# 4. validacao cruzada do P&L com a biblioteca bt
& $py scripts\03_bt_crosscheck.py

# testes de sanidade (anti-lookahead, neutralidade, custos)
& $py -m pytest tests -q
```

## Com dados reais (na máquina com terminal Bloomberg)

```powershell
& $py -m pip install blpapi --index-url=https://blpapi.bloomberg.com/repository/releases/python/simple/
& $py -m pip install xbbg
& $py scripts\01_pull_bloomberg.py    # grava o schema canonico em data/processed
# depois: data.source: bloomberg no config/config.yaml e rodar o backtest
```

## Estrutura

```
config/config.yaml    <- todos os parametros do projeto
statarb/              <- pacote: data, factors, signals, risk, costs, portfolio, backtest
scripts/              <- 00 sintetico | 01 bloomberg | 02 backtest | 03 crosscheck bt
tests/                <- sanidade: neutralidade, convexidade, anti-lookahead, smoke
docs/                 <- PIPELINE.md (funcionamento) + genai_log.md
reports/              <- metricas, graficos, pesos-alvo (gerados)
```

## Trocar o sinal (o plug-in do pipeline)

1. Criar `statarb/signals/meu_sinal.py` com uma subclasse de `Signal`;
2. Registrar em `statarb/signals/__init__.py`;
3. Apontar `signal.name` no `config/config.yaml`.

Nada mais muda — otimizador, custos, hedge e backtest são agnósticos ao sinal.
