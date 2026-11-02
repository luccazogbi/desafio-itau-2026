# Roadmap — Quant Itaú (2026)

Estratégia: **StatArb Long-Short no S&P 500** (composição histórica *as-of*), book de
**$1 bi dollar-neutral**, neutra a **FF5+Momentum**, custos **Almgren-Chriss**, hedge de
beta com **SPY**. Sinal oficial: **`resid_ou`** (reversão de resíduo, Avellaneda-Lee).

**Como usar:** marque `- [x]` ao concluir. `[x]` = feito · `[ ]` = pendente.
**Prazos:** pré-relatório **31/07/2026** · entrega final **17/08/2026** (PDF 16:9, máx. 5 páginas, anônimo).

> # 🔴 HOLDOUT GASTO EM 07/08/2026 — O SINAL FOI REPROVADO
>
> | | dev+val | **holdout (2024-26)** |
> |---|---:|---:|
> | Sharpe bruto | +0,57 | **−0,77** |
> | Sharpe líquido | +0,27 | **−1,15** |
> | IC21 | +0,036 (val) | **−0,030** |
>
> O sinal **inverteu**, e o bruto também é negativo — não é custo. IC negativo nos três
> regimes de vol. Não é artefato de dado (cobertura no holdout é *melhor*: 97,6% vs 92,8%).
> Período inteiro 2020-2026: Sharpe líquido **−0,10**.
> Veredito: [`results/09`](results/09_holdout_o_veredito.md).
>
> **Consequência para este roadmap:** todo item de calibração/melhoria abaixo está
> **congelado**. Ajustar qualquer parâmetro agora seria in-sample. O que segue válido é a
> infraestrutura (painel as-of, motor, funil, snapshot, testes) e os itens que exigem
> **dados novos**.

> **Decisões-chave já tomadas** (para não reabrir):
> 1. **Universo = S&P 500**, não Russell 2000. Motivo medido: das ações **removidas** do
>    índice, só **18%** têm preço no R2000 gratuito, contra **46%** no S&P 500 → survival
>    bias muito mais severo no R2000. (Os 92%/99% citados em outros lugares são a cobertura
>    dos **sobreviventes** de cada índice — outro denominador.) Ver
>    [`considerações/justificativa_universo_sp500_vs_russell2000.md`](considerações/justificativa_universo_sp500_vs_russell2000.md).
> 2. **Sinal = `resid_ou` sozinho**, não um blend. É o melhor dos 11 candidatos do funil,
>    com IC positivo nos dois splits (0,051 dev / 0,036 val); combinar com os outros não
>    agregou nada. Com t-stat Newey-West: **2,50 dev / 1,66 val** — a validação não chega
>    a 2, então "robusto" seria forte demais (ver seção 3).
> 3. **Sem Bloomberg** até etapas futuras do desafio — todo o trabalho roda com dados gratuitos.

---

## 0. Fundação do pipeline — concluída

- [x] Estrutura modular (`statarb/`: data, factors, signals, risk, costs, portfolio, backtest)
- [x] Config central (`config/config.yaml`) — nada hard-coded
- [x] Universo investível point-in-time (membership + filtros de liquidez, anti-survivorship)
- [x] Modelo de fatores FF5+MOM (betas rolling, vol idio, resíduos anti-lookahead)
- [x] Otimizador convexo cvxpy (dollar-neutral, neutralidade de fatores, caps) + portão de viabilidade
- [x] Modelo de custo Almgren-Chriss (no otimizador E no backtest)
- [x] Motor de backtest event-driven próprio (execução t+1 anti-lookahead)
- [x] Hedge de beta residual (config `hedge.instrument`, agora **SPY**)
- [x] Métricas + tearsheet + módulo de estilo `viz/style.py`
- [x] **20 testes** de sanidade (neutralidade, custos convexos, anti-lookahead de 9 sinais,
      IC, smoke, trava do holdout, aluguel do short, Newey-West, Gârleanu-Pedersen, snapshot)
