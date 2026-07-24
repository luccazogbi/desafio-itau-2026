# Gârleanu-Pedersen vs. a heurística do `horizon_days` — a heurística reage ~6× demais ao sinal

> **Tarefa:** roadmap 5 — *"otimização multi-período (Gârleanu-Pedersen) vs. horizonte heurístico"*.
> **Pergunta:** nosso otimizador é de **um** período. Para não ficar míope, inflamos o alfa
> por `horizon_days = 21`. Isso é paliativo. GP (JF 2013) resolvem o problema multi-período
> de verdade — **a heurística chega perto do ótimo? Onde erra?**
> **Artefatos:** `reports/gp_vs_heuristica.md` · `scripts/15_gp_vs_heuristica.py` ·
> módulo `statarb/portfolio/garleanu_pedersen.py`
> **Holdout:** painel até 2023-12-31, sem backtest nem métrica de desempenho. **Intocado.**
>
> ⚠️ **Corrigido em 24/07/2026.** A versão anterior deste documento foi gerada sobre o
> painel **sintético**, não sobre o S&P 500 real — ver §6. Todos os números de custo abaixo
> mudaram. A direção da conclusão não mudou; a magnitude e o peso das ressalvas, sim.

---

## 1. O que GP dizem

Com sinal que reverte e custo quadrático, a política ótima **não** é ir até a carteira ideal:

$$ x_t \;=\; x_{t-1} \;+\; D\,(\text{aim}_t - x_{t-1}) $$

Ande uma **fração** $D$ na direção do alvo. E o alvo não é Markowitz — é um *aim* que
encolhe o sinal pela sua **persistência**: sinal que morre rápido merece menos posição,
porque não há tempo de amortizar o custo de entrada.

A forma fechada foi **derivada no módulo**, não citada de memória, e **validada por
simulação**: a política GP domina todas as perturbações dela (taxa ±20%/±50%, aim ±20%,
aim = Markowitz, taxa = 1). Se a álgebra estivesse errada, alguma perturbação renderia mais.

---

## 2. Os insumos foram MEDIDOS, não assumidos

### Persistência do sinal — autocorrelação do z-score do `resid_ou`

| Defasagem (dias) | 5 | 10 | 15 | 20 | 25 | 30 | 35 | 40 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Autocorrelação | 0,886 | 0,777 | 0,674 | 0,576 | 0,486 | 0,399 | 0,313 | 0,231 |

Decaimento exponencial limpo → **φ = 0,0318/dia**, **meia-vida = 21,4 dias úteis**.

> ### ⚠️ Esta medição NÃO valida o `horizon_days = 21`
>
> A versão anterior deste documento apresentava a meia-vida de ~21 dias como *"validação
> independente de um parâmetro calibrado às cegas"*. **Isso está errado, e o erro é de
> raciocínio, não de cálculo.**
>
> O sinal `resid_ou` acumula resíduos numa janela de **J = 60 dias** (`accum_days`). A
> autocorrelação de uma soma móvel de J dias decai **mecanicamente** como $1 - k/J$,
> independentemente da economia por trás. Passando **ruído branco puro** pelo mesmo
> acumulador e pelo mesmo estimador:
>
> | defasagem | observado | ruído branco com J=60 |
> |---:|---:|---:|
> | 5 | 0,886 | 0,917 |
> | 20 | 0,576 | 0,667 |
> | 40 | 0,231 | 0,333 |
> | **meia-vida ajustada** | **21,4d** | **28,6d** |
>
> O observado decai **mais rápido** que ruído puro, então existe reversão genuína — mas o
> número é dominado por `accum_days = 60`, que também foi escolhido *a priori*. Dizer que
> 21,4 valida 21 é circular: **os dois descendem da mesma decisão de desenho**, não de duas
> evidências independentes.
>
> A leitura honesta: a meia-vida medida é **consistente com** o horizonte adotado, e
> descarta a hipótese de que o sinal fosse rápido demais para um horizonte de um mês.
> Não é confirmação independente.

### Custo quadrático equivalente

λ = **1,0**, casando a **derivada** do custo Almgren-Chriss no tamanho típico de trade —
é o custo *marginal* que entra na condição de primeira ordem. Válido de 1,0× a 2,8× esse
tamanho; fora daí a aproximação degrada.

Insumos reais do painel: ADV mediano **US$ 133 mm**, vol idiossincrática mediana
**1,35%/dia**, trade típico **7,1 bps do book**.

---

## 3. O confronto

Ambas as políticas têm a forma $x' = \text{inércia}\cdot x + \text{resposta}\cdot\alpha$:

| | GP (ótimo) | Heurística `H=21` | razão |
|---|---:|---:|---:|
| Inércia (peso na posição anterior) | 0,797 | 0,951 | 1,19× |
| **Taxa de trade** (1 − inércia) | **0,203** | 0,049 | **4,1×** |
| **Resposta ao alfa** (`H` implícito) | **3,7** | 21 | **5,7×** |
| `aim / markowitz` | 0,889 | — (não encolhe) | |

### 3.1 A heurística reage ~6× demais ao sinal

