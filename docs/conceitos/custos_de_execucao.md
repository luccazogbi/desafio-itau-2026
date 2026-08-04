# Custos de execução: Almgren-Chriss e a lei da raiz quadrada

> Nota de estudo — do conceito à fórmula usada no projeto.
> Implementação: `statarb/costs/almgren_chriss.py` · calibração: `scripts/14_cost_calibration.py`

---

## 1. O problema: o preço que você vê não é o preço que você paga

Negociar não custa apenas a corretagem. Uma ordem grande **move o mercado contra
quem a envia**: ao comprar, você consome as ofertas de venda disponíveis e empurra o
preço para cima; ao vender, o oposto. Quanto maior a ordem em relação à liquidez do
papel, pior.

O custo total de uma execução tem três componentes:

| Componente | O que é | Depende de |
|---|---|---|
| **Spread** | a diferença entre compra e venda que você atravessa | característica do papel |
| **Impacto temporário** | o preço se desloca enquanto você negocia, e **se recupera** depois | tamanho da ordem |
| **Impacto permanente** | parte do deslocamento **não volta** (o mercado leu informação no seu fluxo) | tamanho da ordem |

---

## 2. A variável central: participação no volume (Q/ADV)

Todo modelo de impacto gira em torno de uma razão:

$$\frac{Q}{ADV} = \frac{\text{tamanho da sua ordem}}{\text{volume médio diário do papel}}$$

- **Q** — quanto você quer negociar (em dólares ou ações)
- **ADV** — *Average Daily Volume*, quanto o papel negocia por dia

O que importa **não é o tamanho absoluto**, e sim o **relativo**. US$ 5 milhões na
Apple é uma gota; US$ 5 milhões numa small cap ilíquida pode ser metade do volume do
dia — e o preço se move violentamente.

| Q/ADV | Leitura |
|---:|---|
| 0,1% | irrelevante para o mercado |
| 5% | presença notável |
| 20% | você **é** o mercado naquele papel |

---

## 3. Almgren-Chriss: o arcabouço

**Almgren & Chriss (1999, 2000)** formalizaram o problema da execução ótima. A
contribuição central não é uma fórmula de impacto, e sim a **estrutura**:

1. O custo se separa em **impacto temporário** (some depois) e **permanente** (fica);
2. Existe um **trade-off fundamental**:

```
executar rápido  →  muito impacto, pouco risco de mercado
executar devagar →  pouco impacto, mas você carrega risco enquanto isso
```

3. A solução ótima **minimiza custo esperado + λ · risco** — a mesma forma de um
   problema média-variância.

No paper original, o impacto temporário é assumido **linear** na taxa de negociação:

$$\text{impacto por ação} = \eta\,\frac{v}{V} \quad\Longrightarrow\quad
\text{custo total} \propto Q^{2}$$

Essa escolha não foi empírica: com impacto linear o custo é **quadrático**, o problema
tem **solução analítica fechada** (as trajetórias exponenciais famosas do paper) e é
convexo.

---

## 4. A lei da raiz quadrada: a forma empírica do impacto

Décadas de dados de execução real (Almgren et al. 2005; Bouchaud e a literatura da
CFM; casas de TCA) mostraram que o impacto **não é linear — é côncavo**:

$$\boxed{\;\text{impacto} \;=\; \eta\,\sigma\sqrt{\frac{Q}{ADV}}\;}$$

**Concavidade significa:** dobrar a ordem **não** dobra o impacto. Ordens grandes
custam proporcionalmente menos do que o modelo linear previa.

### De onde vem o expoente 3/2 no custo total

Confusão comum. A raiz está no **impacto por dólar negociado**; o custo total
multiplica isso pelo tamanho:

$$\text{custo} = \underbrace{\eta\,\sigma\sqrt{Q/ADV}}_{\text{impacto por dólar}}
\times \underbrace{Q}_{\text{dólares}} = \eta\,\sigma\,\frac{Q^{3/2}}{\sqrt{ADV}}$$

### Três explicações para a concavidade

1. **Resiliência do livro de ofertas** — enquanto você negocia, novos participantes
   repõem liquidez; o mercado "cicatriza" parcialmente durante a execução.
2. **Argumento de ausência de arbitragem** (Bouchaud) — se o impacto fosse linear,
   existiriam estratégias de manipulação lucrativas; a concavidade é o que torna o
   mercado consistente.
3. **Difusão** — sob dinâmica de passeio aleatório, o deslocamento acumulado escala
   com √tempo, e o tempo de execução escala com Q.

---

## 5. ⚠️ Almgren-Chriss **e** raiz quadrada não são modelos concorrentes

Este é o ponto que mais confunde. São **camadas diferentes**:

| | O que é | Analogia |
|---|---|---|
| **Almgren-Chriss** | o **arcabouço** — impacto temporário + permanente, otimizando custo contra risco | a receita do bolo |
| **Square-root law** | a **fórmula** específica do impacto temporário | o tipo de farinha |

