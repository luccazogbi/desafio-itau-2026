# Duas tentativas de elevar o Sharpe — uma falhou, a outra revelou uma fragilidade

> **Pergunta:** o que dá para fazer para o Sharpe subir **sem inflar o número**?
> Duas hipóteses foram testadas: **(1)** filtrar ações pela velocidade de reversão,
> como no Avellaneda-Lee original; **(2)** reduzir o giro, já que os custos consomem
> 69% do alfa bruto.
> **Artefatos:** `reports/kappa_analysis.md` · `scripts/10_kappa_analysis.py` ·
> `scripts/02_run_backtest.py --rebalance`
> **Holdout:** tudo em dev+val (2020-2023). **Intocado.**

---

## 1. Filtro de κ (Avellaneda-Lee) — **rejeitado pela evidência**

### A hipótese

O A&L estimam a velocidade de reversão κ de cada ação e **descartam** as que não
revertem (passeio aleatório). Nós operávamos todas. Se o IC fosse maior entre as de
reversão rápida, implementar o filtro **não seria overfitting** — seria implementar a
referência de forma mais fiel, com justificativa teórica anterior ao dado.

### O que os dados dizem

| Quartil de velocidade | IC (fwd 21d) | t (Newey-West) |
|---|---:|---:|
| Q1 (mais **lento**) | **+0,0504** | +2,25 |
| Q2 | +0,0510 | +2,48 |
| Q3 | +0,0422 | +2,67 |
| Q4 (mais **rápido**) | **+0,0237** | +1,18 |

| Grupo | IC | t |
|---|---:|---:|
| Todas as ações (como fazemos) | **+0,0454** | +2,52 |
| Só reversão rápida (κ > mediana) | +0,0342 | +2,12 |
| Só reversão lenta (κ < mediana) | +0,0495 | +2,40 |

**Veredito: filtrar não ajuda — atrapalha.** A relação é monotonicamente *decrescente*
na velocidade de reversão, o oposto do previsto. Restringir às rápidas derrubaria o IC
em **25%**.

Além disso, só **4%** do universo falha o teste de reversão (AR(1) com b ≥ 1). Não há
praticamente nada a filtrar num universo de large caps.

### Por que faz sentido econômico

Nosso sinal acumula resíduos por **60 dias** e tem meia-vida medida de **21,7 dias**
(`results/06`). Ele é construído para reversão **lenta**. Resíduos que revertem em poucos
dias são provavelmente ruído de microestrutura — já arbitrados por HFT em large caps, e
mortos antes de o acumulador de 60 dias sequer registrá-los.

*Resultado negativo, mas informativo: a decisão de operar todo o universo, que era
implícita, agora tem respaldo empírico.*

---

## 2. Reduzir o giro — **funciona, mas menos do que parecia**

### 2.1 A primeira leitura era enganosa

| rebalance | Sharpe bruto | Sharpe líquido | turnover | custos |
|---:|---:|---:|---:|---:|
| 3 (atual) | 0,511 | 0,160 | 15,6× | 211 |
| 5 | 0,435 | 0,105 | 13,3× | 191 |
| 8 | 0,401 | 0,075 | 11,8× | 177 |
| **10** | 0,568 | **0,266** | 11,0× | 168 |
| 15 | 0,422 | 0,138 | 9,6× | 152 |

Tentador parar aqui e adotar 10 dias (+0,11 de Sharpe!). **Dois sinais de alerta
impediram:** a curva não é monotônica (5 e 8 são *piores* que 3), e o Sharpe **bruto** —
que é anterior a qualquer custo — oscila 40% entre configurações. Reduzir giro não deveria
mexer no alfa bruto assim.

### 2.2 O teste que desmonta a leitura ingênua

Mudar o intervalo muda **em quais datas do calendário** você negocia. Fixei o intervalo em
10 dias e desloquei apenas a data inicial:

| Início | Sharpe bruto | Sharpe líquido |
|---|---:|---:|
| 2020-01-02 | 0,568 | 0,266 |
| 2020-01-03 | 0,630 | **0,341** |
| 2020-01-06 | 0,604 | 0,292 |
| 2020-01-07 | 0,436 | 0,104 |
| 2020-01-08 | 0,499 | 0,188 |
| 2020-01-09 | 0,388 | **0,077** |
| 2020-01-10 | 0,489 | 0,167 |

**Mesma configuração, mesmo período, mesmo sinal — Sharpe de 0,077 a 0,341.**

