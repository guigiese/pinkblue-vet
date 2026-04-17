# WORKING_MODEL

This document defines the minimum operating model for the PinkBlue platform.

It is intentionally practical.
It should stay small, explicit, and easy for both humans and AIs to follow.

## 0. Vocabulário Canônico

Usar esses termos de forma consistente em toda documentação, cards Jira e sessões de IA.
Nunca usar "projeto" de forma ambígua.

| Termo | Definição |
|---|---|
| **Plataforma** | PinkBlue Vet — o ecossistema completo |
| **Módulo** | Capacidade de produto: Lab Monitor, Financeiro, CRM |
| **Repositório** | O monorepo GitHub: guigiese/pinkblue-vet |
| **Projeto Jira** | Escopo de rastreamento (ver seção 1) |
| **Serviço** | Container deployado no Railway |
| **Sessão** | Unidade de trabalho: branch + card Jira + PR |

## 0A. Workspace Design Decisions

Decisões estruturais sobre o workspace que não devem ser re-questionadas sem um card Jira.

**Estrutura de entrada das IAs (decidido em 2026-04, refinado em 2026-04-08):**
- `CLAUDE.md` e `AGENTS.md` são entradas específicas por ferramenta (mínimas, só redirecionam)
- `SESSION_PRIMER.md` é o contexto operacional compacto — lido sempre por todas as IAs
- `AI_START_HERE.md` é o manifesto de onboarding — para IAs que chegam sem contexto; não duplica SESSION_PRIMER
- `docs/` tem taxonomia explícita por tipo de conhecimento: Governança / Arquitetura / Decisões / Domínio externo / Histórico
- Esta estrutura é intencional. Não simplificar sem card PBVET.

**Branch cleanup policy (decidido em 2026-04-07):**
- Auto-delete de branches ativado no GitHub (branches deletadas ao merge)
- `git fetch --prune` deve ser executado no início de cada sessão
- Tags de release em `main` a cada conjunto significativo de mudanças

**Nomenclatura (decidido em 2026-04-07):**
- Repositório GitHub: `guigiese/pinkblue-vet`
- Projeto Railway: `pinkblue-vet`
- Serviço Railway de produção: `pinkblue-vet`
- Pasta local: pode variar, não é crítico para funcionamento

## 1. Jira Structure

Projetos ativos (consolidação concluída em 2026-04-08):
- `PBVET`: projeto unificado — Lab Monitor, plataforma, infra, governança, docs
- `PBINC`: incubadora para módulos futuros (CRM, automação de atendimento)

Projetos legados arquivados: `PBEXM`, `PBCORE`, `PBFIN` — issues migradas para PBVET.

Workflow de entrega (PBVET):
`Backlog → Descoberta → Refinamento → Pronto pra dev → Em andamento → Em revisão → Concluído`

Workflow de incubação (PBINC):
`Backlog → Descoberta → Validação → Pronto pra incubar → Em incubação → Graduado`

Roteamento de cards:
- trabalho de produto, módulo ou plataforma → `PBVET`
- descoberta de módulo futuro ainda sem entrega comprometida → `PBINC`
- quando o módulo incubado tem backlog próprio e cadência de entrega → criar épico em `PBVET`

## 1A. PBVET Scope Policy

`PBVET` é o projeto unificado. Cobre desde trabalho de produto (Lab Monitor) até plataforma, infra e governança.

Work that belongs in `PBVET`:
- entrega de produto: comportamento, telas, regras, dados, conectores de lab, validação
- plataforma e infra: auth, secrets, persistência, observabilidade, deploy, shared capabilities
- governança: operating model do Jira, workflow rules, DoR/DoD, onboarding de IAs
- docs e decisões: documentação de arquitetura, ADRs, playbooks de integração

Work that belongs in `PBINC` instead:
- descoberta de módulos futuros que ainda não têm entrega comprometida (CRM, automação de atendimento)
- quando o módulo incubar e tiver backlog próprio, abre-se épico em `PBVET`

Ambiguous scope rule:
- se o escopo for ambíguo, usar label `scope-ambiguous` e não mover para `Pronto pra dev` sem decisão
- use label `needs-rehome` para cards cujo projeto correto é conhecido mas ainda carregam histórico do projeto antigo

## 2. When A Module Leaves PBINC

A module can leave `PBINC` when most of the following are true:

- it has a clear problem statement;
- it has a stable scope boundary;
- it already has multiple related cards, not just ideas;
- it has delivery cadence ahead of it;
- it needs its own backlog visibility.

Until then, keep it in `PBINC`.

## 3. Jira Issue Types

Current issue types available in the Jira projects:
- `Epic`
- `Tarefa`
- `Subtarefa`

Use them this way:

- `Epic`: a major stream of work with a shared outcome
- `Tarefa`: a concrete delivery or investigation
- `Subtarefa`: a smaller execution slice under a task

## 4. Jira Status Model

### Delivery workflow — PBVET

