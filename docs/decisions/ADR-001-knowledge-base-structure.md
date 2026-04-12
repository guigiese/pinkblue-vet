# ADR-001: Estrutura da base de conhecimento para IAs

**Status:** Aceito
**Data:** 2026-04-08
**Card:** PBVET-27

---

## Contexto

A plataforma PinkBlue Vet opera com múltiplas IAs (Claude, Codex, e outras) trabalhando em sessões independentes no mesmo repositório. Com o crescimento do número de módulos e documentos, a ausência de uma taxonomia explícita causava:

- Duplicação de conteúdo entre SESSION_PRIMER, AI_START_HERE e WORKING_MODEL
- IAs carregando todos os arquivos por precaução, desperdiçando tokens de contexto
- Referências desatualizadas persistindo em múltiplos arquivos após mudanças estruturais
- Ausência de separação entre conhecimento perene (arquitetura, decisões) e conhecimento operacional (protocolo, regras de trabalho)

---

## Decisão

Adotar uma taxonomia explícita de 6 tipos de arquivo, cada um com propósito exclusivo:

| Tipo | Arquivo(s) | Conteúdo |
|------|-----------|----------|
| **Operacional** | `SESSION_PRIMER.md` | Protocolo de sessão, vocabulário, contexto compacto — sempre carregado |
| **Onboarding** | `AI_START_HERE.md` | Manifesto de roteamento para IAs sem contexto prévio — não duplica SESSION_PRIMER |
| **Governança** | `docs/WORKING_MODEL.md` | Regras de Jira, workflow, DoR/DoD — carregado sob dúvida de processo |
| **Arquitetura** | `docs/CONTEXT.md` | Estado técnico atual do sistema — carregado para tarefas técnicas |
| **Decisões** | `docs/decisions/ADR-*.md` | Registros imutáveis de decisões arquiteturais (este diretório) |
| **Domínio externo** | `docs/integrations/<sistema>.md` | Playbook operacional de sistemas de terceiros |
| **Histórico** | `docs/DEVLOG.md` | Log append-only de decisões relevantes, bugs e lições aprendidas |
| **Notas de sessão** | `docs/discovery/` | Pesquisas, spikes e notas pontuais — ephemeral, consolidar o que for durável |

Regras desta estrutura:
1. Cada arquivo pertence a exatamente um tipo
2. Nenhum tipo duplica conteúdo de outro — quando há sobreposição, um arquivo prevalece e o outro referencia
3. SESSION_PRIMER prevalece sobre AI_START_HERE quando ambos são carregados
4. ADRs são imutáveis após aceitos — novas decisões criam novos ADRs, não editam os antigos

---

## Consequências

**Positivas:**
- IAs carregam apenas o que precisam — menor consumo de tokens por sessão
- Mudanças estruturais têm um único local canônico — sem drift entre arquivos
- Decisões passadas ficam registradas com contexto (por quê) em vez de só resultado (o quê)
- Estrutura já preparada para futura indexação RAG quando o volume de docs crescer

**Negativas / trade-offs:**
- Requer disciplina para não voltar a duplicar conteúdo em novos arquivos
- ADRs imutáveis exigem criar um novo ADR quando uma decisão muda, em vez de editar o antigo

---

## Alternativas consideradas

**Arquivo único (wiki monolítica):** rejeitado — cresce sem limite, força carregamento completo por sessão.

**Distribuição por módulo (docs/lab-monitor/, docs/financeiro/):** rejeitado para agora — útil quando houver 5+ módulos com documentação rica; prematura com 2 módulos ativos.

**RAG (Retrieval-Augmented Generation):** adiado — faz sentido com 50+ documentos; overhead de infraestrutura não se justifica no volume atual. Esta estrutura por tipos é compatível com indexação RAG futura sem reescrita.
