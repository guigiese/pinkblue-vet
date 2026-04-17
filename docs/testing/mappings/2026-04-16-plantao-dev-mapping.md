# Mapeamento do modulo Plantao

## 1. Identificacao

- Modulo: Plantao
- Ambiente: DEV
- Data: 2026-04-16
- Sessao: `20260415-0f5b`
- Branch: `session/20260415-0f5b`
- Worktree de registro: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b`
- Snapshot tecnico lido em: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet`
- Autor da sessao: Codex
- Status do mapeamento: `atualizado`
- Mapeamento anterior usado como base:
  - `docs/testing/mappings/2026-04-15-plantao-dev-mapping.md`

## 2. Contexto lido

### 2.1. Documentacao do modulo

- Documentacao tecnica lida:
  - `docs/discovery/2026-04-12-pbinc-plantao-module-discovery.md`
  - `docs/discovery/design-feedback-log.md`
- Documentacao de negocio lida:
  - `docs/discovery/2026-04-12-pbinc-plantao-module-discovery.md`
- Documentacao interna de testes reutilizada como contexto:
  - `docs/testing/AI_TESTING_STANDARD.md`
  - `docs/testing/mappings/2026-04-15-plantao-dev-mapping.md`
  - `docs/testing/runs/2026-04-15-plantao-dev-run.md`

### 2.2. Artefatos inspecionados

- Backend e regras:
  - `modules/plantao/router.py`
  - `modules/plantao/actions.py`
  - `modules/plantao/business.py`
  - `modules/plantao/queries.py`
  - `modules/plantao/schema.py`
- Shell e superficies principais:
  - `modules/plantao/templates/plantao_base.html`
  - `modules/plantao/templates/plantao_escalas.html`
  - `modules/plantao/templates/plantao_landing.html`
  - `modules/plantao/templates/plantao_sobreaviso.html`
  - `modules/plantao/templates/plantao_notificacoes.html`
  - `modules/plantao/templates/plantao_perfil.html`
- Superficies admin:
  - `modules/plantao/templates/admin/cadastros.html`
  - `modules/plantao/templates/admin/aprovacoes.html`
  - `modules/plantao/templates/admin/candidaturas.html`
  - `modules/plantao/templates/admin/sobreaviso.html`
  - `modules/plantao/templates/admin/tarifas.html`
  - `modules/plantao/templates/admin/locais.html`
  - `modules/plantao/templates/admin/feriados.html`
  - `modules/plantao/templates/admin/configuracoes.html`
  - `modules/plantao/templates/admin/relatorios*.html`
- Shell compartilhado:
  - `web/templates/platform_base.html`

### 2.3. Mudancas estruturais observadas desde o mapeamento anterior

- A superficie principal do modulo foi consolidada em ` /plantao/escalas `.
- As rotas antigas ` /plantao/agenda `, ` /plantao/meus-turnos `, ` /plantao/trocas ` e ` /plantao/admin/escalas ` agora funcionam como alias/redirect.
- O template `plantao_agenda.html` nao faz parte do snapshot atual.
- O template admin dedicado de escalas nao faz parte do snapshot atual; a criacao/publicacao foi embutida na tela unificada `plantao_escalas.html`.
- `Cadastros` agora expõe reativacao, nao apenas desativacao.
- `Tarifas` agora expõe criacao, edicao e exclusao na mesma superficie.

## 3. Entendimento do modulo

- Objetivo do modulo:
  - gerir escalas presenciais e listas de disponibilidade de veterinarios e auxiliares dentro da plataforma PinkBlue Vet, com operacao unificada entre plantonistas e gestores.
- Problema que o modulo resolve:
  - concentrar visualizacao, candidatura, criacao, aprovacao, cancelamento, disponibilidade, configuracao e relatorios em uma camada unica de operacao de plantao.
- Perfis aparentes:
  - gestor com acesso total (`manage_plantao`)
  - gestor com permissoes granulares por acao
  - veterinario plantonista
  - auxiliar plantonista
  - usuario autenticado sem permissao suficiente, relevante para testes negativos