- [x] Crosscheck de P&L contra a biblioteca `bt` (corr 0,996) — **no sintético**
- [x] Gerador sintético (gabarito: valida a esteira recuperando alfa plantado)
- [x] **Correções de 22/07** (todas com teste de regressão):
  - `statarb/stats.py`: t-stat **Newey-West** — o t ingênuo inflava ~2× por
    sobreposição de janelas (IC de 21d numa grade de 5d)
  - **Trava do holdout** no motor: `backtest.end` agora é 2023-12-31 e o engine
    RECUSA passar de `holdout_start` sem `--allow-holdout` explícito
  - **Aluguel da perna short** (`costs.borrow_bps_per_year`, 40 bps/ano) — era o
    único custo relevante ignorado; estava documentado só no PIPELINE v1 arquivado
  - Hedge, deslistagem e rebalance do ETF **deixam de ser gratuitos**; `gross`/`net`
    ganham versão **com hedge** (a neutralidade reportada excluía o ETF)
  - Unidade do objetivo do otimizador: risco agora vive no mesmo horizonte do alfa
    (λ 150 → 7,143 = 150/21 — correção de unidade, **não** muda a solução)

---

## 1. Dados & Universo — S&P 500 as-of (concluído)

- [x] Composição histórica **as-of** via change log da Wikipedia (`fja05680/sp500`) — `scripts/07_pull_sp500_asof.py`
- [x] Preços/volume/abertura/máx-mín (yfinance) dos **665** membros históricos
      (2018–2026) + **SPY** (hedge) — eram 684 antes da correção de renomeações
- [x] Fatores FF5+MOM reais (Ken French — loader próprio robusto)
- [x] Market cap (proxy) — `scripts/07b_add_marketcap_sp500.py`
- [x] **Cobertura medida = 92,8%** dos membros as-of (era 91,7% antes da correção de
      renomeações; viés residual quantificado no `meta.json` e em `results/04`)
- [x] **Estudo que justifica S&P 500 vs R2000** — `scripts/08_delisted_coverage.py`:
      entre as **removidas** de cada índice, **18% (R2000) vs 46% (S&P 500)** têm preço.
      (Os 92%/99% são a cobertura dos **sobreviventes** de cada índice — outro denominador.)
      ⚠️ Medição de 14/07, **não re-derivável** hoje (o script depende de um pickle que
      nenhum script gera). Equivalente reprodutível: `scripts/13` e `scripts/17`.
- [x] **Auditoria da composição as-of (22/07)** — `scripts/13_membership_audit.py`,
      interpretação em [`results/04`](results/04_auditoria_membership_e_cobertura.md):
  - Cross-check de 2 logs de eventos: **94,7% de concordância exata de data** ✓
  - **26 renomeações de ticker** detectadas; o painel tratava só 3 → **20% do "viés de
    dados" era bug nosso**, não indisponibilidade (ex.: sem `UTX→RTX` a United
    Technologies sumia do painel de 2018 a abr/2020). Corrigido.
  - **Erosão retroativa medida**: 3,45% dos meses-membro de 2020-23 pertencem a empresas
    que eram constituintes saudáveis e foram adquiridas **depois** — o Yahoo apaga o
    histórico inteiro. Esse número **cresce a cada aquisição**.
- [x] Estamos operando só ações do universo as-of com preço disponível? **Sim** — o filtro
      `md.returns.notna()` em `data/universe.py` garante isso. O que faltava era medir o
      custo dessa exclusão, agora quantificado acima.
- [x] **Congelar/versionar o painel** (23/07, `scripts/16_snapshot_panel.py` +
      `statarb/snapshot.py`) — repuxar mudava o universo histórico e nenhuma comparação
      entre rodadas era limpa. Agora:
  - `data/snapshots/<id>/` guarda as cópias (70 MB, fora do git);
    `snapshots/<id>.json` guarda o manifesto com SHA-256 de cada arquivo (10 KB, **no git**)
  - o backtest grava `snapshot` no `metrics.json` e **avisa** se o painel não corresponde a
    nenhum snapshot conhecido (resultado não rastreável)
  - `--diff A B` mede a **erosão entre versões** em meses-membro
  - Snapshot inicial: **`2026-07-23`** — 665 tickers, 77 sem preço, gap de 7,04% em dev+val