Você não escolhe "um ou outro": usa o arcabouço AC **com** a fórmula de raiz dentro
dele. Foi exatamente isso que a prática de mercado fez — manteve a estrutura do paper
e trocou a forma funcional do impacto temporário, que a evidência mostrou ser côncava.

---

## 6. A fórmula usada neste projeto

$$\text{custo}_{\text{USD}} = \Big[\underbrace{s\,|\Delta w|}_{\text{spread}}
+ \underbrace{\eta\,\sigma\sqrt{\tfrac{G}{ADV}}\;|\Delta w|^{3/2}}_{\text{temporário — raiz}}
+ \underbrace{\tfrac{1}{2}\,\gamma\,\sigma\,\tfrac{G}{ADV}\;\Delta w^{2}}_{\text{permanente — linear}}\Big]
\times G$$

onde Δw é o trade em **fração do book** e G é o book bruto. **O colchete é adimensional
(fração do book); o `× G` final converte para dólares** — é o `* self.G` do código.

### ⚠️ Espaço de pesos × espaço de ações (onde foram parar o |x| e o P)

A mesma fórmula costuma aparecer em **espaço de ações**:

$$\text{custo}_{\text{USD}} = \big[\text{impacto}\big] \times |x| \times P$$

com x = ações negociadas e P = preço. As duas versões são equivalentes pela identidade

$$Q \;=\; |x|\cdot P \;=\; |\Delta w|\cdot G \qquad \text{(dólares negociados)}$$

- **O `× |x|`** aparece na nossa versão como o salto de |Δw|^0,5 para |Δw|^1,5:
  o impacto (raiz) multiplicado pelo tamanho negociado. O expoente 3/2 é
  literalmente ½ (da raiz) + 1 (do × Q).
- **O `× P`** está embutido: G e ADV estão **ambos em dólares**, então a razão G/ADV é
  adimensional e o preço se cancela.

Derivação, partindo do impacto por dólar:

$$\eta\sigma\sqrt{\frac{Q}{ADV}}
= \eta\sigma\sqrt{\frac{|\Delta w|G}{ADV}}
= \underbrace{\eta\sigma\sqrt{\frac{G}{ADV}}}_{k_{temp}}|\Delta w|^{1/2}
\;\;\xrightarrow{\;\times\,Q = |\Delta w|G\;}\;\;
k_{temp}|\Delta w|^{3/2}\cdot G$$

**Por que pesos e não ações:** Δw é a variável de decisão do otimizador. Em espaço de
pesos, o custo é função direta do que o solver está otimizando — sem conversão a cada
iteração.

### ⚠️ Atenção: **G/ADV não é a participação**

Erro fácil de cometer ao ler a fórmula. A participação de um trade é

$$\frac{Q}{ADV} = \frac{\Delta w \cdot G}{ADV} \qquad\text{(e não } G/ADV\text{)}$$

O Δw não sumiu — ele foi **fatorado para dentro do expoente**. Separando a raiz do
produto, √(ab) = √a·√b:

$$\eta\sigma\sqrt{\frac{\Delta w\,G}{ADV}}
= \underbrace{\eta\sigma\sqrt{\frac{G}{ADV}}}_{k_{temp}\ \text{(constante)}}
\times \underbrace{\sqrt{\Delta w}}_{\text{completa a participação}}$$

Por isso o expoente final é 1,5 — ele decompõe em duas partes com significados distintos:

$$|\Delta w|^{1.5} = \underbrace{|\Delta w|^{0.5}}_{\text{completa }\sqrt{Q/ADV}}
\times \underbrace{|\Delta w|^{1.0}}_{\times\,Q\ \to\ \text{custo total}}$$

**Exemplo numérico** (G = $1 bi, ADV = $100mm, Δw = 0,3%):

| | |
|---|---:|
| Q = Δw·G | $3mm |
| Participação real Q/ADV | **3%** |
| G/ADV | **10** ← constante de escala, não participação |
| Impacto por `η·σ·√(Q/ADV)` | 17,32 bps |
| Impacto por `k_temp·|Δw|^0,5` | **17,32 bps** ✓ idêntico |

**O que G/ADV significa sozinho:** *"se eu negociasse o book inteiro nesta ação, quantas
vezes o volume diário eu seria?"* — uma referência de liquidez do papel relativa ao
tamanho do fundo. A participação de cada trade só aparece ao combinar com Δw.

**Por que o código separa assim:** `k_temp` não depende da variável de decisão (só de σ
e ADV), então é pré-computado como vetor constante por ação/dia. No CVXPY, a variável
aparece apenas em `|Δw|^1.5`, deixando a expressão mais limpa para o parser de
convexidade.

**Um modelo, dois expoentes** — e é importante saber distinguir:

| Componente | Impacto por dólar | Custo total | Origem |
|---|---|---|---|
| Temporário | √ (côncavo) | Q^1,5 | empírica (square-root law) |
| Permanente | linear | Q² (quadrático) | Almgren-Chriss original |

> Se perguntarem *"vocês usam quadrático?"*, a resposta precisa é:
> **quadrático no permanente, 3/2 no temporário**.

### Onde entra no pipeline — duas vezes, de propósito

