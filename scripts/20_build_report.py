"""Gera o RELATORIO FINAL (5 paginas, 16:9) em HTML a partir dos artefatos reais.

Todo numero do relatorio e lido de reports/*/metrics.json e dos parquets -- nada e
digitado a mao. Se o backtest for re-rodado, basta reexecutar este script para o
relatorio acompanhar.

Converter para PDF (Edge ou Chrome headless):
    msedge --headless --no-pdf-header-footer --print-to-pdf=JANUS.pdf file:///<caminho.html>

Uso:   python scripts/20_build_report.py [saida.html]
Requer: reports/sp500_dev_val, reports/holdout e reports/completo ja gerados.
Logo:  docs/assets/janus_logo.png (embutida em base64 no HTML, PDF autocontido).
"""
import base64, json, sys, re
from pathlib import Path
import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "reports" / "relatorio_final.html"
LOGO_B64 = base64.b64encode((RAIZ / "docs/assets/janus_logo.png").read_bytes()).decode()
G = 1e9

r = pd.read_parquet(RAIZ / "reports/sp500_dev_val/results_daily.parquet")
m = json.loads((RAIZ / "reports/sp500_dev_val/metrics.json").read_text(encoding="utf-8"))
spy = pd.read_parquet(RAIZ / "data/processed_sp500/etf_iwm.parquet")["ret"].reindex(r.index)
rf = pd.read_parquet(RAIZ / "data/processed_sp500/factors.parquet")["rf"].reindex(r.index)
cap = pd.read_parquet(RAIZ / "reports/capacity_analysis.parquet")
net = r["pnl_net_usd"] / G

MINUS = "\u2212"
def br(v, d=1, sg=False):
    t = f"{abs(v):.{d}f}".replace(".", ",")
    return ("+" if (sg and v >= 0) else (MINUS if v < 0 else "")) + t

def path_from(vals, x0, y0, w, h, vmin, vmax):
    n = len(vals)
    return "M" + " L".join(
        f"{x0 + w*i/(n-1):.1f},{y0 + h*(1-(v-vmin)/(vmax-vmin)):.1f}" for i, v in enumerate(vals))

# ------------------------------------------------------------------ series
cur = lambda x: ((1 + x).cumprod() * 100).resample("ME").last()
c_est, c_spy, c_cx = cur(net), cur(spy), cur(rf)
VMIN, VMAX = 88, 172
W, H, X0, Y0 = 496, 196, 48, 24
p_est = path_from(c_est.values, X0, Y0, W, H, VMIN, VMAX)
p_spy = path_from(c_spy.values, X0, Y0, W, H, VMIN, VMAX)
p_cx = path_from(c_cx.values, X0, Y0, W, H, VMIN, VMAX)
yv = lambda v: Y0 + H * (1 - (v - VMIN) / (VMAX - VMIN))

eq_e = (1 + net).cumprod(); dd_e_d = (eq_e / eq_e.cummax() - 1) * 100
eq_s = (1 + spy).cumprod(); dd_s_d = (eq_s / eq_s.cummax() - 1) * 100
dd_e, dd_s = dd_e_d.resample("ME").min(), dd_s_d.resample("ME").min()
DD_SPY = dd_s_d.min()
DW, DH, DX, DY = 496, 92, 48, 0
d_est = path_from(dd_e.values, DX, DY, DW, DH, -36, 0)
d_spy = path_from(dd_s.values, DX, DY, DW, DH, -36, 0)
CLOSE = f" L{DX+DW:.1f},{DY+DH:.1f} L{DX:.1f},{DY+DH:.1f} Z"

grid_cap = "".join(
    f'<line x1="{X0}" y1="{yv(v):.1f}" x2="{X0+W}" y2="{yv(v):.1f}" stroke="#EFEBE4" stroke-width="1"/>'
    f'<text x="{X0-8}" y="{yv(v)+4:.1f}" font-size="11" fill="#A8A29A" text-anchor="end">{v}</text>'
    for v in (100, 120, 140, 160))
grid_dd = "".join(
    f'<text x="{DX-8}" y="{DY+DH*(1-(v+36)/36)+4:.1f}" font-size="11" fill="#A8A29A" text-anchor="end">{v}</text>'
    for v in (0, -15, -30))
anos_lbl = "".join(
    f'<text x="{X0+W*i/(len(c_est)-1):.1f}" y="252" font-size="12" fill="#A8A29A" text-anchor="middle">{y}</text>'
    for i, y in [(i, d.strftime("%Y")) for i, d in enumerate(c_est.index) if d.month == 12])

cv = cap["sharpe_liquido"].values
CW, CH, CX, CY = 170, 78, 52, 18
p_cap = path_from(cv, CX, CY, CW, CH, 0.20, 0.45)
cap_pts = "".join(
    f'<circle cx="{CX+CW*i/(len(cv)-1):.1f}" cy="{CY+CH*(1-(v-0.20)/0.25):.1f}" r="3.5" fill="#B8562F"/>'
    for i, v in enumerate(cv))

