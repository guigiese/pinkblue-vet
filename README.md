# PinkBlue Vet

Workspace atual da plataforma PinkBlue Vet.

## Estado atual

Modulo ativo principal:
- `Lab Monitor`

Superficies auxiliares ja existentes:
- home da plataforma em `/`
- mapa operacional em `/ops-map/`
- sandboxes em `/sandboxes/*`

Modulos futuros em discovery:
- CRM veterinario
- conciliacao financeira
- automacao de atendimento

## Stack atual

- Python 3.13
- FastAPI + Jinja2 + HTMX
- Railway

Persistencia/auth oficiais da plataforma:
- `pb_platform/` como camada compartilhada;
- `PostgreSQL` como banco oficial do runtime;
- `SQLite` apenas para testes/CI efemeros quando configurado de forma explicita;
- auth por sessao/cookie para a plataforma.

## Regras de entrada

Antes de qualquer trabalho:
- leia `SESSION_PRIMER.md`
- leia `AI_START_HERE.md` apenas se estiver entrando sem contexto ou configurando uma nova IA/ferramenta
- busque o card Jira relacionado

## Documentos principais

- `SESSION_PRIMER.md` - protocolo operacional de sessao
- `AI_START_HERE.md` - porta de entrada para IAs
- `docs/WORKING_MODEL.md` - modelo operacional do projeto
- `docs/CONTEXT.md` - estado tecnico atual
- `docs/DEVLOG.md` - historico de decisoes
- `docs/discovery/2026-04-03-platform-structure-and-phase1-persistence.md` - estrutura-alvo da plataforma e decisao da persistencia fase 1

## Direcao estrutural

Este repositorio ainda carrega uma estrutura muito centrada no Lab Monitor,
mas a direcao oficial agora e:

- auth compartilhada da plataforma;
- persistencia compartilhada da plataforma;
- shell visual compartilhado;
- modulos de negocio desacoplados dessas capacidades.

Essa migracao deve ser feita por fases, sem reestruturacao destrutiva de uma vez.
