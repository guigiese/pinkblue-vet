# CONTEXT.md - PinkBlue Vet / Platform Workspace
> Documento técnico para onboarding de IAs e desenvolvedores.
> Descreve o estado atual do projeto, arquitetura, contratos de dados e regras de extensão.
> Atualizado em: 2026-04-01

---

## O que é este projeto

Este repositório passou a ser tratado como o workspace atual da plataforma PinkBlue Vet.

PinkBlue Vet é a plataforma principal.
Lab Monitor é o módulo ativo principal hoje, mas não é mais o ente principal do workspace.
Nomes legados como `SimplesVet` podem aparecer em pastas locais ou referências antigas, mas não devem ser tratados como o nome da plataforma.

Hoje o workspace cobre:
- a home da plataforma em `/`;
- o módulo Lab Monitor em `/labmonitor`;
- o mapa operacional em `/ops-map/`;
- sandboxes e superfícies auxiliares sob `/sandboxes/*`.

O Lab Monitor continua sendo um monitor automatizado de exames laboratoriais para uma clínica veterinária (PinkBlue Vet).
Ele faz scraping/API-calls em laboratórios parceiros, detecta novos exames e mudanças de status,
e envia notificações via Telegram (e opcionalmente WhatsApp).

Roda 24/7 na nuvem (Railway) como um único serviço Python que combina:
- um loop de monitoramento em background thread
- uma interface web (FastAPI + Jinja2 + HTMX) acessível em tempo real

**URL de produção:** https://pinkblue-vet-production.up.railway.app

A aplicação de exames é servida sob o prefixo `/labmonitor`. A raiz `/` exibe a home
da plataforma com os módulos e superfícies disponíveis.

Existe também uma superfície operacional acessível em `/ops-map/`, que publica o mapa visual
de sistemas, plataformas, integrações e sinais da operação PinkBlue.

Para explorações visuais paralelas sem risco direto ao módulo principal, existe um
espaço de sandbox separado em `/sandboxes/cards/`, usado para iterar variações de layout
antes de decidir o que sobe para o Lab Monitor.

## Direção estrutural

O estado atual do código ainda é majoritariamente "flat" na raiz do repositório, o que
foi aceitável enquanto o Lab Monitor dominava quase todo o escopo. A direção agora é
evoluir o workspace de forma incremental para uma estrutura mais claramente modular.

Estrutura-alvo de médio prazo:

```
/
├── apps/                  # entradas web/runtime da plataforma
├── pb_platform/           # auth, settings, persistence, shell visual, shared infra
├── modules/
│   ├── lab_monitor/
│   ├── crm/
│   └── financeiro/
├── docs/
├── infra/
├── poc/
└── scripts/
```

Importante:
- esta estrutura-alvo nao precisa ser aplicada de forma destrutiva agora;
- a migracao deve ser gradual e guiada por valor, nao por estetica;
- o primeiro passo e alinhar docs, backlog e fronteiras de responsabilidade.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.13 |
| Web framework | FastAPI 0.115 + Uvicorn 0.30 |
| Templates | Jinja2 3.1 + HTMX (CDN) + TailwindCSS (CDN) |
| HTTP scraping | requests 2.32 + BeautifulSoup4 4.13 |
| Notificações | Telegram Bot API / Callmebot WhatsApp API |
| Persistência oficial | PostgreSQL (`psycopg2` via SQLAlchemy) |
| Auth fase 1 | Sessão por cookie + store compartilhada |
| Deploy | Railway (Railpack, sem Docker customizado) |
| Repositório | GitHub: guigiese/pinkblue-vet |

Hoje a plataforma já possui uma persistência compartilhada oficial:
- `PostgreSQL` como banco canônico do runtime;
- store compartilhada em `pb_platform/storage.py`;
- usuários, sessões, snapshots, subscriptions, tolerâncias e configurações persistidos.

O `AppState` continua existindo como cache quente do runtime, mas deixou de ser a única fonte de verdade do módulo.

---

## Estrutura de arquivos atual