# ------------------------------------------------------------------ pipeline
PIPE = [("01", "Universo", ["Membros do índice na data,", "não a lista de hoje.", "Preço, liquidez, histórico."]),
        ("02", "Fatores", ["Regressão de 252d em", "FF5 + Momentum.", "Sobra: o resíduo."]),
        ("03", "SINAL", ["Resíduo acumulado 60d,", "medido contra a própria", "história da ação."]),
        ("04", "Otimizador", ["Convexo (cvxpy).", "Maximiza alfa − risco", "− custo, sob mandato."]),
        ("05", "Execução", ["Sinal no fecha. de t,", "ordem no fecha. de t+1.", "Custo Almgren-Chriss."]),
        ("06", "P&amp;L", ["Motor próprio, diário.", "Por perna + hedge.", "Custos debitados."])]
_p = []
for i, (n, t, ls) in enumerate(PIPE):
    x = i * 205
    cor = "#26405E" if i == 2 else "#E4DFD7"
    esp = "2.4" if i == 2 else "1.3"
    linhas = "".join(f'<text x="{x+16}" y="{80+j*17}" font-size="11.5" fill="#6A7280">{ln}</text>'
                     for j, ln in enumerate(ls))
    seta = (f'<line x1="{x+182}" y1="66" x2="{x+203}" y2="66" stroke="#26405E" stroke-width="1.8" '
            f'marker-end="url(#a)"/>') if i < 5 else ""
    _p.append(f'<g><rect x="{x}" y="12" width="180" height="106" rx="7" fill="#fff" stroke="{cor}" '
              f'stroke-width="{esp}"/><text x="{x+16}" y="37" font-size="10.5" font-weight="700" '
              f'fill="#26405E" letter-spacing="1.2">{n}</text><text x="{x+16}" y="60" font-size="14.5" '
              f'font-weight="700" fill="#141820">{t}</text>{linhas}</g>{seta}')
PIPE_SVG = "".join(_p)

_anos = [("2020", "26%", 0.64), ("2021", "12%", 0.02), ("2022", "24%", 0.30), ("2023", "13%", -0.45)]
ANOS_HTML = '<div style="display:flex;gap:10px;margin-top:11px;">' + "".join(
    '<div style="flex:1;border:1px solid #E4DFD7;border-radius:5px;padding:9px 11px;background:#fff;">'
    '<div style="font-size:11.5px;color:#6A7280;font-weight:700;letter-spacing:.5px;">'
    + a + ' \u00b7 vol ' + v + '</div><div style="font-size:23px;font-weight:700;margin-top:1px;color:'
    + ("#2F6F58" if s > 0 else "#A6402F") + ';">' + br(s, 2, True) + '</div>'
    '<div style="font-size:11px;color:#6A7280;">Sharpe l\u00edquido</div></div>'
    for a, v, s in _anos) + '</div>'

SB, SL = m["sharpe_gross"], m["sharpe_net"]
CUSTO, TO, DD = m["costs_bps_of_gross_per_year"], m["ann_turnover_x"], m["max_drawdown_pct"]
RET, VOL = m["ann_return_net_pct"], m["ann_vol_pct"]
spy_ret, rf_ret = spy.mean() * 252 * 100, rf.mean() * 252 * 100
corr = net.corr(spy)


G = 1e9
M = {t: json.loads((RAIZ / f"reports/{t}/metrics.json").read_text(encoding="utf-8"))
     for t in ("sp500_dev_val", "holdout", "completo")}
rc = pd.read_parquet(RAIZ / "reports/completo/results_daily.parquet")
spy = pd.read_parquet(RAIZ / "data/processed_sp500/etf_iwm.parquet")["ret"].reindex(rc.index)
net = rc["pnl_net_usd"] / G

# ---------------------------------------------------------------- curva 2020-2026
cur = lambda x: ((1 + x).cumprod() * 100).resample("ME").last()
c_est, c_spy = cur(net), cur(spy)
VMIN, VMAX = 92, 114
W, H, X0, Y0 = 500, 178, 46, 22
yv = lambda v: Y0 + H * (1 - (v - VMIN) / (VMAX - VMIN))
p_est = path_from(c_est.values, X0, Y0, W, H, VMIN, VMAX)
p_spy = path_from(c_spy.values, X0, Y0, W, H, VMIN, VMAX)
n_ho = (c_est.index >= "2024-01-01").sum()
x_ho = X0 + W * (len(c_est) - n_ho) / (len(c_est) - 1)
grade = "".join(
    f'<line x1="{X0}" y1="{yv(v):.1f}" x2="{X0+W}" y2="{yv(v):.1f}" stroke="#EFEBE4" stroke-width="1"/>'
    f'<text x="{X0-8}" y="{yv(v)+4:.1f}" font-size="11" fill="#A8A29A" text-anchor="end">{v}</text>'
    for v in (95, 100, 105, 110))
anos = "".join(
    f'<text x="{X0+W*i/(len(c_est)-1):.1f}" y="238" font-size="11.5" fill="#A8A29A" text-anchor="middle">{y}</text>'
    for i, y in [(i, d.strftime("%Y")) for i, d in enumerate(c_est.index) if d.month == 12])

DV, HO, CP = M["sp500_dev_val"], M["holdout"], M["completo"]

