# Mapeamento do modulo Plantao

## 1. Identificacao

- Modulo: Plantao
- Ambiente: DEV
- Data: 2026-04-15
- Sessao: `20260415-0f5b`
- Branch: `session/20260415-0f5b`
- Worktree: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b`
- Autor da sessao: Codex
- Status do mapeamento: `novo`
- Mapeamento anterior usado como base: nenhum

## 2. Contexto lido

### 2.1. Documentacao do modulo

- Documentacao tecnica lida:
  - `docs/discovery/2026-04-12-pbinc-plantao-module-discovery.md`
  - `docs/DESIGN.md`
  - `docs/discovery/design-feedback-log.md`
- Documentacao de negocio lida:
  - `docs/discovery/2026-04-12-pbinc-plantao-module-discovery.md`
- Documentacao adicional relevante lida:
  - `Testes/test_platform_auth.py`
  - `pb_platform/storage.py`

### 2.2. Artefatos inspecionados

- Arquivos principais:
  - `modules/plantao/router.py`
  - `modules/plantao/actions.py`
  - `modules/plantao/queries.py`
  - `modules/plantao/business.py`
  - `modules/plantao/notifications.py`
  - `modules/plantao/jobs.py`
  - `modules/plantao/calendar_utils.py`
  - `modules/plantao/audit.py`
  - `modules/plantao/schema.py`
- Rotas principais:
  - `/plantao/`
  - `/plantao/agenda`
  - `/plantao/escalas`
  - `/plantao/perfil`
  - `/plantao/notificacoes`
  - `/plantao/admin/*`
  - `/plantao/api/*`
- Templates ou componentes principais:
  - `modules/plantao/templates/*.html`
  - `modules/plantao/templates/admin/*.html`
  - `modules/plantao/templates/plantao_base.html`
  - `modules/plantao/templates/plantao_admin_base.html`
- Outros artefatos relevantes:
  - `web/app.py`
  - `web/templates/platform_base.html`

## 3. Entendimento do modulo

- Objetivo do modulo:
  - Gerenciar escalas, candidaturas, trocas, disponibilidade e relatorios de veterinarios e auxiliares plantonistas dentro da plataforma PinkBlue Vet.
- Problema que o modulo resolve:
  - Reduzir carga operacional do gestor e dar autonomia controlada aos plantonistas para visualizar vagas, candidatar-se, cancelar, trocar turnos e acompanhar disponibilidade.
- Perfis de usuario aparentes:
  - gestor com permissoes administrativas do modulo
  - veterinario plantonista
  - auxiliar plantonista
- Principais capacidades aparentes:
  - landing role-aware
  - agenda unificada do plantonista
  - escalas abertas
  - candidaturas e confirmacoes
  - trocas e substituicoes
  - disponibilidade/sobreaviso
  - notificacoes in-app
  - perfil do plantonista
  - administracao de cadastros
  - administracao de escalas
  - aprovacao de candidaturas
  - gestao de locais, tarifas, feriados e configuracoes
  - relatorios e audit log
- Limites do entendimento atual:
  - o mapeamento confirma a superficie e a intencao do modulo, mas nao valida ainda o comportamento real das telas nem o estado atual do banco de dados para cada fluxo.

## 4. Resumo operacional para retorno em tela

### 4.1. Entendimento do modulo

- O Plantao e um modulo role-aware da plataforma para gestores e plantonistas.
- A superficie atual cobre agenda, escalas abertas, trocas, disponibilidade, notificacoes, perfil e uma area administrativa completa.
- A implementacao atual usa auth unificada com a plataforma e permissao granular por acao.

### 4.2. O que foi mapeado

- Perfis: gestor, veterinario plantonista, auxiliar plantonista
- Telas e rotas: landing, agenda, escalas, notificacoes, perfil, dashboard admin, cadastros, escalas admin, aprovacoes, candidaturas, sobreaviso admin, relatorios, locais, tarifas, feriados, configuracoes e audit log
- Fluxos: candidatura, cancelamento, troca direta, substituicao, adesao em sobreaviso, aprovacao de cadastros, publicacao de escalas, geracao mensal, confirmacao de candidaturas e gestao de configuracoes
- Componentes relevantes: shell do Plantao, agenda/calendario, paineis admin, notificacoes e endpoints de API

### 4.3. O que pode ser testado depois

- Fluxos completos por perfil
- Permissoes e bloqueios
- Exploracao guiada de calendarios e filtros
- Cenarios negativos e inconsistencias
- Revisao visual desktop e mobile
- Estado vazio, navegacao e coerencia documental

### 4.4. O que a IA sugere rodar primeiro

- `PKG-01` smoke funcional de acesso e navegacao
- `PKG-02` fluxos essenciais do plantonista
- `PKG-03` fluxos essenciais do gestor
- `PKG-04` revisao visual inicial de agenda, escalas e admin
- `PKG-05` permissao e bloqueios do modulo

### 4.5. O que depende de decisao do usuario

- quais perfis entram na primeira rodada
- se a primeira rodada sera desktop apenas ou desktop + mobile
- se o foco inicial sera funcional, visual ou ambos
- quais fluxos completos devem ser priorizados
- se quer rodada minima, por pacote ou completa

### 4.6. Arquivo completo

- `docs/testing/mappings/2026-04-15-plantao-dev-mapping.md`

## 5. Inventario mapeado

### 5.1. Artefatos

- `ART-01`: router principal do modulo em `modules/plantao/router.py`
- `ART-02`: regras mutaveis do modulo em `modules/plantao/actions.py`
- `ART-03`: consultas e relatorios em `modules/plantao/queries.py`
- `ART-04`: regras de negocio de horario, cancelamento e remuneracao em `modules/plantao/business.py`
- `ART-05`: notificacoes in-app em `modules/plantao/notifications.py`
- `ART-06`: jobs periodicos em `modules/plantao/jobs.py`
- `ART-07`: calendario mensal em `modules/plantao/calendar_utils.py`
- `ART-08`: auditoria em `modules/plantao/audit.py`
- `ART-09`: schema e tabelas/view do modulo em `modules/plantao/schema.py`
- `ART-10`: shell visual e navegacao em `modules/plantao/templates/plantao_base.html`

### 5.2. Perfis

- `PER-01`: gestor com `manage_plantao`
- `PER-02`: gestor com permissao granular `plantao_gerir_escalas`
- `PER-03`: gestor com permissao granular `plantao_aprovar_candidaturas`
- `PER-04`: gestor com permissao granular `plantao_aprovar_cadastros`
- `PER-05`: gestor com permissao granular `plantao_ver_relatorios`
- `PER-06`: veterinario plantonista
- `PER-07`: auxiliar plantonista

### 5.3. Dispositivos ou contextos de uso

- `DIS-01`: desktop autenticado
- `DIS-02`: mobile autenticado

### 5.4. Tipos de teste possiveis

- `TIP-01`: funcional
- `TIP-02`: visual
- `TIP-03`: permissao
- `TIP-04`: exploracao guiada
- `TIP-05`: inconsistencia/negativo
- `TIP-06`: regressao
- `TIP-07`: ponta a ponta

### 5.5. Fluxos

- `FLX-01`: acesso ao modulo e landing role-aware
- `FLX-02`: navegacao da agenda do plantonista
- `FLX-03`: candidatura a vaga aberta
- `FLX-04`: cancelamento de candidatura/turno
- `FLX-05`: troca direta entre plantonistas
- `FLX-06`: abertura de substituicao e aceite
- `FLX-07`: adesao e cancelamento em disponibilidade/sobreaviso
- `FLX-08`: leitura e marcacao de notificacoes
- `FLX-09`: edicao de perfil e senha
- `FLX-10`: aprovacao ou rejeicao de cadastro
- `FLX-11`: criacao, publicacao, cancelamento e geracao mensal de escalas
- `FLX-12`: aprovacao e recusa de candidaturas
- `FLX-13`: reordenacao de sobreaviso
- `FLX-14`: consulta de relatorios
- `FLX-15`: gestao de locais
- `FLX-16`: gestao de tarifas
- `FLX-17`: gestao de feriados
- `FLX-18`: gestao de configuracoes
- `FLX-19`: consulta de audit log

### 5.6. Cenarios

- `CEN-01`: gestor acessa landing e dashboard admin
- `CEN-02`: plantonista acessa agenda e visualiza escalas disponiveis
- `CEN-03`: plantonista se candidata a uma vaga aberta
- `CEN-04`: gestor confirma ou recusa candidatura
- `CEN-05`: plantonista cancela candidatura dentro do prazo
- `CEN-06`: plantonista solicita troca direta
- `CEN-07`: plantonista abre substituicao
- `CEN-08`: plantonista adere ao sobreaviso
- `CEN-09`: gestor cria escala unica
- `CEN-10`: gestor gera escala mensal
- `CEN-11`: gestor publica escala
- `CEN-12`: gestor consulta relatorio de pre-fechamento
- `CEN-13`: usuario le notificacoes e marca como lidas
- `CEN-14`: usuario atualiza perfil e senha

## 6. Vetores de teste sugeridos

Listar apenas sugestoes. Nao executar nada aqui.

### 6.1. Exploracao guiada

- `EXP-01`: navegar agenda e escalas alguns dias/meses para tras e para frente
- `EXP-02`: alternar filtros e modos de visualizacao onde houver calendario/lista
- `EXP-03`: verificar estados vazios de agenda, escalas, trocas e sobreaviso
- `EXP-04`: explorar fluxo de criacao de escala unica e em lote
- `EXP-05`: explorar navegacao entre landing, agenda, escalas, dashboard admin e relatorios

### 6.2. Inconsistencia ou negativo

- `NEG-01`: tentar candidatar-se a vaga ja ocupada ou sem disponibilidade
- `NEG-02`: tentar candidatura duplicada na mesma data
- `NEG-03`: tentar cancelar turno fora do prazo configurado
- `NEG-04`: tentar agir em data passada
- `NEG-05`: tentar publicar ou cancelar escala em estado inesperado
- `NEG-06`: tentar acessar area admin sem permissao granular correspondente
- `NEG-07`: tentar reordenar sobreaviso para configuracoes invalidas
- `NEG-08`: tentar salvar configuracao com valor mal formatado

### 6.3. Limites e bordas

- `BND-01`: calendario em virada de mes
- `BND-02`: turno atravessando meia-noite
- `BND-03`: prazo de cancelamento proximo do limite
- `BND-04`: vaga com lista de espera ou maximo de candidaturas provisoria
- `BND-05`: sobreaviso sem participantes e com reordenacao apos cancelamento

### 6.4. Revisao visual

- `VIS-01`: landing do Plantao desktop
- `VIS-02`: landing do Plantao mobile
- `VIS-03`: agenda do plantonista desktop
- `VIS-04`: agenda do plantonista mobile
- `VIS-05`: admin de escalas desktop
- `VIS-06`: dashboard admin desktop
- `VIS-07`: consistencia da sidebar e estados ativos
- `VIS-08`: legibilidade de cards, calendario e CTA primarios

## 7. Sugestoes pre-prontas da IA

### 7.1. Pacotes sugeridos

- `PKG-01`: smoke de acesso e navegacao
  - `FLX-01`, `FLX-02`, `FLX-11`, `VIS-01`, `VIS-03`, `VIS-05`
- `PKG-02`: jornada essencial do plantonista
  - `FLX-02`, `FLX-03`, `FLX-04`, `FLX-05`, `FLX-07`, `FLX-08`, `FLX-09`
- `PKG-03`: jornada essencial do gestor
  - `FLX-10`, `FLX-11`, `FLX-12`, `FLX-13`, `FLX-14`, `FLX-18`
- `PKG-04`: permissao e bloqueios
  - `TIP-03`, `NEG-03`, `NEG-04`, `NEG-06`
- `PKG-05`: revisao visual inicial
  - `VIS-01`, `VIS-02`, `VIS-03`, `VIS-04`, `VIS-05`, `VIS-06`, `VIS-07`, `VIS-08`
- `PKG-06`: calendario e inconsistencias
  - `EXP-01`, `EXP-02`, `NEG-01`, `NEG-02`, `BND-01`, `BND-04`

### 7.2. Escopos completos

- `FULL-01`: completo funcional minimo
  - `PKG-01`, `PKG-02`, `PKG-03`
- `FULL-02`: completo funcional + permissao
  - `PKG-01`, `PKG-02`, `PKG-03`, `PKG-04`
- `FULL-03`: completo visual inicial
  - `PKG-05`
- `FULL-04`: completo combinado da primeira rodada
  - `PKG-01`, `PKG-02`, `PKG-03`, `PKG-04`, `PKG-05`, `PKG-06`

## 8. Riscos, restricoes e limites operacionais

### 8.1. Riscos e restricoes

- `RST-01`: ha varias frentes ativas no Jira alterando Plantao; o mapeamento deve assumir que a superficie pode mudar rapidamente
- `RST-02`: a documentacao de discovery do modulo ainda fala em auth isolado, mas o codigo atual usa auth unificada da plataforma
- `RST-03`: o design feedback log registra problemas conhecidos de calendario, permissoes e UX que podem ou nao ja ter sido corrigidos
- `RST-04`: o valor do mapeamento depende do estado real do banco DEV para fluxos com dados
- `RST-05`: PRD esta fora do escopo do processo de teste neste momento

### 8.2. Limites operacionais selecionaveis

- `LIM-01`: sem criacao automatica de card Jira
- `LIM-02`: sem PRD
- `LIM-03`: rodada inicial apenas em DEV
- `LIM-04`: pode executar acoes mutaveis em DEV somente se aprovadas na rodada

## 9. Known issues e excecoes conhecidas

- `KI-01`: historico de agenda vazia e/ou permissao inconsistente registrado em `docs/discovery/design-feedback-log.md`
- `KI-02`: historico de calendario admin parecer clicavel sem acao registrada em `docs/discovery/design-feedback-log.md`
- `KI-03`: historico de problema em botoes de criacao de escala registrado em `docs/discovery/design-feedback-log.md`
- `WA-01`: nomenclatura e percepcao de permissoes ainda podem refletir heranca tecnica do modelo atual

## 10. Nivel de confianca

Para itens `inferido` ou `precisa validar com o usuario`, sempre preencher descricao, motivo e pergunta.

### 10.1. Itens confirmados

- `PER-01` a `PER-07`
  - Descricao: a combinacao de `router.py` e `pb_platform/storage.py` confirma perfis de gestor, veterinario e auxiliar, com permissao granular no Plantao.
- `FLX-01` a `FLX-19`
  - Descricao: as rotas do router e os nomes das funcoes em `actions.py` confirmam a existencia dessas superficies e intencoes operacionais.
- `VIS-01` a `VIS-08`
  - Descricao: os templates e o guia de design confirmam que essas telas sao candidatas naturais para revisao visual.

### 10.2. Itens inferidos

- `CEN-12`
  - Descricao: relatorio de pre-fechamento aparenta ser fluxo de validacao financeira do modulo.
  - Motivo da duvida: o endpoint e a view existem, mas o peso operacional desse fluxo ainda nao foi validado com o usuario.
  - Pergunta objetiva para o usuario: o pre-fechamento deve entrar na primeira rodada ou fica para uma rodada posterior?
- `PKG-06`
  - Descricao: calendario e inconsistencias parecem ser area de alto retorno.
  - Motivo da duvida: essa prioridade vem do historico de feedback e do tipo de interacao, nao de um pedido fechado seu para a primeira rodada.
  - Pergunta objetiva para o usuario: voce quer priorizar o calendario logo na primeira rodada ou prefere deixar isso para uma segunda passada?

### 10.3. Itens que precisam validar com o usuario

- `DIS-02`
  - Descricao: mobile e uma superficie relevante do modulo.
  - Motivo da duvida: ainda nao foi definido se a primeira rodada cobrira mobile junto com desktop.
  - Pergunta objetiva para o usuario: a primeira rodada deve incluir mobile ou ficar em desktop primeiro?
- `FULL-04`
  - Descricao: rodada completa combinada funcional + visual + permissoes + inconsistencias.
  - Motivo da duvida: esse escopo e mais pesado e pode gerar muito retorno de uma vez.
  - Pergunta objetiva para o usuario: voce quer uma rodada minima orientada a prioridade ou uma rodada completa logo de inicio?

## 11. O que precisa da aprovacao do usuario

- Ambiente: DEV
- Perfis: quais entre `PER-01` a `PER-07` entram na primeira rodada
- Dispositivos: `DIS-01` apenas ou `DIS-01` + `DIS-02`
- Fluxos: quais entre `FLX-01` a `FLX-19`
- Cenarios: quais entre `CEN-01` a `CEN-14`
- Pacotes sugeridos: `PKG-01` a `PKG-06`
- Escopo completo: `FULL-01` a `FULL-04`
- Limites operacionais: `LIM-01` a `LIM-04`

## 12. Decisao sobre reuso futuro

- Este mapeamento pode ser reutilizado em reruns?
  - Sim, desde que a superficie principal do modulo nao mude de forma relevante.
- Em quais condicoes ele deixa de ser confiavel?
  - mudanca substancial de rotas, templates, shell, permissoes ou estado de dados base da rodada.
- Sinais que exigem atualizacao parcial:
  - mudanca de menu, landing, nomes de tela, novos endpoints, alteracao de um fluxo especifico, novos feedbacks de UX.
- Sinais que exigem novo mapeamento completo:
  - reorganizacao ampla do modulo, unificacao de telas, troca grande de permissao/roles, alteracao estrutural de escopo do modulo.