```
/
├── config.json              # Bootstrap legado da configuração runtime (não é mais a fonte oficial)
├── core.py                  # Loop de monitoramento + detecção de novidades
├── monitor.py               # Entrypoint standalone (sem web, para testes locais)
├── deploy.py                # Script de deploy canônico — usa serviceInstanceDeploy(commitSha=...)
├── requirements.txt
├── nixpacks.toml            # Instrui o Railpack a usar pip e o comando de start correto
├── Procfile                 # Fallback de start command
│
├── labs/
│   ├── base.py              # ABC LabConnector — contrato que todo lab deve seguir
│   ├── __init__.py          # Registry: CONNECTORS = {"bitlab": ..., "nexio": ...}
│   ├── bitlab.py            # Conector BioAnálises — REST API + JWT
│   └── nexio.py             # Conector Nexio Patologia — session cookie + HTML parsing
│
├── notifiers/
│   ├── base.py              # ABC Notifier — método enviar(msg: str)
│   ├── __init__.py          # Registry: NOTIFIERS = {"telegram": ..., "whatsapp": ...}
│   ├── telegram.py          # Telegram Bot API — subscriptions persistidas na store compartilhada
│   ├── telegram_polling.py  # Thread de polling do bot: /assinar, /sair, /status, /start
│   └── whatsapp.py          # Callmebot API (desabilitado por padrão)
│
├── pb_platform/
│   ├── settings.py          # Configuração compartilhada da plataforma
│   ├── security.py          # Hash de senha e tokens de sessão
│   ├── storage.py           # Store compartilhada da plataforma (PostgreSQL oficial; SQLite explícito só para uso efêmero)
│   └── auth.py              # Regras de proteção de rotas e helpers de sessão
│
├── web/
│   ├── app.py               # FastAPI: auth, home, admin, /ops-map, /sandboxes e APIRouter /labmonitor
│   ├── ops_map.py           # Runtime do mapa operacional (snapshot com cache curto)
│   ├── state.py             # AppState singleton compartilhado entre thread e web
│   └── templates/
│       ├── index.html       # Home da plataforma
│       ├── login.html       # Login da plataforma
│       ├── admin_users.html # Gestão inicial de acessos
│       ├── base.html        # Layout sidebar responsivo (Tailwind CDN + HTMX CDN)
│       ├── platform_base.html # Shell visual compartilhado da plataforma
│       ├── ops_map.html     # Wrapper do mapa operacional servido pelo próprio app
│       ├── dashboard.html   # Contadores por lab + feed de notificações
│       ├── exames.html      # Tabela de exames com filtros
│       ├── labs.html        # Gerenciar labs (toggle, test connection)
│       ├── canais.html      # Gerenciar canais + lista de usuários Telegram
│       ├── notificacoes.html # Templates e política operacional de notificações
│       ├── thresholds.html   # Tolerâncias por exame
│       ├── settings.html    # Intervalo de verificação
│       └── partials/        # Fragmentos HTMX (atualizados sem reload de página)
│           ├── lab_counts.html
│           ├── exames_table.html      # Mobile cards + desktop table; alertas por item e grupo
│           ├── ultimos_liberados.html # Feed de exames Pronto/Parcial recentes com alertas
│           ├── resultado_bitlab.html  # Tabela inline de resultados BitLab (valor + referência + alerta)
│           └── telegram_users.html   # Lista de usuários inscritos no bot
│
├── .github/
│   └── workflows/
│       └── session-route.yml  # Session Router: conta branches session/*, roteia PRs para fast-path ou full-path
│
├── docs/
│   ├── CONTEXT.md           # Este arquivo
│   ├── DEVLOG.md            # Log narrativo de decisões e lições aprendidas
│   └── discovery/           # Notas de descoberta e propostas ainda não implementadas
│
└── poc/
    ├── architecture-map/    # PoC/base do mapa operacional PinkBlue
    │   ├── index.html
    │   ├── app.js
    │   ├── styles.css
    │   ├── README.md
    │   ├── assets/
    │   └── data/
    │       ├── pinkblue-map.v1.json       # grafo base estático
    │       └── pinkblue-map.runtime.json  # snapshot ao vivo (gerado por scripts/refresh_*)
    └── lab-card-variants/   # Sandbox servido em /sandboxes/cards/ para explorar cards de exames
        ├── index.html
        └── styles.css
```

Leitura importante:
- `config.json` e `telegram_users.json` ainda existem apenas como bootstrap legado de primeira carga;
- `web/app.py` ainda acumula home da plataforma, auth, admin, modulo Lab Monitor, ops-map e sandboxes;
- `labs/` e `notifiers/` ainda vivem no nível raiz porque a separação completa por módulo/shared capability ainda não foi executada.

