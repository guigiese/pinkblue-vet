# Relatório de Teste Completo — PKG-FULL-COMPLETO
**Data:** 2026-04-19  
**Branch:** `session/20260417-7395`  
**Ambiente:** DEV local PostgreSQL (`pinkblue_dev`) + dados de produção sincronizados  
**Executor:** Claude Sonnet 4.6 (AI Testing Agent)  
**Protocolo:** PKG-FULL-COMPLETO + foco especial em permissionamento

---

## Resumo Executivo

Foram testados todos os fluxos principais da plataforma: login, cadastro, módulo Plantão (gestor, veterinário e auxiliar), módulo Lab Monitor, sistema de admin/permissões/perfis, dev switcher e plataforma home. Foram identificados **5 bugs funcionais confirmados**, **7 issues de UX/design prioritários**, **4 issues de sistema de permissões** e **7 dívidas arquiteturais** pré-existentes.

| Categoria | Qtd | Prioridade máxima |
|---|---|---|
| Bugs funcionais | 5 | P1: 2 bugs de feedback perdido |
| UX / Design | 7 | P2: aux vê botão indevido |
| Sistema de permissões | 4 | P2: operator sem acesso a admin |
| Arquitetura | 7 | P3-P4: lab monitor desalinhado |

---

## 1. Bugs Funcionais Confirmados

### BUG-01 — Feedback de cancelamento de candidatura perdido [P1]
**Módulo:** Plantão  
**Path:** `POST /plantao/candidaturas/{id}/cancelar`  
**Arquivo:** `modules/plantao/router.py`

**Comportamento atual:**  
Ao cancelar candidatura, o redirect vai para `/plantao/meus-turnos?ok=1`. A rota `/plantao/meus-turnos` é uma rota de compatibilidade que faz 302 para `/plantao/escalas` — **sem preservar query params**. O toast de sucesso nunca aparece.

**Comportamento esperado:**  
Redirect direto para `/plantao/escalas?ok=cancelado` (ou equivalente), com toast visível.

**Causa raiz:**  
O router usa a rota antiga como destino do redirect. A rota de compat não repassa query params.

**Correção:**  
Substituir `RedirectResponse(url="/plantao/meus-turnos?ok=1")` por `RedirectResponse(url="/plantao/escalas?ok=cancelado")` no handler de cancelamento.

---

### BUG-02 — Feedback de troca/substituição perdido [P1]
**Módulo:** Plantão  
**Path:** `POST /plantao/trocas/...` e `POST /plantao/substituicoes/...`  
**Arquivo:** `modules/plantao/router.py`

**Comportamento atual:**  
Redirects pós-troca apontam para `/plantao/trocas?ok=1` ou `/plantao/trocas?erro=...`. A rota `/plantao/trocas` faz 302 para `/plantao/escalas` sem preservar query params. Mensagens de sucesso e erro são perdidas.

**Comportamento esperado:**  
Redirect direto para `/plantao/escalas?ok=troca` ou `?erro=...` com exibição de feedback.

**Causa raiz:**  
Mesma causa do BUG-01: rotas de compat não repassam query params.

**Correção:**  
Atualizar todos os `RedirectResponse` em handlers de troca/substituição para apontar para `/plantao/escalas` diretamente, com parâmetros de feedback adequados.

---

### BUG-03 — Botão "Aderir" visível para auxiliar em disponibilidade [P2]
**Módulo:** Plantão  
**Path:** `GET /plantao/disponibilidade`  
**Arquivo:** `modules/plantao/templates/plantao_disponibilidade.html`

**Comportamento atual:**  
O auxiliar vê o botão "Aderir" na página de disponibilidade. O backend bloqueia corretamente (resposta de erro ao POST), mas o botão **não deveria aparecer na UI**.

**Comportamento esperado:**  
Para usuários com role `auxiliar`, o botão "Aderir" deve ser oculto. A disponibilidade é exclusiva para veterinários.

**Causa raiz:**  
O template não verifica `user.role` ou permissão antes de exibir o botão.

**Correção:**  
Adicionar condicional `{% if user.role != 'auxiliar' %}` em torno do botão Aderir no template.

---

### BUG-04 — `valor_base_calculado` NULL silencioso [P2]
**Módulo:** Plantão  
**Path:** Criação de candidatura / aprovação  
**Arquivo:** `modules/plantao/business.py` — `calcular_valor_base()`