- [x] **Auditoria do deslistamento (24/07)** — `scripts/17_delisting_audit.py`,
      interpretação em [`results/08`](results/08_deslistamento_ausente_no_backtest.md):
      das **68 empresas que saíram do índice em 2020-2023**, **36 não têm preço algum**, e o
      motor processou **ZERO** liquidações por deslistagem em 1.006 dias. A linha de custo
      "liquidação por deslistagem = 0,0 bps" não é custo desprezível — é caminho de código
      nunca executado. Consequência: a composição as-of resolve o viés de **seleção de
      membros**; o de **seleção de desfechos** permanece inteiro e não é corrigível no
      gratuito. A limitação "deslistagem sem perda terminal" estava listada como endereçada
      e é, na prática, **vazia**.
- [ ] Validação **independente** da composição (S&P Global bloqueia acesso automatizado,
      HTTP 403) — rota possível: holdings do IVV via SEC EDGAR N-PORT
- [ ] (proposto, `results/08` §4) impor **desfecho explícito** na data de saída do índice
      (falência = −100%, M&A = prêmio), usando o motivo já baixado pelo `scripts/13` —
      troca uma premissa silenciosa por uma declarada
- [ ] (opcional) Ampliar janela para 2010+ se o relatório pedir histórico mais longo


## 2. Modelo de Fatores — validado nos dados reais

- [x] Betas/resíduos rodando no painel S&P 500 as-of (89 datas de estimação)
- [ ] (fino) Sensibilidade a janela de beta (252d) e frequência de re-estimação (21d)

## 3. Sinal de Alfa — decidido por evidência

- [x] Verificar sinais de alfa da literatura para o novo modelo de estratégia que estamos buscando (Big Caps - S&P 500)
  > Pesquisa 14/07 (Claude): 3 candidatos implementados e TESTADOS no funil
  > (dev/val, S&P 500 as-of). Veredito: **NENHUM agrega — blend segue descartado.**
  > **Re-medido em 24/07 no painel atual, com t Newey-West** (os números de 14/07 eram t
  > INGÊNUOS — a correção de 22/07 chegou ao `resid_ou` e não aos cortados).
  > Artefatos: `reports/funnel.md` (12 linhas) e `reports/blend_analysis.md`.
  - [x] **STM** (Medhat-Schmeling, *RFS* 2022): CORTADO — no nosso universo fator-neutro o
        efeito **INVERTE**: IC21 dev **−0,054** (t_NW **−2,25**; o "t −3,6" citado antes era o
        ingênuo, hoje −3,37). É o anti-resid_ou (corr P&L **−0,667**).
  - [x] **Overnight** (Lou-Polk-Skouras, *JFE* 2019): CORTADO — IC ≈ 0 e troca de sinal entre
        splits (IC21 dev −0,021 / val +0,010). Confirmado (painel ganhou `prices_open` de
        brinde, script 07c).
  - [x] **Salience** (Cosemans-Frehen, *JFE* 2021): CORTADO — e o corte fica **mais forte** com
        Newey-West: dev IC21 t **1,77** (não 2,8 — aquele era o ingênuo), ou seja **nem passa
        no dev**; val t **0,13**. Redundante c/ resid_ou (corr P&L **+0,655**).
  - [x] Funil + análise de correlação rodados (scripts 04 e 09) — decisão por evidência
  > Conclusão: **`resid_ou` segue sendo O sinal.** Sinais novos só com mudança estrutural
  > (dados pagos, small caps, ou afrouxar neutralidade) — decisão futura c/ orientador.

- [x] **11** candidatos da literatura implementados como plug-ins (`statarb/signals/`) —
      dos quais **10 são avaliáveis no painel real**: o `earnings_yield` exige EPS, que o
      painel gratuito não tem, e sempre foi rotulado como sinal de **validação da esteira**
      no sintético (cobertura 0,00 no funil, linha `NaN`).
