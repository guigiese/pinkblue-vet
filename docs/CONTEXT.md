# CONTEXT.md — Lab Monitor (SimplesVet)
> Documento técnico para onboarding de IAs e desenvolvedores.
> Descreve o estado atual do projeto, arquitetura, contratos de dados e regras de extensão.
> Atualizado em: 2026-03-29

---

## O que é este projeto

Monitor automatizado de exames laboratoriais para uma clínica veterinária.
Faz scraping/API-calls em laboratórios parceiros, detecta novos exames e mudanças de status,
e envia notificações via Telegram (e opcionalmente WhatsApp).

Roda 24/7 na nuvem (Railway) como um único serviço Python que combina:
- um loop de monitoramento em background thread
- uma interface web (FastAPI + Jinja2 + HTMX) acessível em tempo real

**URL de produção:** https://ideal-communication-production.up.railway.app

---

## Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.13 |
| Web framework | FastAPI 0.115 + Uvicorn 0.30 |
| Templates | Jinja2 3.1 + HTMX (CDN) + TailwindCSS (CDN) |
| HTTP scraping | requests 2.32 + BeautifulSoup4 4.13 |
| Notificações | Telegram Bot API / Callmebot WhatsApp API |
| Deploy | Railway (Railpack, sem Docker customizado) |
| Repositório | GitHub: guigiese/monitor-exames-bitlab |

Não há banco de dados. O estado vive em memória (`AppState`) e é resetado a cada restart do serviço.
Isso é intencional: o custo zero de infra exige zero serviços adicionais.

---

## Estrutura de arquivos

```
/
├── config.json              # Configuração runtime (labs ativos, notifiers, intervalo)
├── core.py                  # Loop de monitoramento + detecção de novidades
├── monitor.py               # Entrypoint standalone (sem web, para testes locais)
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
│   ├── telegram.py          # Telegram Bot API
│   └── whatsapp.py          # Callmebot API (desabilitado por padrão)
│
├── web/
│   ├── app.py               # FastAPI: rotas, partials HTMX, ações
│   ├── state.py             # AppState singleton compartilhado entre thread e web
│   └── templates/
│       ├── base.html        # Layout sidebar (Tailwind CDN + HTMX CDN)
│       ├── dashboard.html   # Contadores por lab + feed de notificações
│       ├── exames.html      # Tabela de exames com filtros
│       ├── labs.html        # Gerenciar labs (toggle, test connection)
│       ├── canais.html      # Gerenciar canais de notificação (toggle, test send)
│       ├── settings.html    # Intervalo de verificação
│       └── partials/        # Fragmentos HTMX (atualizados sem reload de página)
│           ├── notifications.html
│           ├── lab_counts.html
│           └── exames_table.html
│
└── docs/
    ├── CONTEXT.md           # Este arquivo
    └── DEVLOG.md            # Log narrativo de decisões e lições aprendidas
```

---

## config.json — esquema e semântica

```json
{
  "interval_minutes": 5,
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

## Contrato do snapshot (LabConnector.snapshot)

Todos os conectores devem retornar exatamente este formato:

```python
{
    "RECORD_ID": {
        "label": "NOME PACIENTE - NOME PROPRIETÁRIO",  # str legível
        "data":  "YYYY-MM-DD",                          # data do exame
        "itens": {
            "ITEM_ID": {
                "nome":   "Nome do exame",
                "status": "Em Andamento"   # string livre, vinda do lab
            }
        }
    }
}
```

`RECORD_ID` é a chave primária de comparação entre snapshots (detecta novas entradas).
`ITEM_ID` + `status` é o que detecta mudanças de resultado.

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
| `_config` | `dict` | Lazy-loaded de config.json, recarregado a cada chamada ao loop |

`config` é uma property que carrega do disco. Após qualquer escrita via `save_config()`,
o próximo ciclo do loop pega o valor atualizado automaticamente.

---

## Variáveis de ambiente (Railway)

Todas as credenciais vivem como env vars no Railway — nunca no repositório.

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

Para desenvolvimento local, as credenciais ficam em `.secrets` (formato INI, gitignored).

---

## Deploy (Railway)

- Builder: **Railpack** (detecta Python automaticamente)
- `nixpacks.toml` define explicitamente a fase de install e o comando de start
- O comando de start **deve** ser `python -m uvicorn web.app:app --host 0.0.0.0 --port $PORT`
- Usar `uvicorn` diretamente (sem `python -m`) falha porque o PATH do container não inclui o venv bin

**Atenção:** Railpack pode ignorar `nixpacks.toml` e auto-detectar `monitor.py` como entrypoint
se o `startCommand` no Railway for deixado vazio. A solução é setar o `startCommand` via API
ou deixar o nixpacks.toml com o `[start]` correto e garantir que o Railway não sobrescreva.

---

## Como adicionar um novo laboratório

1. Criar `labs/novolab.py` herdando `LabConnector` e implementando `snapshot()`
2. Registrar em `labs/__init__.py`: `CONNECTORS["novolab"] = NovoLabConnector`
3. Adicionar entrada em `config.json`:
   ```json
   {"id": "novolab", "name": "Nome Legível", "connector": "novolab", "enabled": true}
   ```
4. Adicionar as env vars de credenciais no Railway

Nenhuma outra mudança é necessária — o loop, a UI e as notificações já suportam N labs.

---

## Como adicionar um novo canal de notificação

1. Criar `notifiers/novocanal.py` herdando `Notifier` e implementando `enviar(msg)`
2. Registrar em `notifiers/__init__.py`: `NOTIFIERS["novocanal"] = NovoCanalNotifier`
3. Adicionar entrada em `config.json`:
   ```json
   {"id": "novocanal", "type": "novocanal", "enabled": true}
   ```
4. Adicionar as env vars no Railway

---

## Rotas da web

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Dashboard: contadores + notificações |
| GET | `/exames` | Tabela de exames com filtros |
| GET | `/labs` | Gerenciar laboratórios |
| GET | `/canais` | Gerenciar canais de notificação |
| GET | `/settings` | Configurações gerais |
| GET | `/partials/notifications` | Fragmento HTMX: lista de notificações |
| GET | `/partials/lab_counts` | Fragmento HTMX: contadores por lab |
| GET | `/partials/exames` | Fragmento HTMX: tabela de exames |
| POST | `/labs/{id}/toggle` | Habilitar/desabilitar lab |
| POST | `/labs/{id}/test` | Testar conexão com lab |
| POST | `/canais/{id}/toggle` | Habilitar/desabilitar canal |
| POST | `/canais/{id}/test` | Enviar mensagem de teste |
| POST | `/settings/interval` | Atualizar intervalo de verificação |

---

## Limitações conhecidas (v1)

- **Estado em memória:** restart apaga histórico de notificações e snapshots anteriores.
  Na prática isso significa que o primeiro ciclo pós-restart nunca notifica (comportamento intencional).
- **Sem autenticação na web:** qualquer um com a URL pode ver e controlar o monitor.
- **Callmebot limitado:** 16 mensagens por 240 minutos. Desabilitado por padrão.
- **Nexio:** o parsing é frágil (depende de posição de colunas HTML). Uma mudança de layout no Pathoweb quebra o conector.
- **Config no container:** `config.json` é versionado e fica dentro da imagem. Mudanças via UI são salvas no disco do container — sobrevivem enquanto o container está vivo, mas são perdidas no redeploy.
