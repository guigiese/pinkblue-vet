# Mapeamento de Testes — Plataforma Completa
**Data:** 2026-04-19  
**Branch:** session/20260417-7395 (sobre main, apenas docs)  
**Ambiente:** Local — PostgreSQL localhost:5432/pinkblue_dev  
**Gerado por:** AI (claude-sonnet-4-6) seguindo AI_TESTING_STANDARD.md  

---

## 1. SUPERFÍCIES E ARTEFATOS (ART)

| ID | Artefato | Localização |
|----|----------|-------------|
| ART-01 | Plataforma — Login / Logout / Cadastro | `/login`, `/logout`, `/cadastro` |
| ART-02 | Plataforma — Landing (home) | `/` |
| ART-03 | Plataforma — Admin de Usuários | `/admin/usuarios`, `/admin/perfis` |
| ART-04 | Lab Monitor — Dashboard | `/labmonitor` |
| ART-05 | Lab Monitor — Exames | `/labmonitor/exames` |
| ART-06 | Lab Monitor — Laboratórios | `/labmonitor/labs` |
| ART-07 | Lab Monitor — Canais | `/labmonitor/canais` |
| ART-08 | Lab Monitor — Notificações | `/labmonitor/notificacoes` |
| ART-09 | Lab Monitor — Tolerâncias | `/labmonitor/tolerancias` |
| ART-10 | Lab Monitor — Configurações | `/labmonitor/settings` |
| ART-11 | Lab Monitor — Partials HTMX | `/labmonitor/partials/*` |
| ART-12 | Plantão — Landing (role-aware) | `/plantao/` |
| ART-13 | Plantão — Escalas (view unificado) | `/plantao/escalas` |
| ART-14 | Plantão — Disponibilidade (plantonista) | `/plantao/disponibilidade` |
| ART-15 | Plantão — Notificações (plantonista) | `/plantao/notificacoes` |
| ART-16 | Plantão — Perfil (plantonista) | `/plantao/perfil` |
| ART-17 | Plantão Admin — Dashboard | `/plantao/admin` |
| ART-18 | Plantão Admin — Cadastros | `/plantao/admin/cadastros` |
| ART-19 | Plantão Admin — Escalas (gestão) | integrado em `/plantao/escalas` |
| ART-20 | Plantão Admin — Aprovações | `/plantao/admin/aprovacoes` |
| ART-21 | Plantão Admin — Candidaturas | `/plantao/admin/candidaturas` |
| ART-22 | Plantão Admin — Disponibilidade | `/plantao/admin/disponibilidade` |
| ART-23 | Plantão Admin — Locais | `/plantao/admin/locais` |
| ART-24 | Plantão Admin — Tarifas | `/plantao/admin/tarifas` |
| ART-25 | Plantão Admin — Feriados | `/plantao/admin/feriados` |
| ART-26 | Plantão Admin — Configurações | `/plantao/admin/configuracoes` |
| ART-27 | Plantão Admin — Relatórios | `/plantao/admin/relatorios/*` |
| ART-28 | Plantão Admin — Audit Log | `/plantao/admin/audit-log` |
| ART-29 | Dev Switcher | Badge âmbar `/dev/switch-user` |
| ART-30 | Ops Map | `/ops-map/` |
| ART-31 | API Plantão — Fechamento | `/plantao/api/fechamento` |
| ART-32 | API Plantão — Disponibilidade Ativa | `/plantao/api/disponibilidade-ativa` |

---

## 2. PERFIS (PER)

| ID | Perfil | Email (dev) | Senha | Permissões-chave |
|----|--------|-------------|-------|-----------------|
| PER-01 | Admin / Master | guigiese@gmail.com | (prod) | tudo |
| PER-02 | Gestor de Plantão | gestor.plantao.dev@pinkbluevet.local | PlantaoDev@123 | manage_plantao + todas as sub-perms |
| PER-03 | Veterinária confirmada | veterinaria.dev@pinkbluevet.local | PlantaoDev@123 | plantao_access |
| PER-04 | Veterinária em espera | veterinaria.espera.dev@pinkbluevet.local | PlantaoDev@123 | plantao_access |
| PER-05 | Auxiliar | auxiliar.dev@pinkbluevet.local | PlantaoDev@123 | plantao_access |
| PER-06 | Cadastro pendente | cadastro.pendente.dev@pinkbluevet.local | PlantaoDev@123 | nenhuma (status=pendente) |
| PER-07 | Viewer (sem Plantão) | piper.melanie@gmail.com | (prod) | labmonitor_access |

