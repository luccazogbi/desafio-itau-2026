# Análise de capacidade — o tamanho do book é uma decisão de desenho

> **Pergunta:** no book oficial de $1 bi, custos comem 63% do alfa. Quanto sobreviveria
> em books menores? **Método:** o backtest **completo foi re-rodado** em 5 tamanhos
> (não é aproximação de escala — o otimizador reage ao tamanho: caps de liquidez e
> penalidade de impacto mudam as decisões). Janela dev+val; holdout trancado.
> **Artefatos:** `reports/capacity_analysis.md` / `.png` / `.parquet` · `scripts/11_capacity_analysis.py`

## 1. A curva medida

> **Atualizada em 23/07/2026** — regerada após as correções de 22/07 (aluguel de short,
> restrição setorial ativa, painel com renomeações corrigidas) e a calibração de custos.

| Book | Sharpe bruto | **Sharpe líquido** | Ret. líq. a.a. | P&L líq. 2020–23 | Custos (bps/ano) | Turnover |
|---:|---:|---:|---:|---:|---:|---:|
| **$100mm** | 0,61 | **0,33** | 2,1% | $8,3mm | 174 | 20,8× |
| $200mm | 0,59 | 0,29 | 1,8% | $14,6mm | 185 | 19,3× |
| $300mm | 0,57 | 0,26 | 1,6% | $19,7mm | 192 | 18,4× |
| $500mm | 0,54 | 0,22 | 1,3% | $26,6mm | 200 | 17,2× |
| $1.000mm (oficial) | 0,51 | **0,16** | 1,0% | $38,3mm | 211 | 15,6× |

*Curva anterior (15/07, antes das correções): 0,37 → 0,20. O nível caiu ~0,04 em toda a
curva, dominado pela restrição setorial que passou a ser aplicada de fato — a **forma**
monotônica, que é a conclusão, não mudou.*

## 2. Três leituras

**a) A capacidade é finita e a curva é monotônica.** Cada dólar adicional de book
degrada o Sharpe — de 0,33 ($100mm) para 0,16 ($1bi). Até o Sharpe **bruto** melhora
em books menores (0,61 vs 0,51): com mais folga nos caps de liquidez, o otimizador
aloca melhor.

**b) Mas o trade-off Sharpe × dinheiro é real.** Em dólares, o book de $1bi ainda gera
mais P&L absoluto ($38mm vs $8mm). O "tamanho ótimo" depende do objetivo: um fundo
que cobra performance sobre retorno quer Sharpe (book menor); um proprietário de capital
pode preferir o P&L. Para o desafio, a resposta defensável é: **a estratégia como
desenhada suporta ~$100–300mm com Sharpe respeitável; o mandato de $1 bi está acima
da capacidade do sinal**.

**c) O piso de custo agora é o SPREAD, não o impacto.** Note que os custos caem pouco
(211→174 bps) ao encolher o book 10×. Motivo: com turnover ~16–21×/ano, o spread de
4 bps por trade cria um piso de ~80 bps/ano **independente do tamanho** — e o giro
até **aumenta** em books pequenos (15,6× → 20,8×), porque os caps de liquidez soltam.
Implicação: em books pequenos, a alavanca de melhoria não é mais reduzir impacto — é
**reduzir giro** (rebalanceamento mais espaçado, bandas de no-trade).

> `results/06` dá o mecanismo por trás disso: a heurística do `horizon_days` **reage ~6×
> demais ao sinal** frente ao ótimo multi-período de Gârleanu-Pedersen (`H` implícito 3,7
> vs 21). E como o spread responde por **45%** do custo no trade típico, a implementação
> teoricamente correta não é mexer no `horizon_days` — é uma **banda de não-negociação**,
> que é a política que custo linear gera. É a implementação natural desta recomendação.

## 3. Conexão com a análise de regime

A análise de regime (`results/03`) mostrou que o IC é ~zero em vol baixa. Combinando as
duas: **parte relevante do turnover atual acontece em regimes onde não há alfa a
capturar** — giramos e pagamos spread em mercados calmos por nada. A evolução natural
(proposta, não implementada — seria overfitting retro-ajustar): condicionar gross e
frequência de rebalanceamento ao regime de volatilidade.

## 4. Frase para o relatório

> *"O sinal tem alfa real (Sharpe bruto 0,51–0,61), mas capacidade finita: o mandato de
> $1 bi opera acima do tamanho ótimo da estratégia, e a curva de capacidade medida
> aponta $100–300mm como faixa sustentável. Reconhecer o limite de capacidade de uma
> estratégia é parte do desenho — não uma fraqueza."*
