# JANUS — arbitragem estatística long-short no S&P 500

Projeto desenvolvido em equipe para o **Desafio Quant AI 2026 da Itaú Asset**: pesquisa, construção e backtest de uma estratégia de arbitragem estatística *long-short* sobre
o **S&P 500 com composição histórica as-of** (sem viés de sobrevivência).

| | |
|---|---|
| Book | US$ 1 bi, *dollar-neutral* (~US$ 500 mm por perna) |
| Neutralidade | fatores Fama-French 5 + Momentum, setores e beta (hedge com SPY) |
| Sinal | `resid_ou` — reversão à média do resíduo idiossincrático (Avellaneda & Lee, 2010) |
| Carteira | otimização convexa (CVXPY) com limites de concentração e de liquidez |
| Custos | spread + impacto de mercado Almgren-Chriss + aluguel da perna vendida |
| Protocolo | splits de desenvolvimento (2020-22), validação (2023) e holdout (2024-26) trancado no código |

## Resultado: o sinal foi reprovado no holdout

O holdout foi lacrado antes de qualquer resultado ser conhecido e aberto **uma única vez**
(07/08/2026). O sinal não sobreviveu:

| | dev+val (2020-23) | **Holdout (2024-26)** |
|---|---:|---:|
| Sharpe bruto | +0,57 | **−0,77** |
| Sharpe líquido | +0,27 | **−1,15** |
| Retorno líquido a.a. | +1,49% | **−5,09%** |
| IC do sinal (21 dias) | +0,036 (validação) | **−0,030** |

**O sinal não parou de funcionar — ele inverteu.** O Sharpe bruto também é negativo, então
não é problema de custo ou de execução. A defesa natural ("o holdout foi um período calmo")
foi testada e não se sustenta: o IC é negativo nos três regimes de volatilidade, inclusive no
de vol alta, onde a tese previa que o sinal fosse mais forte. O dado também não explica a
perda: a cobertura de preços no holdout é melhor (97,6% contra 92,8%).

Em retrospecto, o aviso já estava na validação: estatística t de Newey-West de 1,66, abaixo
de 2. O que este repositório entrega é a **infraestrutura de pesquisa e o protocolo que
detectou o sobreajuste** — não uma estratégia que funciona. Veredito completo em
[`results/09`](results/09_holdout_o_veredito.md).

## Como a estratégia funciona

1. **Universo** — membros do S&P 500 em cada data (composição as-of), com filtros de preço,
   liquidez e histórico mínimo. Por que S&P 500 e não Russell 2000: [`considerações/`](considerações/).
2. **Modelo de fatores** — betas em janela móvel contra FF5 + Momentum; o resíduo de cada ação
   é a parte do retorno que os fatores não explicam.
3. **Sinal** — o resíduo acumulado em 60 dias é padronizado contra o histórico da própria ação
   (252 dias): acúmulo anormalmente alto vira venda, anormalmente baixo vira compra. O sinal
   foi escolhido num funil de 11 candidatos da literatura, avaliados por IC e spread entre
   quintis em dev e validação (`scripts/04_signal_funnel.py`).
4. **Carteira** — otimização convexa que maximiza alfa menos risco e custo, com neutralidade de
   dólar (±0,2% do book), de fatores (±2% por fator) e de setores (±5%), no máximo 0,5% do
   book por ação, posição até 1× o volume médio diário e negociação até 5% dele.
5. **Execução e custos** — sinal no fechamento de *t*, execução no fechamento de *t+1*;
   rebalanceamento a cada 10 dias úteis; custo por negociação com spread medido e impacto
   de Almgren-Chriss.
6. **Backtest** — motor *event-driven* próprio, com P&L por perna (long, short, hedge) e
   custos decompostos.

## Destaques