```
Backlog → Descoberta → Pronto pra dev → Em andamento → Em revisão → Concluído
```

| Status | Significado | Critério para avançar |
|---|---|---|
| `Backlog` | Capturado, ainda não refinado | Ter objetivo claro e escopo definido |
| `Descoberta` | Escopo, abordagem ou dependência ainda sendo clarificados | Objetivo claro + critério de aceite conhecido |
| `Pronto pra dev` | Refinado o suficiente para entrar em execução | Sessão de IA/dev iniciar e registrar [CLAIM] |
| `Em andamento` | Implementação ativa | PR aberto com a entrega |
| `Em revisão` | Em revisão, validação ou aceite final | PR mergeado + [CLOSE-OUT] no card + docs atualizados |
| `Concluído` | Concluído conforme DoD | — |

### Incubator workflow — PBINC

```
Backlog → Descoberta → Validação → Pronto pra incubar → Em incubação → Graduado
                                                                      ↘ Descartado
```

| Status | Significado | Critério para avançar |
|---|---|---|
| `Backlog` | Ideia capturada, ainda não trabalhada | Valer a pena explorar |
| `Descoberta` | Problema, escopo ou oportunidade sendo explorados | Problema entendido + hipótese de valor formulada |
| `Validação` | Ideia sendo pressure-tested antes de investir | Validada: problema real, solução viável, fit com plataforma |
| `Pronto pra incubar` | Pronto para receber esforço focado de incubação | Sessão iniciar trabalho ativo |
| `Em incubação` | Incubação ativa com shaping e primeira construção | Maduro o suficiente para virar módulo real |
| `Graduado` | Maduro para sair da incubadora e virar frente de entrega real | — |
| `Descartado` | Fechado intencionalmente por fit, prioridade ou viabilidade | — |

When a new PB project is created, use the helper below:
- `powershell -File scripts/apply_pb_jira_workflow.ps1 -ProjectKey <KEY>`

Profile behavior:
- `PBINC` uses the incubator workflow automatically
- any other PB project uses the delivery workflow automatically
- if needed, force it with `-Profile delivery` or `-Profile incubator`

If a temporary mismatch appears before the workflow is applied, represent the missing stages
through card comments and labels when needed:
- `discovery`
- `ready`
- `review`
- `blocked`
- `follow-up`

Do not rely on labels alone.
Always explain the current state in the Jira comments when it matters.

## 5. Definition Of Ready

A task is ready enough to start when it has:

- clear objective;
- clear scope;
- constraints or assumptions;
- expected output;
- a reasonable acceptance signal.

If one of these is missing, the AI or developer should call it out before starting.

## 6. Definition Of Done

A task is done only when:

- the intended change exists;
- the Jira card explains what was done;
- validation is described;
- affected docs were updated if needed;
- follow-up tasks were created for newly discovered work;
- no hidden sensitive data was introduced.

## 7. Required Jira Behavior

For substantial work, the card must receive at least:

1. a start comment
2. a progress update or blocker note
3. a close-out comment

Minimum content of each:

Start comment:
- goal
- assumptions
- first implementation move

Progress update:
- milestone reached or blocker found
- change in scope, risk, or understanding

Close-out:
- what changed
- how it was validated
- docs updated
- follow-ups created

## 8. Required AI Behavior

Every AI working on the project is expected to:

- read `AI_START_HERE.md` first;
- read this file before coding;
- read `docs/CONTEXT.md` and `docs/DEVLOG.md`;
- treat Jira as a living execution artifact;
- document meaningful decisions;
- create follow-up cards instead of burying debt;
- keep output aligned with the current platform naming.

If there is active work in progress by another AI or developer:
- default to parallel-safe work first;
- prefer discovery, Jira structure, docs, and isolated artifacts;
- avoid touching the same delivery scope, deploy path, or shared implementation files unless coordination is explicit;
- document any unavoidable overlap before changing it.

## 9. Documentation Rules

Use docs for durable knowledge.
Use Jira for operational progress.

Update docs when:
- product behavior changes;
- architecture changes;
- workflow/process changes;
- a lesson learned should persist beyond one task.

### 9.1. Testing Docs Governance

`docs/testing/**` is the official source of truth for AI-assisted testing in this repository.

Rules:
- every AI must read `docs/testing/AI_TESTING_STANDARD.md` before starting any testing, QA, mapping, or module validation task;
- before starting a new mapping, the AI must inspect `docs/testing/mappings/` for prior context;
- before starting a new test round, the AI must inspect `docs/testing/runs/` for prior executions and known results;
- every new mapping must create or update a file in `docs/testing/mappings/`;
- every new executed round must create or update a file in `docs/testing/runs/`;
- changes to the testing process itself must update `docs/testing/AI_TESTING_STANDARD.md`;
- testing docs created in isolated worktrees are not official until promoted back into the main repository history.

