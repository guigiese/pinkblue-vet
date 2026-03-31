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

### CRÍTICO: githubRepoDeploy sempre cria um novo serviço
Descoberto após múltiplos serviços órfãos aparecerem no projeto Railway.
A mutation `githubRepoDeploy` **sempre** cria um novo serviço — não atualiza o existente.

**Isso causou:**
- URL mudando a cada deploy
- Histórico de deploys fragmentado
- Custos acumulados de serviços não utilizados
- Perda de env vars configuradas no serviço original

**Solução definitiva:** `serviceInstanceDeploy(serviceId, environmentId, commitSha)`.
Essa mutation deploya no serviço existente, pegando o commit exato do GitHub.
Criado `deploy.py` para encapsular este workflow e nunca mais errar.

```python
# CORRETO — atualiza serviço existente
serviceInstanceDeploy(serviceId="...", environmentId="...", commitSha="abc123")

# ERRADO — sempre cria novo serviço
githubRepoDeploy(projectId="...", branch="main")
```

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

## Fase 7 — Telegram multi-usuário e layout mobile

### Motivação
O usuário queria poder usar o sistema pelo celular com qualidade, e que mais de uma pessoa
pudesse receber as notificações do Telegram sem precisar de intervenção técnica.

### Design: bot com auto-inscrição
Em vez de configurar chat IDs manualmente em variáveis de ambiente, implementamos um
sistema de inscrição por comando no próprio bot.

```python
# telegram_polling.py — thread daemon rodando em paralelo ao uvicorn
/start    → boas-vindas neutras, sem mencionar a clínica
/assinar  → adiciona chat_id ao telegram_users.json
/sair     → remove chat_id do telegram_users.json
/status   → informa se está inscrito
```

**Decisão de design:** `/start` propositalmente neutro (sem mencionar clínica ou labs).
O bot é público — qualquer usuário do Telegram pode interagir com ele pelo username.
O comando para entrar na lista é `/assinar`, não `/start`, evitando inscrições acidentais.

**Persistência:** os chat IDs ficam em `telegram_users.json` (gitignored).
**Limitação conhecida:** arquivo perdido a cada redeploy. Usuários precisam re-assinar.
Sem impacto operacional relevante — o processo leva 5 segundos.

### Layout mobile responsivo
A interface foi desenhada mobile-first:
- Desktop: sidebar fixa à esquerda, conteúdo à direita
- Mobile: barra superior com hamburger menu, sidebar deslizante com overlay

Tabela de exames com duas renderizações:
- Mobile (`md:hidden`): cards empilhados com paciente, status, lab, número e data
- Desktop (`hidden md:block`): tabela tradicional com colunas

TailwindCSS CDN suporta isso nativamente com os prefixos `md:` sem nenhum build step.

---

## Fase 8 — Arquitetura escalável: prefix /labmonitor e landing page

### Motivação
O usuário queria uma estrutura que suportasse múltiplos apps no futuro sob o mesmo domínio.
Exemplo: `/labmonitor`, `/financeiro`, `/agenda`, etc.

### Design adotado
**FastAPI APIRouter com prefix:**
```python
router = APIRouter(prefix="/labmonitor")
# app.include_router(router)

# A landing page fica em app diretamente:
@app.get("/")
async def landing(): ...
```

A raiz `/` exibe `index.html` — landing page standalone listando os apps disponíveis.
Cada app fica completamente encapsulado sob seu prefix.

**Sem nenhum custo adicional** — é apenas organização de código. A infra Railway não muda.

### Renomeação do serviço Railway
O serviço foi renomeado para `pinkblue-vet` para refletir a identidade real da clínica.
A URL gerada pelo Railway passou a ser `https://pinkblue-vet-production.up.railway.app`.

**ATENÇÃO:** renomear o serviço no Railway muda a URL automaticamente gerada.
Se houver um domínio customizado configurado, ele permanece. Sem domínio customizado,
a URL muda junto com o nome.

### Limpeza de serviços órfãos
O projeto Railway acumulou 4+ serviços órfãos de deploys incorretos com `githubRepoDeploy`.
Todos foram deletados. O único serviço ativo é `215d2612`.

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

## Fase 9 — Deep links, horário de liberação, limpeza e link Home

### Contexto
Sessão de refinamento do Lab Monitor. Objetivo: melhorar qualidade dos dados exibidos e limpar arquivos legados.

