# DEVLOG.md — Lab Monitor (SimplesVet)
> Log narrativo de decisões de arquitetura, problemas encontrados e lições aprendidas.
> Escrito para que uma IA (ou desenvolvedor futuro) entenda o **porquê** de cada escolha,
> não apenas o **o quê**. Ordenado cronologicamente.

---

## Fase 1 — Scraping do BitLab

### Objetivo
Acessar o portal https://bitlabenterprise.com.br/bioanalises/resultados e extrair dados de exames.

### Problema: o portal é um SPA React
A primeira abordagem natural seria Selenium/Playwright para renderizar o JavaScript.
Mas isso traz dependências pesadas (Chrome, chromedriver) incompatíveis com o tier gratuito do Railway.

### Solução: engenharia reversa da API REST
Usando Chrome DevTools Protocol (CDP) para capturar o tráfego de rede durante o login manual,
identificamos que o frontend consome uma API REST própria em `/api/v1/`:

- `POST /api/v1/SignIn` → retorna JWT
- `POST /api/v1/Requisicao?pageNumber=1&pageSize=200` → lista de requisições (com filtro de datas)
- `POST /api/v1/ItemRequisicao` → itens de uma requisição específica

O JWT é Bearer token padrão. Sem necessidade de browser — `requests` puro.

**Decisão:** usar a API interna diretamente. Mais rápido, mais estável e sem dependências pesadas.
**Risco:** APIs internas não são documentadas e podem mudar sem aviso.

### Parâmetros importantes
- `cdConvenio`: código do convênio da clínica (1170 para esta clínica específica)
- `cdPosto`: código do posto (8)
- A busca por requisições exige intervalo de datas — usamos os últimos 30 dias por padrão

---

## Fase 2 — Notificações WhatsApp (Callmebot)

### Objetivo
Notificar via WhatsApp quando novos exames aparecerem ou mudarem de status.

### Problema crítico: flood no primeiro boot
Na primeira execução em produção (Railway), o estado anterior estava vazio.
O código tratou todos os ~30 exames existentes como "novos" e disparou 30+ mensagens simultâneas.

O Callmebot tem rate limit de **16 mensagens por 240 minutos**. A fila saturou.
As mensagens nunca chegaram ao destinatário.

### Solução: guarda de primeiro boot
```python
if not anterior:
    print("  Primeira execução — estado salvo.")
    # salva o estado atual sem notificar
    continue
```
**Regra:** se o snapshot anterior está vazio, salvar o estado atual e pular notificações.
Isso acontece apenas no primeiro ciclo após cada restart do serviço.

### Migração para Telegram
O Callmebot continuou problemático mesmo após a correção (rate limit atingido, fila cheia).
Migramos para o Telegram Bot API que:
- Não tem rate limit prático para uso individual
- Suporta HTML formatting nativo (`parse_mode=HTML`)
- É mais confiável para uso em produção

O WhatsApp permanece no código mas desabilitado por padrão (`"enabled": false` em config.json).
Mantido para uso futuro ou para quem preferir.

---

## Fase 3 — Arquitetura escalável multi-lab multi-notifier

### Motivação
O usuário queria adicionar o laboratório Nexio. Em vez de um script monolítico,
projetamos para suportar N labs e N canais sem mudanças no core.

### Design adotado

**Abstract Base Classes:**
```python
class LabConnector(ABC):
    def snapshot(self) -> dict[str, dict]: ...

class Notifier(ABC):
    def enviar(self, msg: str) -> None: ...
```

**Registries de dicionário:**
```python
CONNECTORS = {"bitlab": BitlabConnector, "nexio": NexioConnector}
NOTIFIERS   = {"telegram": TelegramNotifier, "whatsapp": WhatsappNotifier}
```

**config.json como orquestrador:**
O arquivo de configuração declara quais labs e notifiers estão ativos.
O loop lê a config a cada ciclo — mudanças na UI refletem no próximo ciclo automaticamente.

