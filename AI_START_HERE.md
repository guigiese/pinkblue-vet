# AI_START_HERE

Read this file before doing any work in this repository.

Its job is simple:
- give any new AI a single entry point;
- route the AI to the right project context;
- enforce the minimum operating rules before execution starts.

## 1. Mission

This repository is part of the PinkBlue platform.

Right now, the active product module is the exam monitoring system.
Future modules will be incubated separately and may later become their own products.

The AI must not assume the whole platform is called "SimplesVet".
That name may appear in legacy paths or local folder names, but it is not the platform name.

## 2. Mandatory Reading Order

Always read in this order before starting implementation:

1. `AI_START_HERE.md`
2. `docs/WORKING_MODEL.md`
3. `docs/CONTEXT.md`
4. `docs/DEVLOG.md`
5. the Jira card related to the task
6. only then, the relevant code files

If there is no Jira card yet, the AI should say so clearly and avoid inventing hidden scope.

## 3. Source Of Truth

Use these sources in this order:

1. active Jira card
2. `docs/WORKING_MODEL.md`
3. `docs/CONTEXT.md`
4. current code
5. `docs/DEVLOG.md`

Jira is the operational source of truth.
Repository docs are the durable source of truth.
Chat messages help with context, but they do not replace Jira or docs.

## 4. Before Starting Work

Before changing code, the AI must:

1. state what it understood from the task;
2. state which files and docs were read;
3. state the execution plan briefly;
4. check whether the Jira card is ready enough to start;
5. add or update a Jira comment if the work is substantial.

Minimum readiness check:
- clear goal;
- clear scope;
- acceptance signal;
- known constraints or assumptions.

If one of those is missing, the AI should surface that explicitly.

## 5. While Working

The AI is expected to:
- keep the Jira card alive during execution;
- record important decisions and blockers;
- create follow-up work instead of hiding debt in silence;
- update docs when behavior, architecture, workflow, or assumptions change;
- avoid treating the Jira card as a static ticket.

Expected working behavior:
- start comment: plan, assumptions, first move;
- progress comment: meaningful milestone or blocker;
- close-out comment: result, validation, changed docs, open follow-ups.

## 5A. Parallel Work Guardrail

If another AI or developer has active work in progress, especially near validation or deploy,
do not assume it is safe to edit the same scope.

Default behavior in that situation:
- prefer Jira, docs, discovery, and planning work first;
- prefer isolated files, routes, modules, or artifacts that do not affect the active delivery line;
- do not change deploy-critical paths, release steps, or shared implementation files without explicit need;
- if overlap is unavoidable, document the risk clearly in Jira and in the final handoff.

When there is an active paused deploy or unfinished implementation by another AI,
the safest default is to work in parallel, not in-place.

## 6. Before Finishing

Before closing a task, the AI must check:

1. code or docs were updated if needed;
2. the Jira card explains what changed;
3. acceptance criteria were checked;
4. follow-ups were created if new work was discovered;
5. no sensitive information was introduced into code or docs.

## 7. When To Update Which Document

Update `docs/WORKING_MODEL.md` when:
- the Jira operating model changes;
- workflow rules change;
- AI working agreements change;
- project structure changes.

Update `docs/CONTEXT.md` when:
- the current technical behavior changes;
- architecture changes;
- data flow or module boundaries change.

Update `docs/DEVLOG.md` when:
- a decision matters for future reasoning;
- a lesson learned should not be rediscovered later;
- a failed approach is worth remembering.

## 8. Jira Project Map

Current Jira structure:
- `PBEXM`: exam module work
- `PBCORE`: platform, process, docs, security, data, infra
- `PBINC`: incubator for future modules

Cross-project board:
- `PB Triage`: transversal board for cards with ambiguous scope or re-home decisions
- it is a view, not a project
- cards shown there still belong to one real project: `PBEXM`, `PBCORE`, or `PBINC`

Working meaning of each project:
- `PBEXM`: work that belongs to the exam module itself, including product behavior, data, UI, lab connectors, validation, and delivery of the Lab Monitor line.
- `PBCORE`: governance plus shared platform capabilities. This is the home for workflow rules, docs, AI operating model, naming, auth, secrets, persistence, infra, observability, and any capability meant to serve more than one module.
- `PBINC`: discovery for future business modules that are not yet committed as active delivery lines.

Quick routing rule:
- if the work changes one module only, it probably does not belong in `PBCORE`;
- if the work creates or explores a new business module, it belongs in `PBINC`;
- if the work defines rules, tooling, or technical capabilities that sit above modules or can be reused across modules, it belongs in `PBCORE`.

`PBCORE` is not a generic overflow bucket.
If a task is only a local feature or page for the exam module, prefer `PBEXM` unless there is a clear cross-platform reason not to.
If scope is still ambiguous, the discovery can start in `PBCORE`, but the downstream implementation should move to the module project as soon as the work proves to be module-local.

Board routing rule:
- use label `scope-ambiguous` when the card still needs a home decision
- use label `needs-rehome` when the correct home is already known but the card still carries old project history
- no card with one of those labels should move to `Pronto pra dev` without a clear home decision

Jira project keys cannot use an internal hyphen such as `PB-EXM`.
Because of that platform limitation, the actual keys stay `PBEXM`, `PBCORE`, and `PBINC`,
while the human naming convention can still be read as `PB / Exames`, `PB / Core`, and `PB / Incubadora`.

If a task does not clearly belong to one of those, raise that ambiguity instead of guessing.

## 9. Non-Negotiable Rules

- Do not assume hidden requirements.
- Do not leave major decisions undocumented.
- Do not leave discovered work only in chat.
- Do not treat docs as optional.
- Do not introduce or keep sensitive credentials in versioned files.

## 10. Quick Start Prompt For New IAs

If you are a new AI entering this project, begin by saying:

"I read `AI_START_HERE.md`, `docs/WORKING_MODEL.md`, `docs/CONTEXT.md`, and `docs/DEVLOG.md`. I will summarize my understanding, identify the active Jira card, and only then propose or execute changes."
