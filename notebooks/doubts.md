# Dúvidas
Esse arquivo é destinado a listar eventuais dúvidas ao longo do estudo do notebook "pipeline_walkthrough.ipynb".

## 1ª Seção - Dados
- [x] Para as ações que fizeram parte do índice S&P 500, desde 1996 até 2026, nós temos acesso a todos os dados de volume/preço?
    R: Não. Começa em 2018
- [ ] Verificar a cobertura média pela yfinance dos preços/volumes das ações que foram deslistadas do S&P 500 ao longo do tempo.
    R (Claude, 14/07): Medido em `reports/delisted_coverage_sp500.md` — dos 181 REMOVIDOS do índice na janela 2018–2026, **46% têm preço** no yfinance, vs **99% dos 503 sobreviventes** (gap de 53pp; rotatividade da janela: 26%). No Russell 2000 era 18% vs 92% (gap 74pp) — por isso a migração para o S&P 500.
- [ ] Gap no gráfico do "Universo as-of negociável por dia". Verificar o que é esse problema.
    R (Claude, 14/07): Não é bug nem falta de dados — é o **warm-up do filtro de histórico**: o universo exige ≥260 dias úteis de histórico (para estimar betas/vol), então de jan/2018 a ~fev/2019 quase nenhuma ação é elegível. Nota explicativa adicionada no notebook, logo abaixo do gráfico 1.3a. Toda avaliação começa após o warm-up (`backtest.start = 2020`).