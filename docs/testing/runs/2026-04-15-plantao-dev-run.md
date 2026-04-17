# Rodada Plantao DEV - 2026-04-15

## 1. Identificacao

- Modulo: Plantao
- Ambiente: DEV
- Data: 2026-04-15
- Sessao: `20260415-0f5b`
- Branch: `session/20260415-0f5b`
- Worktree: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b`
- Autor da sessao: Codex
- Status da rodada: `executada`
- Mapeamento base: `docs/testing/mappings/2026-04-15-plantao-dev-mapping.md`

## 2. Recorte aprovado pelo usuario

Registrar apenas o que foi aprovado para esta rodada.

### 2.1. Ambiente e limites

- Ambiente aprovado: `DEV`
- Limites operacionais aprovados:
  - `LIM-01`
  - `LIM-02`
  - `LIM-03`
  - `LIM-04`

### 2.2. Itens aprovados

- `PER-`: `PER-01` a `PER-07`
- `DIS-`: `DIS-01`, `DIS-02`
- `TIP-`: `TIP-01`, `TIP-02`, `TIP-03`, `TIP-04`, `TIP-05`, `TIP-06`, `TIP-07`
- `FLX-`: `FLX-01` a `FLX-19`
- `CEN-`: `CEN-01` a `CEN-14`
- `EXP-`: `EXP-01` a `EXP-05`
- `NEG-`: `NEG-01` a `NEG-08`
- `BND-`: `BND-01` a `BND-05`
- `VIS-`: `VIS-01` a `VIS-08`
- `PKG-`: `PKG-01` a `PKG-06`
- `FULL-`: `FULL-04`

### 2.3. Itens fora da rodada

- Nao aprovados: nenhum
- Bloqueados:
  - parte dos fluxos de `FLX-09`, `FLX-10`, `FLX-11`, `VIS-04` e `VIS-05` na interface renderizada, por quebra/redirect das rotas de plantonista
- Nao aplicaveis: nenhum

## 3. Plano de execucao

- Objetivo desta rodada:
  - executar a primeira rodada completa em DEV do modulo Plantao, cobrindo desktop e mobile.
- Ordem planejada de execucao:
  - preparar base local isolada
  - validar acesso e navegacao
  - executar fluxos essenciais de plantonista
  - executar fluxos essenciais de gestor
  - verificar permissoes e cenarios negativos
  - avaliar cobertura visual possivel em desktop e mobile
- Dependencias para executar:
  - base local funcional
  - usuarios de fixture
  - escalas e candidaturas seedadas
  - servidor local do app para navegacao renderizada
- Riscos esperados:
  - workspace atual do Codex sem acesso ao PostgreSQL local
  - possivel divergencia entre documentacao e codigo
  - cobertura visual limitada pelas ferramentas disponiveis neste ambiente
- Criterio de parada esperado:
  - interromper somente em caso de bloqueio tecnico total, risco indevido fora do escopo DEV ou impossibilidade de prosseguir sem nova decisao do usuario

## 4. Execucao por item

Para cada item executado, registrar status e observacao.

### 4.1. Itens executados

- Preparacao de ambiente:
  - base local isolada em SQLite criada para a rodada
  - fixture com perfis admin, gestor, vet, auxiliar, colaborador e perfis granulares de permissao
  - fixture com escalas futuras, rascunho, passada, sobreaviso, fila de espera, trocas e candidaturas
- Desktop:
  - navegacao renderizada em landing admin, escalas admin, cadastros admin, landing vet, agenda vet, escalas vet e perfil vet
  - validacao funcional de criacao de escala unica e em lote
  - validacao funcional de aprovacao de cadastro pendente
  - validacao funcional de candidatura em escala aberta
  - validacao funcional de candidatura invalida em posicao inexistente
  - validacao funcional de atualizacao de perfil e alteracao de senha
  - validacao funcional de marcacao de notificacoes como lidas
  - validacao funcional de permissoes granulares por rota
  - validacao de lockout por tentativas de login
- Mobile:
  - navegacao renderizada em escalas admin, landing vet, agenda vet, escalas vet e perfil vet
  - validacao visual de responsividade das superficies principais
- Endpoints testados diretamente para diferenciar UI x backend:
  - `POST /plantao/admin/locais/criar` e `POST /plantao/admin/configuracoes/salvar` com CSRF valido
  - `POST /plantao/sobreaviso/3/aderir` com CSRF valido extraido da agenda
  - `POST /plantao/trocas/1/aceitar` com CSRF valido extraido da agenda

### 4.2. Itens nao executados

- Fluxo completo via UI de sobreaviso do plantonista:
  - nao foi possivel concluir na interface porque `/plantao/sobreaviso` redireciona para `/plantao/disponibilidade`, que quebra com `500`
- Submissoes via UI em `Locais`, `Tarifas`, `Feriados` e `Configuracoes`:
  - os formularios renderizam `csrf_token` vazio; a submissao pela interface retorna `403`

### 4.3. Itens bloqueados ou abortados

- Bloqueio inicial identificado:
  - PostgreSQL local indisponivel no workspace do Codex
  - Mitigacao adotada: base SQLite local isolada para a rodada
- Bloqueio estrutural identificado durante a montagem da rodada:
  - o codigo escreve em `plantao_datas.auto_approve`, mas o schema do modulo nao cria essa coluna
  - mitigacao adotada apenas para a rodada: `ALTER TABLE` na base isolada

## 5. Evidencia visual usada

- Tela renderizada observada:
  - desktop:
    - `runtime-data/plantao-round1-artifacts/desktop-admin-landing.png`
    - `runtime-data/plantao-round1-artifacts/desktop-admin-escalas.png`
    - `runtime-data/plantao-round1-artifacts/desktop-admin-cadastros.png`
    - `runtime-data/plantao-round1-artifacts/desktop-vet-landing.png`
    - `runtime-data/plantao-round1-artifacts/desktop-vet-agenda.png`
    - `runtime-data/plantao-round1-artifacts/desktop-vet-escalas.png`
    - `runtime-data/plantao-round1-artifacts/desktop-vet-perfil.png`
  - mobile:
    - `runtime-data/plantao-round1-artifacts/mobile-admin-escalas.png`
    - `runtime-data/plantao-round1-artifacts/mobile-vet-landing.png`
    - `runtime-data/plantao-round1-artifacts/mobile-vet-agenda.png`
    - `runtime-data/plantao-round1-artifacts/mobile-vet-escalas.png`
    - `runtime-data/plantao-round1-artifacts/mobile-vet-perfil.png`
- Limitacoes de observacao visual:
  - nao houve inspeção visual real de `trocas` e `sobreaviso` do plantonista porque as rotas nao renderizam as telas esperadas
- Itens visuais cobertos:
  - shell do modulo
  - sidebar desktop
  - calendario admin desktop
  - lista de escalas do plantonista em desktop e mobile
  - formulario de perfil do plantonista em mobile
  - responsividade da area administrativa em mobile

## 6. Achados

Cada achado deve ser rastreavel ao item de origem.

### 6.1. Achados criticos

- Nenhum.

### 6.2. Achados de alta

- `A-01` `FLX-11`, `EXP-03`, `VIS-05`
  - Titulo: tela de disponibilidade do plantonista quebra com `500`
  - Origem: acesso a `/plantao/disponibilidade` e redirect de `/plantao/sobreaviso`
  - Resultado atual: erro `NameError: _get_perfil is not defined`
  - Impacto: bloqueia toda a gestao de disponibilidade/sobreaviso pela interface do plantonista
  - Evidencia:
    - artefato HTTP: `runtime-data/plantao-round1-artifacts/http-results.json`
    - stacktrace em `runtime-data/plantao-round1-server.err.log`
  - Referencias:
    - [router.py:391](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:391)
    - [router.py:396](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:396)
- `A-02` `FLX-15`, `FLX-16`, `CEN-11`
  - Titulo: formularios admin de locais, tarifas, feriados e configuracoes renderizam `csrf_token` vazio
  - Origem: GET das paginas admin e POSTs subsequentes
  - Resultado atual: submissao pela interface retorna `403`; os endpoints funcionam quando recebem um CSRF valido extraido de outra tela
  - Impacto: as telas existem, mas o usuario nao consegue salvar pela propria UI
  - Evidencia:
    - artefato HTTP: `runtime-data/plantao-round1-artifacts/http-results.json`
    - token vazio confirmado nas paginas renderizadas
  - Referencias:
    - [router.py:1227](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:1227)
    - [router.py:1258](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:1258)
    - [router.py:1292](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:1292)
    - [router.py:1326](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:1326)
    - [locais.html:14](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\locais.html:14)
    - [tarifas.html:14](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\tarifas.html:14)
    - [feriados.html:14](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\feriados.html:14)
    - [configuracoes.html:12](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\configuracoes.html:12)
- `A-03` `FLX-09`, `FLX-10`, `CEN-08`, `VIS-04`
  - Titulo: "Minha Agenda" quebra na hidratacao do JavaScript e fica em branco
  - Origem: abertura renderizada de `/plantao/agenda`
  - Resultado atual: a tela exibe conteudo por uma fracao de segundo e depois oculta calendario e lista; o browser registra `Unexpected token '&'` e erros Alpine como `agenda is not defined`
  - Impacto: a principal superficie do plantonista aparenta estar vazia, bloqueando consulta de agenda, trocas integradas e aderencia a sobreaviso pela UI
  - Evidencia:
    - revisao complementar da rodada em browser real apos relato do usuario
    - `runtime-data/plantao-round1-server.err.log`
  - Referencias:
    - [plantao_agenda.html:344](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\plantao_agenda.html:344)
    - [plantao_agenda.html:348](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\plantao_agenda.html:348)
- `A-04` `RST-01`, `FLX-07`
  - Titulo: schema do modulo diverge do codigo em `auto_approve`
  - Origem: preparacao da base local isolada
  - Resultado atual: `actions.criar_data_plantao` e a UI de escalas tentam persistir `plantao_datas.auto_approve`, mas o DDL nao cria a coluna
  - Impacto: qualquer execucao baseada em SQLite/local falha ao criar escalas sem correcao manual de schema
  - Evidencia:
    - erro observado ao montar a massa da rodada
  - Referencias:
    - [actions.py:498](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\actions.py:498)
    - [actions.py:520](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\actions.py:520)
    - [schema.py:278](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\schema.py:278)
    - [schema.py:402](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\schema.py:402)
- `A-05` `NEG-08`, `PER-06`
  - Titulo: colaborador autenticado sem acesso entra em fluxo propenso a loop de redirect
  - Origem: login do usuario `colab.plantao@teste.local`
  - Resultado atual: o login autenticado responde com `Location: /login`; a middleware redireciona usuario autenticado em `/login` de volta para `default_redirect_for_user`, que tambem retorna `/login`
  - Impacto: experiencia inconsistente e potencial loop infinito para usuario sem permissoes efetivas
  - Evidencia:
    - artefato HTTP: `runtime-data/plantao-round1-artifacts/http-results.json`
  - Referencias:
    - [auth.py:90](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\pb_platform\auth.py:90)
    - [auth.py:99](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\pb_platform\auth.py:99)
    - [app.py:105](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\web\app.py:105)
    - [app.py:108](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\web\app.py:108)
- `A-06` `FLX-07`, `CEN-05`, `EXP-04`, `VIS-03`
  - Titulo: botoes "Nova Escala" e "+" da tela admin de escalas nao executam nenhuma acao
  - Origem: interacao renderizada com `/plantao/admin/escalas`
  - Resultado atual: os cliques nao abrem o painel; o browser registra `Unexpected token '&'` e depois `abrirPainelEscala is not defined` e `abrirPainelEscalaDia is not defined`
  - Impacto: a principal acao de criacao de escala fica indisponivel pela propria UI administrativa
  - Evidencia:
    - revisao complementar da rodada em browser real apos relato do usuario
    - historico ja apontado em `docs/discovery/design-feedback-log.md`
  - Referencias:
    - [escalas.html:323](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\escalas.html:323)
    - [design-feedback-log.md:73](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\docs\discovery\design-feedback-log.md:73)

### 6.3. Achados de media

- `M-01` `VIS-08`, `DIS-02`
  - Titulo: layout administrativo em mobile fica comprimido e dificulta uso do calendario
  - Origem: `mobile-admin-escalas.png`
  - Resultado atual: a sidebar ocupa grande parte da viewport antes do conteudo principal; a grade do calendario fica estreita e com leitura ruim
  - Impacto: uso administrativo em celular fica possivel, mas com baixa legibilidade e baixa eficiencia
  - Evidencia:
    - `runtime-data/plantao-round1-artifacts/mobile-admin-escalas.png`
  - Referencias:
    - [platform_base.html:153](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\web\templates\platform_base.html:153)
    - [platform_base.html:155](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\web\templates\platform_base.html:155)
    - [escalas.html:67](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\escalas.html:67)
- `M-02` `FLX-09`, `FLX-10`, `CEN-08`, `VIS-04`
  - Titulo: fluxo de trocas esta integrado na agenda, mas ainda ha rota, redirects e template legados desalinhados
  - Origem: revisao do fluxo apos confronto com o contexto de produto e com o codigo
  - Resultado atual: `/plantao/trocas` redireciona para `/plantao/agenda`, a agenda contem os eventos `cedido`, mas os POSTs de troca ainda redirecionam para `/plantao/trocas` e o template legado segue no modulo
  - Impacto: nao bloqueia o fluxo se a agenda for a superficie oficial, mas aumenta ambiguidade tecnica, dificulta manutencao e pode confundir documentacao e retestes
  - Evidencia:
    - decisao de produto informada pelo usuario com referencia aos cards `PBVET-157/158/159`
    - comportamento observado no codigo
  - Referencias:
    - [router.py:197](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:197)
    - [router.py:229](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:229)
    - [router.py:304](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:304)
    - [router.py:381](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:381)
    - [router.py:524](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\router.py:524)
    - [plantao_trocas.html:19](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\plantao_trocas.html:19)
- `M-03` `FLX-14`, `VIS-06`
  - Titulo: tela de cadastros usa acao unilateral de "Desativar" e nao respeita o padrao de reversibilidade
  - Origem: revisao de interacao da tela admin `/plantao/admin/cadastros`
  - Resultado atual: usuarios ativos so oferecem `Desativar`; nao ha acao simetrica de reativacao nem indicacao de filtro para arquivados/inativos
  - Impacto: a UI diverge do manual de design e reduz seguranca operacional em cadastros administrativos
  - Evidencia:
    - template atual do modulo
    - regra de design registrada em `docs/discovery/design-feedback-log.md`
  - Referencias:
    - [cadastros.html:91](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\modules\plantao\templates\admin\cadastros.html:91)
    - [design-feedback-log.md:69](c:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b\docs\discovery\design-feedback-log.md:69)

### 6.4. Achados de baixa

- Nenhum.

## 7. Inconsistencias documentais

- A documentacao lida no mapeamento ainda descreve auth isolada do Plantao em trechos antigos, enquanto o codigo atual usa auth unificada da plataforma.
- A interface disponivel hoje redireciona `/plantao/trocas` para agenda e `/plantao/sobreaviso` para disponibilidade; se a documentacao ainda tratar essas telas como superficies dedicadas e acessiveis diretamente, ela precisa ser atualizada para refletir o estado real ou o produto precisa ser corrigido para voltar ao fluxo esperado.

## 8. Known issues e repeticoes

- Itens ja conhecidos revisitados:
  - auth unificada da plataforma versus narrativa antiga de auth isolada no modulo
  - agenda em branco apos hidratacao quebrada e botoes de escala sem resposta ja apareciam no historico de design, mas precisavam de confirmacao tecnica no estado atual
- Itens confirmados como persistentes:
  - divergencia entre schema e codigo em `auto_approve`
  - parse de JavaScript quebrado em telas que interpolam `tojson` dentro de `<script>` sem serializacao segura
- Itens corrigidos e retestados: nao aplicavel nesta etapa

### 8.1. Falhas de cobertura da primeira rodada

- A primeira rodada confiou demais em validacao HTTP/back-end em superficies onde a UI e fortemente dirigida por JavaScript.
- Nao houve verificacao obrigatoria de `console errors` e `page errors` apos a hidratacao da tela.
- Nao houve regra obrigatoria de acionar todos os CTAs primarios das telas incluidas no escopo visual.
- A agenda foi considerada carregada pela presenca inicial de DOM e screenshot, mas faltou validar o estado apos alguns instantes de execucao do JavaScript; por isso o comportamento "pisca e some" passou.
- O fluxo de escalas admin teve o back-end exercitado, mas a cobertura nao distinguiu com rigor suficiente "endpoint funcional" de "UI funcional".
- A avaliacao de `Cadastros` nao cruzou a tela com a regra de design de reversibilidade registrada no historico de produto, o que deixou passar a inconsistencia de interacao.

## 9. Diagnostico da rodada

- Sintese geral:
  - o modulo esta navegavel e funcional em partes importantes de agenda, escalas, candidatura, perfil, notificacoes e permissao granular
  - ha, porem, regresses de interface e integracao suficientes para impedir considerar a frente pronta para producao
- Estado observado do modulo nesta rodada:
  - backend principal de escalas e candidatura respondeu bem na maior parte
  - disponibilidade/sobreaviso do plantonista esta quebrado na rota de leitura
  - a agenda do plantonista quebra na hidratacao do JavaScript e pode se apresentar como tela em branco
  - a criacao de escala pela UI admin tambem quebra na camada JavaScript antes de abrir o painel
  - trocas aparenta estar intencionalmente integrada na agenda, mas ainda deixa residuos tecnicos e documentais do fluxo legado
  - varias telas admin de configuracao existem, mas a propria UI nao consegue submeter por CSRF vazio
- Principais riscos:
  - regressao funcional em superficies do plantonista
  - falsas validacoes positivas em telas que renderizam HTML inicial mas quebram na hidratacao
  - falsas sensacoes de completude em telas admin que nao salvam
  - fragilidade de ambiente local por divergencia de schema
- Principais confiancas:
  - permissao granular de leitura/roteamento admin
  - criacao de escalas unica e em lote
  - lockout de login
  - candidatura, perfil e notificacoes
- O que ainda precisa validar:
  - rerun completo apos correcao de `disponibilidade`, agenda do plantonista, escalas admin e CSRF admin
  - revisao mobile adicional das telas admin restantes depois de ajustar a navegacao lateral

## 10. Proximos passos

- Ajustes recomendados:
  - corrigir `disponibilidade_page` para usar helper existente ou recuperar o perfil de forma consistente
  - serializar de forma segura os objetos JSON injetados em `<script>` na agenda do plantonista e na tela admin de escalas
  - injetar `csrf_token` nas telas admin `Locais`, `Tarifas`, `Feriados` e `Configuracoes`
  - alinhar o fluxo legado de `trocas` com a decisao de produto: consolidar agenda como superficie oficial ou remover residuos de rota/template/redirect
  - alinhar schema e codigo em `auto_approve`
  - tratar usuarios autenticados sem permissao efetiva sem redirecionar para `/login`
  - alinhar `Cadastros` ao padrao de reversibilidade de entidades administrativas
  - revisar layout admin mobile com colapso/alternancia de sidebar
- Reruns recomendados:
  - rerun funcional completo do plantonista apos corrigir `A-01` e `A-03`
  - rerun da UI admin de escalas apos corrigir `A-06`
  - rerun admin de configuracao apos corrigir `A-02`
  - rerun visual mobile admin apos corrigir `M-01`
- Follow-ups de documentacao:
  - atualizar documentacao de auth do modulo
  - atualizar documentacao de superficies ativas de trocas e sobreaviso
- Necessidade de aprovacao adicional:
  - nenhuma para seguir com correcoes locais
  - criacao de novos cards Jira continua dependendo de aprovacao do usuario
- Recomendacao sobre Jira:
  - nao abrir automaticamente
  - recomendar aprovacao manual para card(s) de correcao focados em:
    - disponibilidade/sobreaviso do plantonista
    - CSRF nas telas admin
    - UI de trocas
