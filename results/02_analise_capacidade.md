# Análise de capacidade — o tamanho do book é uma decisão de desenho

> **Pergunta:** no book oficial de $1 bi, custos comem 63% do alfa. Quanto sobreviveria
> em books menores? **Método:** o backtest **completo foi re-rodado** em 5 tamanhos
> (não é aproximação de escala — o otimizador reage ao tamanho: caps de liquidez e
> penalidade de impacto mudam as decisões). Janela dev+val; holdout trancado.
> **Artefatos:** `reports/capacity_analysis.md` / `.png` / `.parquet` · `scripts/11_capacity_analysis.py`

## 1. A curva medida

> **Atualizada em 24/07/2026** — regerada com `rebalance_every_days = 10` (era 3).

| Book | Sharpe bruto | **Sharpe líquido** | Ret. líq. a.a. | P&L líq. 2020–23 | Custos (bps/ano) | Turnover |
|---:|---:|---:|---:|---:|---:|---:|
| **$100mm** | 0,63 | **0,41** | 2,4% | $9,6mm | 125 | 13,6× |
| $200mm | 0,61 | 0,37 | 2,2% | $17,2mm | 137 | 13,0× |
| $300mm | 0,59 | 0,34 | 1,9% | $23,3mm | 145 | 12,5× |
| $500mm | 0,58 | 0,31 | 1,7% | $34,7mm | 156 | 11,9× |
| $1.000mm (oficial) | 0,57 | **0,27** | 1,5% | $59,3mm | 168 | 11,0× |

*Curva anterior (23/07, rebalance de 3 dias): 0,33 → 0,16. O nível subiu ~0,08–0,11 em toda a
curva ao espaçar o rebalanceamento — a **forma** monotônica, que é a conclusão, não mudou.*

> ⚠️ **Todos os pontos herdam a dependência de fase** de ±0,09 medida em `results/07` §2.2.
> A curva serve para ler a **inclinação**, não para cravar o nível de cada ponto.

## 2. Três leituras

**a) A capacidade é finita e a curva é monotônica.** Cada dólar adicional de book
degrada o Sharpe — de 0,41 ($100mm) para 0,27 ($1bi). Até o Sharpe **bruto** melhora
em books menores (0,63 vs 0,57): com mais folga nos caps de liquidez, o otimizador
aloca melhor.

**b) Mas o trade-off Sharpe × dinheiro é real.** Em dólares, o book de $1bi ainda gera
mais P&L absoluto ($59mm vs $10mm). O "tamanho ótimo" depende do objetivo: um fundo
que cobra performance sobre retorno quer Sharpe (book menor); um proprietário de capital
pode preferir o P&L. Para o desafio, a resposta defensável é: **a estratégia como
desenhada suporta ~$100–300mm com Sharpe respeitável; o mandato de $1 bi está acima
da capacidade do sinal**.

**c) A alavanca do giro já foi puxada — e funcionou.** Esta análise, na versão de 23/07,
apontava **reduzir giro** como a alavanca principal. Foi feito: `rebalance_every_days`
passou de 3 para 10 em 24/07, e a curva inteira subiu ~0,08–0,11. É a recomendação desta
seção sendo executada e medida, não uma coincidência.

O que **não** mudou: os custos continuam caindo pouco (168→125 bps) ao encolher o book 10×,
porque o spread cria um piso independente do tamanho e o giro até **aumenta** em books
pequenos (11,0× → 13,6×), quando os caps de liquidez soltam. A próxima alavanca de giro não
é espaçar mais o rebalanceamento — é a **banda de não-negociação** (§ abaixo).

> `results/06` dá o mecanismo por trás disso: a heurística do `horizon_days` **reage ~7×
> demais ao sinal** frente ao ótimo multi-período de Gârleanu-Pedersen (`H` implícito 3,1
> vs 21). E como o spread responde por **35%** do custo no trade típico, a implementação
> teoricamente correta não é mexer no `horizon_days` — é uma **banda de não-negociação**,
> que é a política que custo linear gera. É a implementação natural desta recomendação.

## 3. Conexão com a análise de regime

A análise de regime (`results/03`) mostrou que o IC é ~zero em vol baixa. Combinando as
duas: **parte relevante do turnover atual acontece em regimes onde não há alfa a
capturar** — giramos e pagamos spread em mercados calmos por nada. A evolução natural
(proposta, não implementada — seria overfitting retro-ajustar): condicionar gross e
frequência de rebalanceamento ao regime de volatilidade.

## 4. Frase para o relatório

> *"O sinal tem alfa real (Sharpe bruto 0,57–0,63), mas capacidade finita: o mandato de
> $1 bi opera acima do tamanho ótimo da estratégia, e a curva de capacidade medida
> aponta $100–300mm como faixa sustentável. Reconhecer o limite de capacidade de uma
> estratégia é parte do desenho — não uma fraqueza."*