- Principais capacidades aparentes:
  - landing role-aware
  - tela unificada de escalas com modos calendario e lista
  - criacao de escala unica e em lote dentro da propria tela de escalas
  - candidatura, desistir, assumir turno cedido e entrar/sair de lista de disponibilidade
  - fluxo de disponibilidade/sobreaviso separado, mas ligado a escalas
  - notificacoes in-app e perfil
  - aprovacoes de cadastros e candidaturas
  - cadastros com desativar/reativar
  - locais, tarifas, feriados e configuracoes
  - relatorios e audit log
- Limites do entendimento atual:
  - este mapeamento descreve o estado estrutural atual do modulo, mas nao afirma que os fluxos estejam funcionais no browser ou consistentes com a documentacao; isso depende da proxima rodada.

## 4. Resumo operacional para retorno em tela

### 4.1. Entendimento do modulo

- O Plantao agora gira em torno de uma superficie principal unificada em ` /plantao/escalas `.
- O gestor e o plantonista compartilham a mesma tela-base de escalas, com acoes condicionadas por permissao.
- Rotas antigas de agenda, trocas e admin de escalas continuam existindo principalmente como compatibilidade.

### 4.2. O que foi mapeado

- Perfis:
  - gestor full
  - gestor granular
  - veterinario
  - auxiliar
  - usuario sem permissao
- Superficies:
  - landing
  - escalas unificadas
  - disponibilidade do plantonista
  - notificacoes
  - perfil
  - cadastros
  - aprovacoes
  - candidaturas
  - sobreaviso admin
  - locais
  - tarifas
  - feriados
  - configuracoes
  - relatorios
  - audit log
- Fluxos centrais:
  - navegar mes/local/view
  - criar/publicar/cancelar escala
  - candidatar/desistir
  - assumir turno cedido
  - entrar/sair da lista de disponibilidade
  - aprovar/recusar cadastros e candidaturas
  - editar/excluir tarifa

### 4.3. O que pode ser testado depois

- rodada completa funcional + visual na tela unificada de escalas
- revalidacao dos redirects/aliases legados
- permissoes e bloqueios por perfil
- estados vazios, filtros e alternancia calendario/lista
- CRUD admin de cadastros, tarifas, locais, feriados e configuracoes
- coerencia entre comportamento atual e a documentacao antiga de discovery

### 4.4. O que a IA sugere rodar primeiro

- `PKG-01` smoke estrutural da superficie unificada
- `PKG-02` jornada completa do plantonista no modelo atual
- `PKG-03` jornada completa do gestor no modelo atual
- `PKG-04` aliases, redirects e compatibilidade
- `PKG-05` configuracao e cadastros administrativos
- `PKG-06` visual desktop e mobile da tela unificada

### 4.5. Arquivo completo

- `docs/testing/mappings/2026-04-16-plantao-dev-mapping.md`

## 5. Inventario mapeado

### 5.1. Artefatos

- `ART-01`: router principal em `modules/plantao/router.py`
- `ART-02`: acoes mutaveis em `modules/plantao/actions.py`
- `ART-03`: consultas e agregacoes em `modules/plantao/queries.py`
- `ART-04`: regras de negocio em `modules/plantao/business.py`
- `ART-05`: schema do modulo em `modules/plantao/schema.py`
- `ART-06`: shell visual e navegacao lateral em `modules/plantao/templates/plantao_base.html`
- `ART-07`: superficie unificada de escalas em `modules/plantao/templates/plantao_escalas.html`
- `ART-08`: superficie de disponibilidade do plantonista em `modules/plantao/templates/plantao_sobreaviso.html`
- `ART-09`: fluxo de cadastros admin em `modules/plantao/templates/admin/cadastros.html`
- `ART-10`: fluxo de tarifas admin em `modules/plantao/templates/admin/tarifas.html`

### 5.2. Perfis

- `PER-01`: gestor com `manage_plantao`
- `PER-02`: gestor com `plantao_gerir_escalas`
- `PER-03`: gestor com `plantao_aprovar_candidaturas`
- `PER-04`: gestor com `plantao_aprovar_cadastros`
- `PER-05`: gestor com `plantao_ver_relatorios`
- `PER-06`: veterinario plantonista
- `PER-07`: auxiliar plantonista
- `PER-08`: usuario autenticado sem permissao efetiva para o modulo

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
- `TIP-08`: compatibilidade de alias/redirect