- [x] Funil de avaliação (IC 1/5/21d vs retorno residual, quintis, splits dev/val/holdout) — `scripts/04_signal_funnel.py`
- [x] Funil rodado no S&P 500 as-of → **`resid_ou` é o melhor dos 11** — mas o quão forte é
      a evidência mudou com a correção de 22/07. Medido com **Newey-West** (23/07):

      | split | IC21 | t ingênuo | **t Newey-West** |
      |---|---:|---:|---:|
      | dev (n=151) | 0,051 | 4,20 | **2,50** |
      | val (n=50)  | 0,036 | 2,26 | **1,66** |

      O "t≈4 dev / t≈2 val" citado antes era o t **ingênuo**, que assume ICs independentes
      quando as janelas de 21d numa grade de 5d se sobrepõem. Honestamente: o IC é positivo
      e consistente nos dois splits (0,051 / 0,036), o dev é significativo, mas **a validação
      fica em t = 1,66 — abaixo de 2**. `resid_ou` continua sendo a melhor escolha entre os
      candidatos, mas "robusto nos dois splits" era forte demais.
- [x] **Funil COMPLETO re-rodado (24/07)** — o artefato só tinha o `resid_ou`, porque
      `04_signal_funnel.py resid_ou` sobrescreve o `funnel.md` do funil inteiro. Agora
      `reports/funnel.md` tem as **12 linhas** (11 sinais + blend) que sustentam a decisão.
      **O `resid_ou` reproduziu bit a bit** os números de 23/07 (diferença máxima 0,0) —
      teste de reprodutibilidade de graça, ganho por acaso. IC21 por sinal:

      | sinal | IC21 dev (t_NW) | IC21 val (t_NW) | veredito |
      |---|---:|---:|---|
      | **`resid_ou`** | **+0,051 (2,50)** | **+0,036 (1,66)** | **escolhido** |
      | blend | +0,051 (2,47) | +0,034 (1,51) | **pior que o `resid_ou` sozinho** |
      | idio_reversal | +0,024 (2,02) | +0,019 (1,21) | positivo nos 2, mais fraco |
      | str_turnover | +0,031 (1,31) | +0,020 (0,71) | cobertura 26%, t baixo |
      | salience | +0,028 (1,77) | +0,003 (0,13) | não valida |
      | seasonality | +0,015 (0,79) | −0,009 (−0,44) | ~0 |
      | mad · trend_factor · left_tail | ~0 ou negativo | ~0 ou negativo | cortados |
      | overnight | −0,021 (−1,61) | +0,010 (0,54) | troca de sinal |
      | stm | −0,054 (−2,25) | −0,017 (−0,52) | inverte |

      ⚠️ **Risco de repetição:** o `04` grava sempre no mesmo `funnel.md`, então rodar um
      subconjunto apaga o funil completo em silêncio — mesmo padrão do `07` sem `07b`.
- [x] Blend testado e **descartado** — agora com artefato: o blend rende IC21 **0,051 dev /
      0,034 val** contra **0,051 / 0,036** do `resid_ou` puro. Ou seja, adicionar
      `str_turnover` **piora** a validação. Confirmado por correlação (`scripts/09`): STM tem
      corr de P&L **−0,667** com o `resid_ou` e salience **+0,655** — um é o espelho, o outro
      é redundante; nenhum traz informação nova.
- [x] Notebook explicativo focado no `resid_ou`, passo a passo (`notebooks/pipeline_walkthrough.ipynb`)
- [ ] (fino) Sensibilidade dos parâmetros do `resid_ou` (acúmulo J=60d, janela z W=252d) — sem overfitar

## 4. Backtest & Validação