Promotion rule:
- prefer a docs-only commit and controlled integration into the active branch;
- avoid keeping competing versions of the canon, mappings, or runs across separate worktrees;
- the main repository copy is the one future sessions should trust.

For third-party systems that are accessed repeatedly across modules:
- maintain a canonical playbook in `docs/integrations/<system>.md`;
- keep that playbook short, operational, and safe for fast AI onboarding;
- use `docs/discovery/` for deeper session notes, then consolidate stable
  learnings back into the canonical playbook.

## 9A. Third-Party Production Systems Policy

When an AI accesses a third-party production system such as SimplesVet, the default behavior is strict observational mode.

Default rules:
- treat the system as production and potentially high-impact;
- navigation, visual inspection, queries, and report generation are allowed;
- creating, editing, deleting, confirming, syncing, billing, issuing, canceling, or triggering operational workflows is forbidden by default;
- the AI must not "test" actions in production to discover what they do;
- if the interface, wording, or API behavior is ambiguous, stop and surface the ambiguity instead of guessing.

Escalation rule for mutable actions:
- before any action that could change data or operational state, the AI must explain exactly:
  - what will be changed;
  - in which system/module/screen;
  - why the change is needed;
  - what the expected side effect is;
- then wait for explicit user approval;
- after approval, execute only the approved action, nothing broader.

Error-handling rule:
- system errors, warnings, permission denials, validation failures, or suspicious behavior must not be bypassed aggressively;
- bring them to the user for explicit approval before retrying with a different approach.

Credential rule:
- credentials for third-party systems must remain local-only and never enter versioned files, docs, Jira comments, or repository artifacts.

## 10. Naming Rule

A plataforma é PinkBlue Vet. Ver vocabulário canônico na seção 0.

`SimplesVet` era o nome do cliente/projeto anterior e não deve aparecer em novos artefatos.
Toda nomenclatura deve convergir para PinkBlue: repositório, Railway, módulos, documentação.

## 11. Collaboration Model: Multi-Session Protocol

Any number of AI sessions may work on this repository concurrently.
This section defines how they coordinate without stepping on each other.

### Session Identity

Every working session is an independent actor identified by a unique session-id:

```
session-id = YYYYMMDD + 4 hex chars (e.g. 20260331-a1b2)
```

There is no distinction between AI tools, agents, or human developers.
The unit of coordination is the **session**, not the actor.

### Branch Naming

Every session works on a dedicated branch:

```
session/YYYYMMDD-XXXX
```

Pushing directly to `main` is not allowed. Every change goes through a PR.

### PR Format

When opening a PR to main:
- Title: `session/YYYYMMDD-XXXX: <one-line summary>`
- Body: brief description of what changed and why, plus the Jira card reference

### Fast-Path vs Full-Path Routing

The GitHub Actions workflow `session-route.yml` is the neutral arbiter.
It counts active `session/*` branches at PR open time:

- **Fast-path** (1 active session): syntax check passes → merge immediately → deploy
- **Full-path** (2+ active sessions): syntax check + import check → merge → deploy

Sessions do not select the path. They only open the PR and fix failures.
The Actions workflow decides based on observed branch count.

### Claim / Release Protocol

**Before starting any file change**, add a `[CLAIM]` comment to the Jira card:

```
[CLAIM] session-id: 20260331-a1b2
Files in scope: web/app.py, labs/bitlab.py
```

**After the PR is merged or abandoned**, add a `[RELEASE]` comment:

```
[RELEASE] session-id: 20260331-a1b2
Files unlocked: web/app.py, labs/bitlab.py
```

If another session sees a `[CLAIM]` on a file it needs, it should prefer different files or coordinate explicitly before proceeding.

### Valid Session Close-Out

A session is closed-out when all of the following are true:

1. The `session/` branch has an open or merged PR targeting `main`
2. The Jira card has a `[CLOSE-OUT]` comment describing: what changed, how it was validated, which docs were updated, and any follow-ups
3. A `[RELEASE]` comment was added for all claimed files
4. The `session/` branch is deleted (merged PRs auto-delete if configured)

### Shared Artifact Rules

- `docs/CONTEXT.md` and `docs/DEVLOG.md` are shared — add, do not overwrite existing entries.
- `config.json` is deploy-sensitive — only change it when the Jira card explicitly requires it.
- `scripts/` is shared but non-destructive — sessions may add scripts; do not delete another session's scripts without a Jira card.
- `.secrets` may be read whenever operationally necessary.
- New entries may be added with caution.
- Existing entries must be edited only with extreme care, never overwriting or deleting valid secrets unintentionally.

### Conflict Resolution

If two sessions edited the same file and a merge conflict arises:
1. Human reviews both diffs.
2. Merge the non-conflicting additions manually.
3. Log the conflict in `docs/DEVLOG.md`.
4. Add a Jira comment on the relevant card.

### When in Doubt

Default to: docs first, isolated artifacts second, shared implementation third, deploy last.
If uncertain about scope overlap, check open PRs from `session/*` branches before starting.
