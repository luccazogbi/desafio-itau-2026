# A ida única ao holdout — o sinal não sobreviveu

> **Executado em 07/08/2026**, com autorização explícita do responsável pelo projeto.
> **Janela:** 2024-01-02 a 2026-05-29 · 604 dias úteis · 2,40 anos · 503 membros/dia
> **Artefatos:** `reports/holdout/` · `reports/completo/` · `reports/holdout_diagnostico.md` ·
> `reports/funnel_resid_ou.md` · scripts `02` (`--allow-holdout`), `04` (`--include-holdout`), `18`
> **Esta é a única ida.** O holdout está gasto. Nenhuma decisão de calibração pode mais ser
> tomada com base nele — qualquer ajuste feito a partir daqui é, por definição, in-sample.

---

## 1. O resultado

| Métrica | dev+val (2020-23) | **HOLDOUT (2024-26)** |
|---|---:|---:|
| Sharpe **bruto** | +0,57 | **−0,77** |
| Sharpe **líquido** | +0,27 | **−1,15** |
| Retorno líquido a.a. | +1,49% | **−5,09%** |
| Volatilidade | 5,58% | 4,44% |
| Max drawdown | −7,9% | **−12,8%** |
| P&L líquido | +US$ 59,3mm | **−US$ 122,1mm** |
| Custos | 168 bps | 165 bps |
| Turnover | 11,0× | 11,7× |

**O sinal não parou de funcionar — ele inverteu.**

Isso é o que mais importa, e é preciso dizer com clareza: **o Sharpe bruto também é negativo**
(−0,77). Não é um problema de custo, de execução ou de tamanho de book. Se fosse, o bruto
ficaria positivo e o líquido negativo. O alfa, antes de qualquer fricção, virou contra nós.

### O IC confirma, e é a evidência mais limpa

| Split | IC (21d) | t (Newey-West) | Spread Q5−Q1 |
|---|---:|---:|---:|
| dev (2020-22) | +0,051 | +2,50 | +7,73 bps/dia |
| validação (2023) | +0,036 | +1,66 | +5,17 bps/dia |
| **HOLDOUT (2024-26)** | **−0,030** | **−1,54** | **−3,28 bps/dia** |

O IC mede o sinal **puro** — sem otimizador, sem custo, sem carteira. Ele mudou de sinal.

---

## 2. A defesa óbvia — e por que ela não se sustenta

A tese do projeto (`results/03`) prevê que o alfa **depende do regime**: aparece quando há
estresse e demanda por liquidez, e some na calmaria. A defesa natural seria: *"o holdout foi
um período calmo, então o resultado ruim era esperado."*

**Metade dessa defesa é verdadeira.** O holdout foi mesmo muito mais calmo:

| % dos dias | dev+val | HOLDOUT |
|---|---:|---:|
| Vol baixa (< 12,8%) | 33,4% | **56,3%** |
| Vol média | 33,3% | 33,4% |
| **Vol ALTA (> 19,5%)** | 33,3% | **10,3%** |

*(limiares congelados no dev+val, para que "vol alta" signifique a mesma coisa nos dois períodos)*

**Mas a outra metade destrói o argumento.** A tese prevê IC ≈ **zero** na calmaria — não IC
**negativo**. E, sobretudo, prevê que em vol alta o sinal **funcione**:

| Regime | IC dev+val | **IC holdout** |
|---|---:|---:|
| Vol baixa | +0,000 | **−0,028** |
| Vol média | +0,064 | **−0,035** |
| **Vol ALTA** | **+0,079** | **−0,020** *(n=12)* |

**O IC é negativo em todos os três regimes do holdout — inclusive naquele onde a tese diz que
ele deveria ser mais forte.** A defesa por regime não se sustenta.

> **Ressalva honesta que corta para o nosso lado:** o holdout teve apenas **12 observações**
> em vol alta, e o t de −0,28 significa que esse −0,020 é **estatisticamente indistinguível de
> zero**. Não é evidência forte de que o sinal inverteu em vol alta; é evidência de que **não
> há mais nada parecido com o +0,079 do dev+val**. A conclusão correta é *"não confirmado"*,
> não *"refutado com força"*.

---

## 3. Não é problema de dado

A primeira suspeita ao ver um resultado assim é falha no painel do período recente. **É o
contrário** — o dado do holdout é melhor:

| | dev+val | HOLDOUT |
|---|---:|---:|
| Cobertura de preço dos membros | 92,8% | **97,6%** |
| Universo negociável médio | 465 | **489** |

Faz sentido: a erosão por M&A (`results/04`) apaga o passado, então prejudica mais os anos
antigos. **O resultado negativo não é artefato de dados.**

---

## 4. Onde a perda aconteceu

| Ano | Vol do SPY | Sharpe bruto | Sharpe líquido | Ret. líquido |
|---|---:|---:|---:|---:|
| 2024 | 12% | −1,20 | −1,63 | −6,42% |
| 2025 | 16% | +0,22 | −0,17 | −0,70% |
| 2026 (5 meses) | 13% | −1,81 | −2,08 | −12,58% |

E a perda é **extremamente concentrada**:

