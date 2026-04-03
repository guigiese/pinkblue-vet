# Discovery - Platform Structure And Phase 1 Persistence

Data: 2026-04-03
Escopo Jira: `PBCORE-57`, `PBCORE-58`, `PBCORE-59`, `PBCORE-60`, `PBCORE-16`, `PBEXM-42`, `PBEXM-43`, `PBEXM-44`, `PBEXM-45`, `PBEXM-46`

## Objetivo

Consolidar a proxima camada da plataforma PinkBlue Vet sem quebrar a linha estavel
atual:

- repositório tratado como workspace de plataforma, nao como "repo do Lab Monitor";
- auth compartilhada da plataforma, e nao auth paralela do modulo;
- persistencia fase 1 com custo zero e baixo atrito;
- base para sync incremental, configuracoes persistentes e futuros modulos;
- shell visual compartilhado para home, modulos e telas auxiliares.

## Decisao executiva da fase atual

### Escolha para persistencia fase 1

Escolha recomendada:

- `SQLite`
- `SQLAlchemy 2.0`
- `Alembic`
- `Pydantic Settings`
- arquivo do banco em `Railway Volume`

### Atualizacao apos a implementacao inicial

Na primeira entrega executavel, a ponte entrou de forma ainda mais enxuta do que a recomendacao
original acima:

- `SQLite` com `sqlite3` da stdlib;
- schema inicial criado pela propria aplicacao;
- settings centralizados em `pb_platform/settings.py`;
- auth por sessao/cookie;
- arquivo do banco em `runtime-data/` ou no volume do Railway quando disponivel.

Motivo:
- menor atrito para entrar logo;
- zero dependencia nova de ORM ou migrations nesta fase;
- atende auth, usuarios, sessoes, thresholds, notificacoes e snapshots persistidos;
- preserva a opcao de migrar depois para `SQLAlchemy + Alembic + Postgres` sem jogar fora a camada de dominio.

### Por que esta opcao foi escolhida

Ela atende melhor ao momento atual:

- custo zero ou proximo de zero dentro do stack ja usado;
- nenhuma dependencia de um novo provedor externo agora;
- sobrevive a redeploys quando armazenada em volume persistente;
- simplifica auth, configuracoes persistentes, sync incremental e auditoria;
- permite evolucao futura para Postgres sem jogar fora ORM/migrations/settings.

Em outras palavras:
- simples o suficiente para entrar logo;
- seria o mesmo stack Python que usaríamos com Postgres depois;
- evita alongar esta fase com infra demais.

## Aplicacoes e tecnologias envolvidas

### Railway

Onde o produto ja roda hoje.

Papel nesta fase:
- continuar servindo o app web;
- hospedar o volume persistente do arquivo SQLite;
- manter segredos nas variaveis do servico.

### Railway Volume

Armazenamento persistente anexado ao servico.

Papel nesta fase:
- guardar o arquivo `sqlite` fora do filesystem efemero do container;
- sobreviver a redeploys sem depender de JSON mutavel em runtime;
- reduzir atrito operacional ao maximo.

### SQLite

Banco relacional em arquivo unico.

Papel nesta fase:
- usuarios, sessoes, settings, subscriptions, configuracoes por exame;
- protocolos, itens, resultados e eventos sincronizados;
- base local principal do modulo.

### SQLAlchemy

Camada ORM/acesso a dados em Python.

Papel nesta fase:
- evitar SQL espalhado;
- desacoplar modelo de dados da escolha do banco;
- facilitar futura migracao para Postgres.

### Alembic

Ferramenta de migrations do schema.

Papel nesta fase:
- evoluir tabelas de forma controlada;
- registrar historico de mudancas;
- permitir rollout e ajuste seguro.

### Pydantic Settings

Camada centralizada para configuracao.

Papel nesta fase:
- parar de espalhar leitura de ambiente;
- separar config local, config de deploy e segredos;
- preparar melhor transicao entre dev/prod.

### Session auth por cookie

Modelo de autenticacao server-rendered.

Papel nesta fase:
- proteger a plataforma inteira antes dos modulos;
- iniciar com usuario master + gestao basica de usuarios;
- encaixar melhor no FastAPI + Jinja + HTMX do que JWT-first.

## O que ficou de fora e por que ficou de fora

### Postgres gerenciado agora

Ficou fora da fase 1, nao do futuro.

Motivo:
- melhor como destino estrutural permanente;
- mais infraestrutura para esta rodada do que o necessario;
- o ganho imediato nao compensa o atrito adicional agora.

### Provedores externos como Supabase, Neon ou Turso

Ficaram fora da escolha atual.

Motivo:
- adicionam mais um provedor e mais uma superficie operacional;
- nao sao necessarios para iniciar auth + persistencia + sync incremental;
- podem voltar a fazer sentido quando quisermos sair do arquivo unico.

### Vault

Ficou fora da fase 1.

Motivo:
- madura a trilha de segredos, mas nao entrega o melhor custo-beneficio agora;
- Railway variables + saneamento do codigo ainda sao o proximo passo pragmatico.

### JWT, SSO e perfis complexos

Ficaram fora da fase 1.

Motivo:
- custo de implementacao maior sem beneficio proporcional no estado atual;
- sessao por cookie resolve melhor o caso atual da plataforma web interna.

### Segmentacao de deploys imediata

Ficou em discovery.

Motivo:
- auth compartilhada e persistencia compartilhada precisam vir antes;
- separar cedo demais pode aumentar a complexidade sem reduzir risco de verdade.