### 5.5. Fluxos

- `FLX-01`: acesso a landing do modulo
- `FLX-02`: navegacao na tela unificada de escalas por mes, local e view
- `FLX-03`: candidatura a vaga aberta pela tela unificada
- `FLX-04`: desistir de turno/candidatura
- `FLX-05`: assumir turno cedido pela tela unificada
- `FLX-06`: criar escala unica a partir da tela unificada
- `FLX-07`: criar escala em lote a partir da tela unificada
- `FLX-08`: publicar escala rascunho
- `FLX-09`: cancelar escala sem confirmados
- `FLX-10`: entrar na lista de disponibilidade
- `FLX-11`: sair da lista de disponibilidade
- `FLX-12`: acessar a superficie dedicada de disponibilidade do plantonista
- `FLX-13`: ler notificacoes e marcar como lidas
- `FLX-14`: editar perfil e alterar senha
- `FLX-15`: aprovar, rejeitar, desativar e reativar cadastros
- `FLX-16`: aprovar/recusar candidaturas pela fila e pela tela detalhada
- `FLX-17`: reordenar sobreaviso admin
- `FLX-18`: gerir locais
- `FLX-19`: gerir tarifas
- `FLX-20`: gerir feriados
- `FLX-21`: gerir configuracoes
- `FLX-22`: consultar relatorios e audit log
- `FLX-23`: validar aliases e redirects legados (`agenda`, `trocas`, `meus-turnos`, `admin/escalas`, `admin/disponibilidade`)

### 5.6. Cenarios

- `CEN-01`: gestor entra em escalas e cria uma nova escala pelo CTA principal
- `CEN-02`: gestor abre um dia do calendario e cria escala contextual pelo drawer
- `CEN-03`: gestor publica um rascunho existente
- `CEN-04`: plantonista navega entre calendario e lista e se candidata a uma vaga
- `CEN-05`: plantonista desiste de um turno confirmado
- `CEN-06`: plantonista assume um turno cedido
- `CEN-07`: plantonista entra e sai da lista de disponibilidade
- `CEN-08`: gestor aprova um cadastro pendente e reativa um inativo
- `CEN-09`: gestor confirma e recusa candidaturas
- `CEN-10`: gestor cria, edita e exclui uma tarifa
- `CEN-11`: gestor cria local, feriado e salva configuracoes
- `CEN-12`: gestor consulta relatorios e pre-fechamento
- `CEN-13`: usuario percorre aliases legados e valida destinos corretos
- `CEN-14`: usuario sem permissao tenta acessar superficies do modulo

## 6. Vetores de teste sugeridos

Listar apenas sugestoes. Nao executar nada aqui.

### 6.1. Exploracao guiada

- `EXP-01`: alternar calendario/lista em ` /plantao/escalas ` e navegar meses para tras e para frente
- `EXP-02`: abrir dias com e sem eventos, inclusive via clique na celula e no chip de evento
- `EXP-03`: alternar filtros de tipo e status na tela unificada
- `EXP-04`: abrir o painel de criacao de escala pelo CTA principal e pelo CTA contextual do dia
- `EXP-05`: percorrer locais diferentes e comparar o reflexo no conteudo renderizado
- `EXP-06`: percorrer os aliases legados e verificar se preservam contexto minimo (mes, ano, local, query string)

### 6.2. Inconsistencia ou negativo

- `NEG-01`: tentar candidatura duplicada para a mesma data
- `NEG-02`: tentar assumir turno cedido de forma invalida
- `NEG-03`: tentar criar escala em data passada
- `NEG-04`: tentar cancelar escala com confirmados quando a UI nao deveria permitir
- `NEG-05`: tentar salvar configuracao malformada
- `NEG-06`: tentar acessar admin sem permissao granular correspondente
- `NEG-07`: tentar editar/excluir tarifa em combinacoes invalidas
- `NEG-08`: tentar usar aliases legados autenticado sem permissao adequada