> **Rodada oficial vigente: 24/07/2026** (`reports/sp500_dev_val/`, seção 7 do notebook).
> Substitui a de 23/07 após a decisão de `rebalance_every_days` 3 → 10.
>
> **Sharpe bruto 0,57 / líquido 0,27** · turnover 11,0×/ano · custos **168 bps/ano**
> (impacto 61% · spread 26% · **aluguel do short 12%**) · P&L líq. US$ 59,3mm ·
> gross 0,999 (**1,012 com hedge**) · |net| 0,002 (**0,042 com hedge**) ·
> |net setorial| = 0,050 (no limite, restrição **ativa**) · max DD −7,9%.
>
> ⚠️ **O número honesto é 0,21 ± 0,09, não 0,27.** O resultado depende da data de início:
> deslocando só ela, o Sharpe vai de **0,077 a 0,341**. A rodada oficial (início 2020-01-02,
> fixado a priori pelo warm-up dos betas) caiu no lado **favorável** — e a tabela de fases de
> `results/07` §2.2 já previa exatamente 0,568/0,266 para essa data, reproduzindo ao centavo.
> Sempre reportar o 0,27 com a banda ao lado.
>
> **Por que subiu de 0,16 para 0,27:** custos caíram 43 bps/ano (211 → 168) ao girar 3×
> menos vezes — esse é o mecanismo, e vale **+0,06** na média entre fases. O resto (+0,05) é
> a fase favorável.
>
> **Custos colaterais registrados:** |net| com hedge dobrou (0,022 → 0,042) e a participação
> típica no ADV mais que dobrou (0,47% → 1,10%). Nenhum viola o mandato; os dois consomem
> folga.
>
> *Medição à parte:* uma rodada intermediária saiu com a restrição setorial **inativa**
> (sem rodar o `scripts/07b` os setores viram todos `"Unknown"`) e deu 0,220 contra 0,160 —
> quantifica o custo do controle setorial em **−0,06**.
>
> Calibração a priori feita UMA vez (α=3bps/z ≈ IC×vol_idio). O `rebalance_every_days = 10`
> foi decidido em 24/07 **pelo canal de custo**, não pelo Sharpe de uma rodada — se fosse
> pelo Sharpe teríamos escolhido a fase 2020-01-03 e reportado 0,341. Nota:
> max_abs_factor_expo alto (0,60) é ARTEFATO de medição na crise COVID (betas re-estimados
> explodem em mar-abr/2020); no dia a dia |expo_mkt| ~0,015, e a tolerância adaptativa foi
> acionada em 33 de 1.006 dias.
- [x] **Backtest oficial do `resid_ou`** no S&P 500 as-of (dev+val; holdout trancado)
- [x] Métricas: Sharpe líquido, turnover, drawdown, decomposição de custos (gross → net)
- [x] Confirmar neutralidade de fatores + SETORIAL e hedge SPY nos dados reais
- [x] **Análise de capacidade** (18/07, `scripts/11`, `results/02`): backtest re-rodado em
      5 tamanhos — Sharpe líq. **0,41** ($100mm) → **0,27** ($1bi), monotônico. Faixa sustentável:
      **$100–300mm**; em books pequenos o piso de custo vira o SPREAD (alavanca = reduzir giro)
- [x] **Análise de regime de volatilidade** (18/07, `scripts/12`, `results/03`): IC por tercil
      de vol do SPY = **−0,00 / +0,06 / +0,08** (baixa/média/ALTA) → 2023 foi REGIME, não
      decaimento; a estratégia é provisão de liquidez (ganha quando o mercado precisa)
- [x] **Tentativas de elevar o Sharpe honestamente** (23/07, interpretação em
      [`results/07`](results/07_tentativas_de_elevar_o_sharpe.md)):
  - **Filtro de κ (Avellaneda-Lee) — REJEITADO pela evidência.** `scripts/10` rodado pela
    1ª vez: o IC é **maior** nas de reversão LENTA (Q1 0,050 → Q4 0,024); filtrar
    derrubaria o IC em 25%. Coerente com o sinal acumular 60d — ele é feito para reversão
    lenta. **Corrigido em 24/07:** o argumento auxiliar *"só 4% do universo não reverte"*
    **não vale** — ruído iid puro também "passa" no teste `b<1` em 95% dos casos (viés
    Dickey-Fuller em T=59), e o critério real do A&L (`tau < J/2`) descarta 19%, não 4%.
    Também corrigido o rótulo `tau` = constante de tempo (12d), meia-vida = 8d. O veredito
    não muda: vem do ordenamento por quartil, não do corte binário.
  - **Reduzir giro — funciona, mas menos do que parecia.** A leitura ingênua sugeria
    rebalance 10d dando +0,11 de Sharpe. **Teste de fase desmontou:** fixando 10 dias e
    deslocando só a data inicial, o Sharpe líquido varia de **0,077 a 0,341** — dispersão
    MAIOR que a suposta melhora. Média entre fases: 3d → **0,141**, 5d → 0,172,
    10d → **0,205**. Ganho real ≈ **+0,06**, sustentado pelo mecanismo (bruto constante
    0,50→0,52 + custos caindo 211→168), não pelo número de uma rodada.
  - **Fragilidade descoberta:** o resultado depende de em que dia se começa a operar.
    Causa: giramos 100% do book de uma vez. Correção proposta: **tranching** (girar ~10%
    todo dia). Não implementado — exige mudar o agendamento do motor.
