# PinkBlue Vet - Platform Workspace - Session Primer

Você está no workspace da plataforma PinkBlue Vet.
O Lab Monitor é o módulo ativo principal neste repositório, mas ele não é mais o ente principal da plataforma.
Novos módulos como CRM e conciliação financeira devem entrar sob a mesma camada compartilhada de auth, persistência e shell visual.
Leia este arquivo inteiro. Depois execute a tarefa recebida.
Consulte os arquivos referenciados abaixo apenas se a tarefa exigir.

---

## Vocabulário canônico

| Termo | Definição |
|---|---|
| **Plataforma** | PinkBlue Vet — o ecossistema completo |
| **Módulo** | Capacidade de produto: Lab Monitor, Financeiro, CRM |
| **Repositório** | O monorepo GitHub (único): guigiese/pinkblue-vet |
| **Projeto Jira** | Escopo de rastreamento: PBVET (unificado), PBINC (incubadora) |
| **Serviço** | Container deployado no Railway |
| **Sessão** | Unidade de trabalho: branch + card Jira + PR |

Use esses termos. Não use "projeto" de forma ambígua.

---

## Plataforma

Workspace da plataforma PinkBlue Vet.

Estado atual:
- módulo ativo de produto: Lab Monitor
- módulo em desenvolvimento: Financeiro
- superfícies auxiliares: home da plataforma, ops-map, sandboxes
- módulos futuros incubados: CRM, automação de atendimento

Stack: Python 3.13 / FastAPI 0.115 / Jinja2 3.1 / HTMX 1.9 / TailwindCSS CDN / Railway.
Produção: https://pinkblue-vet-production.up.railway.app
Repositório: github.com/guigiese/pinkblue-vet

Deploy: abrir PR de `session/*` → GitHub Actions faz merge + deploy automaticamente.
Nunca fazer push direto em `main`.

---

## Mapa de conhecimento

Cada arquivo tem um tipo de conhecimento específico. Carregar apenas o que a tarefa exige.

| Arquivo | Tipo | Quando carregar |
|---|---|---|
| `SESSION_PRIMER.md` | **Operacional** — protocolo e contexto compacto | Sempre |
| `docs/WORKING_MODEL.md` | **Governança** — regras de Jira, workflow, DoR/DoD | Dúvida de processo ou escopo |
| `docs/CONTEXT.md` | **Arquitetura** — como o sistema foi construído e funciona | Tarefas técnicas / arquitetura |
| `docs/decisions/` | **Decisões** — ADRs imutáveis, o porquê das escolhas | Quando questionar uma decisão passada |
| `docs/integrations/<sistema>.md` | **Domínio externo** — playbook operacional de cada sistema terceiro | Tarefas que tocam sistema externo |
| `docs/DEVLOG.md` | **Histórico** — o que aconteceu, bugs, lições aprendidas | Debugging ou contexto histórico |
| `AI_START_HERE.md` | **Onboarding** — para IAs que chegam sem contexto nenhum | Primeira sessão neste repositório |
| `docs/discovery/` | **Notas de sessão** — ephemeral, profundidade pontual | Pesquisa ativa ou spike |

---

## Ao receber qualquer tarefa: Jira primeiro

Antes de tocar qualquer arquivo:

**1. Busque cards existentes**
Jira: https://guigiese.atlassian.net | Credenciais: `~/.codex/jira-auth.json`
Projetos: PBVET (Lab Monitor + plataforma) · PBINC (incubadora: CRM, Financeiro)
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

`Backlog` → `Descoberta` → `Refinamento` → `Pronto pra dev` → `Em andamento` → `Em revisão` → `Concluído`

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
| "e depois continue" | Fecha card, busca próximo `Pronto pra dev` em PBVET, executa. |
| "e depois me mostre o planejado" | Fecha card, lista `Pronto pra dev` + `Descoberta` com resumo. |
| "e depois planeje X" | Fecha card, cria cards de discovery para X no projeto correto. |
| "e depois faça X" | Fecha card, inicia X (cria card se não existir). |

Se a instrução for ambígua, conclua a tarefa atual e pergunte antes de continuar.
