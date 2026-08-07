# Análise de regime de volatilidade — o alfa depende do regime (e isso *era* a tese)

> # 🔴 ESTE DOCUMENTO FOI FALSEADO PELO HOLDOUT
>
> **Atualizado em 04/08/2026.** A tese abaixo — *"o alfa some na calmaria e aparece no
> estresse"* — foi construída em dev+val e **não sobreviveu ao teste fora da amostra**.
>
> No holdout (2024-2026) o IC do sinal é **negativo nos três regimes**:
>
> | Regime | IC dev+val | **IC holdout** |
> |---|---:|---:|
> | Vol baixa | +0,000 | **−0,028** |
> | Vol média | +0,064 | **−0,035** |
> | **Vol ALTA** | **+0,079** | **−0,020** *(n=12)* |
>
> A tese previa IC ≈ 0 na calmaria e IC **forte** em vol alta. O holdout foi de fato mais
> calmo (56% de dias de vol baixa contra 33%), o que explica *parte* do resultado ruim — mas
> **o sinal falhou inclusive em vol alta**, que é onde a tese apostava. A defesa por regime
> **não se sustenta**.
>
> *Ressalva a favor do documento:* o holdout teve só **12 observações** em vol alta e o t é
> −0,28 — estatisticamente indistinguível de zero. O correto é dizer que a tese ficou
> **não confirmada**, não que foi refutada com força.
>
> **Leia este documento como registro histórico do raciocínio que fizemos em dev+val**, e o
> [`results/09`](09_holdout_o_veredito.md) para o veredito. A escada monotônica abaixo é
> real nos dados de 2020-2023 — ela simplesmente não se repetiu.

> **Pergunta que motivou:** 2023 foi negativo (Sharpe líq. −0,70). Isso é **decaimento do
> alfa** (o efeito foi arbitrado) ou **dependência de regime** (o alfa só existe em certos
> mercados)? As duas hipóteses têm implicações opostas para a estratégia.
> **Método:** desempenho e IC medidos por tercil da vol realizada 21d do SPY, **defasada
> em 1 dia** (só usamos a vol que já era conhecida ao entrar no dia).
> **Artefatos:** `reports/regime_analysis.md` / `.png` · script `scripts/12_regime_analysis.py`

---

## 1. Resultado

### Desempenho da estratégia por regime (dev+val, 2020–2023)

> **Atualizado em 24/07/2026** — regerado com `rebalance_every_days = 10` (era 3).

| Regime | Vol média SPY | Sharpe bruto | Sharpe líquido | Ret. líquido a.a. |
|---|---:|---:|---:|---:|
| Vol baixa | 10% | +0,40 | **−0,18** | −0,5% |
| Vol média | 16% | +0,28 | −0,19 | −0,6% |
| **Vol ALTA** | 30% | **+0,86** | **+0,65** | **+5,6%** |

*Versão anterior (rebalance 3d): −0,26 / −0,33 / +0,51. Girar menos **reduziu o prejuízo nos
regimes calmos** — exatamente onde o IC é zero e só se paga custo — e ampliou o ganho em vol
alta. O padrão fica mais nítido, não diferente.*

### Qualidade pura do sinal (IC, sem otimizador nem custos)

| Regime | IC (fwd 21d) | t ingênuo | **t Newey-West** | n |
|---|---:|---:|---:|---:|
| Vol baixa | **−0,004** | −0,26 | **−0,17** → *o sinal não prevê NADA* | 65 |
| Vol média | +0,064 | 3,47 | **+2,51** | 65 |
| **Vol ALTA** | **+0,079** | 4,08 | **+2,78** | 67 |

> **Correção metodológica (22/07), agora com números medidos.** Os t-stats originais
> assumiam ICs independentes, mas o IC olha 21 dias à frente numa grade de 5 dias —
> medições vizinhas compartilham ~16 dias. `statarb/stats.py` aplica Newey-West com lag 4.
>
> **A correção é mais branda do que a estimativa grosseira sugeria.** O limite teórico
> √(21/5) ≈ 2,05 previa t ≈ 2,0; o medido é **2,78** em vol alta e **2,51** em vol média —
> queda de ~30%, não de 50%. Motivo: os pesos de Bartlett atenuam os lags mais distantes e
> a autocorrelação real da série de ICs é menor que o máximo teórico.
>
> **O que isso significa:** o IC médio e a escada monotônica não mudam. Em vol alta,
> **t = 2,78 continua significativo** a 5% — mais forte do que eu havia estimado. Mas
> "t = 4,1" era exagero: a leitura honesta é que a evidência de dependência de regime é
> **sólida, não esmagadora**, com 4 anos de amostra.

### O contexto anual que fecha o quebra-cabeça

| Ano | Vol média SPY | Sharpe líquido do ano |
|---|---:|---:|
| 2020 | **26%** | **+0,64** ✓ |
| 2021 | 12% | +0,02 |
| 2022 | **24%** | +0,30 |
| 2023 | 13% | **−0,45** ✗ |

---

## 2. Veredito: dependência de regime, não decaimento

O teste decisivo é o **IC** — que mede o sinal *antes* de custos e carteira. Em vol baixa
o IC é **estatisticamente zero** (t = −0,17): não é que a estratégia "perde para os custos"
em mercado calmo; é que **não há o que prever**. Em vol alta, o IC de 0,079 com **t = 2,78
(Newey-West)** é significativo a 5%.

2023 (vol 13%) foi um ano em que o fenômeno que exploramos simplesmente não ocorreu.
Isso é **consistente com a tese econômica**, não uma anomalia dela:

> A reversão do retorno idiossincrático é a remuneração de quem **provê liquidez** a
> vendedores/compradores apressados. Em mercados calmos não há pressa, não há
> sobre-reação — e não há o que reverter. Em mercados estressados, a demanda por
> liquidez dispara e o provedor é bem pago.

A estratégia é, na essência, **um seguro vendido contra a falta de liquidez do mercado** —
com a característica atraente de render mais exatamente quando o resto do portfólio
de um alocador tende a sofrer (vol alta).

## 3. Implicações práticas

1. **Para o relatório:** o ano negativo de 2023 deixa de ser fraqueza escondida e vira
   evidência de mecanismo — *sabemos quando e por que a estratégia ganha*. Poucos
   trabalhos de backtest conseguem explicar seus períodos ruins.
2. **Evolução natural (próximos passos, não implementada):** condicionar a exposição ao
   regime — reduzir o gross em vol baixa (onde IC≈0, só pagamos custo) e operar cheio em
   vol alta. *Atenção metodológica:* isso deve ser proposto como evolução, não
   retro-ajustado no backtest atual (seria overfitting de regime).
3. **Cuidado honesto:** com 4 anos de amostra, "regime" e "ano" se confundem em parte.
   A escada monotônica do IC (0 → 0,06 → 0,08) e o mecanismo econômico dão suporte à
   leitura, mas mais história (ampliar o painel para trás) a fortaleceria.

---

## 4. Epílogo (04/08/2026): a ressalva 3 estava certa

O item acima dizia que "regime" e "ano" podiam estar se confundindo, e que mais história
fortaleceria a leitura. **O holdout mostrou que a ressalva era o ponto principal, não um
detalhe.** A escada 0 → 0,06 → 0,08 não se repetiu; virou −0,028 / −0,035 / −0,020.

A lição de método que fica: **uma tese que explica bem o passado não é evidência de que ela
está certa.** A explicação de regime era coerente, econômica e ajustava os dados — e ainda
assim não previu nada. É exatamente por isso que o holdout existia. Ver
[`results/09`](09_holdout_o_veredito.md).
