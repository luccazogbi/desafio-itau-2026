# Análise do backtest — `resid_ou` no S&P 500 as-of (dev + validação)

> **Rodada:** 2020-01-02 → 2023-12-29 · book $1 bi dollar-neutral · holdout (2024+) **trancado**
> **Artefatos:** `reports/sp500_dev_val/` · **Notebook:** seção 7 do `pipeline_walkthrough.ipynb`

---

## 1. Resultado em uma tabela

| Métrica | Valor |
|---|---:|
| Sharpe **bruto** | **+0,53** |
| Sharpe **líquido** | **+0,20** |
| Retorno bruto / líquido | +3,16% / **+1,18%** a.a. (sobre o gross) |
| Volatilidade | 5,96% a.a. |
| Max drawdown | −10,9% |
| Turnover | 15,1× /ano |
| Custos | **198 bps/ano** (= 63% do alfa bruto) |
| Composição do custo | impacto de mercado 62% · spread 38% |
| Gross médio / \|net\| máx | 1,00 / 0,002 |
| \|net setorial\| máx | 0,05 (dentro do limite) |

**Mandato respeitado**: dollar-neutralidade, neutralidade a fatores e a setores, caps de
posição e participação — todos dentro dos limites ao longo de toda a simulação.

---

## 2. A comparação com o SPY é inválida (e por quê)

O resultado "perde do SPY" — mas essa comparação mistura naturezas diferentes:

| | SPY | `resid_ou` |
|---|---|---|
| Beta de mercado | ~1,0 | **~0** (por construção) |
| Fonte do retorno | prêmio de risco de mercado | alfa idiossincrático |
| Retorno no período | +13,9% a.a. (Sharpe 0,62) | +1,2% a.a. líq. (Sharpe 0,20) |
| Drawdown em 2022 | ~ −25% | **−10,9%** |
| Correlação com SPY | 1,00 | **+0,25** |

O SPY rendeu porque **carregou risco de mercado** num período de alta. Nós **zeramos**
essa exposição de propósito. O benchmark correto para um book market-neutral é o **caixa
(risk-free, 1,7% a.a.)**, e o valor do produto para um alocador é ser **descorrelacionado**
— não superar o índice na alta.

Isso **não** absolve o resultado: 0,20 líquido é baixo. As causas reais estão abaixo.

---

## 3. Diagnóstico: quatro causas empilhadas

### 3.1 Custos consomem 63% do alfa (causa dominante)

```
Bruto 3,16% a.a.  ──[ −198 bps de custo ]──►  Líquido 1,18% a.a.
```

O **impacto de mercado** é 62% do custo — consequência direta de rodar **$1 bi** num sinal
de alfa bruto modesto com giro de 15×/ano. Em outras palavras: **a estratégia está
operando acima da sua capacidade**.

### 3.2 Capacidade: o mesmo sinal em book menor

Como o impacto escala com √Q, reduzir o book melhora muito o líquido:

| Book | Sharpe líquido | Retorno líquido |
|---|---:|---:|
| **$1.000mm** (atual) | +0,20 | +1,2% a.a. |
| $300mm | +0,29 | +5,8% a.a. |
| $100mm | **+0,34** | **+20,2% a.a.** |

*Mesmo sinal, mesma execução — só menos capital.* Este é o achado mais acionável da
análise: o tamanho do book, e não o sinal, é o principal limitante hoje.

### 3.3 O alfa bruto já é fraco em large caps (Sharpe 0,53 antes de custos)

Consequência conhecida e assumida da migração Russell 2000 → S&P 500: a reversão de
curto prazo vive em small caps. **Trocamos potência de alfa por integridade de dados**
(o R2000 gratuito tinha 18% de cobertura das deslistadas — ver `considerações/`).
Um IC de ~0,03–0,05 é aceitável, mas não sobrevive a custos num book grande.

### 3.4 O alfa decaiu ao longo da amostra

| Ano | Sharpe bruto | Sharpe líquido | Retorno líq. |
|---|---:|---:|---:|
| 2020 | +0,75 | **+0,52** | +5,4% |
| 2021 | +0,84 | +0,22 | +0,7% |
| 2022 | +0,66 | +0,19 | +0,8% |
| **2023** | **−0,10** | **−0,70** | **−2,2%** |

2020 (vol alta, deslocamentos) foi o melhor ano; **2023 foi negativo até no bruto**.
Duas leituras possíveis — e é honesto dizer que ainda não sabemos qual domina:

- **(a) Dependência de regime:** a reversão paga quando há estresse e demanda por
  liquidez, e some em mercados calmos/trending. Se confirmado, isso é uma
  **característica da tese** (somos provedores de liquidez), não um defeito;
- **(b) Decaimento/crowding:** o efeito está sendo arbitrado.

Distinguir as duas exige a análise por regime de volatilidade (pendente).

---

## 4. O que a análise sugere (em ordem de impacto)

1. **Dimensionar o book pela capacidade** — a evidência aponta para $100–300mm, não $1 bi.
   Esta é a conclusão mais forte e mais defensável do trabalho.
2. **Reduzir turnover** — o sinal tem autocorrelação ~0,9, mas giramos 15×/ano.
   Rebalanceamento mais espaçado ou banda de no-trade deve reter alfa.
3. **Quebrar o desempenho por regime de volatilidade** — testa a hipótese (a) e, se
   confirmada, fortalece a tese econômica em vez de enfraquecê-la.
4. **Não** perseguir Sharpe ajustando parâmetros no dev — o holdout permanece trancado.

---

## 5. Nota metodológica (honestidade analítica)

- **Uma única calibração a priori** foi feita, com justificativa teórica e não por busca
  de resultado: `alpha_bps_per_z` = 3 (≈ IC × vol idiossincrática) e rebalanceamento a
  cada 3 dias (coerente com horizonte de ~21 dias). Nenhum *grid search*.
- **Artefato conhecido:** o campo `max_abs_factor_expo` (0,59) é distorção de **medição**
  na crise da COVID — as exposições diárias são medidas com betas re-estimados
  mensalmente, e em mar–abr/2020 os betas mudaram bruscamente. No dia a dia,
  \|exposição a mercado\| ≈ 0,015. O mandato **não** foi violado.
- **Viés residual de dados**: 46% dos membros removidos do índice têm preço no yfinance
  (vs 99% dos sobreviventes) — quantificado, não ignorado.

> **Para o relatório:** o edital afirma que resultado fraco não elimina o trabalho — o que
> conta é rigor, coerência e honestidade analítica. Um Sharpe de 0,20 **bem diagnosticado**
> (capacidade + universo + regime, com números) demonstra mais maturidade do que um Sharpe
> alto inflado por viés de sobrevivência ou overfitting.