1. **Dentro do objetivo do otimizador** — a carteira nasce ciente do próprio
   *footprint* e negocia devagar por conta própria;
2. **Como débito no backtest** — o P&L líquido paga o custo de fato.

Usar o **mesmo** modelo nos dois lugares é deliberado: se o otimizador otimizasse
contra um custo e o backtest cobrasse outro, o resultado seria inconsistente.

Além da penalização no objetivo, o mandato impõe um **limite duro** de participação:

```yaml
participation_cap: 0.05    # nunca negociar mais que 5% do ADV do papel
```

### ⚠️ Limitação: custo **debitado**, não preço **realimentado**

O backtest cobra o impacto como uma taxa — **não move os preços da simulação**:

```python
r = md.returns.loc[d]              # retorno historico, dado EXOGENO
pnl_gross = (pesos * r).sum()      # P&L com os precos que o mercado teve
pnl_net   = pnl_gross - cost_usd   # o impacto entra como DEBITO
```

Os preços do painel permanecem intocados, tivéssemos negociado \$1mm ou \$1bi naquele
papel.

| Abordagem | O que faz | Usamos? |
|---|---|---|
| **Contabilidade de custo** | debita uma taxa que *representa* o impacto | ✅ |
| **Simulação com feedback** | o preço se move pela nossa ordem, afetando P&L e decisões futuras | ❌ |

**Para o impacto temporário isso é correto, não uma aproximação.** Por definição ele
reverte: você paga pior que a tela durante a execução e o preço volta. É um custo
genuinamente pontual — não há deslocamento a propagar.

**Para o impacto permanente há uma folga.** Conceitualmente, empurrar o preço para cima
de forma permanente deveria (a) valorizar a posição que você carrega e (b) piorar o
ponto de partida das suas ordens futuras naquele papel. O fator ½ do termo permanente já
captura parcialmente (a) — representa o preço médio pago durante a execução —, mas o
**auto-impacto acumulado entre rebalanceamentos** não existe no modelo.

Também ficam de fora: o *crowding* consigo mesmo (com turnover de ~15×/ano, negociamos
os mesmos papéis repetidamente) e o feedback no próprio sinal (preços deslocados mudariam
os resíduos e, portanto, o score).

**Materialidade:** modesta, por três razões — o cap de 5% do ADV limita cada trade, large
caps do S&P 500 são resilientes, e o permanente é a menor fatia do custo no nosso modelo
(γ = 0,05 contra η = 0,5). Simulação com feedback exigiria um simulador de mercado —
outro projeto, com erros de modelagem próprios.

---

## 7. Por que isso governa a estratégia

Os custos não são detalhe de implementação — são a **restrição econômica dominante**
deste projeto. Números medidos (dev+val 2020–2023, book de $1 bi):

| | |
|---|---:|
| Custo total | **211 bps/ano** |
| — impacto de mercado | 60% |
| — spread | 30% |
| — aluguel das ações vendidas | 9% |
| Turnover | 15,6× /ano (one-way) |
| Sharpe bruto → líquido | 0,51 → **0,16** |

**Os custos consomem cerca de dois terços do alfa bruto.**

### A ligação com capacidade

Aumentar o book multiplica todos os Q — e com eles, todos os Q/ADV. Cada trade passa a
pesar mais no mercado:

| Book | Sharpe líquido |
|---:|---:|
| $100mm | **0,33** |
| $300mm | 0,26 |
| $1.000mm | **0,16** |

É literalmente o Q/ADV subindo que a curva de capacidade mede (`results/02`).

### O piso que a raiz não resolve

Detalhe contra-intuitivo: reduzir o book 10× derruba os custos apenas de 211 para 174
bps. Motivo — com turnover de ~16–21×/ano, o **spread** (≈4 bps por trade, fixo) cria
um piso de ~80 bps/ano **independente do tamanho**. Em books pequenos, a alavanca de
melhoria deixa de ser reduzir impacto e passa a ser **reduzir giro**.

---

## 8. Resumo para revisão rápida

- **Q/ADV** (participação no volume) é a variável que governa tudo; o que importa é o
  tamanho **relativo** à liquidez, não o absoluto.
- **Almgren-Chriss** = arcabouço (temporário + permanente, custo *vs* risco).
  **Square-root law** = fórmula empírica do impacto temporário. Usamos os dois juntos.
- **Impacto é côncavo**: dobrar a ordem não dobra o impacto → custo total ∝ Q^1,5.
- O modelo entra **no otimizador e no backtest**, com a mesma parametrização.
- Neste projeto, custos consomem ~2/3 do alfa bruto e definem a **capacidade** da
  estratégia (~$100–300mm, não $1 bi).

### Referências

- Almgren, R. & Chriss, N. (2000). *Optimal execution of portfolio transactions*.
  **Journal of Risk**.
- Almgren, R., Thum, C., Hauptmann, E. & Li, H. (2005). *Direct estimation of equity
  market impact*. **Risk**.
- Bouchaud, J.-P. et al. — literatura sobre impacto côncavo e resiliência do livro.