**Decisão de não usar herança pesada:** os conectores apenas herdam a ABC e implementam
`snapshot()`. Toda a lógica de comparação e notificação está em `core.py`, não nos conectores.
Isso facilita testar cada conector isoladamente.

---

## Fase 4 — Conector Nexio

### Problema: autenticação Spring Security
O Nexio usa o portal Pathoweb (`pathoweb.com.br`) com Spring Security form login.
Não há API REST — a autenticação é por formulário e a sessão é mantida por cookie.

```python
session.post("/j_spring_security_check", data={
    "j_username": ...,
    "j_password": ...,
    "_spring_security_remember_me": "on"
})
```

A lista de exames é retornada como HTML de uma tabela, parseada com BeautifulSoup.

### Bug: coluna errada no parsing HTML
A tabela tem 9 colunas: `[0]checkbox | [1]Exame | [2]Senha | [3]Nome | ...`

O código original usava `cols[0]` como número do exame. Como a coluna 0 é um checkbox
(célula vazia), todos os exames recebiam `""` como ID e eram descartados.
**Resultado:** conector retornava 0 exames silenciosamente.

**Correção:** usar `cols[1]` (coluna "Exame") como identificador.

**Lição:** ao fazer parsing de HTML, validar com um print dos primeiros registros antes
de assumir que o mapeamento de colunas está correto.

---

## Fase 5 — Interface Web

### Decisão: FastAPI + Jinja2 + HTMX, sem frontend framework
O usuário queria uma interface web com custo zero adicional.

**Alternativas consideradas:**
- React/Next.js: requer Node.js, build step, e idealmente um CDN separado
- Streamlit/Gradio: opiniados demais, difíceis de customizar
- FastAPI + Jinja2 + HTMX: sem build step, sem JS framework, HTMX faz atualizações parciais via atributos HTML

**Decisão:** HTMX para reatividade sem JS customizado. TailwindCSS via CDN para estilização.
Ambos carregados via CDN sem nenhum asset local.

### Compartilhamento de estado entre thread e web
O monitor roda em uma `threading.Thread` daemon iniciada no `lifespan` do FastAPI.
A web precisa ler os dados que o monitor coleta.

**Solução:** `AppState` como singleton de módulo:
```python
# web/state.py
state = AppState()  # instância única

# web/app.py
from web.state import state  # importa a mesma instância

# core.py
def run_monitor_loop(state=None):  # recebe o state como parâmetro
```

Isso evita variáveis globais espalhadas e torna o core testável standalone (passa `state=None`).

### HTMX para atualizações parciais
- Dashboard: contadores por lab atualizados a cada 60s, notificações a cada 30s
- Exames: tabela atualizada a cada 5 minutos (alinhado ao intervalo do monitor)
- Toggle e test: respostas inline sem reload de página

---

## Fase 6 — Deploy no Railway

### Problema: Railway CLI não funciona no Windows Git Bash
`railway whoami` retornava "Unauthorized" mesmo com token válido setado via `railway login`.
Causa provável: problema de armazenamento de credenciais do keychain no Windows Git Bash.

**Solução:** contornar completamente o CLI e usar a Railway GraphQL API v2 diretamente via Python.
Todas as operações (criar projeto, setar env vars, fazer deploy, checar logs) foram feitas
via `requests.post("https://backboard.railway.app/graphql/v2", ...)`.

**Lição:** o Railway GraphQL API é poderoso o suficiente para automatizar tudo.
Documentado em https://docs.railway.app/reference/public-api

### Problema: repositório privado não suportado por githubRepoDeploy
A mutation `githubRepoDeploy` do Railway só funciona com repositórios públicos.

**Solução:** tornar o repositório público e mover todas as credenciais para env vars do Railway.
O `.secrets` local permanece para desenvolvimento, mas **nunca** é commitado (está no .gitignore).

### Problema: startCommand sobrescrevendo o Procfile
Ao setar `startCommand` via API para testar, esse valor teve prioridade sobre o Procfile.
O Procfile foi ignorado silenciosamente.

**Regra:** se `startCommand` está setado (não vazio), ele prevalece sobre Procfile e nixpacks.toml.
Para limpar: `serviceInstanceUpdate(input: {startCommand: ""})`.