- [x] **DECIDIDO em 24/07:** `rebalance_every_days` **3 → 10**. Base: o **canal de custo**
      (bruto praticamente constante entre fases, custos caindo monotonicamente 211 → 168
      bps), não o Sharpe de uma rodada. Ganho atribuível ao mecanismo: **+0,06**. Todos os
      números do projeto foram regerados (02, 05, 11, 12, 14, 15, 17 + notebook).
      ⚠️ A rodada oficial marca **0,266**, mas a expectativa honesta é **0,205 ± 0,09** — a
      data de início do config é uma fase favorável. Ver `results/07` §4.
- [ ] (proposto) Implementar **tranching** — elimina a dependência de fase sem mexer no Sharpe médio
- [ ] Crosscheck `bt` nos dados reais
- [x] **Ida única ao holdout (2024+) — FEITA em 07/08/2026, com autorização explícita.**
      Resultado: Sharpe bruto **−0,77**, líquido **−1,15**, IC21 **−0,030**, P&L **−US$ 122mm**.
      O sinal inverteu. A defesa por regime não se sustenta (IC negativo nos 3 regimes,
      inclusive vol alta). Diagnóstico reprodutível: `scripts/19_holdout_diagnostico.py`.
      Interpretação: [`results/09`](results/09_holdout_o_veredito.md).
      ⚠️ **O holdout está gasto** — a trava do `engine.py` fica no lugar para impedir
      calibração in-sample sobre 2024-2026.
- [ ] (evolução proposta, NÃO retro-ajustar) condicionar gross/rebalance ao regime de vol

## 5. Otimização & Custos — calibração final

- [x] Restrição de **neutralidade setorial** no otimizador (|net por setor| ≤ 5%) + setores reais no painel
- [x] Calibração a priori de `alpha_bps_per_z` (3) — justificada, sem grid search.
      `rebalance_every_days` foi a priori 3 e passou a **10** em 24/07, por evidência do
      canal de custo (não por busca de Sharpe) — ver `results/07` §4.
- [x] **Calibrar η, γ e spread com ADV/volatilidade reais do S&P 500** (23/07,
      `scripts/14` + `scripts/07d`, interpretação em
      [`results/05`](results/05_calibracao_custos.md)). Resultado: **só o spread era
      estimável** com dado diário — os outros dois foram *demonstrados* não-identificáveis:
  - **`spread_bps` 5,0 → 4,0** — MEDIDO por Corwin-Schultz (JF 2012): 5,55 bps round-trip,
    monotônico na liquidez (D1 8,1 → D10 3,8). O valor antigo era conservador em ~25%.
    Armadilha: sem o ajuste de gap overnight e truncando negativos antes da agregação, o
    estimador dava 55 bps — 10× o correto.
  - **`ac_gamma` mantido (0,05)** — a rota do Amihud **degenera**: `ILLIQ × ADV ≈ E|r|`,
    logo `γ ≈ E|r|/σ ≈ 0,66` para qualquer ação (medido idêntico nos 10 decis de liquidez).
  - **`ac_eta` mantido (0,5)** — não estimável sem dados de execução; passou no teste de
    plausibilidade (10,2 bps a 1% do ADV, faixa publicada 5–15 bps).
  - Contexto medido: a estratégia opera a **0,47% do ADV**, um décimo do próprio cap de 5%.