---

## 3. DISPOSITIVOS / CONTEXTOS (DIS)

| ID | Contexto |
|----|----------|
| DIS-01 | Desktop Chrome — janela larga (≥1280px) |
| DIS-02 | Desktop simulando tablet (768px) |
| DIS-03 | Desktop simulando mobile (375px) |

---

## 4. TIPOS DE TESTE (TIP)

| ID | Tipo |
|----|------|
| TIP-01 | Funcional — fluxo happy path |
| TIP-02 | Funcional — fluxo negativo / validação |
| TIP-03 | Visual — layout, cores, responsividade |
| TIP-04 | Permissões — acesso indevido / bloqueio correto |
| TIP-05 | Integração — HTMX partials, auto-refresh |
| TIP-06 | Integração — links externos (labs) |
| TIP-07 | Arquitetura — separação plataforma/módulos |
| TIP-08 | UX — consistência, feedback, estados vazios |

---

## 5. FLUXOS FIM-A-FIM (FLX)

### Plataforma

| ID | Fluxo |
|----|-------|
| FLX-01 | Novo usuário → se cadastra → aguarda aprovação → gestor aprova → login funcionando |
| FLX-02 | Login com erro (senha errada, conta pendente, rejeitada) → mensagens corretas |
| FLX-03 | Admin cria usuário diretamente → atribui role → habilita/desabilita |
| FLX-04 | Redirecionamento pós-login por role (labmonitor→dashboard, plantao→plantão, ambos→home) |
| FLX-05 | Dev switcher: trocar entre perfis e validar que cada um vê o que deve |

### Lab Monitor

| ID | Fluxo |
|----|-------|
| FLX-10 | Acesso ao dashboard → auto-refresh 60s → lab_counts e ultimos_liberados atualizam |
| FLX-11 | Exames → filtros (lab, status, busca texto) → resultados corretos |
| FLX-12 | Exames → resultado inline BitLab → expand → rows numéricas carregam via HTMX |
| FLX-13 | Exames → laudo texto → modal abre com diagnóstico + seções |
| FLX-14 | Exames → histórico de paciente → filtra por nome → painel lateral abre |
| FLX-15 | Exames → deep link → aponta para URL correta (bitlabenterprise / pathoweb) |
| FLX-16 | Labs → toggle habilita/desabilita → estado persiste |
| FLX-17 | Labs → test connection → retorna status correto |
| FLX-18 | Canais → toggle Telegram → test envia mensagem |
| FLX-19 | Canais → listar assinantes Telegram → remover assinante |
| FLX-20 | Notificações → editar template → salvar → resetar para padrão |
| FLX-21 | Tolerâncias → criar regra de exame → editar → excluir |
| FLX-22 | Configurações → alterar intervalo → salvar |
| FLX-23 | Labs → histórico manual → dispara backfill |

### Plantão — Gestor

| ID | Fluxo |
|----|-------|
| FLX-30 | Gestor cria escala única → publicar → aparece para plantonistas |
| FLX-31 | Gestor cria lote de escalas (range de datas + dias da semana) |
| FLX-32 | Gestor cancela escala publicada → notificações enviadas aos confirmados |
| FLX-33 | Gestor abre painel de criação → preenche → fecha sem salvar → estado limpo |
| FLX-34 | Gestor vê candidatura pendente → aprova individualmente |
| FLX-35 | Gestor vê candidatura pendente → rejeita com motivo |
| FLX-36 | Gestor faz aprovação em lote (múltiplas candidaturas) |
| FLX-37 | Gestor acessa relatório de escalas por período |
| FLX-38 | Gestor acessa relatório de participação por plantonista |
| FLX-39 | Gestor acessa relatório de cancelamentos/trocas |
| FLX-40 | Gestor acessa relatório de pré-fechamento (com valores) |
| FLX-41 | Gestor cria local → aparece na lista e nos selects de escala |
| FLX-42 | Gestor cria tarifa → aparece na lista de tarifas |
| FLX-43 | Gestor cria feriado → aparece na lista |
| FLX-44 | Gestor salva configurações de prazo e limites |
| FLX-45 | Gestor aprova cadastro de plantonista |
| FLX-46 | Gestor rejeita cadastro e desativa plantonista |
| FLX-47 | Gestor reordena lista de disponibilidade |
| FLX-48 | API `/plantao/api/fechamento` retorna JSON correto |