---

## config.json — esquema e semântica

```json
{
  "interval_minutes": 15,
  "labs": [
    {
      "id": "bitlab",          // chave usada em snapshots e rotas
      "name": "Nome legível",  // exibido na UI
      "connector": "bitlab",   // chave em labs/CONNECTORS
      "enabled": true
    }
  ],
  "notifiers": [
    {
      "id": "telegram",        // chave usada nas rotas
      "type": "telegram",      // chave em notifiers/NOTIFIERS
      "enabled": true
    }
  ]
}
```

`id` e `type` podem ser diferentes. `id` é o identificador de instância na UI;
`type` aponta para a classe no registry.

---

## Política atual de notificações

Hoje o projeto separa dois fluxos:

- feed interno do app: continua registrando mudanças finas de status por item
- notificações externas (Telegram / outros canais): seguem política operacional mais restrita

Política externa atual:
- notificar quando uma nova requisição entra no laboratório
- notificar quando itens da mesma requisição passam para `Pronto`
- agrupar os itens concluídos por requisição no mesmo ciclo de monitoramento
- suprimir reenvio do mesmo evento externo por assinatura/idempotência em memória

Isso reduz spam e deixa o Telegram mais próximo da leitura operacional desejada.

---

## Contrato do snapshot (LabConnector.snapshot)

Todos os conectores devem retornar exatamente este formato:

```python
{
    "RECORD_ID": {
        "label":     "NOME PACIENTE - NOME PROPRIETÁRIO",  # str legível
        "data":      "YYYY-MM-DD",                          # data do exame
        "portal_id": "ID_INTERNO_DO_LAB",                   # usado para construir deep link
        "itens": {
            "ITEM_ID": {
                "nome":       "Nome do exame",
                "status":     "Em Andamento",  # string livre, vinda do lab
                "liberado_em": "2026-03-30T14:32:00",  # ISO, injetado por core.py ao detectar Pronto
                # BitLab adiciona: "dtColeta": "2026-03-30T16:08:44.873"
            }
        }
    }
}
```

`RECORD_ID` é a chave primária de comparação entre snapshots (detecta novas entradas).
`ITEM_ID` + `status` é o que detecta mudanças de resultado.
`portal_id` é usado por `state.py` para construir deep links diretos ao laudo de cada lab.
`liberado_em` é injetado por `core._stamp_liberados()` no momento em que o status transita para Pronto.

---

## Lógica de detecção de novidades (core.py)

```
para cada lab:
    atual = lab.snapshot()
    anterior = estado salvo na memória

    se anterior está vazio:
        salvar atual sem notificar  ← CRÍTICO: evita flood no primeiro boot

    senão:
        para cada record_id em atual:
            se record_id não existe em anterior → notificar "Nova entrada"
            senão:
                para cada item_id:
                    se status mudou → notificar "Resultado disponível"

        _stamp_liberados(anterior, atual, now.isoformat())
        ← injeta liberado_em nos itens que acabaram de virar Pronto
        ← preserva liberado_em de ciclos anteriores
```

**Regra do primeiro boot:** na primeira execução após um restart, o estado está vazio.
Sem essa guarda, todos os exames existentes seriam tratados como "novos" e disparariam
dezenas de notificações simultâneas. Isso aconteceu de verdade com o Callmebot — ver DEVLOG.

---

## AppState (web/state.py)

Singleton em módulo — instância criada em `web/state.py` e importada em `web/app.py` e `core.py`.
Não é thread-safe com locks, mas as operações são atômicas o suficiente para este uso
(uma thread de monitor escrevendo, FastAPI lendo).

| Atributo | Tipo | Descrição |
|---|---|---|
| `snapshots` | `dict[lab_id, snapshot]` | Estado mais recente de cada lab |
| `last_check` | `dict[lab_id, "HH:MM:SS"]` | Horário da última verificação bem-sucedida |
| `last_error` | `dict[lab_id, str]` | Último erro, se houver |
| `is_checking` | `dict[lab_id, bool]` | Flag de verificação em andamento |
| `notifications` | `list[dict]` | Últimas 50 notificações: `{time, lab, msg}` |
| `_config` | `dict` | Snapshot da configuração runtime persistida na store |

