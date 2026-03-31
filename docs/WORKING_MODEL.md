# WORKING_MODEL

This document defines the minimum operating model for the PinkBlue platform.

It is intentionally practical.
It should stay small, explicit, and easy for both humans and AIs to follow.

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

Delivery workflow for `PBEXM` and `PBCORE`:
- `Backlog`
- `Descoberta`
- `Pronto pra dev`
- `Em andamento`
- `Em revisÃ£o`
- `ConcluÃ­do`

Working meaning for the delivery flow:
- `Backlog`: item captured, but not yet refined
- `Descoberta`: scope, approach, or dependency is still being clarified
- `Pronto pra dev`: refined enough to enter execution
- `Em andamento`: active implementation work
- `Em revisÃ£o`: review, validation, or final acceptance
- `ConcluÃ­do`: done according to DoD

Incubator workflow for `PBINC`:
- `Backlog`
- `Descoberta`
- `ValidaÃ§Ã£o`
- `Pronto pra incubar`
- `Em incubaÃ§Ã£o`
- `Graduado`
- `Descartado`

Working meaning for the incubator flow:
- `Backlog`: idea captured, but not yet worked
- `Descoberta`: problem, scope, or opportunity is being explored
- `ValidaÃ§Ã£o`: the idea is being pressure-tested before investment
- `Pronto pra incubar`: ready to receive focused incubation effort
- `Em incubaÃ§Ã£o`: active incubation with shaping and first construction
- `Graduado`: mature enough to leave the incubator and become a real delivery front
- `Descartado`: intentionally closed due to fit, priority, or viability

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

## 10. Naming Rule

The platform is PinkBlue.

`SimplesVet` may remain in legacy paths for now, but it must not be treated as the platform-level name.
Any naming cleanup should align platform, modules, repositories, and documentation around PinkBlue.

## 11. Collaboration Model: Claude + Codex

Two AI agents may work on this repository at the same time.
This section defines the minimum coordination rules to prevent conflicts.

### Roles

At any given moment, define one AI as **deploy owner** and the other as **discovery AI**.

- **Deploy owner**: holds the active delivery line. May edit production code, run deploys, create PBEXM delivery cards.
- **Discovery AI**: works in isolation — docs, Jira discovery cards, scripts, and isolated artifacts (like `poc/`). Does not touch deploy-critical files, shared implementation, or `main` branch active paths.

The roles can rotate between sessions, but the handoff must be explicit (Jira comment or commit message).

### Coordination via Jira

Before starting work on any shared scope:
1. Check whether another AI has an open card for the same area.
2. If yes, default to discovery or isolated work.
3. Add a Jira comment to the relevant card noting: which AI, what scope, what timestamp.
4. At close-out, add a comment with what changed and what the other AI needs to know.

### Branch and file rules

- Each AI should prefer working on isolated paths:
  - Claude Code → active delivery in `labs/`, `web/`, `core.py`
  - Codex → docs, `scripts/`, `poc/`, `AI_START_HERE.md`, `WORKING_MODEL.md`, PBCORE cards
- If both AIs need to touch the same file, use separate git branches and coordinate the merge explicitly.
- `poc/` is Codex territory by convention until validated for production.
- Production deploy path (`deploy.py`, Railway, `main` branch) is Claude Code territory unless explicitly handed off.

### Shared artifact rules

- `docs/CONTEXT.md` and `docs/DEVLOG.md` are shared — add, do not overwrite.
- `config.json` is deploy-sensitive — only the deploy owner should edit it.
- `scripts/` is shared but non-destructive — both AIs may add scripts; neither should delete the other's scripts without a Jira card.
- `.secrets` is never touched by either AI — human-managed only.

### Conflict resolution

If a conflict is detected (two AIs edited the same file in separate sessions):
1. Human reviews both diffs.
2. Merge the non-conflicting additions manually.
3. Log the conflict in DEVLOG.md.
4. Add a Jira comment on the relevant card.

### When the model does not apply

This model applies to sessions where both AIs have active context.
If only one AI is active, it acts as deploy owner by default.
If uncertain, always default to: docs first, code second, deploy last.