| Documento | O que mostra |
|---|---|
| [`results/09`](results/09_holdout_o_veredito.md) | A ida única ao holdout e o diagnóstico (regime × decaimento) |
| [`results/05`](results/05_calibracao_custos.md) | Calibração de custos: o spread foi medido (Corwin-Schultz); os dois coeficientes de impacto **não são identificáveis** com dados diários, e isso foi demonstrado, não assumido |
| [`results/06`](results/06_gp_multiperiodo_vs_heuristica.md) | Solução multiperíodo de Gârleanu-Pedersen, derivada em código, contra a regra heurística de rebalanceamento |
| [`results/02`](results/02_analise_capacidade.md) | Capacidade: o backtest completo refeito em cinco tamanhos de book |
| [`results/04`](results/04_auditoria_membership_e_cobertura.md) e [`results/08`](results/08_deslistamento_ausente_no_backtest.md) | Auditoria da composição as-of e do deslistamento |
| [`notebooks/pipeline_walkthrough.ipynb`](notebooks/pipeline_walkthrough.ipynb) | Passo a passo do pipeline, com gráficos |

## Rigor e reprodutibilidade

- **Holdout trancado no código:** `backtest.end` termina em 2023 e o motor recusa passar de
  `holdout_start` sem a flag `--allow-holdout`.
- **20 testes automatizados** (`tests/`): ausência de look-ahead em 9 sinais, neutralidades e
  limites do otimizador, convexidade dos custos, trava do holdout, aluguel do short,
  Newey-West, Gârleanu-Pedersen e snapshot.
- **Snapshots do painel** com hash SHA-256 (`snapshots/`): cada número dos relatórios fica
  amarrado a um estado de dados identificável.
- **Limitações medidas, não escondidas** — tabela abaixo.

## Como reproduzir

Os dados não são versionados (~150 MB); os scripts os baixam de fontes gratuitas:
composição do índice (Wikipedia / fja05680), preços (yfinance), fatores (Ken French) e
market cap e setor (Nasdaq screener).

```bash
python -m venv .venv
.venv/Scripts/activate        # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# painel S&P 500 as-of e congelamento (snapshot)
python scripts/07_pull_sp500_asof.py
python scripts/07b_add_marketcap_sp500.py
python scripts/07c_add_open_sp500.py
python scripts/07d_add_highlow_sp500.py
python scripts/16_snapshot_panel.py

# calibração de custos, funil de sinais e backtest dev+val
python scripts/14_cost_calibration.py
python scripts/04_signal_funnel.py
python scripts/02_run_backtest.py --tag sp500_dev_val

# holdout (já gasto em 07/08/2026; reproduz o veredito)
python scripts/02_run_backtest.py --tag holdout --bt-start 2024-01-02 --bt-end 2026-05-29 --allow-holdout
python scripts/19_holdout_diagnostico.py

# testes
python -m pytest tests -q
```

Todos os parâmetros (sinal ativo, mandato, custos, splits) ficam em
[`config/config.yaml`](config/config.yaml).

## Estrutura

```
config/          parâmetros do projeto
statarb/         pacote: data, factors, signals (11 plug-ins), risk, costs,
                 portfolio (otimizador + Gârleanu-Pedersen), backtest, stats
scripts/         00-20: painel, funil, backtest, auditorias, análises e relatório
tests/           testes de sanidade (pytest)
results/         análises interpretadas, 01 a 09
notebooks/       walkthrough do pipeline
snapshots/       manifestos SHA-256 do painel
considerações/   justificativas metodológicas (universo, vieses)
docs/            conceitos, log de uso de IA generativa, roadmap e histórico
```

## Limitações conhecidas

| Limitação | Tamanho | Onde |
|---|---|---|
| Deslistadas sem preço no yfinance | 6,8% dos meses-membro | `results/04` |
| Universo de 2020-23 erodido por fusões e aquisições de 2024-26 | 3,5% e crescendo | `results/04` |
| Viés de desfecho: o backtest processa zero deslistamentos; 36 das 68 saídas do índice em 2020-23 não têm preço | não corrigível com dados gratuitos | `results/08` |
| Setor e market cap vêm do screener atual | look-ahead brando | `scripts/07b` |
| Validação independente da composição | em aberto | `results/04` |
| Impacto de mercado é custo debitado, não preço realimentado | ignora o auto-impacto permanente entre rebalanceamentos (mitigado pelo teto de 5% do volume) | `docs/conceitos/custos_de_execucao.md` |

## Uso de IA generativa

O edital exigia o uso de IA generativa em pelo menos uma etapa. O registro do que foi feito
com apoio de IA, e do que foi corrigido no caminho, está em
[`docs/genai_log.md`](docs/genai_log.md).