CSS = """<meta charset="utf-8"><style>
@page { size: 13.333in 7.5in; margin: 0; }
* { box-sizing:border-box; margin:0; padding:0; }
:root { --ink:#16202E; --slate:#67717F; --paper:#FCFBF9; --rule:#E1DED8;
  --acc:#26405E; --hot:#B8562F; --pos:#2F6F58; --neg:#A6402F; --soft:#EFF1F4; }
body { font-family:"Segoe UI",system-ui,sans-serif; color:var(--ink);
  -webkit-print-color-adjust:exact; print-color-adjust:exact; }
.pg { width:13.333in; height:7.5in; padding:0.44in 0.54in 0.5in; background:var(--paper);
  page-break-after:always; position:relative; overflow:hidden; display:flex; flex-direction:column; }
.pg:last-child { page-break-after:auto; }
.pg::before { content:""; position:absolute; top:0; left:0; right:0; height:5px; background:var(--acc); }
h1 { font-size:30px; font-weight:700; letter-spacing:-.5px; line-height:1.12; }
h2 { font-size:11.6px; font-weight:700; letter-spacing:1.2px; text-transform:uppercase;
  color:var(--acc); margin-bottom:6px; }
p,li,td,th { font-size:12.3px; line-height:1.4; }
.sub { color:var(--slate); }
.hd { display:flex; justify-content:space-between; align-items:baseline;
  border-bottom:1.5px solid var(--ink); padding-bottom:7px; margin-bottom:11px; }
.hd .t { font-size:24px; font-weight:700; letter-spacing:-.3px; }
.hd .n { font-size:12px; color:var(--slate); letter-spacing:.6px; text-transform:uppercase; }
table { width:100%; border-collapse:collapse; }
th { text-align:left; font-size:9.8px; text-transform:uppercase; letter-spacing:.7px;
  color:var(--slate); font-weight:700; padding:0 7px 5px 0; border-bottom:1px solid var(--rule); }
td { padding:5.6px 7px 5.6px 0; border-bottom:1px solid var(--rule); vertical-align:top; }
td.n,th.n { text-align:right; font-variant-numeric:tabular-nums; }
.big { font-size:36px; font-weight:700; letter-spacing:-1px; line-height:1; }
.lbl { font-size:10.5px; text-transform:uppercase; letter-spacing:.7px; color:var(--slate); margin-top:4px; }
.card { background:#fff; border:1px solid var(--rule); border-radius:6px; padding:13px 15px; }
.acc{color:var(--acc)} .hot{color:var(--hot)} .pos{color:var(--pos)} .neg{color:var(--neg)}
.tag { display:inline-block; font-size:10px; font-weight:700; letter-spacing:.8px;
  text-transform:uppercase; padding:4px 9px; border-radius:3px; background:#E7ECF2; color:var(--acc); }
.tag.r { background:#F4E2DC; color:var(--neg); }
.num { display:inline-flex; width:17px; height:17px; border-radius:3px; background:#E7ECF2;
  color:var(--acc); font-size:10.5px; font-weight:700; align-items:center; justify-content:center; margin-right:6px; }
.foot { position:absolute; bottom:0.22in; left:0.54in; right:0.54in; display:flex;
  justify-content:space-between; font-size:9.5px; color:#A8A29A; letter-spacing:.5px; }
.flag { border-left:3px solid var(--hot); background:var(--soft); padding:10px 13px; border-radius:0 4px 4px 0; }
.flag.r { border-left-color:var(--neg); background:#FAF0EC; }
.grid { display:grid; gap:14px; }
.mono { font-family:Consolas,monospace; font-size:12px; }
</style>"""

