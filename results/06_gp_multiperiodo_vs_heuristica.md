# Gârleanu-Pedersen vs. a heurística do `horizon_days` — a heurística reage 4× demais ao sinal

> **Tarefa:** roadmap 5 — *"otimização multi-período (Gârleanu-Pedersen) vs. horizonte heurístico"*.
> **Pergunta:** nosso otimizador é de **um** período. Para não ficar míope, inflamos o alfa
> por `horizon_days = 21`. Isso é paliativo. GP (JF 2013) resolvem o problema multi-período
> de verdade — **a heurística chega perto do ótimo? Onde erra?**
> **Artefatos:** `reports/gp_vs_heuristica.md` · `scripts/15_gp_vs_heuristica.py` ·
> módulo `statarb/portfolio/garleanu_pedersen.py`
> **Holdout:** painel até 2023-12-31, sem backtest nem métrica de desempenho. **Intocado.**

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
| Autocorrelação | 0,842 | 0,738 | 0,652 | 0,568 | 0,485 | 0,402 | 0,322 | 0,243 |

Decaimento exponencial limpo → **φ = 0,0315/dia**, **meia-vida = 21,7 dias úteis**.

> **Achado colateral que vale o relatório:** o `horizon_days = 21` foi escolhido *a priori*,
> por argumento econômico ("o sinal tem horizonte de ~1 mês"), sem olhar dado. A meia-vida
> medida é **21,7 dias**. É uma **validação independente** de um parâmetro calibrado às cegas.

### Custo quadrático equivalente

λ = **6,9**, casando a **derivada** do custo Almgren-Chriss no tamanho típico de trade —
é o custo *marginal* que entra na condição de primeira ordem. Válido de 1,0× a 2,8× esse
tamanho; fora daí a aproximação degrada.

---

## 3. O confronto

Ambas as políticas têm a forma $x' = \text{inércia}\cdot x + \text{resposta}\cdot\alpha$:

| | GP (ótimo) | Heurística `H=21` | razão |
|---|---:|---:|---:|
| Inércia (peso na posição anterior) | 0,866 | 0,980 | 1,13× |
| **Taxa de trade** (1 − inércia) | **0,134** | 0,020 | **6,7×** |
| **Resposta ao alfa** (`H` implícito) | **5,5** | 21 | **3,8×** |
| `aim / markowitz` | 0,831 | — (não encolhe) | |

### 3.1 A heurística reage ~4× demais ao sinal

O `H` que reproduziria a resposta ótima é **5,5**, não 21. O raciocínio original —
*"a posição rende ~21 dias, logo vale 21 dias de alfa"* — ignora duas coisas que GP
descontam: **(a)** o sinal decai ao longo desses 21 dias (meia-vida 21,7d significa que
metade do alfa já evaporou no meio do caminho) e **(b)** haverá custo de negociação de novo
no futuro.

### 3.2 Mas quase não rebalanceia por conta própria

Inércia de 0,980 contra 0,866: a política ótima fecha **13%** do gap até o alvo por
rebalance; a heurística fecha 2%. GP antecipa que carregar posição grande custa caro depois
e a puxa de volta mais rápido.

### 3.3 Os dois erros se cancelam em parte

Reage demais ao sinal, mas move devagar. É compensação **acidental** — funciona até parar de
funcionar. Não há garantia de que sobreviva a uma mudança no sinal, nos custos ou no tamanho
do book. Essa é a fragilidade real que o exercício expõe.

---

## 4. Ressalva que impede exagerar a conclusão

O confronto acima é **sem restrições**. No pipeline real o otimizador opera com
`gross = 0,999` — **na restrição de orçamento**. Ali o nível do alfa deixa de determinar o
tamanho do book e passa a determinar só o **tilt** entre as ações. Então a diferença de
nível **não se traduz 1:1** em diferença de carteira.

O que sobrevive à restrição é a **dinâmica**: com que velocidade se persegue o alvo. E aí
o GP é inequívoco.

Além disso, GP supõem custo **quadrático**. O nosso AC tem três componentes: spread
(**linear**, 11% do custo no trade típico), impacto temporário (**potência 3/2**) e
permanente (quadrático). O componente linear é justamente o que GP não representa — custo
linear gera, na teoria, uma **banda de não-negociação**, enquanto o quadrático gera ajuste
parcial suave. São políticas qualitativamente diferentes.

**Por isso este exercício diagnostica a heurística; não substitui o otimizador convexo**,
que trata o custo com a curvatura certa e carrega todo o mandato (dollar-neutral,
neutralidade de fator e setor, caps de posição e ADV) que o GP não tem.

---

## 5. O que fazer com isso

1. **Não trocar o otimizador por GP.** Ele perderia todas as restrições de mandato, que são
   a tese de risco do projeto.
2. **Revisar `horizon_days`** — a evidência aponta para algo entre 5 e 10, não 21. Mas isso
   **muda o backtest** e deve ser feito como decisão consciente e documentada, não silenciosa.
   *Não alterei o config.*
3. **Evolução natural (proposta, não implementada):** usar a taxa de trade do GP como
   **banda de não-negociação** dentro do otimizador convexo — fica com a inércia correta do
   multi-período *e* com as restrições do mandato.
4. **Para o relatório:** o item mais forte aqui não é o número, é o método — a heurística foi
   confrontada com a solução ótima da literatura, os insumos foram medidos no próprio painel,
   a derivação foi validada numericamente, e as limitações da comparação estão declaradas.