`config` é uma property alimentada pela configuração runtime persistida no banco.
Após qualquer escrita via `save_config()`, o próximo ciclo do loop pega o valor atualizado automaticamente.

---

## Telegram Bot — multi-usuário

O bot (`notifiers/telegram_polling.py`) roda em thread daemon separada.
Usuários se inscrevem pelo próprio Telegram — sem necessidade de configurar chat IDs manualmente.

| Comando | Comportamento |
|---|---|
| `/start` | Boas-vindas neutras, lista os comandos disponíveis |
| `/assinar` | Inscreve o usuário para receber notificações |
| `/sair` | Cancela a inscrição |
| `/status` | Informa se está inscrito ou não |

Os chat IDs inscritos agora vivem na store compartilhada da plataforma.
`telegram_users.json` só pode aparecer como artefato legado de bootstrap.

A UI em `/labmonitor/canais` exibe a lista de usuários inscritos com botão de remoção.
A lista atualiza automaticamente a cada 10 segundos via HTMX polling.

---

## Variáveis de ambiente (Railway)

Estado alvo: credenciais em produção devem viver como env vars do Railway, ou em cofre dedicado quando a plataforma evoluir.
Estado atual: ainda existem fallbacks sensíveis no código e um arquivo `.secrets` local para desenvolvimento; isso é dívida ativa de segurança, não padrão desejado.

| Variável | Onde usado | Descrição |
|---|---|---|
| `BITLAB_USUARIO` | labs/bitlab.py | Login BitLab |
| `BITLAB_SENHA` | labs/bitlab.py | Senha BitLab |
| `BITLAB_CD_CONVENIO` | labs/bitlab.py | Código do convênio (default: 1170) |
| `BITLAB_CD_POSTO` | labs/bitlab.py | Código do posto (default: 8) |
| `DIAS_ATRAS` | labs/bitlab.py | Janela de busca em dias (default: 30) |
| `NEXIO_USUARIO` | labs/nexio.py | Login Nexio |
| `NEXIO_SENHA` | labs/nexio.py | Senha Nexio |
| `TELEGRAM_TOKEN` | notifiers/telegram.py | Token do bot Telegram |
| `TELEGRAM_CHATID` | notifiers/telegram.py | Chat ID do destinatário |
| `WHATSAPP_PHONE` | notifiers/whatsapp.py | Número Callmebot |
| `CALLMEBOT_APIKEY` | notifiers/whatsapp.py | API key Callmebot |

Para desenvolvimento local, as credenciais atualmente ficam em `.secrets` (formato INI, gitignored).

---

## Deploy (Railway)

- Builder: **Railpack** (detecta Python automaticamente)
- `nixpacks.toml` define explicitamente a fase de install e o comando de start
- O comando de start **deve** ser `python -m uvicorn web.app:app --host 0.0.0.0 --port $PORT`
- Usar `uvicorn` diretamente (sem `python -m`) falha porque o PATH do container não inclui o venv bin

### deploy.py — script canônico

**Nunca usar `githubRepoDeploy`** — essa mutation SEMPRE cria um novo serviço.
O script `deploy.py` usa `serviceInstanceDeploy(commitSha=...)` que deploya no serviço existente.

```
Workflow correto:
1. git add + git commit
2. git push origin main
3. python deploy.py  ← lê .secrets, aciona deploy no serviço correto, aguarda SUCCESS
```

### IDs do serviço Railway

| Campo | Valor |
|---|---|
| service_id | 215d2612-2f33-475c-8a4f-3c8588089164 |
| env_id | f95eb850-1680-4d28-95ce-6dc77b5d7653 |
| URL | https://pinkblue-vet-production.up.railway.app |

---

## Arquitetura de rotas