### Plantão — Veterinário

| ID | Fluxo |
|----|-------|
| FLX-50 | Vet vê landing com próximos turnos confirmados |
| FLX-51 | Vet vê escalas publicadas (não vê rascunhos) |
| FLX-52 | Vet se candidata a escala disponível → status provisório |
| FLX-53 | Vet tenta se candidatar a escala já cheia → entra na lista de espera |
| FLX-54 | Vet cancela candidatura dentro do prazo → sucesso |
| FLX-55 | Vet tenta cancelar candidatura fora do prazo → bloqueado com mensagem |
| FLX-56 | Vet solicita troca direta com outro vet |
| FLX-57 | Vet recebe solicitação de troca → aceita → turnos trocados |
| FLX-58 | Vet recebe solicitação de troca → recusa |
| FLX-59 | Vet abre substituição → notificação para outros vets |
| FLX-60 | Outro vet aceita substituição |
| FLX-61 | Vet adere à disponibilidade → aparece na fila por prioridade |
| FLX-62 | Vet cancela disponibilidade → fila reordenada |
| FLX-63 | Vet atualiza perfil (nome, telefone) |
| FLX-64 | Vet altera senha |
| FLX-65 | Vet lê notificações → marca como lida → marca todas como lidas |

### Plantão — Auxiliar

| ID | Fluxo |
|----|-------|
| FLX-70 | Auxiliar vê apenas posições de tipo auxiliar |
| FLX-71 | Auxiliar se candidata → confirma → vê turno |
| FLX-72 | Auxiliar NÃO consegue aderir à disponibilidade (somente vets) |
| FLX-73 | Auxiliar NÃO vê opções de troca com veterinários |

---

## 6. CENÁRIOS (CEN) — Negativos e Bordas

| ID | Cenário |
|----|---------|
| CEN-01 | Acessar `/plantao/admin` sem permissão → redirect ou 403 |
| CEN-02 | Acessar `/admin/usuarios` como veterinário → bloqueado |
| CEN-03 | Acessar `/labmonitor` como auxiliar (sem labmonitor_access) → bloqueado |
| CEN-04 | Candidatura duplicada no mesmo dia → bloqueada com mensagem |
| CEN-05 | Troca entre usuários de tipos diferentes (vet↔aux) → bloqueada |
| CEN-06 | Cancelamento de troca já expirada → estado correto |
| CEN-07 | Criar escala com data no passado → validação |
| CEN-08 | Criar tarifa com vigente_ate < vigente_de → validação |
| CEN-09 | Candidatura em escala cancelada → não deveria ser possível |
| CEN-10 | Login com usuário pendente → mensagem "aguardando aprovação" |
| CEN-11 | Login com usuário rejeitado → mensagem correta |
| CEN-12 | Registro com CRMV ausente para veterinário → validação |
| CEN-13 | Senhas não coincidem no cadastro → validação |
| CEN-14 | Intervalo de sync < 1 ou > 60 → validação |
| CEN-15 | Tolerância < 100% → validação |
| CEN-16 | Relatório com data_fim < data_inicio → resultado vazio ou erro |

---

## 7. EXPLORAÇÃO GUIADA (EXP)