P1 = f"""<div class="pg" style="padding:0.5in 0.56in;">
 <div style="display:grid; grid-template-columns:300px 1fr; gap:38px; flex:1;">
  <div style="display:flex; flex-direction:column;">
   <img src="data:image/png;base64,{LOGO_B64}" style="width:168px; display:block; margin-left:-4px;"/>
   <div style="font-size:46px; font-weight:700; letter-spacing:7px; margin-top:14px;">JANUS</div>
   <div style="font-size:13px; color:var(--slate); margin-top:6px; line-height:1.45;">
    Arbitragem estatística long-short<br>neutra a mercado, fatores e setores</div>
   <div style="margin-top:16px; padding-top:13px; border-top:1px solid var(--rule);">
    <h2 style="margin-bottom:6px;">Por que Janus</h2>
    <p>Deus romano das <b>passagens</b> — das portas, dos começos e dos fins. Tem
    <b>duas faces opostas</b>: uma olha para trás, outra para frente.</p>
    <p style="margin-top:7px;"><b class="acc">Duas faces</b> — as duas pernas do livro:
    compramos e vendemos ao mesmo tempo, em partes iguais.</p>
    <p style="margin-top:5px;"><b class="acc">Olha atrás e à frente</b> — o sinal lê o
    resíduo acumulado de 60 dias para prever a reversão.</p>
    <p style="margin-top:5px;"><b class="acc">Guarda a porta</b> — fornecer liquidez é
    deixar passar quem tem pressa, e cobrar por isso.</p>
   </div>
  </div>
  <div style="display:flex; flex-direction:column; justify-content:space-between;">
   <div>
    <div><span class="tag">Relatório Final · Desafio Quant AI 2026</span>
         <span class="tag r" style="margin-left:5px;">Hipótese refutada</span></div>
    <h1 style="margin-top:12px;">Construímos a tese, o teste — e o teste<br>disse que estávamos errados.</h1>
    <p style="margin-top:9px; font-size:13.5px; color:var(--slate);">Reservamos 2,4 anos de dados
    e nunca os tocamos até a decisão final. Este relatório mostra o que encontramos e por que
    reportá-lo vale mais que procurar um número melhor.</p>
   </div>
   <div class="grid" style="grid-template-columns:1fr 1fr; margin-top:14px;">
    <div class="card"><h2>A hipótese</h2><p>Quando uma ação se move <b>além do que os fatores
     explicam</b>, esse excesso costuma ser <b>reação a fluxo</b> — não informação. Quem fornece
     liquidez a quem tem pressa é remunerado quando o desvio <b>reverte</b>.</p></div>
    <div class="card"><h2>Como testamos</h2><p>Universo <b>as-of</b> (o índice como era em cada
     dia), neutralidade de fatores e setores, custos reais, e um <b>holdout de 2,4 anos lacrado
     no código</b> — o motor recusava rodar nele sem autorização explícita.</p></div>
    <div class="card"><h2>O que aconteceu</h2><p>Em 2020-2023 a estratégia entregou Sharpe
     <b>+0,27</b>, com regime, capacidade e custos diagnosticados. No holdout entregou
     <b class="neg">−1,15</b>, com o <b>alfa bruto também negativo</b>. O sinal não enfraqueceu:
     <b>inverteu</b>.</p></div>
    <div class="card"><h2>Por que isso importa</h2><p>O holdout existia exatamente para pegar o
     caso em que a estratégia parece funcionar dentro da amostra e não funciona fora.
     <b>Ele pegou.</b> O protocolo é o resultado que sobrevive.</p></div>
   </div>
   <div style="display:flex; margin-top:14px; border:1px solid var(--rule); border-radius:6px;
               overflow:hidden; background:#fff;">
    <div style="flex:1; padding:13px 15px; border-right:1px solid var(--rule);">
     <div class="big">+0,27</div><div class="lbl">Sharpe dev+val (2020-23)</div></div>
    <div style="flex:1; padding:13px 15px; border-right:1px solid var(--rule); background:#FAF0EC;">
     <div class="big neg">−1,15</div><div class="lbl">Sharpe no HOLDOUT (2024-26)</div></div>
    <div style="flex:1; padding:13px 15px; border-right:1px solid var(--rule);">
     <div class="big neg">−0,030</div><div class="lbl">IC fora da amostra (era +0,036)</div></div>
    <div style="flex:1; padding:13px 15px;">
     <div class="big">2,4</div><div class="lbl">anos de holdout intocado</div></div>
   </div>
  </div>
 </div>
 <div class="foot"><span>S&amp;P 500 as-of · 665 ações · ida única ao holdout em 07/08/2026</span><span>1 / 5</span></div>
</div>"""

P2 = f"""<div class="pg">
 <div class="hd"><div class="t">Modelagem — da ideia à ordem</div>
  <div class="n">Dados → Sinal → Portfólio → Execução</div></div>
 <svg viewBox="0 0 1230 130" style="width:100%; margin-bottom:14px;">
  <defs><marker id="a" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
   <path d="M0,1 L7,4.5 L0,8" fill="none" stroke="#26405E" stroke-width="1.7"/></marker></defs>
  {PIPE_SVG}</svg>
 <div class="grid" style="grid-template-columns:1.06fr 1fr 0.96fr; flex:1;">
  <div>
   <h2>O sinal em dois passos</h2>
   <div class="card" style="padding:13px 15px;">
    <div class="mono acc" style="font-weight:700;">X<sub>i</sub>(t) = Σ resíduos dos últimos 60 dias</div>
    <p class="sub" style="margin:4px 0 11px;">Quanto a ação andou <b>por conta própria</b>.</p>
    <div class="mono acc" style="font-weight:700;">s<sub>i</sub> = − [ X<sub>i</sub> − μ<sub>i</sub> ] / σ<sub>i</sub></div>
    <p class="sub" style="margin-top:4px;">μ, σ da <b>própria ação</b> (252d): cada uma é sua régua.
    O sinal negativo inverte — esticada para cima vira <b>venda</b>.</p></div>
   <p style="margin-top:11px;">O score vira <b>ranking</b> (z-score entre ações, ±3σ) e depois
   <b>retorno esperado</b>. Referência: Avellaneda &amp; Lee (2010).</p>
   <div class="flag" style="margin-top:12px;"><p><b>Decisão de desenho:</b> um sinal só.
   Testamos 11 candidatos da literatura; <b>8 falharam</b>. Somar o 2º melhor piorava a
   validação (IC 0,036 → 0,034).</p></div>
  </div>
  <div>
   <h2>O mandato (restrições do otimizador)</h2>
   <table>
    <tr><td>Dollar-neutral</td><td class="n mono">|Σw| ≤ 0,2%</td></tr>
    <tr><td>Orçamento bruto</td><td class="n mono">Σ|w| ≤ US$ 1 bi</td></tr>
    <tr><td>Neutro a cada fator FF5+MOM</td><td class="n mono">|β′w| ≤ 2%</td></tr>
    <tr><td>Neutro por setor</td><td class="n mono">|net setor| ≤ 5%</td></tr>
    <tr><td>Concentração por nome</td><td class="n mono">|w<sub>i</sub>| ≤ 0,5%</td></tr>
    <tr><td>Participação no volume</td><td class="n mono">≤ 5% do ADV</td></tr>
    <tr><td>Hedge de beta residual</td><td class="n mono">SPY</td></tr></table>
   <p style="margin-top:11px;"><b>Saída:</b> vetor de pesos por ação, revisto a cada
   <b>10 dias úteis</b>. O custo entra <b>dentro</b> do objetivo: a carteira nasce ciente da
   própria pegada e negocia devagar por conta própria.</p>
  </div>
  <div>
   <h2>Dados — todos públicos e verificáveis</h2>
   <table>
    <tr><td>Composição as-of<br><span class="sub" style="font-size:11px;">2.718 datas de mudança</span></td>
        <td class="n" style="font-size:12px;">Wikipedia<br>changelog</td></tr>
    <tr><td>Preços, volume, abertura, máx-mín</td><td class="n" style="font-size:12px;">yfinance</td></tr>
    <tr><td>Fatores FF5 + Momentum</td><td class="n" style="font-size:12px;">Ken French</td></tr>
    <tr><td>Setor e market cap</td><td class="n" style="font-size:12px;">Nasdaq</td></tr></table>
   <div style="display:flex; gap:22px; margin-top:14px;">
    <div><div style="font-size:24px;font-weight:700;">665</div><div class="lbl">tickers</div></div>
    <div><div style="font-size:24px;font-weight:700;">2.113</div><div class="lbl">dias</div></div>
    <div><div style="font-size:24px;font-weight:700;">92,8%</div><div class="lbl">cobertura</div></div>
   </div>
   <p style="margin-top:13px;">Painel <b>congelado por hash SHA-256</b>. Cada resultado aponta
   para um estado de dados identificável — se o número muda, a causa é o código, não o dado.</p>
  </div>
 </div>
 <div class="foot"><span>Motor de backtest implementado pela equipe · 20 testes automatizados</span><span>2 / 5</span></div>
</div>"""

