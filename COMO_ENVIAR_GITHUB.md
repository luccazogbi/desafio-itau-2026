# 📤 Como enviar o projeto para o GitHub (guia de bolso)

> Repositório: **https://github.com/luccazogbi/Desafio-Quant-2026** (privado)
> Pasta local: `C:\Users\Lucca\Desktop\Quant\Desafio Quant\quant_ai_2026`
> Tudo já está configurado (remote, identidade, .gitignore). Este guia é o passo a passo
> para o dia a dia, sem depender de ninguém.

---

## ⚠️ Antes de tudo: você tem DOIS repositórios

Eles ficam em pastas vizinhas e é fácil commitar no lugar errado (já aconteceu).

| Pasta | Repositório | O que é |
|---|---|---|
| `Desktop\Quant\Desafio Quant\quant_ai_2026` | **Desafio-Quant-2026** | a estratégia do desafio Itaú |
| `Desktop\Quant\Quant Learning` | **quant-studies** | material de estudo (Grinold, Fama-French) |

> A pasta `Desktop\Quant\Project - Lucas Abbade\FinRL-Meta` também é um repo git, mas
> **não é seu** — é um clone do projeto open-source da AI4Finance. Não tente dar push lá.

**Na dúvida, confira antes de commitar:**

```powershell
git remote get-url origin
```

Se responder `Desafio-Quant-2026`, você está no repo da estratégia. Se responder
`quant-studies`, está no de estudos.

---

## O fluxo de sempre (95% dos casos são só isto)

Abra o **PowerShell** e rode, linha por linha:

```powershell
# 1. entrar na pasta do projeto
cd "C:\Users\Lucca\Desktop\Quant\Desafio Quant\quant_ai_2026"

# 2. ver o que mudou (opcional, mas bom hábito)
git status

# 3. preparar TODAS as mudanças para envio
git add -A

# 4. criar o "pacote" com uma mensagem do que foi feito
git commit -m "descreva aqui o que mudou"

# 5. enviar para o GitHub
git push
```

Pronto. Se aparecer uma janela do navegador pedindo login do GitHub, faça o login
normalmente (é o Git Credential Manager — só acontece de vez em quando).

> **Você é dono do repo, então não precisa de Pull Request.** Commit direto na `main` é o
> fluxo certo aqui. Se por acidente aparecer a opção "Create PR" no chat, ela só está
> avisando que existe trabalho não commitado — resolva commitando, não abrindo PR.

### Exemplos de mensagens de commit boas

```
git commit -m "Adiciona sinais STM, overnight e salience + analise de blend"
git commit -m "Atualiza roadmap apos decisao do funil"
git commit -m "Notebook: nota sobre warm-up do universo + respostas do doubts.md"
```

Regra prática: a mensagem deve completar a frase *"este commit... [Adiciona/Corrige/Atualiza X]"*.

---

## O que sobe e o que NÃO sobe

O arquivo `.gitignore` já cuida disso automaticamente:

| Sobe ✅ | Não sobe ❌ (de propósito) |
|---|---|
| Código (`statarb/`, `scripts/`, `tests/`) | `data/` (150 MB de parquets — regeneráveis pelos scripts) |
| Notebook, docs, roadmap, considerações | `reports/` (métricas/gráficos — regeneráveis) |
| `config.yaml`, `requirements.txt` | `.venv`, caches, logs |

Você **não precisa fazer nada** para excluir essas pastas — o `git add -A` já as ignora.

> **Atenção ao lado ruim disso:** como `reports/` não sobe, quem clonar o repo (ou você
> mesmo, em outra máquina) **não recebe os artefatos das rodadas**. Eles precisam ser
> regenerados pelos scripts. Já houve confusão por causa disso: arquivos velhos de uma
> rodada sintética ficaram em `reports/` fingindo ser resultado real.

---

## Situações comuns

### "Quero ver o que exatamente mudou antes de enviar"
```powershell
git status            # lista os arquivos alterados
git diff roadmap.md   # mostra as mudancas linha a linha de UM arquivo
```

### "Editei algo errado e quero descartar (ANTES do commit)"
```powershell
git restore caminho\do\arquivo.md    # volta o arquivo ao ultimo commit (perde a edicao!)
```

### "Fiz commit mas ainda nao dei push e quero corrigir a mensagem"
```powershell
git commit --amend -m "mensagem corrigida"
```

### "O push foi rejeitado (rejected / fetch first)"
Significa que o GitHub tem algo que você não tem localmente (ex.: editou um arquivo
pelo site, ou mergeou uma PR por lá). Traga primeiro, depois envie:
```powershell
git pull --rebase
git push
```

### "Quero ver o histórico do que já foi enviado"
```powershell
git log --oneline -10
```

### "Sobrou uma branch antiga que eu não uso mais"
```powershell
git branch -d nome-da-branch                 # apaga a local
git push origin --delete nome-da-branch      # apaga a do GitHub
```

---

## Avisos que podem aparecer (e são inofensivos)

- **`warning: LF will be replaced by CRLF`** → normalização de fim de linha do Windows. Ignorar.
- **Janela de login do GitHub** → autentique uma vez; fica salvo para os próximos pushes.
- **`remote: This repository moved`** → o repo foi renomeado e o redirecionamento funcionou.
  Se aparecer, vale corrigir o endereço com `git remote set-url origin <URL nova>`.

## Sinais de alerta (aí sim, cuidado)

- **`error: failed to push`** persistente após `git pull --rebase` → me chame.
- **Arquivo > 50 MB no commit** → provavelmente algo de `data/` escapou do
  `.gitignore`; NÃO force o push, rode `git status` e me chame.
- **`CONFLICT` durante o pull** → o mesmo trecho foi editado em dois lugares;
  se não souber resolver, me chame (não apague nada).
- **Commit no repositório errado** → confira com `git remote get-url origin` antes.

---

## Colinha final (o combo completo em uma linha)

**Desafio (estratégia):**
```powershell
cd "C:\Users\Lucca\Desktop\Quant\Desafio Quant\quant_ai_2026"; git add -A; git commit -m "SUA MENSAGEM AQUI"; git push
```

**Estudos:**
```powershell
cd "C:\Users\Lucca\Desktop\Quant\Quant Learning"; git add -A; git commit -m "SUA MENSAGEM AQUI"; git push
```

*Criado em 14/07/2026 · atualizado em 05/08/2026 (caminhos novos após a saída do OneDrive,
repos renomeados para `Desafio-Quant-2026` e `quant-studies`, e o segundo repo documentado).
Se a pasta mudar de lugar, só o `cd` muda — o resto é idêntico.*