## Estrutura-alvo recomendada

### Logica

A plataforma precisa separar:

- `entrada e shell da plataforma`;
- `capacidades compartilhadas`;
- `modulos de negocio`;
- `artefatos de suporte`.

### Estrutura de medio prazo

```text
/
├── apps/
│   └── web/                     # entrypoint principal da plataforma
├── pb_platform/
│   ├── auth/
│   ├── db/
│   ├── settings/
│   ├── shell/
│   └── observability/
├── modules/
│   ├── lab_monitor/
│   │   ├── connectors/
│   │   ├── notifications/
│   │   ├── services/
│   │   ├── routes/
│   │   └── templates/
│   ├── crm/
│   └── financeiro/
├── docs/
├── infra/
├── poc/
├── scripts/
└── tests/
```

### Como aplicar sem quebrar o estado atual

Nao mover tudo de uma vez.

Sequencia segura:

1. alinhar Jira e docs
2. introduzir namespaces/shared packages novos
3. mover capacidades compartilhadas primeiro
4. mover o Lab Monitor por fatias
5. so depois reorganizar entradas e templates restantes

## Estrutura operacional recomendada agora

### Home da plataforma

Continua em `/`.

Papel:
- porta de entrada apos auth;
- biblioteca de modulos e superficies auxiliares;
- ponto de retorno comum.

### Shell visual compartilhado

Padroes compartilhados que devem valer para home, Lab Monitor, ops-map e futuros modulos:

- cabecalho comum;
- tipografia comum;
- acao clara para voltar a home;
- area reservada para icone/logomarca do modulo;
- espaco futuro para logomarca da empresa;
- responsividade padronizada.

### Modulos

O Lab Monitor passa a ser tratado explicitamente como modulo.

Modulos futuros:
- CRM veterinario
- conciliacao financeira
- outros

Todos entram atras da mesma auth e do mesmo shell.

## Plano de desenvolvimento recomendado

### Fase 0 - alinhamento estrutural

- Jira ajustado para plataforma x modulo
- docs-base ajustados
- plano documentado

### Fase 1 - fundacao compartilhada

- `pb_platform/settings`
- `pb_platform/db`
- `pb_platform/auth`
- arquivo SQLite persistido em volume Railway
- migrations iniciais

### Fase 2 - auth da plataforma

- login por email/senha
- usuario master inicial
- sessao por cookie
- tela admin minima para gestao de usuarios
- protecao da home autenticada e dos modulos

### Fase 3 - persistencia do Lab Monitor

- protocolos, itens, resultados, eventos de status
- usuarios Telegram e configuracoes
- templates/configs de notificacao
- tolerancias por exame

### Fase 4 - sync incremental

- high-water marks por laboratorio quando possivel
- reconciliacao por janela curta de rechecagem
- rehidratacao no startup sem revarredura total
- deduplicacao por assinatura de evento

### Fase 5 - shell visual compartilhado

- cabecalho comum
- navegacao comum
- adaptacoes desktop/mobile
- espaco preparado para a logomarca da PinkBlue Vet

### Fase 6 - avaliar segmentacao de deploys

- manter deploy unico por enquanto
- separar apenas quando auth/persistencia/shared shell estiverem consolidados

## Estrategia para reduzir consultas aos laboratorios sem perder dados

Objetivo:
- parar de usar o portal do laboratorio como fonte principal do app em todo ciclo;
- evitar revarredura completa;
- reduzir risco de lentidao, congestionamento ou ban.

### Estrategia

1. banco local vira fonte principal do app
2. conectores passam a buscar so o necessario
3. manter janela curta de reconciliacao
4. registrar `ultimo sync`, `portal_id`, hash/status, e timestamps por item
5. aplicar retry com backoff e jitter
6. manter uma reconciliacao mais ampla em baixa frequencia

### Garantia contra perda

- eventos/status relevantes ficam persistidos localmente
- restart nao limpa a base
- rechecagens curtas capturam mudancas atrasadas
- reconciliacao mais ampla detecta eventuais lacunas

## Notificacoes - direcao da proxima fase

A tela de notificacoes deve evoluir para incluir:

- template de recebimento
- template de conclusao
- template de atualizacao de status, desativado por padrao
- glossario completo de variaveis
- explicacao dos criterios de aglutinacao em um unico bloco
- revisao visual dos icones/templates

Isto continua sendo funcionalidade do modulo, mas depende da persistencia
compartilhada para nao voltar a depender de arquivo volatil.

## Resultados nao numericos

Direcao mantida:
- reaproveitar o bom padrao do Nexio;
- trazer exames textuais e laudos nao numericos para um modelo comum;
- separar parser, modelo de dados e UI no backlog.

## Por que thresholds por exame nao foram implementados nos ciclos anteriores

`threshold` significa `limiar` ou `tolerancia`.

No contexto do projeto:
- quanto acima/abaixo da referencia gera `Atencao`;
- quanto acima/abaixo da referencia gera `Critico`.

O tema apareceu antes, mas nao foi implementado por dois motivos:

1. o card foi encerrado como discovery, nao como entrega
2. a funcionalidade depende de persistencia real para sobreviver a redeploys

Ou seja:
- a necessidade era real;
- o fechamento anterior foi de planejamento, nao de execucao.

## Fontes oficiais consultadas

- Railway basics: https://docs.railway.com/overview/the-basics
- Railway pricing: https://docs.railway.com/pricing
- SQLAlchemy ORM quickstart: https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Pydantic Settings: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