```
Soma dos 10 PIORES dias  :  −9,44 pp
Resultado bruto do período: −8,27 pp
```

**Os 10 piores dias, de 604, explicam mais que a perda inteira.** Fora deles, o período seria
levemente positivo. As datas: 2024-08-01, 2024-11-06, 2025-04-03, 2025-10-29, 2026-04-23.

Isso tem uma leitura econômica coerente: são dias de **repactuação violenta e persistente**
de preços — o tipo de movimento que é **informação, não fluxo**. Uma carteira de reversão
aposta que o desvio volta; quando o desvio é uma reprecificação genuína, ela é atropelada.
A estratégia vende seguro contra falta de liquidez e, nesses dias, o seguro foi acionado.

Mas isso **não salva o resultado**: nos outros 594 dias o IC continuou negativo. O problema
não é só a cauda.

---

## 5. O que isso significa

### 5.1 O protocolo funcionou — e essa é a notícia boa

O holdout foi lacrado no código em 22/07, antes de qualquer resultado ser conhecido, e o motor
recusava rodar além de 2023-12-31 sem flag explícita. **Ele foi criado exatamente para pegar o
caso em que a estratégia parece funcionar em dev+val e não funciona fora — e pegou.**

Sem essa disciplina, o projeto teria reportado Sharpe +0,27 com capacidade, regime e custos
lindamente diagnosticados, e a estratégia estaria errada.

### 5.2 O Sharpe de dev+val era, em boa parte, sobreajuste

Isso precisa ser dito sem eufemismo. As pistas já estavam no relatório e nós as reportamos
honestamente — mas subestimamos o peso delas:

| Sinal de alerta, já documentado | O que ele significava |
|---|---|
| Validação com **t = 1,66** (abaixo de 2) | a evidência nunca foi forte |
| Dependência de calendário de **±0,09** | metade do "alfa" era sorte de data |
| 8 de 10 candidatos falharam no funil | a taxa-base de falso positivo era alta |
| IC de **0,05** | pequeno demais para sobreviver a qualquer erosão |

Um IC de 0,05 com t de 1,66 na validação é, em retrospecto, **exatamente o perfil de um achado
que não replica** — o mesmo que Hou, Xue & Zhang (2020) documentam em 82% das anomalias
publicadas. Nós citamos esse número no relatório sobre os *outros* sinais. Ele valia para o
nosso também.

### 5.3 O resultado consolidado

Rodando o período inteiro (2020-01-02 a 2026-05-29, 6,4 anos):

| | |
|---|---:|
| Sharpe bruto | **+0,22** |
| Sharpe líquido | **−0,10** |
| P&L líquido | **−US$ 32,6mm** |
| Max drawdown | **−15,7%** |

**A estratégia, como está, perde dinheiro.**

---

## 6. O que NÃO vamos fazer

O holdout está gasto. A partir daqui, qualquer parâmetro ajustado olhando para 2024-2026 é
in-sample, e o número resultante não significa nada. Especificamente, **recusamos**:

| Tentação | Por que não |
|---|---|
| Inverter o sinal (IC negativo ⇒ comprar as esticadas) | Seria ajustar ao holdout. Além disso o IC não é significativo (t −1,54) |
| Filtrar os "10 piores dias" | Cherry-picking puro |
| Reduzir o horizonte / mexer em `accum_days` | Calibrar no holdout |
| Rodar só 2025 (o ano menos ruim) | Escolha oportunista de período |
| Buscar um novo painel/período onde funcione | É o que produziu o problema em primeiro lugar |

Qualquer evolução real exige **dados novos**: um holdout diferente (outro mercado, outro
período histórico anterior a 2018) ou uma fonte que permita ampliar a amostra.

---

## 7. Próximos passos honestos

1. **Reportar o resultado como ele é.** Um projeto que reservou um holdout, encontrou
   sobreajuste e disse isso vale mais que um Sharpe positivo não testado.
2. **Ampliar a amostra para trás** (CRSP/Bloomberg, pré-2018) é a única forma de distinguir
   *"o efeito nunca existiu"* de *"o efeito existiu e foi arbitrado"*. Com 2018-2026 não dá.
3. **Momentum residual** (`results/06`, Blitz et al.) continua sendo o candidato mais bem
   fundamentado — mas agora com uma exigência nova: qualquer sinal futuro precisa de um
   **holdout novo e intocado** para ser avaliado. O nosso acabou.
4. **A infraestrutura sobrevive ao resultado.** Painel as-of auditado, motor com custos
   realistas, funil com Newey-West, snapshot por hash, 20 testes, trava de holdout: nada disso
   depende de o `resid_ou` funcionar. É o que se reaproveita.

---

## 8. Para o relatório

A frase que resume o trabalho:

> *"Reservamos 2,4 anos de dados e nunca os tocamos até a decisão final. Em dev+val a
> estratégia entregava Sharpe +0,27 com regime, capacidade e custos diagnosticados. No holdout
> entregou **−1,15**, com IC negativo em todos os regimes e alfa bruto negativo. O protocolo
> que construímos para nos proteger do autoengano funcionou: ele nos disse que estávamos
> errados. Reportamos isso em vez de procurar um número melhor."*
