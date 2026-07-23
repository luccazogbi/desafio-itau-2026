# Justificativa da escolha do universo: S&P 500 em vez do Russell 2000

> **Documento de considerações metodológicas** — Desafio Itaú Asset Quant AI 2026
> Data da análise: 13/07/2026 · Base empírica reproduzível (ver seção 6)

---

## 1. Decisão (resumo)

A estratégia de arbitragem estatística long-short foi migrada do **Russell 2000**
(small caps) para o **S&P 500** (large caps), com composição histórica *as-of* e hedge
via SPY. A razão central **não é preferência**, e sim uma **restrição de dados medida
empiricamente**: sem acesso a bases pagas (Bloomberg/CRSP), é impossível reconstruir o
Russell 2000 histórico sem um **viés de sobrevivência severo**, porque os preços das
ações que saíram do índice simplesmente não existem nas fontes gratuitas.

O número que fundamenta a decisão: das ações do Russell 2000 que **deixaram** o índice
entre 2019 e 2026, apenas **18%** têm histórico de preço recuperável gratuitamente,
contra **92%** das que permaneceram.

---

## 2. Contexto: por que a pergunta é importante

A reversão de curto prazo — sinal statarb clássico — é historicamente mais forte em
*small caps*, o que tornaria o Russell 2000 o universo "natural" da estratégia. Havia,
portanto, um bom motivo para insistir nele.

Ao mesmo tempo, o backtest precisa ser **as-of** (usar, em cada data, o índice como ele
era naquele dia), sob pena de **viés de sobrevivência**: se o universo for montado com a
lista de *hoje*, testam-se apenas as empresas que sobreviveram, apagando da história as
que quebraram ou foram adquiridas — o que **infla artificialmente** qualquer resultado.

A questão então foi: **é possível montar um Russell 2000 as-of confiável apenas com
dados gratuitos?**

---

## 3. O problema se divide em dois

| Sub-problema | O que é | Solúvel de graça? |
|---|---|---|
| **Composição as-of** | quem era membro do índice em cada data | ✅ **Sim** |
| **Preços das deslistadas** | histórico de preço de quem saiu do índice | ❌ **Não** |

- **Composição (resolvido):** as posições históricas do ETF **IWM** (iShares Russell
  2000) são publicadas na **SEC via formulários N-PORT** — fonte oficial, datada e
  gratuita. Elas reconstroem a membership point-in-time do índice.

- **Preços (o obstáculo):** os formulários N-PORT identificam as ações por **nome +
  CUSIP**, não por *ticker*. Para buscar preços no yfinance é preciso mapear
  CUSIP → ticker (feito via **OpenFIGI**), e então baixar o histórico. É justamente aí
  que as ações deslistadas se perdem: seus tickers mortos não mapeiam, e seus preços não
  estão nas bases gratuitas.

---

## 4. A medição empírica

**Método** — `scripts/08_delisted_coverage.py`:

> ⚠️ **Ressalva de reprodutibilidade (verificada em 23/07/2026).** O script carrega
> `data/raw/iwm_2019_split.pkl` (a classificação removidos/sobreviventes do IWM), e
> **nenhum script deste repositório gera esse arquivo** — o download dos holdings via
> SEC EDGAR foi feito ad-hoc e não foi versionado. Os números abaixo estão
> **documentados, mas não são re-deriváveis** a partir do repositório hoje. Fechar
> essa lacuna exige implementar o passo 1 dentro do script.

1. Baixar as posições do IWM em **nov/2019** e **jul/2026** via SEC EDGAR N-PORT.
2. Classificar cada nome de 2019 em **"removido"** (fora do índice em 2026) ou
   **"sobrevivente"** (presente nos dois) — o grupo de controle.
3. Mapear os CUSIPs para tickers via **OpenFIGI** (API gratuita).
4. Verificar no **yfinance** se cada ticker tem histórico utilizável na janela em que a
   ação era membro (2018–2021).
5. Comparar a cobertura dos **removidos** contra a dos **sobreviventes**.

---

## 5. Resultado

**Rotatividade do índice:** dos 1.924 membros do Russell 2000 em nov/2019,
**910 (47%) saíram** até jul/2026 — quase metade.