| ID | Exploração |
|----|------------|
| EXP-01 | **Shell visual:** Navegar por todos os módulos e avaliar consistência do header, sidebar, footer, breadcrumbs, estados ativos de nav |
| EXP-02 | **Estados vazios:** Acessar cada tela com dados zerados e avaliar mensagens de empty state |
| EXP-03 | **Feedback de ações:** Disparar cada POST/ação e avaliar mensagem de sucesso/erro |
| EXP-04 | **Mobile:** Simular 375px em cada tela principal e avaliar layout |
| EXP-05 | **Links externos Lab Monitor:** Clicar em cada deep link de exame e verificar para onde aponta |
| EXP-06 | **Painel flutuante Escalas:** Abrir, fechar com X, fechar com Escape, fechar clicando no overlay |
| EXP-07 | **Notificações Plantão:** Badge de contagem, lista, marcar como lida, limpar todas |
| EXP-08 | **Dev Switcher:** Trocar entre todos os perfis e validar que o contexto muda corretamente |
| EXP-09 | **Redirects de compatibilidade:** Acessar URLs antigas (sobreaviso, meus-turnos, etc.) e confirmar redirect |

---

## 8. REVISÃO VISUAL (VIS)

| ID | Superfície | Pontos a revisar |
|----|------------|-----------------|
| VIS-01 | Header/plataforma | Logo, nome, account menu, badge notificações |
| VIS-02 | Sidebar Lab Monitor | Links ativos, ícones, responsividade |
| VIS-03 | Sidebar Plantão | Links ativos, ícones, separadores de seção, responsividade |
| VIS-04 | Plantão — Escalas | Grid de cards, badges de status, botão candidatar, painel flutuante |
| VIS-05 | Plantão — Landing gestor | KPI cards (cores: amber/red/orange), alertas |
| VIS-06 | Plantão — Landing plantonista | Próximas escalas, meus turnos |
| VIS-07 | Plantão — Tabelas admin | Linhas, badges, ações, paginação |
| VIS-08 | Lab Monitor — Dashboard | Contadores, feed de últimos liberados |
| VIS-09 | Lab Monitor — Exames | Cards mobile vs tabela desktop, expand de resultado |
| VIS-10 | Formulários globais | Inputs, labels, botões primário/secundário/destrutivo |
| VIS-11 | Mensagens de erro/sucesso | Toast, inline, redirect com ?saved= |
| VIS-12 | Tela de login e cadastro | Layout, validações inline |

---

## 9. PROBLEMAS CONHECIDOS (KI)

| ID | Problema | Criticidade | Fonte |
|----|----------|-------------|-------|
| KI-01 | `test_manual_result_fetch_rehydrates_snapshot_item` — `web.app._cache_resultado` removido no refactor | media | baseline testes |
| KI-02 | `test_operational_rules_mark_ready_without_payload_as_inconsistent` — item sem payload marcado `Pronto` em vez de `Inconsistente` | media | baseline testes |
| KI-03 | `test_get_exames_uses_received_at_for_card_date` — diferença de 3h (UTC vs BRT/ZoneInfo) | media | baseline testes |
| KI-04 | Links de exame no Lab Monitor apontam para plataformas externas (bitlabenterprise, pathoweb) por design — PDF não é servido pelo nosso ambiente | baixa (design) | docs/code |
| KI-05 | Nexio deep links requerem sessão ativa no pathoweb — link direto não funciona fora do browser com sessão | baixa (limitação externa) | docs |

---

## 10. LIMITAÇÕES OPERACIONAIS (LIM)

| ID | Limitação |
|----|-----------|
| LIM-01 | Não testar em produção — apenas localhost:8000 |
| LIM-02 | Não mutar dados no SimplesVet/BitLab/Nexio (modo observacional) |
| LIM-03 | Telegram bot não testável sem chat_id ativo — testar apenas UI de gerenciamento |
| LIM-04 | WhatsApp (Callmebot) desabilitado por padrão — não testar |
| LIM-05 | Dados de prod sincronizados — tratar usuários reais com cuidado (não deletar, não rejeitar) |
| LIM-06 | Servidor precisa estar rodando localmente (`start_dev.bat`) antes do run |

---

## 11. RISCOS (RST)