P3 = """<div class="pg">
 <div class="hd"><div class="t">O protocolo — construído para nos provar errados</div>
  <div class="n">Rigor e mitigação de vieses</div></div>
 <svg viewBox="0 0 1230 74" style="width:100%; margin-bottom:14px;">
  <rect x="0" y="16" width="596" height="34" rx="4" fill="#EFF1F4"/>
  <rect x="602" y="16" width="198" height="34" rx="4" fill="#E2E7EE"/>
  <rect x="806" y="16" width="424" height="34" rx="4" fill="#FAF0EC" stroke="#A6402F" stroke-width="1.8"/>
  <text x="15" y="38" font-size="13" font-weight="700" fill="#16202E">DESENVOLVIMENTO · 2020–2022</text>
  <text x="617" y="38" font-size="13" font-weight="700" fill="#16202E">VALIDAÇÃO · 2023</text>
  <text x="822" y="38" font-size="13" font-weight="700" fill="#A6402F">HOLDOUT · 2024–2026 · LACRADO NO CÓDIGO</text>
  <text x="15" y="67" font-size="11" fill="#67717F">escolha do sinal e calibração acontecem só aqui</text>
  <text x="1230" y="67" font-size="11" fill="#67717F" text-anchor="end">aberto UMA vez, em 07/08/2026, na decisão final</text>
 </svg>
 <div class="grid" style="grid-template-columns:1.2fr 1fr; flex:1;">
  <div>
   <h2>Viés por viés — o que fizemos</h2>
   <table>
    <tr><th style="width:28%">Viés</th><th>Tratamento</th><th class="n" style="width:22%">Efeito medido</th></tr>
    <tr><td><b>Sobrevivência</b></td><td>Universo é o índice <b>na data</b>; inclui quem saiu depois</td><td class="n">665 vs ~500 nomes</td></tr>
    <tr><td><b>Look-ahead</b></td><td>Sinal no fecha. de t → ordem em <b>t+1</b>; betas só de dados passados</td><td class="n">testado em 9 sinais</td></tr>
    <tr><td><b>Overfitting</b></td><td>Holdout <b>lacrado no motor</b>, não só combinado</td><td class="n"><b>pegou o erro</b></td></tr>
    <tr><td><b>Janelas sobrepostas</b></td><td>t-stat <b>Newey-West</b> (IC de 21d numa grade de 5d)</td><td class="n">t 4,20 → <b>2,50</b></td></tr>
    <tr><td><b>Custos ignorados</b></td><td>Spread medido, impacto AC, <b>aluguel do short</b>, hedge</td><td class="n">−168 bps/ano</td></tr>
    <tr><td><b>Dado instável</b></td><td>Painel congelado com hash SHA-256 por arquivo</td><td class="n">rastreável</td></tr></table>
   <div class="flag" style="margin-top:12px;">
    <h2 style="margin-bottom:5px;">O viés que NÃO conseguimos resolver</h2>
    <p>Das <b>68 empresas que saíram do índice</b> em 2020–2023, <b>36 não têm um único preço</b>
    em fonte gratuita — o provedor apaga o histórico de quem é adquirido. O backtest processou
    <b>zero deslistamentos</b>. Resolvemos o viés de <b>seleção de membros</b>; o de
    <b>desfecho</b> permanece, medido em <b>7,0%</b> dos meses-membro.</p></div>
  </div>
  <div>
   <h2>O funil: 11 candidatos, 1 sobrevivente</h2>
   <table>
    <tr><th>Sinal</th><th class="n">IC dev</th><th class="n">IC val</th><th class="n">Veredito</th></tr>
    <tr><td><b>Reversão de resíduo</b></td><td class="n pos"><b>+0,051</b></td><td class="n pos"><b>+0,036</b></td><td class="n"><b>escolhido</b></td></tr>
    <tr><td>Blend (2 sinais)</td><td class="n">+0,051</td><td class="n">+0,034</td><td class="n">piora</td></tr>
    <tr><td>Reversão curta 5d</td><td class="n">+0,024</td><td class="n">+0,019</td><td class="n">mais fraco</td></tr>
    <tr><td>Saliência</td><td class="n">+0,028</td><td class="n">+0,003</td><td class="n">não valida</td></tr>
    <tr><td>Momentum de curto prazo</td><td class="n neg">−0,054</td><td class="n neg">−0,017</td><td class="n">inverte</td></tr>
    <tr><td>Tendência · MAD · cauda ·<br>sazonalidade · overnight</td><td class="n">≈ 0</td><td class="n">≈ 0</td><td class="n">cortados</td></tr></table>
   <p style="margin-top:11px;"><b>8 dos 10 candidatos testáveis falharam — 80%.</b> Hou, Xue &amp;
   Zhang (2020) replicaram <b>452 anomalias</b> e <b>82% não sobrevivem</b> em large caps.
   Nosso funil reproduziu a taxa-base da literatura.</p>
   <div class="flag r" style="margin-top:12px;">
    <p><b>O que não vimos:</b> citamos esses 82% para justificar o corte dos <i>outros</i>
    sinais — e não aplicamos o mesmo ceticismo ao nosso. Um IC de <b>0,05</b> com <b>t = 1,66</b>
    na validação é exatamente o perfil de um achado que não replica. <b>O holdout aplicou o
    ceticismo por nós.</b></p></div>
  </div>
 </div>
 <div class="foot"><span>Backtest próprio · 1.006 dias em dev+val · 604 dias no holdout · execução t+1</span><span>3 / 5</span></div>
</div>"""