### 6.3. Limites e bordas

- `BND-01`: virada de mes na tela unificada
- `BND-02`: mudanca de local com mais de um local cadastrado
- `BND-03`: escala atravessando meia-noite
- `BND-04`: lista de disponibilidade vazia e depois preenchida
- `BND-05`: lote mensal com multiplos dias da semana
- `BND-06`: filtro que oculta todos os eventos e precisa mostrar estado vazio coerente

### 6.4. Revisao visual

- `VIS-01`: landing desktop
- `VIS-02`: escalas unificadas desktop em modo calendario
- `VIS-03`: escalas unificadas desktop em modo lista
- `VIS-04`: escalas unificadas mobile
- `VIS-05`: drawer/painel de criacao de escala
- `VIS-06`: cadastros admin
- `VIS-07`: tarifas admin
- `VIS-08`: consistencia da sidebar e estados ativos no shell
- `VIS-09`: relatorios admin

## 7. Sugestoes pre-prontas da IA

### 7.1. Pacotes sugeridos

- `PKG-01`: smoke estrutural da superficie unificada
  - `FLX-01`, `FLX-02`, `FLX-06`, `FLX-08`, `VIS-02`, `VIS-03`
- `PKG-02`: jornada essencial do plantonista no modelo atual
  - `FLX-02`, `FLX-03`, `FLX-04`, `FLX-05`, `FLX-10`, `FLX-11`, `FLX-13`, `FLX-14`
- `PKG-03`: jornada essencial do gestor no modelo atual
  - `FLX-06`, `FLX-07`, `FLX-08`, `FLX-09`, `FLX-15`, `FLX-16`, `FLX-17`, `FLX-22`
- `PKG-04`: aliases e compatibilidade
  - `FLX-12`, `FLX-23`, `EXP-06`, `NEG-08`
- `PKG-05`: configuracao e cadastros administrativos
  - `FLX-15`, `FLX-18`, `FLX-19`, `FLX-20`, `FLX-21`, `VIS-06`, `VIS-07`
- `PKG-06`: visual e responsividade da nova superficie
  - `VIS-01`, `VIS-02`, `VIS-03`, `VIS-04`, `VIS-05`, `VIS-08`, `VIS-09`

### 7.2. Escopos completos

- `FULL-01`: completo funcional da superficie unificada
  - `PKG-01`, `PKG-02`, `PKG-03`
- `FULL-02`: completo funcional + compatibilidade
  - `PKG-01`, `PKG-02`, `PKG-03`, `PKG-04`
- `FULL-03`: completo admin de configuracao
  - `PKG-05`
- `FULL-04`: completo visual desktop + mobile
  - `PKG-06`
- `FULL-05`: rerun completo do modulo no estado atual
  - `PKG-01`, `PKG-02`, `PKG-03`, `PKG-04`, `PKG-05`, `PKG-06`

## 8. Riscos, restricoes e limites operacionais

### 8.1. Riscos e restricoes

- `RST-01`: o snapshot tecnico atual esta no workspace principal, que segue com varias mudancas locais nao consolidadas
- `RST-02`: a documentacao antiga de discovery ainda descreve auth isolada, enquanto o modulo hoje usa auth unificada da plataforma
- `RST-03`: como varias rotas antigas seguem como alias, a rodada precisa distinguir comportamento oficial de compatibilidade legada
- `RST-04`: a maior parte do valor do proximo teste depende de massa coerente em DEV para vagas, turnos cedidos, disponibilidade e cadastros
- `RST-05`: PRD continua fora de escopo

### 8.2. Limites operacionais selecionaveis

- `LIM-01`: sem criacao automatica de card Jira
- `LIM-02`: sem PRD
- `LIM-03`: rodada em DEV
- `LIM-04`: acoes mutaveis em DEV apenas se entrarem no recorte aprovado

## 9. Known issues e excecoes conhecidas

