# Análise do backtest — `resid_ou` no S&P 500 as-of (dev + validação)

> **Rodada:** 2020-01-02 → 2023-12-29 · book $1 bi dollar-neutral · holdout (2024+) **trancado**
> **Artefatos:** `reports/sp500_dev_val/` · **Notebook:** seção 7 do `pipeline_walkthrough.ipynb`
> **Atualizado em 23/07/2026** — números regerados após as correções de 22/07 e a
> calibração de custos de 23/07. Substituem integralmente a rodada de 15/07.

---

## 1. Resultado em uma tabela

| Métrica | Valor | (rodada de 15/07) |
|---|---:|---:|
| Sharpe **bruto** | **+0,51** | +0,53 |
| Sharpe **líquido** | **+0,16** | +0,20 |
| Retorno bruto / líquido | +3,07% / **+0,96%** a.a. | +3,16% / +1,18% |
| Volatilidade | 6,01% a.a. | 5,96% |
| Max drawdown | −11,3% | −10,9% |
| Turnover (one-way) | 15,6× /ano | 15,1× |
| Custos | **211 bps/ano** (= 69% do alfa bruto) | 198 bps |
| P&L líquido acumulado | **US$ 38,3 mm** | US$ 47,2 mm |
| Posições médias | 265 | 265 |

### Por que o resultado caiu de 0,20 para 0,16

São **duas causas de tamanho parecido** — e é importante não confundi-las:

| Causa | Δ Sharpe líquido | Decomponível? |
|---|---:|---|
| ① Alfa **bruto** caiu (0,532 → 0,511) — efeito do **painel** | **−0,021** | ❌ não isolado |
| ② Custos subiram 13 bps/ano | **−0,021** | ✅ exato (abaixo) |
| **Total** | **−0,038** | |

**① O bruto é anterior a qualquer custo**, então a queda vem da mudança de painel: 688 → 665
tickers (renomeações colapsadas + mais erosão por M&A no re-pull) **e** rótulos de setor
vindos de um snapshot diferente do screener, que muda qual restrição setorial aperta. Os dois
efeitos mudaram juntos e **não foram separados** — exigiria rodar o código novo sobre o painel
antigo, que não existe mais porque não foi versionado. É o problema de reprodutibilidade
apontado em [`results/04`](04_auditoria_membership_e_cobertura.md).

**② Os custos**, esses sim, decompõem-se exatamente:

| Componente | 15/07 | 23/07 | Δ |
|---|---:|---:|---:|
| Spread | 75,3 | 62,2 | **−13,1** (calibração) |
| Impacto de mercado | 123,0 | 127,3 | +4,3 |
| **Aluguel do short** | **0,0** | **20,0** | **+20,0** |
| Rebalance do hedge | 0,0 | 1,3 | +1,3 |
| **Total (bps/ano)** | **198,3** | **210,8** | **+12,5** |

13 bps/ano sobre vol de 6,01% = −0,021 de Sharpe. **Metade da queda é custo que sempre
existiu e não estava sendo cobrado** — não é o resultado piorando, é o resultado ficando
correto.

> **Medição separada — o preço da neutralidade setorial.** Durante a re-execução, uma rodada
> saiu com a restrição setorial **inativa** (o `scripts/07b` não fora rodado após regenerar o
> painel, e o `07` grava todos os setores como `"Unknown"`, colapsando a restrição num balde
> único). Ela rendeu Sharpe líquido **0,220** contra os 0,160 da rodada correta. Isso
> quantifica o custo do controle de risco em **−0,06 de Sharpe** — número útil, mas que **não
> faz parte** da explicação acima: a restrição já estava ativa na rodada de 15/07.

---

## 2. Decomposição dos custos (nova)

| Componente | bps/ano | % do custo |
|---|---:|---:|
| Impacto de mercado | 127,3 | **60,4%** |
| Spread | 62,2 | 29,5% |
| **Aluguel do short** | **20,0** | 9,5% |
| Rebalance do hedge | 1,3 | 0,6% |
| Liquidação por deslistagem | 0,0 | 0,0% |
| **Total** | **210,9** | |

O aluguel do short é o item que **não existia** antes de 22/07 — estava documentado apenas
no `PIPELINE v1` arquivado e havia sumido na reescrita dos docs.

> **O zero da penúltima linha não é "custo desprezível" — é evento que nunca ocorre.** Em
> 1.006 dias o motor processou **zero** liquidações por deslistagem: as empresas adquiridas
> não saem do painel no meio do backtest, elas nunca entram (o yfinance apaga o histórico
> inteiro). Auditado em [`results/08`](08_deslistamento_ausente_no_backtest.md).

---

## 3. Neutralidade: o livro real vs. o livro reportado

| | Só ações | **Com hedge SPY** |
|---|---:|---:|
| Gross médio | 0,999 | **1,012** |
| \|Net\| máximo | 0,0020 | **0,0223** |