### Limpeza de arquivos legados
`monitor_exames.py` e `monitor_telegram.py` eram scripts monolíticos da v1 (WhatsApp/Telegram) completamente supersedados pela arquitetura multi-lab. Tinham credenciais hardcoded no código. Removidos.
`Conciliador/teste_api.py` era um script de exploração sem propósito atual. Removido junto com o diretório.
`monitor.py` foi simplificado para um thin wrapper de 3 linhas que chama `run_monitor_loop(state=None)` — mantido apenas como runner local sem web server.

### Link Home na sidebar
`base.html` recebeu link "Início" para `/` no topo da nav, com ícone SVG de casa e divisor visual separando do menu do Lab Monitor.

### Investigação de APIs (resultados)
- **BitLab `/ItemRequisicao`**: retorna apenas status/metadata. Sem valores numéricos, sem referências, sem unidades. Resultados só existem no PDF do laudo.
- **BitLab deep link**: a SPA usa a rota `/bioanalises/laudos/{req["id"]}` onde `req["id"]` é o campo `id` da resposta da API (string encoded como `ugaz4HXboGHZ5PsvFyFJuA@3D@3D`). URL testada e funcional.
- **Nexio deep link**: não há URL pública e estável por exame. O visualizador `visualizarLaudoAjax?id={exame_id}` requer sessão ativa. O PDF é gerado com path temporário e não-reutilizável. Link mantido para o portal raiz como fallback.
- **Nexio `exame_id`**: o ID interno (campo `value` do radio input na tabela HTML) foi adicionado ao snapshot via `"portal_id"`.

### Horário de liberação
Nenhum lab expõe timestamp de liberação na API de status. Solução: `core._stamp_liberados()` injeta `liberado_em` (ISO) no item no momento exato em que o monitor detecta a transição para Pronto. O timestamp sobrevive nos ciclos seguintes via carry-over do snapshot anterior.

Exibição na UI: `✓ DD/MM HH:MM` em verde no desktop; `Lib. DD/MM HH:MM` no mobile. Substitui a data do exame quando disponível.

### Contrato do snapshot — campos adicionados
- `record["portal_id"]`: ID do exame no sistema do lab, usado por `state.py` para construir deep links.
- `item["liberado_em"]`: timestamp ISO injetado por `core._stamp_liberados()`, preservado entre ciclos.
- `item["dtColeta"]`: timestamp de coleta do BitLab (disponível na API, armazenado para uso futuro).

### Jira — investigação
Token existente no `.secrets` está expirado (HTTP 401 na API). Workspace `guigiese.atlassian.net` existe e está acessível, mas sem projetos criados. Necessário gerar novo token em `id.atlassian.com/manage-profile/security/api-tokens` para estruturar o Jira.

---

## Fase 10 — Refinamentos de UI, busca, bug de duplicação e dashboard por protocolo

### Bug: duplicação de notificações Nexio + "Arquivo morto" ghost
O `normalize_status()` era case-sensitive. "Arquivo morto" → "Arquivado" funcionava, mas "Arquivo Morto" (M maiúsculo) passava como desconhecido. No ciclo seguinte, o raw armazenado era "Arquivado", o novo era "Arquivo Morto" → normalized comparavam diferente → nova notificação disparada.

**Fix:** `normalize_status` faz `.strip().lower()` antes do lookup. STATUS_MAP agora tem todas as chaves em lowercase.

**Regra:** sempre que adicionar novos mapeamentos ao STATUS_MAP, usar chaves em lowercase.

### Arquivado/Cancelado não contam mais pra dias em aberto
`_STATUS_DONE = {"Pronto", "Arquivado", "Cancelado"}` — qualquer status nesse set zera `dias_em_aberto`.

### Dashboard redesenhado — contagem por protocolo
`get_lab_counts()` agora conta GRUPOS (protocolos) em vez de itens individuais. Categorias: Pronto, Parcial, Em Andamento, Total. Barra de progresso visual por lab. Filtros de lab por tab.

### BitLab pageSize
Aumentado de 200 para 500 para capturar mais histórico.

### BitLab deep links
Links `laudos/{portal_id}` tecnicamente corretos mas requerem sessão ativa no portal BitLab (SPA com JWT em localStorage). Link abre a SPA mas se o usuário não estiver logado naquela aba, vai para login. Limitação conhecida — sem solução cross-origin sem armazenar token do usuário. Link mantido pois usuários logados conseguem acessar.

### Busca melhorada
`_search_match(q, text)`: accent-insensitive (unicodedata NFD), case-insensitive, multi-word sequencial. Cada palavra do query deve aparecer em ordem no texto, com qualquer conteúdo entre elas.

### Visual
- Sidebar: logo com ícone clicável como home. Link "Início" isolado removido.
- Toggle switches: CSS animados (cinza → índigo) em Labs e Canais.
- SVG icons na sidebar em vez de emojis.
- Dashboard com cards individuais por indicador + progress bar.