**Comportamento atual:**  
Quando nenhuma tarifa corresponde ao tipo do perfil do veterinário, `calcular_valor_base()` retorna `(None, None)`. A candidatura é criada/aprovada com valor NULL sem qualquer alerta ao gestor.

**Comportamento esperado:**  
Ao aprovar candidatura com valor NULL, o sistema deve exibir um aviso ao gestor: "Nenhuma tarifa encontrada para este perfil. Verifique as configurações de tarifas."

**Correção:**  
Na aprovação, verificar se `valor_base_calculado` é None e retornar warning visível na UI; considerar bloquear aprovação ou exigir confirmação explícita.

---

### BUG-05 — `/plantao/api/disponibilidade-ativa` retorna 403 para todos usuários autenticados [P3]
**Módulo:** Plantão  
**Path:** `GET /plantao/api/disponibilidade-ativa`

**Comportamento atual:**  
Retorna 403 mesmo para usuários autenticados com `manage_plantao`. Requer API key via header `X-API-Key` que não está configurada no ambiente local.

**Comportamento esperado:**  
Para uso interno (dentro da plataforma), deveria autenticar via sessão; para uso externo, via API key.

**Causa raiz:**  
O endpoint só aceita API key, não session-based auth.

**Correção:**  
Aceitar autenticação por sessão (usuários com `manage_plantao`) OU por API key; ou documentar claramente que é endpoint externo e configurar a API key no `.env`.

---

## 2. Sistema de Permissões e Perfis

Esta seção responde diretamente às dúvidas do usuário sobre "perfis deveriam ter mais detalhes", "perfil padrão que não entendo pra que existe" e "quem tem acesso de Vet vs Auxiliar".

### PER-01 — `operator` (gestor) não tem acesso a `/admin/usuarios` [P2]

**Situação atual:**  
`manage_users: False` para o role `operator` (`DEFAULT_ROLE_PERMISSIONS` em `pb_platform/storage.py:47`). Quando um gestor acessa `/admin/usuarios`, é redirecionado para `/plantao/admin/` sem mensagem explicativa.

**Impacto:**  
O gestor não pode criar usuários, atribuir perfis nem gerenciar acessos. Apenas role `admin` (guigiese@gmail.com) tem acesso total ao admin.

**Pergunta ao usuário:**  
O gestor de plantão deveria poder gerenciar usuários? Se sim, definir `manage_users: True` para `operator`.

---

### PER-02 — "Perfis padrão de sistema" — o que são e por que existem

**Situação atual:**  
Existem 5 "perfis padrão de sistema" (`is_system=1`):
- **Administrador** — todos as permissões
- **Veterinário Plantonista** — `plantao_access`
- **Auxiliar Veterinário** — `plantao_access`
- **Operador** — `labmonitor + plantao gerência`
- **Colaborador** — sem permissões

**O que são:**  
São "templates" de conjunto de permissões vinculados aos roles padrão do sistema. Servem como referência para criação de perfis customizados.

**Por que o usuário não entende:**  
- Aparecem misturados com perfis customizados na UI sem separação clara
- Não podem ser excluídos (is_system=1) mas não há explicação disso na interface
- A diferença entre **role** (papel de negócio) e **perfil** (conjunto de permissões customizado) não está explicada em lugar nenhum

**Recomendação UX:**  
1. Separar visualmente na UI: seção "Perfis padrão (sistema)" vs "Perfis customizados"
2. Adicionar tooltip/help: "Perfis padrão definem as permissões padrão de cada papel. Crie perfis customizados para casos especiais."
3. Desabilitar edição/exclusão de perfis de sistema com indicador visual claro

---

### PER-03 — Perfis customizados não expõem permissões granulares de Plantão [P3]

**Situação atual:**  
O editor de perfis em `/admin/perfis` mostra 7 checkboxes de permissão, faltando:
- `plantao_gerir_escalas`
- `plantao_aprovar_candidaturas`
- `plantao_aprovar_cadastros`
- `plantao_ver_relatorios`
- `manage_labmonitor_labs`
- `manage_labmonitor_settings`

**Impacto:**  
Não é possível criar um perfil que dê apenas acesso ao relatório de Plantão sem dar `manage_plantao` completo. A granularidade existe no sistema mas é inacessível via UI.

**Arquivo:** `web/templates/admin_profiles.html` e `web/routers/admin.py`

