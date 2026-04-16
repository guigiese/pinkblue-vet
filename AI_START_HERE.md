# AI_START_HERE

Este arquivo é o ponto de entrada para IAs que chegam sem contexto nenhum neste repositório.

Se você já tem SESSION_PRIMER.md carregado, este arquivo é redundante — ignore-o.

---

## Missão

Este repositório é o workspace da plataforma **PinkBlue Vet**.

O módulo ativo de produto é o **Lab Monitor** (monitoramento de exames laboratoriais).
A plataforma está sendo expandida para incluir módulos de Financeiro, CRM e automação de atendimento.

O repositório é um monorepo. O nome da pasta local pode variar — o que importa é:
- Repositório GitHub: `guigiese/pinkblue-vet`
- Produção: `https://pinkblue-vet-production.up.railway.app`

---

## Ordem de leitura obrigatória

**Sessão de trabalho normal:** leia apenas `SESSION_PRIMER.md`. Ele é suficiente.

Exceção:
- se a tarefa envolver mapeamento, testes, QA, validação de módulo ou revisão de comportamento/UI,
  leia também `docs/testing/AI_TESTING_STANDARD.md` antes de agir.

**Onboarding completo** (primeira vez no repositório ou dúvida de protocolo):

1. `SESSION_PRIMER.md` — contexto operacional e protocolo
2. `docs/testing/AI_TESTING_STANDARD.md` — obrigatório para tarefas de teste/QA
3. `docs/WORKING_MODEL.md` — governança, regras de Jira, DoR/DoD
4. `docs/CONTEXT.md` — arquitetura técnica atual
5. card Jira da tarefa — escopo e histórico da entrega específica
6. arquivos de código relevantes — somente então

---

## Mapa de conhecimento

| Arquivo | Tipo | Quando carregar |
|---|---|---|
| `SESSION_PRIMER.md` | Operacional | Sempre |
| `docs/WORKING_MODEL.md` | Governança | Dúvida de processo |
| `docs/CONTEXT.md` | Arquitetura | Tarefas técnicas |
| `docs/decisions/` | Decisões (ADRs) | Quando questionar decisão passada |
| `docs/integrations/<sistema>.md` | Domínio externo | Tarefas com sistema terceiro |
| `docs/DEVLOG.md` | Histórico | Debugging / contexto histórico |
| `docs/discovery/` | Notas de sessão | Pesquisa ativa ou spike |
| `docs/testing/AI_TESTING_STANDARD.md` | Canônico de testes com IA | Tarefas de teste, QA e validação |
| `docs/testing/mappings/` | Histórico de mapeamentos | Antes de novo mapeamento |
| `docs/testing/runs/` | Histórico de rodadas | Antes de nova rodada de teste |

---

## Regras não-negociáveis

- Nunca pushar direto em `main`. Sempre via `session/` branch + PR.
- Nunca executar entrega sem card Jira ativo.
- Nunca introduzir credenciais em arquivos versionados.
- Nunca mutar sistemas de terceiros em produção sem aprovação explícita.
- Sempre registrar `[CLAIM]` antes de editar, `[CLOSE-OUT]` ao concluir.
