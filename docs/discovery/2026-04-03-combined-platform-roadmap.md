# Discovery - Combined Platform Roadmap

Data: 2026-04-03
Escopo Jira: `PBCORE-56`

## Objetivo

Transformar os discoveries ja existentes em um trilho unico de execucao para a
proxima camada da PinkBlue Vet, sem misturar:

- evolucao do produto ativo no Railway;
- estrutura de multiplas IAs e workers;
- chamadas pontuais de IA;
- persistencia real em banco;
- infraestrutura auxiliar em nuvem;
- separacao dev/prod.

Este documento nao implementa a migracao. Ele consolida as decisoes e define a
ordem de ataque recomendada.

## Cards consolidados

### Base de plataforma

- `PBCORE-14` - arquitetura de persistencia e banco
- `PBCORE-15` - plano de migracao do estado atual
- `PBCORE-55` - separacao de ambientes dev/prod

### IA, workers e chamada pontual

- `PBINC-14` - arquitetura de workers por papel
- `PBINC-15` - frameworks multi-agente
- `PBINC-16` - orquestracao alem do GitHub Actions
- `PBINC-17` - comparativo de APIs de IA
- `PBINC-18` - casos de uso para chamada pontual
- `PBINC-22` - Codex na rotina
- `PBINC-23` - VS Code e integracoes de produtividade

### Infra auxiliar

- `PBINC-19` - necessidade real de VPS
- `PBINC-20` - Oracle vs Hetzner vs Fly.io
- `PBINC-21` - VS Code Remote

## Sintese executiva

### 1. O app principal deve continuar no Railway

O discovery convergiu para uma direcao pragmatica:

- manter o Lab Monitor como servico principal no Railway;
- adicionar `PostgreSQL no Railway` como primeiro banco oficial;
- evitar migrar o app principal para VPS por aspiracao tecnica.

Conclusao combinada:
- `Railway` segue como runtime do produto;
- `VPS` entra apenas como runtime auxiliar para automacao persistente.

### 2. Persistencia vem antes de automacao pesada

Hoje o sistema ainda depende de:

- `config.json` mutado em runtime;
- `telegram_users.json`;
- caches em memoria;
- estado perdido em restart/redeploy.

Sem banco, os proximos passos de IA e automacao ficam frageis.

Conclusao combinada:
- a trilha `PBCORE-14` + `PBCORE-15` deve abrir a fila;
- workers autonomos, n8n e staging fixo devem depender dessa fundacao.

### 3. Existem duas frentes de IA, e elas nao devem nascer juntas

Os cards apontam para duas linhas diferentes:

- `IA por chamada`: request/response, invocada por tela, webhook ou acao manual;
- `IA como worker`: processos autonomos, agendados, com fila, retries e estado.

Conclusao combinada:
- a primeira IA a entrar no produto deve ser a `IA por chamada`;
- o primeiro worker autonomo deve ser o `monitor_worker`;
- `downstream_worker` e `qa_worker` so devem entrar quando persistencia e
  separacao minima de ambiente ja existirem.

Isto e uma inferencia operacional a partir dos discoveries: o valor de negocio
da IA por chamada vem antes, com risco menor.

### 4. A estrategia de provider deve ser multi-provider

Os cards nao apontam para um provider unico.
O desenho mais robusto e:

- `Gemini` ou `Groq` para prototipo e custo baixo;
- `Anthropic` para casos clinicos com maior exigencia de raciocinio;
- `OpenAI/Codex` para execucao de codigo e partes secundarias de automacao.

Conclusao combinada:
- nao acoplar a arquitetura a um provedor unico;
- persistir `provider`, `model`, `prompt_version` e metadados de request.

### 5. Docker deve ser usado como dev-infra, nao como estrategia primaria de deploy

O stack atual ja esta funcional no Railway sem imagem customizada.
Docker ainda e valioso, mas no lugar certo:

- `docker-compose` para Postgres local e n8n local;
- containers numa VPS apenas quando a linha de workers sair do experimento.

Conclusao combinada:
- `Docker` agora acelera o desenvolvimento;
- `Docker em producao` so entra como camada da sidecar infra.

### 6. A separacao de ambientes deve acontecer em duas camadas

Do card `PBCORE-55` sai uma sequencia clara:

- agora: `dev local + PR Environments do Railway + smoke checks`;
- depois: `staging fixo` quando banco, settings e requests de IA estiverem sob
  persistencia.

Conclusao combinada:
- ainda nao vale abrir um staging fixo completo sem banco;
- ja vale preparar templates e politica de ambiente imediatamente.

### 7. Oracle Free Tier e a sidecar preferida; Hetzner e o fallback

Os discoveries se encaixam assim:

- `Oracle Free Tier`: melhor custo para n8n e workers persistentes;
- `Hetzner CX22`: fallback mais simples se Oracle falhar ou o I/O incomodar;
- `Fly.io`: nao e a opcao recomendada para este caso.

Conclusao combinada:
- nao abrir sidecar infra antes da necessidade real;
- quando abrir, `Oracle primeiro`, `Hetzner se Oracle nao for viavel`.

## Arquitetura alvo combinada

### Runtime primario

- `Railway web service` para app FastAPI/Jinja/HTMX
- `Railway PostgreSQL` para estado oficial

### Runtime auxiliar

- `Docker Compose local` para desenvolvimento de infra
- `Oracle Free Tier` como host preferido de `n8n` + workers Python persistentes
- `Hetzner` como fallback pago e simples

