# O backtest nunca vive um deslistamento — e isso diz mais sobre o viés do que a cobertura

> **Pergunta que motivou:** o motor tem um caminho de código para deslistamento — liquida a
> posição, cobra o spread e **não** realiza perda terminal, o que está documentado como
> *"otimista na perna long"*. Auditando a decomposição de custos do backtest oficial, a linha
> `liquidação por deslistagem` marca **0,0 bps/ano**. Zero exato, em 4 anos.
> A pergunta que nunca havia sido feita: **esse caminho chega a ser executado?**
> **Método:** contar eventos de saída do índice pela composição as-of e confrontar com as
> liquidações efetivamente processadas pelo motor.
> **Artefatos:** `reports/delisting_audit.md` · `scripts/17_delisting_audit.py`
> **Holdout:** lê apenas metadados do painel e o resultado já gravado de dev+val. **Intocado.**

---

## 1. A resposta é não

| | |
|---|---:|
| Dias simulados (2020-01-02 a 2023-12-29) | 1.006 |
| Dias com liquidação por deslistagem | **0** |
| Notional liquidado | **0,0000** |
| Custo de liquidação cobrado | **US$ 0,00** |

Não é arredondamento. O bloco nunca roda.

---

## 2. Por que zero: as empresas não morrem, elas nunca nascem

| | |
|---|---:|
| Empresas que **saíram do S&P 500** durante 2020-2023 (membership as-of) | **68** |
| — destas, **sem nenhum preço** no painel | **36** |
| Liquidações processadas pelo motor | **0** |
| Tickers do painel que perdem preço no **meio** da janela | 8 (só 1 dentro de dev+val) |

Os únicos oito nomes com "morte" observável no painel inteiro (2018-2026) são
`CSRA`, `TWX`, `ANDV`, `EVHC`, `AET`, `ESRX`, `SCG` (todos em 2018) e `COL` (2020-11) —
e nenhum estava em carteira quando parou de ter preço.

O mecanismo é o que `results/04` já descrevia, visto pelo outro lado: quando uma empresa é
adquirida ou quebra, **o yfinance apaga o histórico inteiro dela**. Ela não *sai* do painel
no meio do backtest — ela **nunca entra**. O filtro `md.returns.notna()` em
`data/universe.py` a exclui desde o primeiro dia, anos antes do evento.

---

## 3. As duas consequências

### 3.1 A limitação documentada está vazia

O `README` e o docstring de `engine.py` declaram:

> *"Deslistagem sem perda terminal — otimista na perna long."*

A frase descreve corretamente o código e **descreve um caminho que nunca é percorrido**.
O custo reportado é zero e continuaria zero sob qualquer premissa de perda terminal — se
amanhã impuséssemos −100% em toda deslistagem, o Sharpe não se moveria um dígito.

Isso é o oposto de uma limitação inofensiva: é uma limitação que **parece** endereçada
(está listada, quantificada em 0,0 bps, com ressalva escrita) quando na verdade o dado
necessário para exercê-la não existe. Um leitor da tabela de custos conclui que o
deslistamento foi modelado e custou pouco. O correto é que ele **não foi observado**.

### 3.2 O viés é de outro tipo do que a cobertura mede

A métrica habitual — **7,04%** dos meses-membro de dev+val pertencem a nomes sem preço —
mede quanta **exposição** se perde. É um número honesto e já está no relatório.

O que ele não mostra: a amostra perdida não é aleatória, é **exatamente a população dos
eventos de saída**. Metade das 68 empresas que deixaram o índice na janela não tem um único
dia de preço. O backtest tem exposição **zero** ao tipo de evento que a composição as-of
existe para capturar.

Vale separar dois vieses que costumam ser tratados como um:

| Viés | O que é | Resolvido? |
|---|---|---|
| **Seleção de membros** | operar a lista de hoje em vez da de cada data | ✅ **sim** — composição as-of |
| **Seleção de desfechos** | os membros que tiveram desfecho ruim não têm preço | ❌ **não** — e não dá com dado gratuito |

O universo as-of resolve o primeiro. O segundo permanece inteiro, e é o que a literatura
chama de survivorship bias no sentido forte. Dizer "backtest as-of, sem viés de
sobrevivência" seria impreciso; o correto é "**viés de seleção de membros resolvido; viés
de desfecho quantificado em 7,04% dos meses-membro e não corrigível nas fontes atuais**".

---

## 4. Mitigação (proposta, não implementada)

1. **Reter o último preço negociado** dos nomes que somem e impor um desfecho explícito na
   data de saída do índice: −100% em falência, prêmio de aquisição em M&A. Com dados
   gratuitos o desfecho teria de vir de outra fonte (o motivo da saída está no change log da
   Wikipedia, já baixado por `scripts/13`) — e a premissa passaria a ser **declarada** em vez
   de silenciosa.
2. **Teste de sensibilidade barato:** rodar o backtest só com os nomes de cobertura completa
   e comparar. Se o resultado não se move, o viés é tolerável na prática. Já sugerido em
   `results/04` §6, ainda não feito.
3. **Bloomberg/CRSP resolvem direto** — é exatamente isto que se compra.

---

## 5. Para o relatório

Este é um resultado negativo com bom retorno de credibilidade: mostra que o projeto audita
as próprias limitações em vez de apenas listá-las. A formulação que sugiro:

> *"A composição as-of elimina o viés de seleção de membros. Resta o de desfecho: das 68
> empresas que deixaram o índice em 2020-2023, 36 não têm preço algum em fontes gratuitas,
> e o backtest processou zero liquidações por deslistagem. Medimos o buraco (7,04% dos
> meses-membro) em vez de declará-lo resolvido."*

Também vale como nota de método: **a linha de custo que marcava exatamente 0,0 era a pista**.
Um zero perfeito num backtest de quatro anos raramente é um zero — em geral é um caminho de
código que não foi exercido.