| ID | Risco |
|----|-------|
| RST-01 | Ações de cancelamento de escala notificam usuários reais (usar apenas usuários .local) |
| RST-02 | API `/plantao/api/fechamento` exposta sem autenticação de sessão (apenas API key) — verificar se key está configurada |
| RST-03 | Criação em lote de escalas pode gerar muitas entradas — testar com range pequeno (1 semana) |

---

## 12. PACOTES DE EXECUÇÃO SUGERIDOS

### PKG-ARCH — Arquitetura e Separação
Verificação estática e de navegação sobre a separação plataforma/módulos.
- EXP-09 (redirects de compatibilidade)
- CEN-01, CEN-02, CEN-03 (permissões cross-módulo)
- EXP-08 (dev switcher entre perfis)
- FLX-04 (redirect pós-login por role)
- TIP-07

### PKG-AUTH — Autenticação e Cadastro
- FLX-01 (cadastro completo → aprovação → login)
- FLX-02 (erros de login)
- FLX-03 (admin cria usuário)
- CEN-10, CEN-11, CEN-12, CEN-13

### PKG-LM-CORE — Lab Monitor funcional
- FLX-10 (dashboard + auto-refresh)
- FLX-11, FLX-12, FLX-13, FLX-14 (exames, resultado, laudo, histórico)
- FLX-15 (deep links)
- FLX-16, FLX-17 (labs toggle + teste)
- EXP-05 (links externos)

### PKG-LM-ADMIN — Lab Monitor gestão
- FLX-18, FLX-19 (canais Telegram)
- FLX-20 (templates de notificação)
- FLX-21 (tolerâncias CRUD)
- FLX-22 (intervalo de sync)
- CEN-14, CEN-15

### PKG-PT-GESTOR — Plantão como Gestor
- FLX-30, FLX-31, FLX-32, FLX-33 (criar/publicar/cancelar escalas)
- FLX-34, FLX-35, FLX-36 (aprovar/rejeitar candidaturas)
- FLX-45, FLX-46 (gestão de cadastros)
- FLX-37, FLX-38, FLX-39, FLX-40 (relatórios)
- FLX-41, FLX-42, FLX-43, FLX-44 (locais, tarifas, feriados, config)
- FLX-47 (reordenar disponibilidade)

### PKG-PT-VET — Plantão como Veterinário
- FLX-50, FLX-51 (landing + ver escalas)
- FLX-52, FLX-53 (candidatura + lista de espera)
- FLX-54, FLX-55 (cancelamento dentro/fora do prazo)
- FLX-61, FLX-62 (disponibilidade)
- FLX-63, FLX-64, FLX-65 (perfil, senha, notificações)

### PKG-PT-SWAP — Trocas e Substituições
- FLX-56, FLX-57, FLX-58 (troca direta)
- FLX-59, FLX-60 (substituição aberta)
- CEN-05, CEN-06 (negativos de troca)

### PKG-PT-AUX — Plantão como Auxiliar
- FLX-70, FLX-71, FLX-72, FLX-73

### PKG-PT-E2E — Plantão ciclo completo
Encadeia PKG-PT-GESTOR + PKG-PT-VET + PKG-PT-AUX em sequência real:
Criar escala → publicar → vet candidata → gestor confirma → vet cancela → espera promovida → gestor fecha

### PKG-DESIGN — Visual e UX
- VIS-01 a VIS-12 (todas as revisões visuais)
- EXP-01 a EXP-07
- TIP-03, TIP-08

### PKG-NEG — Cenários negativos completos
- CEN-01 a CEN-16

### PKG-FULL-FUNCIONAL — Tudo funcional
Todos os FLX + CEN

### PKG-FULL-COMPLETO — Cobertura total
Todos os FLX + CEN + VIS + EXP

---

## 13. BASELINE DE REFERÊNCIA

- **Testes unitários:** 55 testes, 2 FAIL + 1 ERROR (KI-01, KI-02, KI-03)
- **Usuários no banco:** 9 (vide PER-01 a PER-07 + 2 extras de prod)
- **Escalas seedadas:** 22 em plantao_datas (maio 2026)
- **Schema:** alembic head `a3b7c9d1e2f4`
- **Servidor:** não inicia automaticamente após reinício — rodar `start_dev.bat`
