# Triage do Backlog — Wave 1: Bugs e Dívidas Técnicas
**Data:** 2026-04-17
**Projetos:** PBVET + PBINC
**Escopo:** Todos os cards abertos (non-Done), excluindo subtarefas

---

## Resumo executivo

| Projeto | Total open | Pronto pra dev | Em andamento | Descoberta |
|---|---|---|---|---|
| PBVET | 203 | 16 | 12 | 34 |
| PBINC | 58 | 21 | 0 | 12 |
| **Total top-level** | **158** | — | — | — |

**Atenção imediata:** 4 bugs identificados, 2 deles em produção ativa.

**Problema estrutural:** Muitos cards duplicados (Plantão tem histórias em 2 versões, epics de Platform Shell triplicados). Limpeza recomendada antes de execução.

---

## 🔴 Wave 1 — Bugs em produção (executar imediato)

| Key | Summary | Status | Criticidade |
|---|---|---|---|
| **PBVET-60** | Exame com resultado disponível não dispara notificação de conclusão | Em revisão (High) | **P1 — produção em risco** |
| **PBVET-196** | BitLab recente devolve HTML nulo, resultados prontos sem conteúdo | Em andamento | **P1 — produção em risco** |
| **PBVET-200** | Nexio pode exibir exame com data futura (data prometida vs. entrega real) | Descoberta | **P2 — dado incorreto** |
| **PBVET-59** | Duplicata do PBVET-60 — fechar como duplicata | Backlog | **Limpeza** |

