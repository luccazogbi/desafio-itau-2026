# Análise do backtest — `resid_ou` no S&P 500 as-of (dev + validação)

> 🔴 **Este documento descreve o dev+val, que NÃO se confirmou fora da amostra.**
> No holdout (2024-2026) o Sharpe líquido foi **−1,15** e o IC do sinal **−0,030**.
> Todos os números abaixo continuam corretos para 2020-2023 — e é justamente por isso que
> valem como registro: eles mostram o que um resultado sobreajustado parece **antes** de ser
> testado. Veredito em [`results/09`](09_holdout_o_veredito.md).

> **Rodada:** 2020-01-02 → 2023-12-29 · book $1 bi dollar-neutral · holdout (2024+) **trancado**
> **Artefatos:** `reports/sp500_dev_val/` · **Notebook:** seção 7 do `pipeline_walkthrough.ipynb`
> **Atualizado em 24/07/2026** — `rebalance_every_days` passou de **3 para 10** (decisão de
> calibração; ver `results/07` §2 e §4). Substitui a rodada de 23/07.

---

## ⚠️ Leia isto antes da tabela

O Sharpe líquido subiu de 0,16 para **0,27**. **Esse número não deve ser lido sozinho**, por
um motivo medido:

O resultado depende de **em que dia do calendário se começa a operar**. Fixando tudo e
deslocando só a data inicial, o Sharpe varia de **0,077 a 0,341** (`results/07` §2.2). A data
oficial (2020-01-02) foi fixada *a priori*, muito antes desta decisão — mas calhou de cair no
lado **favorável** da distribuição.

| | |
|---|---:|
| Rodada oficial (início 2020-01-02) | **0,266** |
| **Média entre 7 fases de calendário** | **0,205** |
| Dispersão entre fases | **±0,09** |

**A expectativa honesta da estratégia é ~0,21, não 0,27.** Os 0,27 são o que aconteceu com a
data de início que já estava no config; a diferença é sorte de calendário, não alfa.

Sempre que o número 0,27 aparecer no relatório, ele precisa vir com essa banda ao lado.

---

## 1. Resultado em uma tabela

| Métrica | **24/07 (rebal. 10d)** | (23/07, rebal. 3d) |
|---|---:|---:|
| Sharpe **bruto** | **+0,57** | +0,51 |
| Sharpe **líquido** | **+0,27** | +0,16 |
| Retorno bruto / líquido | +3,16% / **+1,49%** a.a. | +3,07% / +0,96% |
| Volatilidade | 5,58% a.a. | 6,01% |
| Max drawdown | **−7,9%** | −11,3% |
| Turnover (one-way) | **11,0×** /ano | 15,6× |
| Custos | **168 bps/ano** (= 53% do alfa bruto) | 211 bps (69%) |
| P&L líquido acumulado | **US$ 59,3 mm** | US$ 38,3 mm |
| Posições médias | 278 | 265 |

### Por que melhorou — e por que isso é aritmética, não descoberta

| Causa | Δ Sharpe líquido |
|---|---:|
| ① Custos caíram 43 bps/ano (211 → 168) | **+0,08** |
| ② Alfa bruto subiu levemente (0,51 → 0,57) | +0,03 |
| **Total observado** | **+0,11** |

**O item ① é o mecanismo, e é robusto:** girar a carteira 3× menos vezes paga 3× menos
spread. O spread caiu de 62,2 para 44,0 bps/ano e o impacto de 127,3 para 102,8.

**O item ② é onde mora a sorte.** Reduzir a frequência de rebalanceamento **não deveria**
mexer no alfa bruto — e na média entre fases não mexe (0,499 → 0,516, praticamente
constante). O salto para 0,568 nesta rodada específica é a fase favorável.

> **Regra de leitura:** confie no canal de custo (+0,06 na média entre fases). Desconfie do
> resto.

---

## 2. Decomposição dos custos

| Componente | bps/ano | % do custo | (rebal. 3d) |
|---|---:|---:|---:|
| Impacto de mercado | 102,8 | **61,4%** | 127,3 |
| Spread | 44,0 | 26,2% | 62,2 |
| **Aluguel do short** | **20,0** | 11,9% | 20,0 |
| Rebalance do hedge | 0,8 | 0,5% | 1,3 |
| Liquidação por deslistagem | 0,0 | 0,0% | 0,0 |
| **Total** | **167,6** | | 210,9 |

O aluguel do short é **fixo em 20 bps/ano** (incide sobre o notional vendido, não sobre o
giro) — por isso sua fatia relativa *sobe* de 9,5% para 11,9% quando os custos de execução
caem. Não é o aluguel que ficou mais caro; é o resto que ficou mais barato.

> **O zero da penúltima linha não é "custo desprezível" — é evento que nunca ocorre.** Em
> 1.006 dias o motor processou **zero** liquidações por deslistagem: as empresas adquiridas
> não saem do painel no meio do backtest, elas nunca entram (o yfinance apaga o histórico
> inteiro). Auditado em [`results/08`](08_deslistamento_ausente_no_backtest.md).

---

## 3. Neutralidade: o livro real vs. o livro reportado

| | Só ações | **Com hedge SPY** |
|---|---:|---:|
| Gross médio | 0,999 | **1,012** |
| \|Net\| máximo | 0,0020 | **0,0420** |