- [x] **Otimização multi-período (Gârleanu-Pedersen) vs. horizonte heurístico** (23/07,
      `scripts/15` + `statarb/portfolio/garleanu_pedersen.py`, interpretação em
      [`results/06`](results/06_gp_multiperiodo_vs_heuristica.md)):
      **⚠️ Números corrigidos em 24/07:** a primeira execução rodou sobre o painel
      **sintético** (o `scripts/15` ficou de fora da correção de `data.panel` de 22/07 e
      não foi re-rodado). Detectado por inconsistência de ADV entre `results/05` e `06`.
  - Forma fechada **derivada** no módulo (não citada) e **validada por simulação** — a
    política GP domina todas as perturbações dela.
  - **`φ` medido no painel**: autocorrelação do z-score decai de 0,886 (5d) a 0,231 (40d)
    → **meia-vida de 21,4 dias úteis**. É **consistente com** o `horizon_days = 21`, mas
    **não é validação independente**: a autocorrelação de uma soma móvel de 60 dias decai
    mecanicamente, e ruído branco puro pelo mesmo acumulador dá "meia-vida" de 28,6d. Os
    dois números descendem da mesma escolha de desenho (`accum_days = 60`).
  - **Veredito:** a heurística **reage ~6× demais ao sinal** (`H` ótimo ≈ 3,7, não 21) e
    **rebalanceia devagar demais** (fecha 4,9% do gap por período contra 20% do ótimo).
    Os dois erros **se cancelam em parte** — compensação acidental, frágil a mudanças de
    sinal, custo ou tamanho de book.
  - **Ressalva que ficou CENTRAL com os números reais:** o **spread é 45% do custo** no
    trade típico (não 11%, como saiu do painel sintético) — e é justamente o componente
    **linear** que o GP, com custo quadrático, não representa. Custo linear gera banda de
    não-negociação; quadrático gera ajuste suave. O mapeamento GP → nossa mesa é frouxo.
  - `horizon_days` **NÃO foi alterado** — mudá-lo move o backtest e deve ser decisão
    consciente. Evolução proposta: **banda de não-negociação** dentro do otimizador convexo
    (representa o spread com a curvatura certa e mantém o mandato).

## 6. GenAI (15% da nota) — contínuo

- [x] `docs/genai_log.md` mantido a cada sessão (etapa + contribuição + impacto) — já com ~9 entradas
- [ ] Red team: usar GenAI para atacar a tese do `resid_ou` e listar fragilidades
- [ ] Identidade visual do robô gerada por IA (não pode ser o ÚNICO uso de GenAI)

## 7. Relatório final & Robô

- [ ] Nome + identidade do robô, coerentes com "reversão de resíduo / arbitragem estatística"
- [ ] Deck 16:9, máx. 5 páginas, anônimo, ~750 palavras, visual
- [ ] Cobrir os critérios: conceito, modelagem, backtest, análise, conclusão, GenAI, robô
- [ ] Revisão de anonimato (sem nome/equipe/universidade/logo) — descumprir = eliminação

---

## Anexo — Itens estacionados (fora do escopo atual)

- **Bloomberg** (quando o acesso chegar nas próximas etapas): upgrade de qualidade dos dados
  (`INDX_MWEIGHT_HIST`, TRI, EPS PIT) — o pipeline lê o mesmo schema, é só trocar a fonte.
- **Small caps / Russell 2000**: só viável com **WRDS/CRSP** (checar faculdade), **Sharadar**
  (~US$45/mês) ou **Bloomberg** — inviável no gratuito (medido: 18% de cobertura das deslistadas).

- Scripts legados: `06_pull_yfinance.py` (proxy R2000, substituído pelo `07`); `01_pull_bloomberg.py`
  (aguarda acesso). Sinais dormentes (`trend_factor`, `mad`, `str_turnover`, `left_tail`,
  `seasonality`, `earnings_yield`, `blend`) — implementados, testados, não usados na estratégia atual.