---

## Fase 11 — Resultados inline, alertas em cascata e parser bioquímica BitLab

### Objetivo
Trazer resultados numéricos do BitLab diretamente na interface, com alertas visuais por exame e por grupo, sem custo financeiro adicional.

### Descoberta do endpoint de resultados
A API `/ItemRequisicao` não retorna valores numéricos — apenas status e metadata.
Engenharia reversa da SPA BitLab revelou: `GET /api/v1/ItemRequisicao/{item_id}?type=Html`
retorna os resultados como HTML absoluto-posicionado comprimido com zlib (magic bytes `78 da`).

**Erro inicial:** tentativa com `gzip.decompress()` → falhou. Correto é `zlib.decompress()` com decode `latin-1`.

### Dois layouts HTML distintos no mesmo endpoint
O parse inicial funcionava só para hemogramas (Layout A). Bioquímica (CREATININA, TGP etc.) retornava vazio.

**Layout A (hemograma):** nome + valor bold + referência `X a Y` todos na mesma linha.
**Layout B (bioquímica):** valor não-bold na linha do parâmetro; referências por espécie (Canino/Felino/Ovino/Bovino) em linhas subsequentes à direita.

**Solução:** parser com detecção automática de layout e look-ahead por espécie. Alert logic para Layout B: fora de TODOS os ranges → red/yellow; fora de ALGUNS → yellow; dentro de todos → None.

### Cache stale após parser quebrado
O `enrich_resultados()` carregava `alerta=None + resultado=[]` do ciclo anterior como cache válido, impedindo re-fetch mesmo após fix do parser.

**Fix:** só carry-forward quando `resultado` (rows) é não-vazio. Cache vazio = falha anterior = refetch obrigatório.

### Design do ciclo de enriquecimento (zero custo extra)
`enrich_resultados()` é chamado por `core.py` após `_stamp_liberados()`.
- Items já com `resultado` não-vazio → carry-forward (zero HTTP).
- Items recém-Pronto sem cache → fetch + parse + store.
- Próximos ciclos: zero HTTP adicional para exames estáveis.

### Alertas em cascata
- `alerta` por item: calculado no `parse_resultado()`.
- `alerta_geral` por grupo: `max()` dos alertas dos itens Pronto (em `get_exames()`).
- Template propaga badge no header do grupo e dot colorido por linha de exame.
- Feed "Últimos Liberados" no dashboard colorido pelo `alerta_geral`.

---

## Fase 12 — Estrutura Jira e governança com Codex em paralelo

### Contexto
O Codex atuou em paralelo ao Claude Code mapeando artefatos do Lab Monitor sem alterar código de produção (guideline respeitada: apenas docs, scripts e PoC local).

### Trabalho do Codex
- Criou 3 projetos Jira: PBEXM, PBCORE, PBINC com workflows corretos via `apply_pb_jira_workflow.ps1`.
- Estruturou backlog inicial com ~30 cards distribuídos entre os projetos.
- Expandiu `AI_START_HERE.md` (guardrail de trabalho paralelo, seção 5A) e `WORKING_MODEL.md` (PBCORE scope policy, seção 1A).
- Criou `poc/architecture-map/`: grafo interativo local de artefatos PinkBlue com health checks ao vivo.

### Verificação de integridade (2026-03-31)
Commits no branch main entre as sessões: zero. Os arquivos do Codex estavam como untracked/unstaged, confirmando que nenhuma alteração de produção foi feita. Todos os arquivos foram commitados com atribuição clara.

### Lição aprendida: modelo de colaboração
Para trabalho paralelo entre IAs com artefatos compartilhados:
- IAs devem trabalhar em branches separadas ou diretórios isolados.
- Somente um AI é "deploy owner" a cada momento — o outro trabalha em descoberta/docs.
- Jira como ponto de coordenação: cada AI comenta no card antes de iniciar e ao finalizar.
- Ver seção "Modelo de Colaboração Claude + Codex" em `docs/WORKING_MODEL.md`.

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
| githubRepoDeploy cria novo serviço | Bug/comportamento da mutation Railway | SEMPRE usar serviceInstanceDeploy(commitSha=...) via deploy.py |
| URL muda após renomear serviço | Railway regenera URL baseada no nome | Configurar domínio customizado ou avisar usuários após renomear |
| telegram_users.json perdido | Sem volume persistente no Railway | Usuários enviam /assinar novamente após deploy — processo simples |
| BitLab connect timeout | Servidor lento ou instável | Erro capturado em last_error e exibido na UI; monitor continua os outros labs |
