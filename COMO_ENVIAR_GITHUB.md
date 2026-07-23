# 📤 Como enviar o projeto para o GitHub (guia de bolso)

> Repositório: **https://github.com/luccazogbi/Quant** (privado)
> Tudo já está configurado (remote, identidade, .gitignore). Este guia é o passo a passo
> para o dia a dia, sem depender de ninguém.

---

## O fluxo de sempre (95% dos casos são só isto)

Abra o **PowerShell** e rode, linha por linha:

```powershell
# 1. entrar na pasta do projeto
cd "C:\Users\lucca\OneDrive\Área de Trabalho\Quant-main\Quant-main"

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
pelo site). Traga primeiro, depois envie:
```powershell
git pull --rebase
git push
```

### "Quero ver o histórico do que já foi enviado"
```powershell
git log --oneline -10
```

---

## Avisos que podem aparecer (e são inofensivos)

- **`warning: LF will be replaced by CRLF`** → normalização de fim de linha do Windows. Ignorar.
- **Janela de login do GitHub** → autentique uma vez; fica salvo para os próximos pushes.

## Sinais de alerta (aí sim, cuidado)

- **`error: failed to push`** persistente após `git pull --rebase` → me chame.
- **Arquivo > 50 MB no commit** → provavelmente algo de `data/` escapou do
  `.gitignore`; NÃO force o push, rode `git status` e me chame.
- **`CONFLICT` durante o pull** → o mesmo trecho foi editado em dois lugares;
  se não souber resolver, me chame (não apague nada).

---

## Colinha final (o combo completo em uma linha)

```powershell
cd "C:\Users\lucca\OneDrive\Área de Trabalho\Quant-main\Quant-main"; git add -A; git commit -m "SUA MENSAGEM AQUI"; git push
```

*Criado em 14/07/2026. Se a pasta do projeto mudar de lugar, só o `cd` da linha 1 muda — o resto é idêntico.*