### Duas linhas de IA

#### Linha A - IA por chamada

Uso:

- avaliacao de criticidade de laudo;
- conciliacao financeira;
- resumo/contextualizacao sob demanda.

Caracteristicas:

- trigger via HTTP;
- resposta sincrona ou quase-sincrona;
- persistencia de request/result para auditoria;
- baixo acoplamento com a automacao de longa duracao.

#### Linha B - Workers autonomos

Papeis recomendados:

- `monitor_worker`
- `downstream_worker`
- `qa_worker`
- `on_demand_ai` permanece separado por trigger

Caracteristicas:

- cron/webhook;
- fila de jobs;
- retries;
- logs de execucao;
- opcionalmente n8n como scheduler visual.

## Modelo de dados minimo para habilitar a proxima fase

O recorte base de `PBCORE-14` continua valido:

- `sync_runs`
- `lab_records`
- `lab_items`
- `item_status_events`
- `notification_events`
- `telegram_subscriptions`
- `app_settings`
- `users`
- `roles`
- `user_roles`

Para a trilha de IA, este plano recomenda reservar tambem:

- `ai_requests`
  - quem pediu
  - trigger
  - provider
  - model
  - prompt_version
  - status

- `ai_results`
  - request_id
  - output estruturado
  - custo estimado
  - latencia
  - resumo seguro para auditoria

- `worker_jobs`
  - tipo do worker
  - prioridade
  - payload resumido
  - status

- `worker_runs`
  - job_id
  - started_at / finished_at
  - sucesso / erro
  - logs resumidos

## Fases recomendadas

### Fase 0 - Preparacao segura

Objetivo:
- preparar a base sem alterar o runtime ativo do modulo.

Entradas:
- `PBCORE-56`

Saidas:
- templates de ambiente;
- compose local de infra;
- seed de topologia de workers;
- plano combinado documentado.

### Fase 1 - Fundacao de persistencia

Objetivo:
- tirar a plataforma da dependencia estrutural de memoria + JSON.

Cards foco:
- `PBCORE-14`
- `PBCORE-15`

Entregas minimas:
- `settings.py` centralizado;
- `DATABASE_URL`;
- migrations;
- Postgres provisionado;
- primeiras tabelas operacionais;
- estrategia de migracao de `telegram_users.json` e de caches sensiveis.

### Fase 2 - IA por chamada

Objetivo:
- colocar uma capacidade de IA de baixo risco e alto valor no produto.

Cards foco:
- `PBINC-17`
- `PBINC-18`

Entregas minimas:
- adaptador multi-provider;
- catalogo de prompts/versionamento;
- endpoint ou servico de chamada sob demanda;
- persistencia em `ai_requests` e `ai_results`;
- feature flag por ambiente.

### Fase 3 - Worker autonomo inicial

Objetivo:
- habilitar automacao persistente sem pular direto para um ecossistema complexo.

Cards foco:
- `PBINC-14`
- `PBINC-15`
- `PBINC-16`

Entregas minimas:
- `monitor_worker` primeiro;
- cron simples ou n8n;
- tabela de jobs/runs;
- logs de execucao;
- retries controlados.

Observacao:
- `downstream_worker` e `qa_worker` ficam depois do monitor.

### Fase 4 - Separacao operacional de ambientes

Objetivo:
- reduzir risco de deploy e preparar terreno para schema changes e IA em producao.

Cards foco:
- `PBCORE-55`

Entregas minimas agora:
- `.env` por perfil;
- PR Environments do Railway;
- smoke checks;
- politica explicita de dev/review/prod.

Entregas minimas depois:
- staging fixo apenas quando o banco ja existir e houver valor real em validar
  migrations, prompts e jobs persistidos.

### Fase 5 - Sidecar cloud runtime

Objetivo:
- tirar automacao persistente do notebook local quando isso passar a ser gargalo.

Cards foco:
- `PBINC-19`
- `PBINC-20`
- `PBINC-21`

Decisao combinada:
- sidecar so nasce quando houver `n8n` ou workers de longa duracao;
- `Oracle Free Tier` e a primeira aposta;
- `Hetzner` entra como fallback operacional.

## Ordem sugerida de execucao no backlog

### Executar primeiro

1. `PBCORE-14`
2. `PBCORE-15`
3. sub-slice de `PBCORE-55` focada em env templates, PR envs e smoke check

### Executar na sequencia

4. `PBINC-17`
5. `PBINC-18`

### Abrir depois da fundacao

6. `PBINC-14`
7. `PBINC-15`
8. `PBINC-16`

### Deixar dependente de necessidade real

9. `PBINC-19`
10. `PBINC-20`
11. `PBINC-21`

## Decisoes recomendadas a carregar daqui para frente

- `Railway + Railway Postgres` e a base oficial da plataforma
- `Docker` entra primeiro como dev-infra
- `Oracle/Hetzner` entram apenas como sidecar runtime
- `IA por chamada` vem antes de `worker autonomo de codigo`
- `monitor_worker` vem antes de `downstream_worker`
- `PR Environments + smoke test` vem antes de `staging fixo`
- `multi-provider` e regra, nao excecao

## Artefatos preparatorios desta sessao

- `docs/discovery/2026-04-03-combined-platform-roadmap.md`
- `infra/docker-compose.dev.yml`
- `infra/env/dev.env.example`
- `infra/env/prod.env.example`
- `infra/README.md`
- `poc/ai-workers/topology.example.yaml`