O `H` que reproduziria a resposta ótima é **3,7**, não 21. O raciocínio original —
*"a posição rende ~21 dias, logo vale 21 dias de alfa"* — ignora duas coisas que GP
descontam: **(a)** o sinal decai ao longo desses 21 dias e **(b)** haverá custo de
negociação de novo no futuro.

### 3.2 Mas quase não rebalanceia por conta própria

Inércia de 0,951 contra 0,797: a política ótima fecha **20%** do gap até o alvo por
rebalance; a heurística fecha 4,9%. GP antecipa que carregar posição grande custa caro
depois e a puxa de volta mais rápido.

### 3.3 Os dois erros se cancelam em parte

Reage demais ao sinal, mas move devagar. É compensação **acidental** — funciona até parar de
funcionar. Não há garantia de que sobreviva a uma mudança no sinal, nos custos ou no tamanho
do book. Essa é a fragilidade real que o exercício expõe.

---

## 4. A ressalva que impede exagerar a conclusão

**O spread responde por 45% do custo** no tamanho típico de trade — e é exatamente o
componente que o GP **não consegue representar**. GP supõem custo puramente **quadrático**;
o nosso Almgren-Chriss tem spread (**linear**), impacto temporário (**potência 3/2**) e
permanente (quadrático).

Isso não é um detalhe de rodapé: custo linear gera, na teoria, uma **banda de
não-negociação** (não se opera enquanto o desvio não compensar o spread), enquanto o
quadrático gera ajuste parcial suave. **São políticas qualitativamente diferentes**, e com
quase metade do custo vindo do termo linear, o mapeamento GP → nossa mesa é frouxo.

> Na versão anterior (painel sintético) o spread aparecia como **11%** do custo, o que fazia
> esta ressalva parecer secundária. Com **45%**, ela passa a ser a limitação central do
> exercício.

Além disso, o confronto acima é **sem restrições**. No pipeline real o otimizador opera com
`gross = 0,999` — **na restrição de orçamento**. Ali o nível do alfa deixa de determinar o
tamanho do book e passa a determinar só o **tilt** entre as ações. Então a diferença de
nível **não se traduz 1:1** em diferença de carteira.

O que sobrevive à restrição é a **dinâmica**: com que velocidade se persegue o alvo. E aí
o sinal do GP é claro, mesmo que a magnitude seja incerta.

**Por isso este exercício diagnostica a heurística; não substitui o otimizador convexo**,
que trata o custo com a curvatura certa e carrega todo o mandato (dollar-neutral,
neutralidade de fator e setor, caps de posição e ADV) que o GP não tem.

---

## 5. O que fazer com isso

1. **Não trocar o otimizador por GP.** Ele perderia todas as restrições de mandato, que são
   a tese de risco do projeto.
2. **Revisar `horizon_days`** — a evidência aponta para algo entre 4 e 8, não 21. Mas isso
   **muda o backtest** e deve ser feito como decisão consciente e documentada, não silenciosa.
   *Não alterei o config.*
3. **Evolução natural (proposta, não implementada):** com 45% do custo sendo linear, a
   implementação teoricamente correta não é ajustar `horizon_days` — é uma **banda de
   não-negociação** dentro do otimizador convexo. Fica com a inércia do multi-período *e*
   com as restrições do mandato, e representa o spread com a curvatura certa.
4. **Para o relatório:** o item mais forte aqui não é o número, é o método — a heurística foi
   confrontada com a solução ótima da literatura, os insumos foram medidos no próprio painel,
   a derivação foi validada numericamente, e as limitações da comparação estão declaradas.

---

## 6. Nota de procedência — por que os números mudaram

A primeira execução deste estudo (23/07) rodou sobre o painel **sintético** de
`data/processed`, não sobre o S&P 500 real. É o bug descrito em `MUDANCAS §3.6` — os
scripts 11, 12 e 15 não honravam a chave `data.panel`. A correção passou para
`load_config()`, e os scripts 11 e 12 foram re-executados; **o 15 não foi**.

Detectado em 24/07 por inconsistência entre artefatos: o relatório dizia ADV mediano de
**US$ 8 mm**, contra **US$ 152 mm** medidos em `results/05` sobre o mesmo universo. O
painel sintético dá exatamente **US$ 8,3 mm**.

| | sintético (reportado) | **real (correto)** |
|---|---:|---:|
| ADV mediano | US$ 8 mm | **US$ 133 mm** |
| σ idiossincrática | 2,20%/dia | **1,35%/dia** |
| λ (custo quadrático) | 6,9 | **1,0** |
| taxa de trade GP | 0,134 | **0,203** |
| `H` implícito | 5,5 | **3,7** |
| spread / custo total | 11% | **45%** |
| φ / meia-vida | 0,0315 / 21,7d | 0,0318 / 21,4d |

A persistência do sinal quase não mudou — e isso **não é tranquilizador**, é a confirmação
de §2: a autocorrelação medida é dominada pela janela de acumulação de 60 dias, que é a
mesma nos dois painéis. Um número que sobrevive à troca do painel inteiro estava medindo a
construção do sinal, não o mercado.

**Lição de método:** o pipeline avisa quando o *painel* não é rastreável (`snapshot`), mas
não havia nada avisando quando um *relatório* fora gerado do painel errado. Um carimbo de
proveniência (painel + snapshot) no cabeçalho de cada `reports/*.md` fecharia essa lacuna.
