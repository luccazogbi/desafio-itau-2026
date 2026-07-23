# Análise de capacidade — o tamanho do book é uma decisão de desenho

> **Pergunta:** no book oficial de $1 bi, custos comem 63% do alfa. Quanto sobreviveria
> em books menores? **Método:** o backtest **completo foi re-rodado** em 5 tamanhos
> (não é aproximação de escala — o otimizador reage ao tamanho: caps de liquidez e
> penalidade de impacto mudam as decisões). Janela dev+val; holdout trancado.
> **Artefatos:** `reports/capacity_analysis.md` / `.png` / `.parquet` · `scripts/11_capacity_analysis.py`

## 1. A curva medida

| Book | Sharpe bruto | **Sharpe líquido** | Ret. líq. a.a. | P&L líq. 2020–23 | Custos (bps/ano) |
|---:|---:|---:|---:|---:|---:|
| **$100mm** | 0,64 | **0,37** | 2,3% | $9,2mm | 165 |
| $200mm | 0,62 | 0,33 | 2,0% | $16,2mm | 175 |
| $300mm | 0,60 | 0,30 | 1,8% | $22,0mm | 181 |
| $500mm | 0,56 | 0,25 | 1,5% | $30,6mm | 189 |
| $1.000mm (oficial) | 0,53 | 0,20 | 1,2% | $47,2mm | 198 |

## 2. Três leituras

**a) A capacidade é finita e a curva é monotônica.** Cada dólar adicional de book
degrada o Sharpe — de 0,37 ($100mm) para 0,20 ($1bi). Até o Sharpe **bruto** melhora
em books menores (0,64 vs 0,53): com mais folga nos caps de liquidez, o otimizador
aloca melhor.

**b) Mas o trade-off Sharpe × dinheiro é real.** Em dólares, o book de $1bi ainda gera
mais P&L absoluto ($47mm vs $9mm). O "tamanho ótimo" depende do objetivo: um fundo
que cobra performance sobre retorno quer Sharpe (book menor); um proprietário de capital
pode preferir o P&L. Para o desafio, a resposta defensável é: **a estratégia como
desenhada suporta ~$100–300mm com Sharpe respeitável; o mandato de $1 bi está acima
da capacidade do sinal**.

**c) O piso de custo agora é o SPREAD, não o impacto.** Note que os custos caem pouco
(198→165 bps) ao encolher o book 10×. Motivo: com turnover ~15–20×/ano, o spread fixo
de 5 bps por trade cria um piso de ~100 bps/ano **independente do tamanho**. Implicação:
em books pequenos, a alavanca de melhoria não é mais reduzir impacto — é **reduzir
giro** (rebalanceamento mais espaçado, bandas de no-trade).

## 3. Conexão com a análise de regime

A análise de regime (`results/03`) mostrou que o IC é ~zero em vol baixa. Combinando as
duas: **parte relevante do turnover atual acontece em regimes onde não há alfa a
capturar** — giramos e pagamos spread em mercados calmos por nada. A evolução natural
(proposta, não implementada — seria overfitting retro-ajustar): condicionar gross e
frequência de rebalanceamento ao regime de volatilidade.

## 4. Frase para o relatório

> *"O sinal tem alfa real (Sharpe bruto 0,53–0,64), mas capacidade finita: o mandato de
> $1 bi opera acima do tamanho ótimo da estratégia, e a curva de capacidade medida
> aponta $100–300mm como faixa sustentável. Reconhecer o limite de capacidade de uma
> estratégia é parte do desenho — não uma fraqueza."*
