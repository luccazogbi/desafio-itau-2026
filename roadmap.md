# Roadmap — Quant Itaú (2026)

Estratégia: **StatArb Long-Short no S&P 500** (composição histórica *as-of*), book de
**$1 bi dollar-neutral**, neutra a **FF5+Momentum**, custos **Almgren-Chriss**, hedge de
beta com **SPY**. Sinal oficial: **`resid_ou`** (reversão de resíduo, Avellaneda-Lee).

**Como usar:** marque `- [x]` ao concluir. `[x]` = feito · `[ ]` = pendente.
**Prazos:** pré-relatório **31/07/2026** · entrega final **17/08/2026** (PDF 16:9, máx. 5 páginas, anônimo).

> **Decisões-chave já tomadas** (para não reabrir):
> 1. **Universo = S&P 500**, não Russell 2000. Motivo medido: no R2000 gratuito só 18% das
>    ações deslistadas têm preço (vs 92% no S&P 500) → survival bias severo. Ver
>    [`considerações/justificativa_universo_sp500_vs_russell2000.md`](considerações/justificativa_universo_sp500_vs_russell2000.md).
> 2. **Sinal = `resid_ou` sozinho**, não um blend. O funil no S&P 500 mostrou que é o único
>    com IC robusto; combinar com os outros não agregou nada.
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
- [x] 11 testes de sanidade (neutralidade, custos convexos, anti-lookahead, IC, smoke)
- [x] Crosscheck de P&L contra a biblioteca `bt` (corr 0,996)
- [x] Gerador sintético (gabarito: valida a esteira recuperando alfa plantado)

---

## 1. Dados & Universo — S&P 500 as-of (concluído)

- [x] Composição histórica **as-of** via change log da Wikipedia (`fja05680/sp500`) — `scripts/07_pull_sp500_asof.py`
- [x] Preços/volume (yfinance) de todos os 684 membros históricos (2018–2026) + **SPY** (hedge)
- [x] Fatores FF5+MOM reais (Ken French — loader próprio robusto)
- [x] Market cap (proxy) — `scripts/07b_add_marketcap_sp500.py`
- [x] **Cobertura medida = 91,7%** dos membros as-of (viés residual quantificado no `meta.json`)
- [x] **Estudo que justifica S&P 500 vs R2000** — `scripts/08_delisted_coverage.py` (18% vs 92%)
- [ ] (opcional) Ampliar janela para 2010+ se o relatório pedir histórico mais longo

## 2. Modelo de Fatores — validado nos dados reais

- [x] Betas/resíduos rodando no painel S&P 500 as-of (89 datas de estimação)
- [ ] (fino) Sensibilidade a janela de beta (252d) e frequência de re-estimação (21d)

## 3. Sinal de Alfa — decidido por evidência

- [ ] Verificar sinais de alfa da literatura para o novo modelo de estratégia que estamos buscando (Big Caps - S&P 500)
  > Pesquisa 14/07 (Claude): 3 candidatos implementados e TESTADOS no funil
  > (dev/val, S&P 500 as-of). Veredito: **NENHUM agrega — blend segue descartado.**
  > Resultados em `reports/funnel.md` e `reports/blend_analysis.md`:
  - [x] **STM** (Medhat-Schmeling, *RFS* 2022): CORTADO — no nosso universo fator-neutro o efeito INVERTE (IC21 dev −0,057, t −3,6) e é o anti-resid_ou (corr P&L −0,67)
  - [x] **Overnight** (Lou-Polk-Skouras, *JFE* 2019): CORTADO — IC ≈ 0, inconsistente entre splits (painel ganhou `prices_open` de brinde, script 07c)
  - [x] **Salience** (Cosemans-Frehen, *JFE* 2021): CORTADO — dev IC21 t 2,8 mas NÃO valida (val t 0,3) e é redundante c/ resid_ou (corr P&L +0,66)
  - [x] Funil + análise de correlação rodados (scripts 04 e 09) — decisão por evidência
  > Conclusão: **`resid_ou` segue sendo O sinal.** Sinais novos só com mudança estrutural
  > (dados pagos, small caps, ou afrouxar neutralidade) — decisão futura c/ orientador.

- [x] 8 candidatos da literatura implementados como plug-ins (`statarb/signals/`)
- [x] Funil de avaliação (IC 1/5/21d vs retorno residual, quintis, splits dev/val/holdout) — `scripts/04_signal_funnel.py`
- [x] Funil rodado no S&P 500 as-of → **`resid_ou` é o único robusto** (IC21 t≈4 dev / t≈2 val)
- [x] Blend testado e **descartado** (str_turnover não agregou; demais são proxies de fator)
- [x] Notebook explicativo focado no `resid_ou`, passo a passo (`notebooks/pipeline_walkthrough.ipynb`)
- [ ] (fino) Sensibilidade dos parâmetros do `resid_ou` (acúmulo J=60d, janela z W=252d) — sem overfitar

## 4. Backtest & Validação

> **1ª rodada oficial dev+val concluída em 15/07** (`reports/sp500_dev_val/`, seção 7 do
> notebook): Sharpe bruto 0,53 / líquido 0,20, turnover 15×/ano, custos 198 bps/ano,
> gross ~1,0, |net| ≤ 0,002, |net setorial| ≤ 0,05 ✓. Calibração a priori feita UMA vez
> (α=3bps/z ≈ IC×vol_idio; rebalance a cada 3d, coerente com horizonte 21d) — sem caça
> ao Sharpe. Nota: max_abs_factor_expo alto (0,59) é ARTEFATO de medição na crise
> COVID (betas re-estimados explodem em mar-abr/2020); no dia a dia |expo_mkt| ~0,015.
- [x] **Backtest oficial do `resid_ou`** no S&P 500 as-of (dev+val; holdout trancado)
- [x] Métricas: Sharpe líquido, turnover, drawdown, decomposição de custos (gross → net)
- [x] Confirmar neutralidade de fatores + SETORIAL e hedge SPY nos dados reais
- [ ] **Análise de capacidade** (alfa líquido × tamanho do book) — custos comem 63% do
      bruto em $1bi; book menor deve reter muito mais → análise-chave p/ o relatório
- [ ] Cenários de crise (queda de 2020, bear de 2022) — análise honesta
- [ ] Crosscheck `bt` nos dados reais
- [ ] Ida única ao **holdout** (2024+) — número final da estratégia

## 5. Otimização & Custos — calibração final

- [x] Restrição de **neutralidade setorial** no otimizador (|net por setor| ≤ 5%) + setores reais no painel
- [x] Calibração a priori de `alpha_bps_per_z` (3) e `rebalance_every_days` (3) — justificadas, sem grid search
- [ ] Calibrar η, γ e spread com ADV/volatilidade reais do S&P 500
- [ ] (opcional avançado) otimização multi-período (Gârleanu-Pedersen) vs. horizonte heurístico

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
- **Nasdaq-100 histórico** (projeto de pesquisa do orientador): rota QQQ/IWM via **SEC EDGAR
  N-PORT** + OpenFIGI documentada.
- Scripts legados: `06_pull_yfinance.py` (proxy R2000, substituído pelo `07`); `01_pull_bloomberg.py`
  (aguarda acesso). Sinais dormentes (`trend_factor`, `mad`, `str_turnover`, `left_tail`,
  `seasonality`, `earnings_yield`, `blend`) — implementados, testados, não usados na estratégia atual.