- `KI-01`: o design feedback log registra historico forte de problemas em agenda/escalas, empty state e interacao do calendario
- `KI-02`: a rodada de 2026-04-15 encontrou problemas em hidratao de UI, CSRF admin e consistencia de fluxo; como a estrutura mudou, esses pontos precisam ser revalidados e nao presumidos como corrigidos
- `KI-03`: a documentacao de produto e discovery ainda nao esta totalmente alinhada ao desenho atual unificado
- `WA-01`: parte da nomenclatura no discovery antigo ainda usa "sobreaviso" e "agenda" como superficies separadas, enquanto o snapshot atual concentra mais comportamento em ` /plantao/escalas `

## 10. Nivel de confianca

Para itens `inferido` ou `precisa validar com o usuario`, sempre preencher descricao, motivo e pergunta.

### 10.1. Itens confirmados

- `ART-01` a `ART-10`
  - Descricao: os artefatos inspecionados existem no snapshot atual e sustentam o novo desenho do modulo.
- `FLX-01` a `FLX-23`
  - Descricao: as rotas e templates atuais confirmam a existencia dessas superficies e intencoes operacionais.
- `FULL-05`
  - Descricao: o modulo ja tem inventario suficiente para suportar uma nova rodada completa no estado atual.

### 10.2. Itens inferidos

- `CEN-12`
  - Descricao: o relatorio de pre-fechamento continua com peso operacional alto dentro do modulo.
  - Motivo da duvida: a tela existe e o fluxo de queries existe, mas nao ha evidencias novas neste mapeamento sobre sua prioridade para a rodada completa.
  - Pergunta objetiva para o usuario: no rerun completo, o pre-fechamento entra como parte obrigatoria ou pode ser secundario?
- `PKG-04`
  - Descricao: a camada de aliases e compatibilidade parece importante para o estado atual do modulo.
  - Motivo da duvida: essa importancia vem da reestruturacao recente, nao de uma diretriz explicita sua.
  - Pergunta objetiva para o usuario: no teste completo, voce quer tratar compatibilidade legada como parte obrigatoria ou apenas complementar?

### 10.3. Itens que precisam validar com o usuario

- `DIS-02`
  - Descricao: mobile segue relevante, especialmente porque a nova tela unificada concentra mais interacoes.
  - Motivo da duvida: um teste completo em desktop + mobile e mais pesado e gera mais retorno para consolidar.
  - Pergunta objetiva para o usuario: o proximo teste completo cobre mobile junto com desktop?
- `FULL-05`
  - Descricao: rerun completo do modulo no estado atual.
  - Motivo da duvida: ele e o pacote natural apos esse refresh de mapeamento, mas envolve muitas superficies mutaveis em DEV.
  - Pergunta objetiva para o usuario: quer executar o `FULL-05` integralmente na proxima rodada?

## 11. O que precisa da aprovacao do usuario

- Ambiente: DEV
- Perfis: `PER-01` a `PER-08`
- Dispositivos: `DIS-01` ou `DIS-01` + `DIS-02`
- Fluxos: `FLX-01` a `FLX-23`
- Cenarios: `CEN-01` a `CEN-14`
- Pacotes sugeridos: `PKG-01` a `PKG-06`
- Escopos completos: `FULL-01` a `FULL-05`
- Limites operacionais: `LIM-01` a `LIM-04`

## 12. Decisao sobre reuso futuro

- Este mapeamento pode ser reutilizado em reruns?
  - Sim, enquanto a superficie central continuar sendo ` /plantao/escalas ` e os aliases/rotas auxiliares nao mudarem de forma relevante.
- Em quais condicoes ele deixa de ser confiavel?
  - se a tela unificada for quebrada novamente em telas separadas, se surgirem novos templates centrais, se os aliases legados forem removidos ou se a organizacao de permissoes for reestruturada.
- Sinais que exigem atualizacao parcial:
  - ajuste de sidebar, inclusao de novos CTAs, alteracao relevante em disponibilidade, cadastros, tarifas ou relatorios.
- Sinais que exigem novo mapeamento completo:
  - troca de arquitetura da superficie principal, redesign amplo do shell, mudanca do conjunto de fluxos centrais ou revisao profunda das permissoes.