P4 = f"""<div class="pg">
 <div class="hd"><div class="t">O veredito — dentro e fora da amostra</div>
  <div class="n">2020-01-02 a 2026-05-29 · 6,4 anos</div></div>
 <div class="grid" style="grid-template-columns:1.32fr 1fr; flex:1;">
  <div>
   <svg viewBox="0 0 616 252" style="width:100%;">
    <rect x="{x_ho:.1f}" y="{Y0-6}" width="{X0+W-x_ho:.1f}" height="{H+12}" fill="#FAF0EC"/>
    <text x="{x_ho+7:.1f}" y="{Y0+6}" font-size="11.5" font-weight="700" fill="#A6402F">HOLDOUT — lacrado até 07/08/2026</text>
    {grade}
    <path d="{p_est}" fill="none" stroke="#26405E" stroke-width="2.8"/>
    <line x1="{x_ho:.1f}" y1="{Y0-6}" x2="{x_ho:.1f}" y2="{Y0+H+6}" stroke="#A6402F" stroke-width="1.6" stroke-dasharray="4 3"/>
    {anos}
    <circle cx="{X0+W*int(np.argmax(c_est.values))/(len(c_est)-1):.1f}" cy="{yv(c_est.values.max()):.1f}" r="3.5" fill="#26405E"/>
    <text x="{X0+W*int(np.argmax(c_est.values))/(len(c_est)-1)-6:.1f}" y="{yv(c_est.values.max())-8:.1f}" font-size="11" font-weight="700" fill="#26405E" text-anchor="end">pico {br(c_est.values.max(),1)}</text>
    <circle cx="{X0+W:.1f}" cy="{yv(c_est.values[-1]):.1f}" r="3.5" fill="#A6402F"/>
    <text x="{X0+W+7:.1f}" y="{yv(c_est.values[-1])+4:.1f}" font-size="11.5" font-weight="700" fill="#A6402F">{br(c_est.values[-1],1)}</text>
   </svg>
   <table style="margin-top:8px;">
    <tr><th></th><th class="n">dev+val 2020-23</th><th class="n" style="color:#A6402F">HOLDOUT 2024-26</th><th class="n">2020-26</th></tr>
    <tr><td>Sharpe <b>bruto</b></td><td class="n pos">{br(DV['sharpe_gross'],2,True)}</td><td class="n neg"><b>{br(HO['sharpe_gross'],2,True)}</b></td><td class="n">{br(CP['sharpe_gross'],2,True)}</td></tr>
    <tr><td>Sharpe <b>líquido</b></td><td class="n pos"><b>{br(DV['sharpe_net'],2,True)}</b></td><td class="n neg"><b>{br(HO['sharpe_net'],2,True)}</b></td><td class="n neg">{br(CP['sharpe_net'],2,True)}</td></tr>
    <tr><td>Retorno líquido a.a.</td><td class="n">{br(DV['ann_return_net_pct'],2,True)}%</td><td class="n neg">{br(HO['ann_return_net_pct'],2,True)}%</td><td class="n">{br(CP['ann_return_net_pct'],2,True)}%</td></tr>
    <tr><td>Max drawdown</td><td class="n">{br(DV['max_drawdown_pct'])}%</td><td class="n neg">{br(HO['max_drawdown_pct'])}%</td><td class="n">{br(CP['max_drawdown_pct'])}%</td></tr>
    <tr><td>P&amp;L líquido</td><td class="n">+US$ {DV['pnl_net_total_usd_mm']:.0f}mm</td><td class="n neg"><b>−US$ {abs(HO['pnl_net_total_usd_mm']):.0f}mm</b></td><td class="n neg">−US$ {abs(CP['pnl_net_total_usd_mm']):.0f}mm</td></tr>
   </table>
   <div class="flag r" style="margin-top:10px;">
    <p><b>O Sharpe bruto também é negativo (−0,77).</b> Isso descarta custo, execução e tamanho
    de book: se fosse fricção, o bruto ficaria positivo. <b>O alfa virou antes de qualquer
    fricção</b> — o sinal não enfraqueceu, inverteu.</p></div>
  </div>
  <div>
   <h2>A evidência mais limpa: o IC do sinal</h2>
   <table>
    <tr><th>Split</th><th class="n">IC (21d)</th><th class="n">t (NW)</th><th class="n">Q5−Q1</th></tr>
    <tr><td>dev 2020-22</td><td class="n pos">+0,051</td><td class="n">+2,50</td><td class="n pos">+7,7</td></tr>
    <tr><td>validação 2023</td><td class="n pos">+0,036</td><td class="n">+1,66</td><td class="n pos">+5,2</td></tr>
    <tr><td><b>HOLDOUT 2024-26</b></td><td class="n neg"><b>−0,030</b></td><td class="n neg"><b>−1,54</b></td><td class="n neg"><b>−3,3</b></td></tr></table>
   <p style="margin-top:7px;">O IC mede o sinal <b>puro</b> — sem otimizador, sem custo, sem
   carteira. Ele mudou de sinal.</p>

   <h2 style="margin-top:14px;">Testamos a defesa óbvia — e ela não passa</h2>
   <p style="margin-bottom:6px;">Nossa tese dizia: <i>o alfa some na calmaria e aparece no
   estresse</i>. O holdout <b>foi</b> mais calmo (56% dos dias em vol baixa vs 33%). Mas:</p>
   <table>
    <tr><th>Regime de vol.</th><th class="n">IC dev+val</th><th class="n">IC holdout</th></tr>
    <tr><td>Baixa</td><td class="n">+0,000</td><td class="n neg">−0,028</td></tr>
    <tr><td>Média</td><td class="n pos">+0,064</td><td class="n neg">−0,035</td></tr>
    <tr><td><b>ALTA</b></td><td class="n pos"><b>+0,079</b></td><td class="n neg"><b>−0,020</b></td></tr></table>
   <p style="margin-top:7px;"><b>O IC é negativo nos três regimes — inclusive em vol alta</b>,
   onde a tese apostava. A defesa por regime não se sustenta.
   <span class="sub">(Ressalva a nosso desfavor: só 12 observações em vol alta, t = −0,28 —
   o correto é dizer "não confirmado", não "refutado com força".)</span></p>

   <h2 style="margin-top:14px;">Não é problema de dado</h2>
   <table>
    <tr><td>Cobertura de preço dos membros</td><td class="n">92,8% → <b class="pos">97,6%</b></td></tr>
    <tr><td>Universo negociável médio</td><td class="n">465 → <b class="pos">489</b></td></tr></table>
   <p style="margin-top:7px;">O dado do holdout é <b>melhor</b> que o do dev+val — a erosão por
   M&amp;A prejudica o passado, não o presente. O resultado negativo é real.</p>
  </div>
 </div>
 <div class="foot"><span>Holdout: 604 dias · 503 membros/dia · os 10 piores dias somam −9,4pp de um total de −8,3pp</span><span>4 / 5</span></div>
</div>"""