**Correção:**  
Adicionar os 6 checkboxes faltantes no editor de perfis, agrupados por módulo.

---

### PER-04 — Não há explicação de precedência role vs perfil na tela de usuário [P3]

**Situação atual:**  
Em `/admin/usuarios`, o admin vê dois seletores: `role` e `perfil`. Não há indicação de qual tem precedência, o que acontece quando ambos estão preenchidos, ou como as permissões resultantes são calculadas.

**Recomendação:**  
Adicionar preview de permissões efetivas (calculado dinamicamente ao mudar role/perfil) e texto explicativo: "O perfil, quando atribuído, sobrepõe as permissões padrão do papel."

---

## 3. Issues de UX / Design

### UX-01 — Dev switcher retorna JSON bruto em vez de UI [P2]

**Situação atual:**  
`GET /dev/switch-user` retorna um array JSON com todos os usuários. Sem o contexto Alpine.js da plataforma (e.g., ao acessar direto no browser), exibe texto JSON sem formatação.

**Impacto:**  
O switcher só funciona corretamente dentro da plataforma com JavaScript habilitado. Se JS falhar, a funcionalidade é perdida completamente.

**Recomendação:**  
Retornar HTML quando `Accept: text/html` e JSON quando `Accept: application/json`. Isso garante graceful degradation.

---

### UX-02 — Login: mensagem de erro sem container estilizado [P3]

**Situação atual:**  
Ao errar credenciais, o texto "Credenciais inválidas" é exibido mas sem um container visual consistente (sem card de erro, sem ícone, sem cor de destaque definida via Tailwind). O texto aparece embutido no template sem separação clara.

**Recomendação:**  
Usar o padrão de alert/flash já estabelecido no sistema para erros de login. Adicionar `aria-live="assertive"` para acessibilidade.

---

### UX-03 — Cadastro: campo CRMV visível para todos os roles [P3]

**Situação atual:**  
Em `/cadastro`, o campo `crmv` aparece para todos independente do role selecionado. Apenas veterinários precisam de CRMV.

**Recomendação:**  
Exibir o campo CRMV condicionalmente com Alpine.js: visível apenas quando `role === 'veterinario'`.

---

### UX-04 — Escalas: URL não atualiza ao navegar entre meses [P3]

**Situação atual:**  
A navegação entre meses em `/plantao/escalas` é feita via Alpine.js sem atualizar a URL. O usuário não pode compartilhar um link para um mês específico ou usar o botão voltar do browser.

**Recomendação:**  
Usar `history.pushState()` ao navegar entre meses, atualizando o query param `?mes=2026-05`.

---

### UX-05 — Página de escalas sem `<h1>` [P4]

**Situação atual:**  
`/plantao/escalas` não tem elemento `<h1>`. Prejudica acessibilidade e SEO.

**Correção:**  
Adicionar `<h1>Escalas de Plantão</h1>` visualmente adequado ao layout.

---

### UX-06 — Lab Monitor: links de exames apontam para site externo do laboratório [P2]

**Situação atual:**  
Em `/labmonitor/exames`, os links de laudos apontam diretamente para `https://bitlabenterprise.com.br/...` e `https://www.pathoweb.com.br`. O usuário mencionou que "os links ainda apontam para a plataforma do laboratório e não pro nosso ambiente".

**Esclarecimento técnico:**  
O Lab Monitor **captura snapshots** dos resultados de exames mas **não faz proxy de PDF**. O PDF continua hospedado no site do laboratório externo.

**Opções:**
1. **Download e re-hospedagem** (alta complexidade): baixar PDFs e servir via `/labmonitor/laudos/{id}.pdf`
2. **Proxy transparente** (média complexidade): `GET /labmonitor/laudos/{id}` faz streaming do PDF externo
3. **Status quo documentado** (zero complexidade): adicionar tooltip explicando que o link abre o site do laboratório

**Recomendação imediata:**  
Adicionar ícone externo (`↗`) nos links e tooltip "Abre o site do laboratório" para que o usuário saiba que vai sair da plataforma.

---

### UX-07 — Platform home mostra todos os módulos para usuários de role externo [P4]

**Situação atual:**  
A platform home `/` mostra "Biblioteca de módulos" incluindo Lab Monitor e Plantão. Para veterinários e auxiliares, que só têm acesso a Plantão, ver o card do Lab Monitor (sem acesso) pode causar confusão.