O \|net\| com hedge **dobrou** (0,022 → 0,042) em relação à rodada de 3 dias. Motivo: com
rebalanceamento mais espaçado, o beta residual do book deriva mais entre decisões, e o hedge
precisa carregar posição maior. **É um custo escondido da mudança** que não aparece no
Sharpe: o livro completo carrega até $42mm de net direcional, contra $22mm antes.

Não viola o mandato (que incide sobre a carteira de ações), mas é honesto registrar que a
neutralidade **efetiva** piorou.

| \|net setorial\| máximo | 0,050 (no limite — restrição ativa) |
|---|---|
| \|exposição a fator\| máxima | 0,604 (artefato de medição — ver §5) |

---

## 4. A comparação com o SPY

| | SPY | `resid_ou` |
|---|---|---|
| Retorno no período | **+13,9% a.a.** | +1,49% a.a. líq. |
| Sharpe (excesso sobre RF) | **0,54** | 0,27 |
| Max drawdown | **−33,7%** | **−7,9%** |
| Correlação com SPY | 1,00 | **+0,25** |

*RF no período: 1,73% a.a.*

O SPY rendeu porque **carregou risco de mercado** numa alta. Nós zeramos essa exposição de
propósito. O benchmark correto para um book market-neutral é o **caixa**, e o valor do
produto é ser descorrelacionado — agora com **um quarto** do drawdown.

---

## 5. Diagnóstico

### 5.1 Custos consomem 53% do alfa (era 69%)

```
Bruto 3,16% a.a.  ──[ −168 bps ]──►  Líquido 1,49% a.a.
```

Melhorou, mas impacto de mercado ainda é 61% do custo. **A estratégia continua operando
acima da sua capacidade** — só que menos.

### 5.2 Capacidade

Backtest **re-rodado** em 5 tamanhos (`results/02`): Sharpe líquido de **0,41** ($100mm) a
**0,27** ($1bi), monotônico. A curva subiu ~0,08 em todo o intervalo; a **forma** não mudou.
Faixa sustentável continua **$100–300mm**.

### 5.3 O alfa bruto é fraco em large caps (Sharpe 0,57 antes de custos)

Consequência assumida da migração R2000 → S&P 500: a reversão de curto prazo vive em small
caps. Trocamos potência de alfa por integridade de dados (ver `considerações/`).

### 5.4 Desempenho ano a ano

| Ano | Sharpe bruto | Sharpe líquido | Ret. líq. | Vol do SPY |
|---|---:|---:|---:|---:|
| 2020 | +0,84 | **+0,64** | +6,03% | 26% |
| 2021 | +0,54 | +0,02 | +0,08% | 12% |
| 2022 | +0,71 | +0,30 | +1,19% | 24% |
| **2023** | **+0,07** | **−0,45** | **−1,39%** | 13% |

2023 continua negativo, mas **menos** (−0,45 contra −0,71): parte do prejuízo de 2023 era
custo de girar num ano sem alfa. A análise de regime (`results/03`) mostra que **não é
decaimento, é regime** — em vol baixa o IC é estatisticamente zero.

---

## 6. Nota metodológica

- **Calibração:** `alpha_bps_per_z` = 3 calibrado *a priori*. `rebalance_every_days` = 10
  decidido em 24/07 **pelo canal de custo** (bruto constante entre fases + custos caindo
  monotonicamente), não pelo Sharpe de uma rodada — se fosse pelo Sharpe, teríamos escolhido
  a fase 2020-01-03 e reportado 0,341. `spread_bps` foi **medido** (Corwin-Schultz,
  `results/05`); `eta` e `gamma` foram **demonstrados não-estimáveis** e mantidos da literatura.
- **`horizon_days` = 21** é *consistente com* — mas **não validado por** — a meia-vida medida
  do sinal (21,4 dias úteis, `results/06`). A medição não é independente: é dominada pela
  janela de acumulação de 60 dias do próprio sinal. O mesmo estudo mostra que a heurística
  **reage ~7× demais** ao sinal (`H` implícito 3,1 vs 21).
- **Artefato conhecido:** `max_abs_factor_expo` = 0,604 é distorção de **medição** na COVID —
  exposições diárias usam betas re-estimados mensalmente, e em mar–abr/2020 eles mudaram
  bruscamente. A *restrição* não foi violada (é imposta na data da decisão). No dia a dia
  \|expo_mkt\| ≈ 0,015. Nota adicional: a tolerância adaptativa de fator (0,02 → teto 0,10)
  foi acionada em **33 de 1.006 dias**, e atingiu o teto em 5 — a dollar-neutrality nunca cedeu.
- **Viés de dados:** 6,8% dos meses-membro sem preço, com **3,45% de erosão retroativa** que
  **cresce** a cada aquisição (`results/04`). O viés de **seleção de membros** está resolvido
  pela composição as-of; o de **desfecho** não — das 68 empresas que saíram do índice em
  2020-2023, 36 não têm preço algum (`results/08`).

> **Para o relatório:** o número a comunicar é **0,21 ± 0,09** (média entre fases), com 0,27
> como a rodada oficial. Um Sharpe de 0,21 **bem diagnosticado** — com capacidade, regime,
> custos decompostos, vieses medidos e a própria dependência de calendário quantificada —
> demonstra mais maturidade que um Sharpe alto inflado. A dependência de fase é a fragilidade
> estrutural em aberto, e a correção está identificada (*tranching*, `results/07` §3).
