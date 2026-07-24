# Duas tentativas de elevar o Sharpe — uma falhou, a outra revelou uma fragilidade

> **Pergunta:** o que dá para fazer para o Sharpe subir **sem inflar o número**?
> Duas hipóteses foram testadas: **(1)** filtrar ações pela velocidade de reversão,
> como no Avellaneda-Lee original; **(2)** reduzir o giro, que na época consumia
> 69% do alfa bruto (hoje 53%, justamente por causa da decisão tomada aqui).
> **Artefatos:** `reports/kappa_analysis.md` · `scripts/10_kappa_analysis.py` ·
> `scripts/02_run_backtest.py --rebalance`
> **Holdout:** tudo em dev+val (2020-2023). **Intocado.**
> **Atualizado em 24/07/2026** — §1 ganhou o modelo nulo que invalida o argumento do
> "só 4% não revertem" (o veredito não muda).

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

### O "só 4% não revertem" não significa nada (corrigido em 24/07)

A versão anterior deste documento usava um segundo argumento: *"só 4% do universo falha o
teste de reversão (AR(1) com b ≥ 1), então não há nada a filtrar"*. **Esse argumento não se
sustenta**, por duas razões medidas depois:

| Critério | universo real | **ruído iid puro** |
|---|---:|---:|
| `b ≥ 1` (o que usávamos) | 4% | **5%** |
| `b ≥ 1` **ou** `tau ≥ J/2` (critério real do A&L) | 19% | **22%** |

Um caminho cumulativo de ruído iid é um passeio aleatório — por construção **não reverte**.
Ainda assim ele "passa" no teste `b < 1` em 95% dos casos, porque o OLS de um AR(1) perto da
raiz unitária tem viés de baixa em amostra pequena (Dickey-Fuller: `E[b] ≈ 1 − 5,3/T`, com
T = 59). O universo real é **indistinguível do ruído** sob esse corte.

Duas correções decorrentes:

1. **O critério que aplicávamos não era o do A&L.** O paper não descarta só `b ≥ 1`; exige
   reversão rápida o bastante para a janela (`tau < J/2`). Sob o critério correto o corte é
   **19%**, não 4%.
2. **A constante de tempo estava rotulada como meia-vida.** `tau = 12 dias` é a constante de
   tempo; a meia-vida é `ln2·tau ≈ 8 dias`. O relatório antigo superestimava a persistência
   em ~44%.

**Nada disso muda o veredito**, porque a conclusão vem da tabela de quartis — uma comparação
*relativa* entre ações medidas do mesmo jeito, onde o viés de amostra pequena atinge todas
igualmente — e não do corte binário.

### Por que faz sentido econômico

Nosso sinal acumula resíduos por **60 dias**, e a autocorrelação do z-score decai com
meia-vida de **21,4 dias** (`results/06`). Ele é construído para reversão **lenta**.
Resíduos que revertem em poucos dias são provavelmente ruído de microestrutura — já
arbitrados por HFT em large caps, e mortos antes de o acumulador de 60 dias sequer
registrá-los.

*(Ressalva de `results/06`: essa meia-vida é em boa parte consequência mecânica da própria
janela de 60 dias, não uma medida limpa da persistência econômica do fenômeno.)*

*Resultado negativo, mas informativo: a decisão de operar todo o universo, que era
implícita, agora tem respaldo empírico.*

---

## 2. Reduzir o giro — **funciona, mas menos do que parecia**

### 2.1 A primeira leitura era enganosa

| rebalance | Sharpe bruto | Sharpe líquido | turnover | custos |
|---:|---:|---:|---:|---:|
| 3 (era o default) | 0,511 | 0,160 | 15,6× | 211 |
| 5 | 0,435 | 0,105 | 13,3× | 191 |
| 8 | 0,401 | 0,075 | 11,8× | 177 |
| **10 (adotado em 24/07)** | 0,568 | **0,266** | 11,0× | 168 |
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
  sinal tem meia-vida de ~21 dias e não se perde muito ao segurar posição por mais tempo;
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
| 2 | `rebalance_every_days` 3 → **10** | Bruto constante + custos −20% | ✅ **ADOTADO 24/07** |
| 3 | Implementar **tranching** | Elimina dependência de fase | 📋 proposto |
| 4 | Reportar a curva de capacidade como conclusão | Já medido (`results/02`) | ✅ feito |

### Sobre a recomendação 2 — adotada em 24/07

Mudar o `rebalance_every_days` é uma **decisão de calibração tomada em dev+val** — a mesma
natureza do `alpha_bps_per_z = 3`. É defensável porque o argumento é o **canal de custo**
(robusto: bruto constante, custos caindo monotonicamente), e **não** "escolhemos o valor de
maior Sharpe". Se fosse pelo Sharpe, teríamos escolhido a fase 2020-01-03 e reportado 0,341.

**O que aconteceu ao adotar** (`results/01`): a rodada oficial saiu com Sharpe líquido
**0,266**, custos de 211 → **168 bps** e turnover de 15,6× → **11,0×**.

> ⚠️ **Os 0,266 são a fase 2020-01-02, que é o lado FAVORÁVEL da distribuição.** A tabela
> §2.2 já previa exatamente isso (0,568 bruto / 0,266 líquido para esta data de início) — e
> reproduziu ao centavo. A expectativa honesta continua sendo a **média entre fases: 0,205**,
> com dispersão de ±0,09. A data de início não foi escolhida agora: está no config desde o
> começo, fixada pelo warm-up dos betas. Mas o fato de ela ser favorável **precisa** ser
> reportado junto com o número.

**Ganho atribuível ao mecanismo: ~+0,06.** O resto é calendário.

### Custos colaterais da mudança (não aparecem no Sharpe)

Registrados porque a decisão não é gratuita:

| Efeito | Antes (3d) | Depois (10d) |
|---|---:|---:|
| \|net\| do livro **com hedge** | 0,022 | **0,042** |
| Participação típica no ADV | 0,47% | **1,10%** |

O hedge precisa carregar posição maior porque o beta residual deriva mais entre decisões, e
cada trade fica maior porque se negocia menos vezes. Nenhum dos dois viola o mandato, mas os
dois **consomem folga** — e é essa folga que permitiria escalar o book.

---

## 5. O que NÃO foi feito, de propósito

| Caminho | Ganho aparente | Por que foi recusado |
|---|---|---|
| Remover neutralidade setorial | +0,06 (medido) | Assumir risco não controlado e chamar de alfa |
| Afrouxar neutralidade de fatores | — | O retorno viria de prêmio de risco, não de previsão |
| Escolher a melhor fase de calendário | +0,18 | Puro cherry-picking |
| Condicionar exposição ao regime de vol | potencialmente grande | A análise de regime é *post-hoc* no dev+val; só vale se **pré-registrada** e testada no holdout (`results/03` §3.2) |
| Encurtar o período para 2020-2022 | — | Descartar o único ano ruim |

O caminho de ~0,16 para ~0,21 foi percorrido em 24/07 (recomendação 2), **por mecanismo e não
por busca**. O Sharpe honesto de hoje é **0,21 ± 0,09** — a rodada oficial marca 0,266 porque
a data de início do config calha de ser uma fase favorável.

O que **continua** não sendo feito de propósito é a lista acima. E a fragilidade da §3 segue
aberta: espaçar o rebalanceamento **não** removeu a dependência de fase — apenas mudou o
patamar. Só o *tranching* remove.
