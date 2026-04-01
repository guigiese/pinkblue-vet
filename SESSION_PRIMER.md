# PinkBlue Lab Monitor — Session Primer

Você está no repositório do Lab Monitor da PinkBlue Vet.
Leia este arquivo inteiro. Depois execute a tarefa recebida.
Consulte os arquivos referenciados abaixo apenas se a tarefa exigir.

---

## Projeto

Monitor automatizado de exames laboratoriais veterinários para a PinkBlue Vet.
Stack: Python 3.13 / FastAPI 0.115 / Jinja2 3.1 / HTMX 1.9 / TailwindCSS CDN / Railway.
Produção: https://pinkblue-vet-production.up.railway.app
Repositório: github.com/guigiese/monitor-exames-bitlab

Deploy: abrir PR de `session/*` → GitHub Actions faz merge + deploy automaticamente.
Nunca fazer push direto em `main`.

Referências de detalhe (ler só quando a tarefa exigir):
- Arquitetura completa: `docs/CONTEXT.md`
- Histórico de decisões: `docs/DEVLOG.md`
- Protocolo completo de sessões e governança: `AI_START_HERE.md`

---

## Ao receber qualquer tarefa: Jira primeiro

Antes de tocar qualquer arquivo:

**1. Busque cards existentes**
Jira: https://guigiese.atlassian.net | Credenciais: `~/.codex/jira-auth.json`
Projetos: PBEXM (produto/exames) · PBCORE (plataforma/infra) · PBINC (discovery)
Busque palavras-chave do problema descrito pelo usuário.

**2. Avalie os resultados**
- Card com `[CLAIM]` ativo → outra sessão está trabalhando → prefira escopo adjacente.
- Card sem `[CLAIM]` → disponível → leia comentários para absorver contexto acumulado.
- Nenhum card relevante → crie o card no projeto correto, depois execute.

**3. Se o contexto do card for insuficiente**
Crie subtarefas ou adicione comentário de contexto antes de executar.
Nunca execute entrega sem card ativo.

---

## Protocolo de sessão

```bash
# 1. Gerar session-id
python -c "import secrets; from datetime import date; \
print(f'{date.today().strftime(\"%Y%m%d\")}-{secrets.token_hex(2)}')"

# 2. Criar branch
git checkout -b session/YYYYMMDD-XXXX
```

3. Comentar `[CLAIM] session-id + arquivos em escopo` no card antes de editar.
4. Abrir PR ao concluir → Actions faz merge + deploy.
5. Comentar `[CLOSE-OUT]` + `[RELEASE]` no card e mover para Concluído.

---

## Fluxo dos cards

`Backlog` → `Descoberta` → `Pronto pra dev` → `Em andamento` → `Em revisão` → `Concluído`

---

## Arquivos críticos

| Arquivo / Dir | Regra |
|---|---|
| `deploy.py` / `config.json` | Exige card explícito antes de editar |
| `labs/` `web/` `core.py` | Exige `[CLAIM]` antes de editar |
| `docs/DEVLOG.md` | Append-only — sem `[CLAIM]` necessário |
| `scripts/` `poc/` | Livre — sem `[CLAIM]` necessário |
| `.secrets` | Nunca tocar |

---

## Continuação após tarefa

| Usuário diz | Comportamento |
|---|---|
| "e depois aguarde" | Fecha card, para. |
| "e depois continue" | Fecha card, busca próximo `Pronto pra dev` em PBEXM, executa. |
| "e depois me mostre o planejado" | Fecha card, lista `Pronto pra dev` + `Descoberta` com resumo. |
| "e depois planeje X" | Fecha card, cria cards de discovery para X no projeto correto. |
| "e depois faça X" | Fecha card, inicia X (cria card se não existir). |

Se a instrução for ambígua, conclua a tarefa atual e pergunte antes de continuar.