A coluna da direita é nova e importa: o hedge de beta ficava **fora** da contabilidade.
O livro é dollar-neutral em ações (|net| = 0,2%), mas o **livro completo** carrega até
**2,2% de net** ($22mm) por causa da posição no ETF. Não viola o mandato — mas a
neutralidade reportada antes era melhor do que a efetiva.

| \|net setorial\| máximo | 0,050 (no limite — restrição ativa) |
|---|---|
| \|exposição a fator\| máxima | 0,593 (artefato de medição — ver §5) |

---

## 4. A comparação com o SPY (agora com números medidos)

| | SPY | `resid_ou` |
|---|---|---|
| Retorno no período | **+13,9% a.a.** | +0,96% a.a. líq. |
| Sharpe (excesso sobre RF) | **0,54** | 0,16 |
| Max drawdown | **−33,7%** | **−11,3%** |
| Correlação com SPY | 1,00 | **+0,26** |

*RF no período: 1,73% a.a.*

O SPY rendeu porque **carregou risco de mercado** numa alta. Nós zeramos essa exposição de
propósito. O benchmark correto para um book market-neutral é o **caixa**, e o valor do
produto é ser descorrelacionado — com **um terço** do drawdown.

Isso **não** absolve o resultado: 0,16 líquido é baixo. As causas estão abaixo.

---

## 5. Diagnóstico

### 5.1 Custos consomem 69% do alfa (causa dominante)

```
Bruto 3,07% a.a.  ──[ −211 bps ]──►  Líquido 0,96% a.a.
```

Impacto de mercado é 60% do custo — consequência de rodar **$1 bi** num alfa bruto modesto
com giro de 15,6×/ano. **A estratégia opera acima da sua capacidade.**

### 5.2 Capacidade

Backtest **re-rodado** em 5 tamanhos (`results/02`): Sharpe líquido de **0,33** ($100mm) a
**0,16** ($1bi), monotônico. Faixa sustentável: **$100–300mm**.

### 5.3 O alfa bruto é fraco em large caps (Sharpe 0,51 antes de custos)

Consequência assumida da migração R2000 → S&P 500: a reversão de curto prazo vive em small
caps. Trocamos potência de alfa por integridade de dados (ver `considerações/`).

### 5.4 Desempenho ano a ano

| Ano | Sharpe bruto | Sharpe líquido | Ret. líq. | Vol do SPY |
|---|---:|---:|---:|---:|
| 2020 | +0,67 | **+0,44** | +4,56% | 26% |
| 2021 | +0,91 | +0,26 | +0,80% | 12% |
| 2022 | +0,65 | +0,16 | +0,64% | 24% |
| **2023** | **−0,06** | **−0,71** | **−2,20%** | 13% |

2023 foi negativo até no bruto. A análise de regime (`results/03`) mostra que **não é
decaimento, é regime** — em vol baixa o IC é estatisticamente zero.

---

## 6. Nota metodológica

- **Calibração:** `alpha_bps_per_z` = 3 e rebalance a cada 3 dias foram calibrados *a priori*,
  sem grid search. `spread_bps` foi **medido** (Corwin-Schultz, `results/05`); `eta` e `gamma`
  foram **demonstrados não-estimáveis** com dado diário e mantidos da literatura.
- **`horizon_days` = 21** é *consistente com* — mas **não validado por** — a meia-vida medida
  do sinal, de **21,4 dias úteis** (`results/06`). A medição não é independente: a
  autocorrelação é dominada pela janela de acumulação de 60 dias do próprio sinal, também
  escolhida a priori. O mesmo estudo mostra que a heurística **reage ~6× demais** ao sinal
  frente ao ótimo de Gârleanu-Pedersen (`H` implícito 3,7 vs 21) — fragilidade conhecida, não
  corrigida (mudá-la move o backtest e exige decisão consciente).
- **Artefato conhecido:** `max_abs_factor_expo` = 0,593 é distorção de **medição** na COVID —
  as exposições diárias usam betas re-estimados mensalmente, e em mar–abr/2020 eles mudaram
  bruscamente. A *restrição* não foi violada (ela é imposta na data da decisão); a *exposição
  realizada* foi. No dia a dia \|expo_mkt\| ≈ 0,015.
- **Viés de dados:** 6,8% dos meses-membro sem preço, com **3,45% de erosão retroativa** que
  **cresce** a cada aquisição (`results/04`). O viés de **seleção de membros** está resolvido
  pela composição as-of; o de **desfecho** não — das 68 empresas que saíram do índice em
  2020-2023, 36 não têm preço algum (`results/08`).

> **Para o relatório:** um Sharpe de 0,16 **bem diagnosticado** — com capacidade, regime,
> custos decompostos e vieses medidos — demonstra mais maturidade que um Sharpe alto inflado
> por viés de sobrevivência. E o número piorou porque **encontramos e corrigimos** um controle
> de risco que não estava sendo aplicado. Isso é o trabalho funcionando.