```
GET  /                              → Home autenticada da plataforma
GET  /login                         → Login da plataforma
GET  /logout                        → Encerrar sessão
GET  /admin/usuarios                → Gestão inicial de acessos da plataforma
GET  /labmonitor                    → Dashboard
GET  /labmonitor/exames             → Tabela de exames com filtros
GET  /labmonitor/labs               → Gerenciar laboratórios
GET  /labmonitor/canais             → Gerenciar canais de notificação
GET  /labmonitor/notificacoes       → Templates e política de notificações
GET  /labmonitor/tolerancias        → Tolerâncias por exame
GET  /labmonitor/settings           → Configurações gerais
GET  /labmonitor/partials/notifications     → Fragmento HTMX
GET  /labmonitor/partials/lab_counts        → Fragmento HTMX
GET  /labmonitor/partials/exames            → Fragmento HTMX
GET  /labmonitor/partials/telegram-users    → Fragmento HTMX
POST /labmonitor/labs/{id}/toggle           → Toggle lab
POST /labmonitor/labs/{id}/test             → Testar conexão com lab
POST /labmonitor/canais/{id}/toggle         → Toggle canal
POST /labmonitor/canais/{id}/test           → Enviar mensagem de teste
POST /labmonitor/canais/telegram/users/{chat_id}/remove  → Remover usuário Telegram
POST /labmonitor/notificacoes/salvar        → Persistir templates e eventos
POST /labmonitor/notificacoes/resetar       → Restaurar defaults dos templates
POST /labmonitor/settings/interval          → Atualizar intervalo
POST /labmonitor/tolerancias/salvar         → Salvar tolerância por exame
POST /labmonitor/tolerancias/{slug}/remover → Remover tolerância
```

Implementado via `APIRouter(prefix="/labmonitor")` em `web/app.py`.

---

## Como adicionar um novo laboratório

1. Criar `labs/novolab.py` herdando `LabConnector` e implementando `snapshot()`
2. Registrar em `labs/__init__.py`: `CONNECTORS["novolab"] = NovoLabConnector`
3. Persistir a entrada em `lab_monitor.runtime_config`:
   ```json
   {"id": "novolab", "name": "Nome Legível", "connector": "novolab", "enabled": true}
   ```
4. Adicionar as env vars de credenciais no Railway

Nenhuma outra mudança é necessária — o loop, a UI e as notificações já suportam N labs.

---

## Como adicionar um novo canal de notificação

1. Criar `notifiers/novocanal.py` herdando `Notifier` e implementando `enviar(msg)`
2. Registrar em `notifiers/__init__.py`: `NOTIFIERS["novocanal"] = NovoCanalNotifier`
3. Persistir a entrada em `lab_monitor.runtime_config`:
   ```json
   {"id": "novocanal", "type": "novocanal", "enabled": true}
   ```
4. Adicionar as env vars no Railway

---

## Deep links por laboratório

| Lab | URL do laudo | Campo usado |
|---|---|---|
| BitLab | `https://bitlabenterprise.com.br/bioanalises/laudos/{portal_id}` | `req["id"]` (encoded string da API) |
| Nexio | `https://www.pathoweb.com.br/moduloProcedencia/visualizarLaudoAjax?id={portal_id}` | ID interno do BD (radio input `value`) — **requer sessão ativa** |

O Nexio não tem URL pública estável por exame. O link abre o visualizador do portal (requer login). O PDF em si é gerado dinamicamente com path temporário não-reutilizável.

---

## Limitações conhecidas (fase atual)

- **Bootstrap legado ainda existe:** `config.json` e `telegram_users.json` podem servir como import inicial, mas o runtime oficial já depende do PostgreSQL como fonte de verdade.
- **BitLab timeout:** o servidor `bitlabenterprise.com.br` pode apresentar timeouts intermitentes (connect timeout=15s). Erro capturado em `last_error` e exibido na UI de labs.
- **Nexio:** o parsing é frágil (depende de posição de colunas HTML). Uma mudança de layout no Pathoweb quebra o conector.
- **Sync incremental ainda é parcial:** o BitLab já usa contexto persistido para reduzir a janela de busca; o restante dos conectores ainda precisa amadurecer o mesmo comportamento.
- **Callmebot limitado:** 16 mensagens por 240 minutos. Desabilitado por padrão.
- **Segredos e remotos ainda precisam saneamento:** há artefatos e fallbacks sensíveis que devem sair do repositório/ambiente local antes da plataforma crescer.

---

## Descobertas em aberto

As propostas ainda não implementadas de plataforma e expansão ficam em `docs/discovery/`.

- `docs/discovery/2026-04-01-core-platform-foundations.md`
- `docs/discovery/2026-04-01-pbinc-crm-financeiro.md`