**Recomendação:**  
Filtrar os módulos exibidos na home com base nas permissões do usuário. Ou redirecionar usuários externos diretamente para seu módulo (já parcialmente implementado via `preferred_redirect_for_user`).

---

## 4. Resultados de Teste por Área

### 4.1 — Autenticação e Cadastro

| Teste | Resultado |
|---|---|
| Login com credenciais válidas (gestor, vet, vet2, aux) | ✅ PASSA |
| Login com usuário pendente/inativo | ✅ Bloqueado corretamente |
| Login com credenciais inválidas — mensagem de erro | ✅ Mostra "inválidos" |
| CSRF token presente no form de login | ✅ Presente |
| Formulário de cadastro (`/cadastro`) — campos | ✅ nome, email, crmv, telefone, password, role |
| Cadastro de usuário com role auxiliar (CRMV desnecessário) | ⚠️ Campo CRMV exibido (UX-03) |

### 4.2 — Plantão: Fluxos E2E

| Teste | Resultado |
|---|---|
| Gestor: criar data de plantão (presencial) | ✅ PASSA |
| Gestor: publicar data de plantão | ✅ PASSA |
| Vet: candidatar-se a posição | ✅ PASSA |
| Gestor: aprovar candidatura | ✅ PASSA |
| Vet: cancelar candidatura — feedback visual | ❌ BUG-01: feedback perdido |
| Gestor: troca direta entre candidatos | ✅ Ação OK, feedback perdido (BUG-02) |
| Vet: aderir à disponibilidade | ✅ PASSA |
| Aux: tentar aderir à disponibilidade (backend) | ✅ Bloqueado corretamente |
| Aux: botão "Aderir" visível na UI | ❌ BUG-03: botão visível indevidamente |
| Gestor: criar tarifa | ✅ PASSA |
| Gestor: criar feriado | ✅ PASSA |
| Gestor: configurar local | ✅ PASSA |
| Gestor: ver relatórios | ✅ Renderiza com dados |
| Gestor: audit log | ✅ Renderiza |
| API: fechamento de escala | ✅ 200 OK |
| API: disponibilidade-ativa | ❌ BUG-05: 403 para todos |

### 4.3 — Plantão: Permissões por Role

| Ação | Admin | Operator | Vet | Aux | Viewer |
|---|---|---|---|---|---|
| Ver escalas publicadas | ✅ | ✅ | ✅ | ✅ | ❌ (303) |
| Candidatar-se | ✅ | ✅ | ✅ | ✅ | ❌ |
| Aderir à disponibilidade | ✅ | ✅ | ✅ | ❌ (backend) | ❌ |
| Gerir escalas (admin panel) | ✅ | ✅ | ❌ (303) | ❌ (303) | ❌ (303) |
| Aprovar candidaturas | ✅ | ✅ | ❌ | ❌ | ❌ |
| Ver relatórios | ✅ | ✅ | ❌ | ❌ | ❌ |

### 4.4 — Lab Monitor

| Teste | Resultado |
|---|---|
| Dashboard `/labmonitor` | ✅ 200 OK, conteúdo (57KB) |
| Exames `/labmonitor/exames` | ✅ 200 OK, dados (756KB — página pesada) |
| Labs `/labmonitor/labs` | ✅ 200 OK |
| Canais `/labmonitor/canais` | ✅ 200 OK |
| Notificações `/labmonitor/notificacoes` | ✅ 200 OK |
| Tolerâncias `/labmonitor/tolerancias` | ✅ 200 OK |
| Settings `/labmonitor/settings` | ✅ 200 OK |
| Deep links externos (BitLab) | ⚠️ Apontam para site externo (UX-06) |
| PDFs de laudos hospedados localmente | ❌ Não existe — apenas link externo |
| Acesso de viewer a pages admin | ✅ Bloqueado (303) |
| Acesso de vet a lab monitor | ✅ Bloqueado (303) |

### 4.5 — Admin / Permissões / Perfis

| Teste | Resultado |
|---|---|
| Admin `/admin/usuarios` (role admin) | ✅ 200 OK, mostra usuários |
| Admin `/admin/usuarios` (role operator) | ❌ PER-01: redirect para `/plantao/admin/` |
| Admin `/admin/perfis` — criar perfil | ✅ Formulário disponível |
| Admin `/admin/perfis` — permissões granulares Plantão | ❌ PER-03: sub-permissões ausentes |
| Explicação role vs perfil na UI | ❌ PER-04: ausente |
| Perfis padrão de sistema separados visualmente | ❌ PER-02: misturados com customizados |
| GET `/admin/permissoes` (customização por role) | ❌ Rota não existe — apenas POST |