### Problema: `uvicorn: command not found`
O container usa um venv em `/app/.venv`. O PATH do bash não inclui `/app/.venv/bin`.
Usar `uvicorn web.app:app` falha com "command not found".

**Solução:** `python -m uvicorn web.app:app` — invoca o módulo via Python, que encontra
o uvicorn no venv atual.

### Problema: `No module named uvicorn` (cache de build)
Este foi o mais insidioso. O Railway construiu a imagem com cache de um build anterior,
antes de uvicorn ser adicionado ao requirements.txt. O uvicorn estava no requirements.txt
mas não na imagem — o Railpack reutilizou a camada de cache do venv.

**Sintomas:** deployment com status SUCCESS, logs mostravam apenas o monitor thread rodando,
sem nenhuma linha de log do uvicorn. HTTP 000 (sem resposta).

**Tentativas que não funcionaram:**
1. Criar `nixpacks.toml` com `pip install -r requirements.txt` explícito → cache ainda reutilizado
2. Setar `startCommand` via API e fazer redeploy → mesmo problema, nova imagem com cache antigo
3. `serviceInstanceRedeploy` → usava a última imagem, sem rebuild

**Solução que funcionou:** modificar o `requirements.txt` (adicionando comentários)
para invalidar o hash do arquivo e forçar o Railpack a reconstruir a camada de dependências.
O novo deploy criou um serviço novo com build completamente limpo.

**Observação:** o `githubRepoDeploy` com um commit novo **sempre** faz rebuild.
O `serviceInstanceRedeploy` pode reutilizar a imagem anterior.

### Estado final do deploy
- Railpack detecta Python, cria venv em `/app/.venv`, instala requirements
- nixpacks.toml garante que o comando de start é `python -m uvicorn web.app:app --host 0.0.0.0 --port $PORT`
- O monitor thread é iniciado no `lifespan` do FastAPI — sobe junto com o servidor HTTP

---

## Decisões de design que vale registrar

### Por que não SQLite ou Redis?
Railway tier gratuito: sem volumes persistentes. SQLite funcionaria dentro do container mas
seria perdido a cada redeploy. Redis adicionaria custo.
O estado em memória é suficiente: o que importa são as notificações em tempo real,
não o histórico.

### Por que monitor.py existe separado de web/app.py?
`core.py` foi extraído para funcionar tanto standalone (para debugging local rápido)
quanto embutido na web. `monitor.py` é o entrypoint standalone que passa `state=None`.
Em produção, apenas o uvicorn é executado — `monitor.py` não é usado.

### Por que config.json é versionado?
As configurações de labs e notifiers habilitados são parte da "identidade" do serviço,
não credenciais. Versionar permite rastrear mudanças de configuração junto ao código.
As credenciais **nunca** são versionadas.

### Por que HTMX em vez de WebSockets?
WebSockets requerem conexão persistente e complicam o deploy. HTMX com polling periódico
é suficiente para o caso de uso (verificações a cada 5 minutos, UI para monitoramento,
não para alarmes em tempo real). Mais simples, mais fácil de debugar.

---

## Erros que não devem se repetir

| Erro | Causa | Como evitar |
|---|---|---|
| Flood de notificações no boot | Estado vazio tratado como "tudo novo" | Guarda de primeiro boot em `core.py` — não remover |
| `uvicorn: command not found` | PATH do container não inclui venv bin | Sempre usar `python -m uvicorn` |
| Cache de build silencioso | Railpack reutiliza camada de venv | Se uvicorn/deps somem, invalidar cache modificando requirements.txt |
| startCommand sobrescreve Procfile | Valor não vazio tem prioridade absoluta | Checar `startCommand` via API antes de debugar o Procfile |
| Nexio retornando 0 exames | Coluna 0 do HTML é checkbox vazio | Sempre mapear colunas com print antes de assumir índices |
| Callmebot rate limit | 16 msg/240min — fácil de estourar | Manter desabilitado por padrão; usar Telegram para produção |
