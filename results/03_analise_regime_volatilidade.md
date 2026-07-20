# Análise de regime de volatilidade — o alfa depende do regime (e isso é a tese)

> **Pergunta que motivou:** 2023 foi negativo (Sharpe líq. −0,70). Isso é **decaimento do
> alfa** (o efeito foi arbitrado) ou **dependência de regime** (o alfa só existe em certos
> mercados)? As duas hipóteses têm implicações opostas para a estratégia.
> **Método:** desempenho e IC medidos por tercil da vol realizada 21d do SPY, **defasada
> em 1 dia** (só usamos a vol que já era conhecida ao entrar no dia).
> **Artefatos:** `reports/regime_analysis.md` / `.png` · script `scripts/12_regime_analysis.py`

---

## 1. Resultado

### Desempenho da estratégia por regime (dev+val, 2020–2023)

| Regime | Vol média SPY | Sharpe bruto | Sharpe líquido | Ret. líquido a.a. |
|---|---:|---:|---:|---:|
| Vol baixa | 10% | +0,29 | **−0,34** | −1,0% |
| Vol média | 16% | +0,38 | −0,25 | −0,8% |
| **Vol ALTA** | 30% | **+0,79** | **+0,58** | **+5,4%** |

### Qualidade pura do sinal (IC, sem otimizador nem custos)

| Regime | IC (fwd 21d) | t-stat |
|---|---:|---:|
| Vol baixa | **−0,003** | −0,2 → *o sinal não prevê NADA* |
| Vol média | +0,064 | 3,4 |
| **Vol ALTA** | **+0,080** | **4,1** |

### O contexto anual que fecha o quebra-cabeça

| Ano | Vol média SPY | Sharpe líquido do ano |
|---|---:|---:|
| 2020 | **26%** | **+0,52** ✓ |
| 2021 | 12% | +0,22 |
| 2022 | **24%** | +0,19 |
| 2023 | 13% | **−0,70** ✗ |

---

## 2. Veredito: dependência de regime, não decaimento

O teste decisivo é o **IC** — que mede o sinal *antes* de custos e carteira. Em vol baixa
o IC é **estatisticamente zero**: não é que a estratégia "perde para os custos" em mercado
calmo; é que **não há o que prever**. Em vol alta, o IC de 0,08 com t=4,1 é forte.

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