**Sugestão:** PBVET-60 já está em revisão — validar se o fix do PR recente (#54) realmente fechou o problema. PBVET-196 precisa de atenção urgente antes de qualquer outra coisa.

---

## 🟠 Wave 2 — Platform/Core: dívidas que bloqueiam tudo

Estas dívidas afetam todos os módulos e devem ser resolvidas antes de integração mais profunda.

| Key | Summary | Status | Criticidade | Módulo |
|---|---|---|---|---|
| **PBVET-13** | Remover segredos e fallbacks sensíveis do código e repositório | Pronto pra dev | **P1 — segurança** | Platform |
| **PBVET-36** | Garantir persistência de usuários e parâmetros após novos deploys | Descoberta | **P2 — dado perdido** | Platform |
| **PBVET-47** | Modularizar web/app.py em APIRouters por módulo | Backlog | **P2 — manutenibilidade** | Platform |
| **PBVET-49** | Monitor worker: extrair loop de monitoramento do servidor web | Backlog | **P2 — arquitetura** | Platform |
| **PBVET-46** | RBAC básico: evolução do controle de acesso por papel | Backlog | **P2 — segurança** | Platform |
| **PBVET-15** | Limpar e reorganizar estrutura do projeto e pastas | Backlog | **P3 — devex** | Platform |
| **PBVET-10** | Definir arquitetura de persistência e banco de dados | Pronto pra dev | **P3 — decisão estratégica** | Platform |

> **Nota:** PBVET-10 é uma decisão arquitetural grande (SQLite → PostgreSQL), não apenas uma tarefa. Já há scripts de sync prod→dev. Verificar se a decisão já está tomada na prática (postgres em uso em prod) antes de reabrir o card.

---

## 🟡 Wave 3 — Lab Monitor: dívidas e funcionalidades

| Key | Summary | Status | Criticidade | Tipo |
|---|---|---|---|---|
| **PBVET-43** | Diagnosticar e corrigir fuso horário e datas adiantadas | Descoberta | **P2 — dado incorreto** | Bug/Dívida |
| **PBVET-40** | Corrigir leitura e conclusão do backfill histórico do Nexio | Descoberta | **P2 — funcionalidade** | Bug |
| **PBVET-33** | Documentar e desativar emissor legado de notificações duplicadas | Backlog | **P2 — bug latente** | Limpeza |
| **PBVET-198** | Preservar status informado pelo lab e sinalizar indisponibilidade | Pronto pra dev | **P2 — UX/dados** | Feature |
| **PBVET-199** | Persistir PDFs de contingência localmente com links autenticados | Pronto pra dev | **P3 — funcionalidade** | Feature |
| **PBVET-201** | Separar domínio "plataforma publicadora de laudos" de "lab operacional" | Descoberta | **P3 — modelo de domínio** | Discovery |
| **PBVET-202** | Redefinir papel do status Inconsistente — limitar a contradições reais | Descoberta | **P3 — modelo de domínio** | Discovery |
| **PBVET-41** | Evoluir backfill manual com período e seleção de lab | Descoberta | **P3 — funcionalidade** | Feature |
| **PBVET-42** | Carregamento fragmentado da lista de exames no mobile | Descoberta | **P3 — UX** | Bug/Perf |
| **PBVET-38** | Parametrizar prazo de atraso e notificação diária opcional | Descoberta | **P3 — configurabilidade** | Feature |
| **PBVET-37** | Investigar exames/protocolos abertos há muito tempo | Descoberta | **P3 — dado** | Investigation |
| **PBVET-44** | Avaliar links de labs e exportação completa em PDF | Backlog | **P3 — funcionalidade** | Feature |

---

## 🟡 Wave 4 — Platform Shell: identidade visual e UX unificada

> **Atenção:** Existe triplicata/duplicata de epics aqui. PBVET-100, PBVET-102, PBVET-148 são o mesmo épico "Platform Shell - Identidade visual, Account Menu e Layout unificado". Idem para histórias de Platform Shell em números diferentes.

| Key | Summary | Status | Criticidade | Obs |
|---|---|---|---|---|
| **PBVET-131** | Logo padrão: PinkBlue Vet, avatar rosa, link → / | Pronto pra dev | **P3 — UX** | Duplica PBVET-177 |
| **PBVET-177** | (mesmo) Logo padrão | Em andamento | **P3 — UX** | Versão ativa |
| **PBVET-142** | Lab Monitor UX — header, sidebar, max-width alinhados | Pronto pra dev | **P3 — UX** | Duplica PBVET-188 |
| **PBVET-188** | (mesmo) Lab Monitor UX alinhado | Em andamento | **P3 — UX** | Versão ativa |
| **PBVET-136** | Account menu universal: avatar dropdown em platform_base.html | Descoberta | **P3 — UX** | Duplica PBVET-182 |
| **PBVET-182** | (mesmo) Account menu universal | Descoberta | **P3 — UX** | Versão ativa |

**Ação recomendada antes de executar:** fechar as versões mais antigas (PBVET-100, 102, 131, 142, 136) como duplicatas. Executar apenas as versões ativas.

---

## 🟢 Wave 5 — Plantão: correções bloqueantes e completude

| Key | Summary | Status | Criticidade | Obs |
|---|---|---|---|---|
| **PBVET-103** | Correções bloqueantes: permissões, JS e defaults de formulário | Pronto pra dev | **P2 — funcionalidade** | Duplica PBVET-101 |
| **PBVET-101** | (mesmo) Correções bloqueantes | Pronto pra dev | **P2 — funcionalidade** | Fechar duplicata |
| **PBVET-110** | Renomear Sobreaviso → Disponibilidade em toda a UI | Pronto pra dev | **P3 — UX/vocabulário** | Duplica PBVET-156 |
| **PBVET-108** | Seed de escalas de teste para maio 2026 | Pronto pra dev | **P3 — dados de teste** | Duplica PBVET-154 |
| **PBVET-62** | Épico: Módulo Plantão — Revisão UX e Completude Funcional | Em andamento | **P3 — roadmap** | Versão ativa |
| **PBVET-63** | PLANTAO S1 — Template unificado: sidebar única | Backlog | **P3 — UX** | |
| **PBVET-68** | PLANTAO S2 — Permissões granulares | Backlog | **P3 — funcionalidade** | |
| **PBVET-72** | PLANTAO S3 — Calendário visual com estados e indicadores | Backlog | **P3 — UX** | |
| **PBVET-78** | PLANTAO S4 — Criação de escalas: lote, auto-aprovação, feriados | Backlog | **P3 — funcionalidade** | |
| **PBVET-84** | PLANTAO S5 — Fila unificada de aprovações para o gestor | Backlog | **P3 — funcionalidade** | |
| **PBVET-89** | PLANTAO S6 — Validar fluxo de cadastro com auth unificada | Backlog | **P3 — integração** | |
| **PBVET-94** | PLANTAO S7 — Notificações granulares para todos os eventos | Backlog | **P3 — funcionalidade** | |

---

## 🔵 Wave 6 — Financeiro

| Key | Summary | Status | Criticidade |
|---|---|---|---|
| **PBVET-30** | MVP1 local para fechamento mensal da folha com revisão manual | Em andamento | **P2 — produto** |
| **PBVET-32** | Definir próxima iteração da PoC e casa definitiva do downstream | Backlog | **P3 — decisão** |
| **PBVET-8** | Épico: Financeiro interno e fechamento de folha | Backlog | **P3 — roadmap** |

---

## ⚫ Wave 7 — Infra/DevEx (decisão estratégica pendente)

> Estes cards representam a migração Railway → VPS (Hetzner). Estão "Pronto pra dev" mas é uma decisão grande. **Não executar sem decisão consciente do usuário.**

| Key | Summary | Status | Criticidade |
|---|---|---|---|
| **PBVET-50** | Decisão de infraestrutura: Hetzner CX32 (VPS própria) | Pronto pra dev | **P3 — estratégico** |
| **PBVET-48** | Docker como estratégia de deploy: produção + dev na VPS | Pronto pra dev | **P3 — estratégico** |
| **PBVET-51** | VPS setup base: Hetzner CX32, Docker, Nginx, SSL, code-server | Pronto pra dev | **P3 — estratégico** |
| **PBVET-52** | Migrar app Railway → VPS: Dockerfile, compose, pipeline deploy | Pronto pra dev | **P3 — estratégico** |
| **PBVET-23** | Separação dev/prod: dois ambientes Docker na VPS | Pronto pra dev | **P3 — estratégico** |
| **PBVET-54** | Configurar backup automático do PostgreSQL de produção | Backlog | **P2 — infra** |
| **PBVET-55** | Remover volume Railway /data após confirmação do Postgres | Backlog | **P3 — limpeza** |

---

## ✅ Limpeza executada em 2026-04-17

## 🧹 Limpeza urgente recomendada (antes de qualquer wave)

### Cards duplicados para fechar
| Fechar | Manter | Motivo |
|---|---|---|
| PBVET-59 | PBVET-60 | Mesmo bug de notificação |
| PBVET-61 | PBVET-62 | Mesmo épico Plantão UX |
| PBVET-100, 102 | PBVET-148 | Mesmo épico Platform Shell |
| PBVET-101 | PBVET-103 | Mesma história correções bloqueantes |
| PBVET-156 | PBVET-110 | Mesma história renomear Sobreaviso |
| PBVET-154 | PBVET-108 | Mesma história seed escalas |
| PBVET-188 | PBVET-142 ou fechar ambos | Lab Monitor UX — verificar qual avançou mais |
| PBVET-177 | PBVET-131 ou fechar ambos | Logo padrão — verificar qual avançou mais |
| PBVET-136 | PBVET-182 | Account menu |

### Cards "Em andamento" sem progresso visível
Verificar se há `[CLAIM]` ativo e se a sessão está realmente em curso:
- PBVET-27, PBVET-24, PBVET-22 (Platform — parecem abandonados)
- PBVET-30 (Financeiro MVP1 — checar progresso)

---

## Sequência recomendada de execução

```
Wave 1: PBVET-196 → PBVET-60 (validar) → PBVET-200
Wave 2: PBVET-13 → PBVET-36 → PBVET-47 → PBVET-49
Wave 3: PBVET-43 → PBVET-40 → PBVET-33 → PBVET-198
Wave 4: (após limpeza de duplicatas) PBVET-177/142 → PBVET-182
Wave 5: PBVET-103 → PBVET-110 → PBVET-108 → PBVET-63..94
Wave 6: PBVET-30 (financeiro)
Wave 7: Decisão VPS antes de qualquer execução
```

---

## Cards que precisam de discovery antes de execução

| Key | Por quê |
|---|---|
| PBVET-201/202 | Decisão de modelo de domínio — impacta todo Lab Monitor |
| PBVET-10 | Arquitetura de persistência — decisão já tomada na prática? |
| PBVET-47 | Modularizar app.py — escopo grande, needs spike |
| PBVET-50-52 | Migração VPS — decisão estratégica, não apenas técnica |
| PBVET-46 | RBAC — escopo mal definido |

---

## PBINC — Situação

| Cluster | Cards | Situação |
|---|---|---|
| Plantão (PBINC-25, 36-57) | 22 cards | Backlog de implementação — parte já migrou para PBVET. Verificar sobreposição |
| CRM (PBINC-2, 5, 35) | 3 cards | Incubação, sem execução |
| Automação atendimento (PBINC-3, 6, 57) | 3 cards | Incubação |
| AI/Workers/Infra (PBINC-7-11, 12-23) | 13 cards | Exploração/Validação — não bloqueia nada agora |
| Hardware pessoal (PBINC-58, 59) | 2 cards | Off-topic do produto |
