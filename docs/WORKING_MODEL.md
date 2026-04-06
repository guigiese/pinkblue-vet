# WORKING_MODEL

This document defines the minimum operating model for the PinkBlue platform.

It is intentionally practical.
It should stay small, explicit, and easy for both humans and AIs to follow.

## 0. Repository Scope

This repository is no longer treated as "just the Lab Monitor repo".

Operationally, it is the current PinkBlue platform workspace:
- `PBEXM` owns the Lab Monitor module;
- `PBCORE` owns shared capabilities such as auth, persistence, shell visual,
  security, infra, and cross-module conventions;
- `PBINC` owns future-module discovery.

That means shared capabilities must not be modeled as if they belonged only to
the exam module.
Examples:
- platform-wide auth belongs in `PBCORE`, while `PBEXM` may only keep module
  integration details;
- platform persistence belongs in `PBCORE`, while `PBEXM` keeps the exam-module
  consumers and migration slices;
- visual shell and navigation standards belong in `PBCORE`, while module-level
  pages consume them.

## 1. Jira Structure

There are currently 3 Jira projects:

- `PBEXM`: exam module
- `PBCORE`: platform, governance, docs, security, data, infra
- `PBINC`: incubator for future modules

Important naming note:
- the organizational prefix is PinkBlue (`PB`)
- Jira does not accept project keys with an internal hyphen such as `PB-EXM`
- because of that, the real Jira keys remain `PBEXM`, `PBCORE`, and `PBINC`

Use them like this:

- `PBEXM` for exam product work and exam-specific hardening
- `PBCORE` for cross-cutting work and platform-level decisions
- `PBINC` for future-module discovery until a module deserves its own project

Cross-project board:
- `PB Triage` is the transversal board for cards with ambiguous scope or re-home decisions
- it is a board only, not a fourth project
- cards on that board must still belong to one real project: `PBEXM`, `PBCORE`, or `PBINC`

## 1A. PBCORE Scope Policy

`PBCORE` exists for governance plus shared platform capabilities.
It is not docs-only, but it is also not a generic overflow bucket.

Work that belongs in `PBCORE`:
- Jira operating model, workflow rules, DoR, DoD, and project governance
- AI onboarding, working agreements, documentation standards, and execution guardrails
- naming, repository organization, and platform-level operating conventions
- auth, secrets, persistence, infra, observability, and other technical capabilities meant to serve more than one module
- shared contracts, shared tooling, or platform rules that sit above a single module
- discovery of platform capabilities before they become implementation

Work that does not belong in `PBCORE`:
- product behavior, screens, rules, data, or delivery work that belongs only to the exam module
- active Lab Monitor implementation or deploy-line work when the scope is local to that module
- discovery of future business modules such as CRM, Financeiro, or Automacao de Atendimento

Quick routing rule:
- if the work affects one active module only, prefer that module project
- if the work explores a future business module, use `PBINC`
- if the work defines a reusable rule, platform guardrail, or shared capability, use `PBCORE`

Ambiguous scope rule:
- if the scope is still unclear, discovery may begin in `PBCORE`
- once discovery shows the downstream work is module-local, the implementation cards should move to the module project instead of staying in `PBCORE`

Triage board rule:
- use label `scope-ambiguous` for cards that still need a home decision
- use label `needs-rehome` for cards whose right home is known, but whose history is still being preserved in the old project
- cards with one of those labels may live on the `PB Triage` board while the routing decision is active
- no such card should enter `Pronto pra dev` without a clear destination project

Current incubated module lines:
- Financeiro
- CRM
- Automacao de Atendimento

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

### Delivery workflow — PBEXM e PBCORE

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

The platform is PinkBlue.

`SimplesVet` may remain in legacy paths for now, but it must not be treated as the platform-level name.
Any naming cleanup should align platform, modules, repositories, and documentation around PinkBlue.

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
- `.secrets` is never touched by any session — human-managed only.

### Conflict Resolution

If two sessions edited the same file and a merge conflict arises:
1. Human reviews both diffs.
2. Merge the non-conflicting additions manually.
3. Log the conflict in `docs/DEVLOG.md`.
4. Add a Jira comment on the relevant card.

### When in Doubt

Default to: docs first, isolated artifacts second, shared implementation third, deploy last.
If uncertain about scope overlap, check open PRs from `session/*` branches before starting.
