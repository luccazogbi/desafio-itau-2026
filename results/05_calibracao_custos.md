# Calibração do modelo de custo — dois dos três parâmetros não são estimáveis (e isso é o resultado)

> **Tarefa:** roadmap 5 — *"calibrar η, γ e spread com ADV/volatilidade reais do S&P 500"*.
> Até aqui os três vinham da literatura (5 bps, 0,5, 0,05).
> **Método:** estimar o que dá para estimar no próprio universo; demonstrar — não assumir —
> o que não dá.
> **Artefatos:** `reports/cost_calibration.md` / `.parquet` · `scripts/14_cost_calibration.py`
> · dados de máxima/mínima por `scripts/07d_add_highlow_sp500.py`
> **Amostra:** 570 ações, 2018-01 a 2023-12 — **holdout intocado**.

---

## 1. O modelo e a pergunta

Custo por dólar negociado, com participação $p = Q/ADV$:

$$ c(p) \;=\; \underbrace{\text{spread}}_{\text{cruzar a ponta}} \;+\; \underbrace{\eta\,\sigma\sqrt{p}}_{\text{impacto temporário}} \;+\; \underbrace{\tfrac{1}{2}\gamma\,\sigma\,p}_{\text{impacto permanente}} $$

O σ e o ADV já eram reais (entram por ação, vindos do painel). O que estava por calibrar
eram os **três coeficientes**.

---

## 2. Spread: estimável, e estimado ✅

**Corwin & Schultz (JF 2012)** recupera o spread comparando a amplitude de 1 dia com a de
2 dias: a volatilidade escala com o tempo, o spread entra uma vez por dia.

| | Mediana (round-trip) | Varia com liquidez? |
|---|---:|---|
| **Corwin-Schultz** | **5,55 bps** | **sim** — D1 8,1 → D10 3,8 bps |
| Abdi-Ranaldo (RFS 2017) | 45,2 bps | não — plano em todos os decis |

**O Abdi-Ranaldo não tem poder aqui.** Ele estima $S^2/4$ por covariância; com spread real
de ~5 bps isso vale ~6·10⁻⁸, contra um ruído de ~2,5·10⁻⁵ — **400× maior**. Metade das ações
dá $S^2$ negativo, e o que resta após truncar em zero é raiz de ruído. Por isso o número não
responde à liquidez. O CS usa uma razão de amplitudes, com muito mais sinal, e sobrevive.

> **Armadilha de implementação que custou uma ordem de grandeza.** A primeira versão dava
> **55 bps**. Duas correções, ambas no paper original: (i) **ajuste de gap overnight** — sem
> ele, o gap entra na amplitude de 2 dias e infla o spread; (ii) truncar negativos **depois**
> da agregação mensal, não em cada observação (E[max(X,0)] > max(E[X],0)). Com as duas, 5,55 bps.

**→ `spread_bps`: 5,0 → 4,0** (meio-spread medido 2,8 + ~1 bp de corretagem). O valor antigo
era conservador em ~25%.

---

## 3. γ: a rota do Amihud degenera ❌

A ideia era usar a iliquidez de Amihud (2002) — quanto o preço anda por dólar negociado —
para recuperar o impacto permanente:

$$ \gamma \;=\; \text{ILLIQ} \times ADV \,/\, \sigma $$

O resultado saiu **0,65 em todos os dez decis de liquidez**, de US\$ 43mm a US\$ 884mm de ADV.
Não é coincidência — é álgebra:

```
ILLIQ = E[|r| / volume$]  ≈  E|r| / ADV
γ     = ILLIQ × ADV / σ   ≈  E|r| / σ   ≈  0,66   para QUALQUER ação
```

O ADV **cancela**. O que sobra é a razão entre desvio absoluto médio e desvio-padrão de uma
normal (≈0,8) — sem nenhuma informação de liquidez. A tabela por decil comprova: a coluna
`gamma_amihud` (0,644–0,722) acompanha `E|r|/σ` (0,665–0,691) ponto a ponto.

O ILLIQ serve para **ordenar** ações por iliquidez relativa, não para calibrar um coeficiente
estrutural. **→ `ac_gamma` mantido em 0,05.**

---

## 4. η: não é estimável, mas é plausível ⚠️

O coeficiente da lei da raiz descreve o impacto **dentro** da execução de uma ordem. Dado
diário não vê ordens. Almgren et al. (2005) precisaram da base proprietária do Citigroup;
Tóth et al. (2011), idem. Não há como estimar aqui — e fingir que há seria fabricar rigor.

O que dá para fazer é **testar plausibilidade contra σ e ADV reais deste universo**:

| η | participação típica (0,47% ADV) | a 1% do ADV | a 5% (cap) |
|---|---:|---:|---:|
| 0,25 | 3,5 bps | 5,1 bps | 11,4 bps |
| **0,50 (config)** | **7,0 bps** | **10,2 bps** | **22,8 bps** |
| 0,75 | 10,5 bps | 15,3 bps | 34,2 bps |
| 1,00 | 14,0 bps | 20,4 bps | 45,6 bps |

Frazzini-Israel-Moskowitz (2018) e Almgren et al. (2005) situam o impacto de uma ordem de
~1% do ADV em large caps americanas na faixa de **5–15 bps**. Com σ real de 2,1%/dia,
η = 0,5 implica **10,2 bps** — dentro da faixa. **→ mantido.**

---

## 5. Contexto: onde a estratégia realmente opera

| | |
|---|---:|
| ADV mediano do universo | US$ 152 mm |
| Vol diária mediana | 2,1% |
| Trade típico por nome | US$ 0,71 mm |
| **Participação típica** | **0,47% do ADV** |
| Cap de participação | 5% do ADV |

A estratégia opera a **um décimo do seu próprio cap**. O impacto de mercado não é limitado
pela restrição — é limitado pelo tamanho do book contra o alfa disponível, o que é coerente
com a análise de capacidade (`results/02`).

---

## 6. O que este exercício entrega

Dos três parâmetros, **um foi medido e dois foram demonstrados não-identificáveis**. Isso é
um resultado, não uma falha: a diferença entre "usamos 0,5 porque a literatura usa" e
"0,5 não é estimável com os dados disponíveis, e verificamos que implica 10 bps a 1% do ADV,
dentro da faixa publicada" é exatamente o tipo de rigor que o edital pede.

**Efeito líquido no backtest:** spread de 5,0 → 4,0 bps economiza ~15 bps/ano sobre o gross
(giro de 15×/ano), compensando parte dos ~20 bps/ano do aluguel de short que passou a ser
cobrado nas correções de 22/07.