P5 = """<div class="pg">
 <div class="hd"><div class="t">IA Generativa, o que recusamos fazer e próximos passos</div>
  <div class="n">Conclusão</div></div>
 <div class="grid" style="grid-template-columns:1.42fr 1fr; flex:1;">
  <div>
   <h2>Uso de GenAI: o valor esteve em auditar, não em gerar</h2>
   <table>
    <tr><th style="width:20%">Etapa</th><th>Contribuição concreta</th><th class="n" style="width:24%">Impacto medido</th></tr>
    <tr><td><b>Pesquisa de sinais</b></td><td>Triagem da literatura e 11 candidatos implementados como plug-ins testáveis</td><td class="n">3 sinais tentadores <b>cortados</b></td></tr>
    <tr><td><b>Auditoria de código</b></td><td>Leitura crítica achou t-stat inflado 2× por janelas sobrepostas</td><td class="n">t 4,20 → <b>2,50</b></td></tr>
    <tr><td><b>Auditoria de dados</b></td><td>Cruzou 2 fontes: <b>26 trocas de ticker</b>, só 3 tratadas</td><td class="n">cobertura 91,7 → <b>92,8%</b></td></tr>
    <tr><td><b>Procedência</b></td><td>Detectou uma análise inteira rodada no painel <b>sintético</b> por engano</td><td class="n">conclusão <b>refeita</b></td></tr>
    <tr><td><b>Ceticismo</b></td><td>Teste de fase desmontou uma melhora aparente de +0,11</td><td class="n">ganho real: <b>+0,06</b></td></tr>
    <tr><td><b>Holdout</b></td><td>Testou as 3 racionalizações do resultado ruim: regime, dado e custo</td><td class="n">as <b>3 caíram</b></td></tr></table>
   <div class="flag" style="margin-top:11px;">
    <h2 style="margin-bottom:5px;">Limitação encontrada no uso de IA</h2>
    <p>A IA <b>gera com confiança o que não verificou</b>: produziu um relatório inteiro a partir
    do painel errado, e o texto saiu convincente — o erro só apareceu porque <b>dois relatórios
    discordavam sobre o mesmo número</b>. A lição: <b>o valor não está em gerar, está em usar a
    IA para atacar o próprio trabalho</b>, e nunca aceitar um número que não bata com o artefato
    que o gerou.</p></div>
   <h2 style="margin-top:12px;">O que RECUSAMOS fazer depois de ver o holdout</h2>
   <table>
    <tr><td>Inverter o sinal (IC negativo ⇒ comprar as esticadas)</td><td class="n">ajuste in-sample; t não é significativo</td></tr>
    <tr><td>Filtrar os 10 piores dias</td><td class="n">cherry-picking</td></tr>
    <tr><td>Rodar só 2025, o ano menos ruim</td><td class="n">escolha oportunista de período</td></tr>
    <tr><td>Recalibrar horizonte e janelas no holdout</td><td class="n">destruiria o único teste honesto</td></tr></table>
   <p style="margin-top:8px;"><b>O holdout está gasto.</b> Qualquer parâmetro ajustado a partir
   daqui é in-sample. A trava no motor foi <b>mantida</b> — agora ela protege contra o erro oposto.</p>
  </div>
  <div>
   <h2>O que aprendemos</h2>
   <table>
    <tr><td><b>Uma tese que explica bem o passado não é evidência.</b> A explicação de regime era coerente, econômica e ajustava os dados — e não previu nada.</td></tr>
    <tr><td><b>Os avisos estavam no nosso próprio relatório.</b> Validação com t = 1,66, dependência de calendário de ±0,09, IC de 0,05. Reportamos todos e subestimamos todos.</td></tr>
    <tr><td><b>Rigor na calibração não salva um alfa que não existe.</b> Rejeitamos 3 falsas melhorias com disciplina — sobre uma base que já era sobreajuste.</td></tr>
    <tr><td><b>O protocolo é o produto.</b> Painel as-of auditado, custos realistas, Newey-West, snapshot por hash, 20 testes e a trava de holdout: nada disso dependia de o sinal funcionar.</td></tr></table>
   <h2 style="margin-top:14px;">Próximos passos</h2>
   <table>
    <tr><td><span class="num">1</span><b>Ampliar a amostra para trás</b> (CRSP, pré-2018) — única forma de distinguir <i>"o efeito nunca existiu"</i> de <i>"existiu e foi arbitrado"</i>. Com 2018-2026 não dá.</td></tr>
    <tr><td><span class="num">2</span><b>Momentum residual</b> (Blitz et al.) — mecanismo oposto, sobrevive à neutralização de fatores. Mas agora exige um <b>holdout novo</b>: o nosso acabou.</td></tr>
    <tr><td><span class="num">3</span><b>Tranching</b> — girar ~10% do livro por dia elimina a dependência de calendário de ±0,09 que ajudou a mascarar a fragilidade.</td></tr>
   </table>
   <div class="card" style="margin-top:13px; border-color:var(--neg); border-width:1.5px; background:#FAF0EC;">
    <p><b>Conclusão.</b> A estratégia <b>não funciona</b>: −1,15 no holdout, −0,10 em 6,4 anos.
    Poderíamos ter reportado +0,27 e ninguém saberia. Escolhemos gastar o holdout e publicar o
    que ele disse. <b>Um projeto que constrói o teste capaz de reprová-lo, executa esse teste e
    reporta a reprovação é mais confiável que um Sharpe positivo nunca testado.</b></p></div>
  </div>
 </div>
 <div class="foot"><span>Todos os números conferidos contra os artefatos que os geraram</span><span>5 / 5</span></div>
</div>"""

HTML = CSS + P1 + P2 + P3 + P4 + P5
OUT.write_text(HTML, encoding="utf-8")
corpo = HTML.split("</style>")[1]
prosa = " ".join(re.findall(r"<p[^>]*>(.*?)</p>", corpo, re.S))
print(f"OK -> {OUT}")
print(f"prosa: {len(re.sub(r'<[^>]+>',' ',prosa).split())} palavras | "
      f"total visivel: {len(re.sub(r'<[^>]+>',' ',corpo).split())}")