A dispersão de fase (0,26) é **maior** que a suposta melhora de 3→10 dias (0,106). O
"ganho" de adotar 10 dias estava inteiramente dentro do ruído de calendário.

### 2.3 A comparação honesta: média entre fases

| rebalance | Sharpe bruto | **Sharpe líquido** | desvio entre fases | custos | turnover |
|---:|---:|---:|---:|---:|---:|
| 3 | 0,499 | **0,141** | ±0,022 (n=3) | 211 | 15,6× |
| 5 | 0,509 | **0,172** | ±0,115 (n=5) | 191 | 13,3× |
| 10 | 0,516 | **0,205** | ±0,091 (n=7) | 168 | 11,0× |

Agora a história é coerente e o mecanismo é verificável:

- **o alfa bruto é praticamente constante** (0,499 → 0,516) — como deveria ser, já que o
  sinal tem meia-vida de 21,7 dias e não se perde muito ao segurar posição por mais tempo;
- **os custos caem monotonicamente** (211 → 168 bps/ano);
- **o líquido sobe como consequência aritmética disso**, não por sorte.

**Ganho real: ≈ +0,06 de Sharpe**, não os +0,11 da leitura ingênua.

> **Ressalva estatística:** as fases não são amostras independentes — são a mesma janela,
> o mesmo sinal, os mesmos dados. Não cabe calcular erro-padrão e declarar significância.
> O que sustenta a conclusão **não é o número**, é o **mecanismo**: bruto constante +
> custos caindo ⟹ líquido subindo.

---

## 3. O achado mais importante não era o que procurávamos

A dispersão de fase de **±0,09 a ±0,11** é, por si só, uma fragilidade da estratégia como
está desenhada: **o resultado depende materialmente de em que dia da semana você começa a
operar.** Isso não é alfa nem risco — é sorte de calendário.

A causa é estrutural: rebalanceamos **100% do book de uma vez**, a cada N dias. Toda a
carteira fica exposta às condições de um único dia.

**A correção padrão de mesa é *tranching*:** em vez de girar 100% a cada 10 dias, girar
**~10% todo dia**. O prazo médio de manutenção é o mesmo, o custo é o mesmo — mas o risco
de timing é diversificado ao longo de 10 dias em vez de concentrado num só.

Previsão: colapsaria a dispersão de fase para perto de zero **sem mudar o Sharpe médio**.
Não é um jeito de aumentar o retorno; é um jeito de deixar de depender de sorte.

*Não implementado* — exige mudar a lógica de agendamento do motor (hoje `if i % every == 0`
decide o book inteiro). É a recomendação técnica mais concreta deste documento.

---

## 4. Recomendações

| # | Ação | Base | Status |
|---|---|---|---|
| 1 | **Não** implementar o filtro de κ | Evidência contrária, medida | ✅ decidido |
| 2 | `rebalance_every_days` 3 → **10** | Bruto constante + custos −20% | ⏸️ **aguarda decisão** |
| 3 | Implementar **tranching** | Elimina dependência de fase | 📋 proposto |
| 4 | Reportar a curva de capacidade como conclusão | Já medido (`results/02`) | ✅ feito |

### Sobre a recomendação 2

Mudar o `rebalance_every_days` é uma **decisão de calibração tomada em dev+val** — a mesma
natureza do `alpha_bps_per_z = 3`. É defensável porque o argumento é o **canal de custo**
(robusto: bruto constante, custos caindo monotonicamente), e **não** "escolhemos o valor de
maior Sharpe". Se fosse pelo Sharpe, teríamos escolhido a fase 2020-01-03 e reportado 0,341.

O parâmetro **não foi alterado** — a decisão é sua, e ela move todos os números do relatório.

---

## 5. O que NÃO foi feito, de propósito

| Caminho | Ganho aparente | Por que foi recusado |
|---|---|---|
| Remover neutralidade setorial | +0,06 (medido) | Assumir risco não controlado e chamar de alfa |
| Afrouxar neutralidade de fatores | — | O retorno viria de prêmio de risco, não de previsão |
| Escolher a melhor fase de calendário | +0,18 | Puro cherry-picking |
| Condicionar exposição ao regime de vol | potencialmente grande | A análise de regime é *post-hoc* no dev+val; só vale se **pré-registrada** e testada no holdout (`results/03` §3.2) |
| Encurtar o período para 2020-2022 | — | Descartar o único ano ruim |

O Sharpe honesto de hoje continua **0,16** — e o caminho para ~0,20-0,21 está identificado,
medido e justificado por mecanismo, não por busca.