### 4.6 — Plataforma / Navegação

| Teste | Resultado |
|---|---|
| Platform home `/` (admin) | ✅ "Biblioteca de módulos" com links |
| Platform home (vet) | ⚠️ UX-07: mostra módulos sem acesso |
| Dev switcher `/dev/switch-user` | ✅ Funcional (retorna JSON) |
| Dev switcher — UI sem JavaScript | ❌ UX-01: exibe JSON bruto |
| Compat redirect `/plantao/meus-turnos` → `/plantao/escalas` | ✅ 302 (sem preservar query params) |
| Compat redirect `/plantao/trocas` → `/plantao/escalas` | ✅ 302 (sem preservar query params) |
| Badge DEV visível | ✅ Confirmado |

---

## 5. Dívidas Arquiteturais (já documentadas — sem regressão)

Documentadas nas issues OA-1 a OA-7 no plano de sessão. Não são novos bugs, são limitações de design conhecidas:

| ID | Descrição | Impacto |
|---|---|---|
| OA-1 | `core.py` na raiz (deveria estar em `modules/lab_monitor/`) | Baixo |
| OA-2 | Router Lab Monitor em `web/` (deveria estar em `modules/`) | Baixo |
| OA-3 | Tabelas Lab Monitor em `pb_platform/storage.py` | Alto |
| OA-4 | Path→permission hardcoded em `auth.py` | Médio |
| OA-5 | Dois ambientes Jinja2 separados | Médio |
| OA-6 | `app_kv` sem namespacing formal por módulo | Baixo |
| OA-7 | Zero testes para módulo Plantão | Alto |

---

## 6. Priorização de Correções

### P1 — Corrigir imediatamente (antes do próximo deploy)
- **BUG-01**: Redirect pós-cancelamento para rota antiga → feedback perdido
- **BUG-02**: Redirects pós-troca para rota antiga → feedback perdido

### P2 — Corrigir nesta sprint
- **BUG-03**: Botão "Aderir" visível para auxiliar
- **PER-01**: Operator sem acesso a `/admin/usuarios` (decisão: dar ou não `manage_users` ao operator)
- **PER-02**: Perfis padrão de sistema confusos na UI — separar visualmente e explicar
- **UX-01**: Dev switcher retorna JSON bruto
- **UX-06**: Labmonitor links externos — pelo menos adicionar indicação visual (↗)

### P3 — Próxima sprint / backlog prioritário
- **BUG-04**: Valor base NULL silencioso
- **BUG-05**: API disponibilidade-ativa inacessível
- **PER-03**: Permissões granulares ausentes no editor de perfis
- **PER-04**: Ausência de preview de permissões efetivas
- **UX-02**: Container estilizado para erro de login
- **UX-03**: Campo CRMV sempre visível no cadastro
- **UX-04**: URL não atualiza na navegação entre meses
- **OA-7**: Criar testes para módulo Plantão

### P4 — Backlog técnico
- **UX-05**: `<h1>` ausente em /plantao/escalas
- **UX-07**: Platform home mostra módulos sem acesso para users externos
- **OA-1 a OA-6**: Reorganização arquitetural Lab Monitor

---

## 7. Ambiente de Teste

```
Branch: session/20260417-7395
PostgreSQL: pinkblue_dev @ localhost:5432
Schema head: a3b7c9d1e2f4 (rename sobreaviso→disponibilidade)
Usuários de teste:
  - test.admin@pinkbluevet.local / PlantaoDev@123 (admin)
  - gestor.plantao.dev@pinkbluevet.local / PlantaoDev@123 (operator)
  - veterinaria.dev@pinkbluevet.local / PlantaoDev@123 (veterinario)
  - veterinaria.espera.dev@pinkbluevet.local / PlantaoDev@123 (veterinario)
  - auxiliar.dev@pinkbluevet.local / PlantaoDev@123 (auxiliar)
Escalas: 22 escalas em maio 2026 (6 rascunho, 16 publicadas)
```

---

*Gerado automaticamente por AI Testing Agent em 2026-04-19*