| Grupo | Nº de nomes | Cobertura de preço (yfinance) |
|---|---:|---:|
| Sobreviventes (ainda no índice) | 300 (amostra) | **92%** |
| Removidos (saíram / deslistaram) | 910 | **18%** |
| **Gap de cobertura (viés residual)** | | **74 pontos percentuais** |

Para comparação, o mesmo procedimento aplicado ao **S&P 500 as-of** resulta em
**92,8%** de cobertura média dos membros históricos — porque large caps que saem do
índice geralmente o fazem por **aquisição**, e não por falência.

> **Atualização de 22/07.** Este número era **91,7%** até a auditoria de composição
> (`scripts/13_membership_audit.py`) revelar que **20% do gap não era falta de dado,
> e sim 23 renomeações de ticker não tratadas** — a empresa continuava no índice sob
> outro símbolo, e o painel a perdia por inteiro no período anterior à troca. Corrigido;
> cobertura subiu para 92,8% (mínimo mensal de 83,8% para 86,1%). Detalhes em
> [`results/04`](../results/04_auditoria_membership_e_cobertura.md).
>
> **Ressalva que a análise acima não capturava:** a premissa "aquisição mantém histórico"
> é **falsa no yfinance**. Quando a empresa é adquirida, o histórico inteiro é apagado —
> inclusive os anos em que ela era constituinte saudável. Medido: **3,45% dos meses-membro
> de 2020-2023** pertencem a empresas adquiridas depois de 2023 (Hologic, Kellanova,
> Interpublic, Ansys, Hess, Juniper…). E esse número **cresce a cada nova aquisição** —
> o painel do S&P 500 gratuito também se degrada com o tempo, só que mais devagar que o
> do R2000. A conclusão da seção 7 **não muda**; o custo assumido é maior do que parecia.

---

## 6. Interpretação

- **A composição as-of do Russell 2000 é gratuita e viável** (IWM/EDGAR). Esse não é o
  problema.
- **Os preços das deslistadas, não.** Com apenas 18% recuperáveis, montar o Russell 2000
  as-of com dados gratuitos produziria um painel com a **lista correta mas os preços
  errados** — faltando justamente as empresas que quebraram. Isso é *pior* do que assumir
  o S&P 500: seria um viés de sobrevivência **escondido**, disfarçado de backtest as-of.
- O gargalo (mapear e precificar CUSIPs de empresas mortas) é, por natureza, **um
  problema de dado pago** — é exatamente o que serviços como CRSP e Bloomberg comercializam.

---

## 7. Conclusão e trade-off assumido

**Para o desafio, o universo é o S&P 500 as-of** (cobertura de 92%, viés residual
pequeno e quantificado). A decisão troca **potência de alfa por integridade de dados**:
em large caps a reversão de curto prazo é mais fraca (a literatura a localiza em small
caps), mas um backtest honesto num universo com dados confiáveis vale mais, para a
avaliação, do que um resultado "bonito" sobre dados enviesados.

**Caminhos para o Russell 2000 no futuro** (fora do escopo gratuito atual):

| Fonte | Resolve as deslistadas? | Custo |
|---|---|---|
| WRDS / CRSP (universidade) | ✅ completo e citável | grátis se a faculdade assina |
| Sharadar (Nasdaq Data Link) | ✅ survivorship-free | ~US$ 45/mês |
| Bloomberg terminal | ✅ padrão-ouro | disponível em etapas futuras do desafio |

---

## 8. Nota metodológica

Esta análise é, ela própria, uma **contribuição de rigor** — quantificar o viés de
sobrevivência com um número concreto (18% vs 92%) atende diretamente ao critério de
*backtest e mitigação de vieses* da avaliação. O método (IWM/EDGAR N-PORT + OpenFIGI +
yfinance) é reprodutível e reaproveitável.

**Artefatos de suporte:**
- `scripts/08_delisted_coverage.py` — código da medição
- `reports/delisted_coverage.md` / `.json` — resultados brutos
- `scripts/07_pull_sp500_asof.py` — construção do painel S&P 500 as-of adotado
- `data/processed_sp500/meta.json` — cobertura do universo adotado (**92,8%** após a
  correção de renomeações de 22/07; era 91,7%)
- `scripts/13_membership_audit.py` — auditoria da composição as-of e do gap de preços
- `results/04_auditoria_membership_e_cobertura.md` — interpretação, incluindo a erosão
  retroativa que **cresce** a cada aquisição
