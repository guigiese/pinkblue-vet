# DEVLOG.md - PinkBlue Vet / Lab Monitor Module
> Log narrativo de decisões de arquitetura, problemas encontrados e lições aprendidas.
> Escrito para que uma IA (ou desenvolvedor futuro) entenda o **porquê** de cada escolha,
> não apenas o **o quê**. Ordenado cronologicamente.

Este log pertence ao repositório do módulo Lab Monitor.
Ele não descreve a plataforma PinkBlue Vet inteira, e sim as decisões, problemas e aprendizados deste módulo dentro do guarda-chuva PinkBlue Vet.

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

## Fase 13 — Protocolo de sessões paralelas e automação de CI/CD

### O problema

Com múltiplas sessões de IA podendo trabalhar no repositório ao mesmo tempo, o modelo anterior
(seção 11 do WORKING_MODEL.md "Claude + Codex") era inadequado por dois motivos:

1. Baseado em nomes de ferramentas específicas (Claude Code vs Codex) — frágil e não generalizável
2. Dependia de coordenação manual implícita, sem mecanismo de enforcement

O risco concreto: duas sessões editando o mesmo arquivo em paralelo, ambas fazendo push para
`main`, causando conflitos silenciosos ou sobrescritas.

### Por que isolamento por session-id, não por nome de IA

O nome da ferramenta de IA não é uma identidade confiável de sessão:
- Uma mesma ferramenta pode ter múltiplas instâncias ativas
- O nome pode mudar com versões ou contextos
- Um desenvolvedor humano também é uma "sessão" — precisa do mesmo protocolo

A identidade correta é a **sessão**: `YYYYMMDD + 4 hex chars aleatórios` via `secrets.token_hex(2)`.
Isso garante unicidade mesmo com múltiplas instâncias da mesma ferramenta.

### Fast-path vs Full-path via GitHub Actions

O tradeoff central: como garantir coordenação sem criar burocracia que atrasa o trabalho único?

**Decisão:** o GitHub Actions (`session-route.yml`) é o árbitro neutro.

```
PR aberto → route job conta branches session/* ativos →
  1 sessão  → fast-path: syntax check → merge imediato → deploy
  2+ sessões → full-path: syntax check + import check → merge → deploy
```

Quando há apenas uma sessão ativa, o overhead extra é apenas um job de syntax check —
prático e rápido. Quando há múltiplas sessões, a validação mais robusta protege o merge.

### O tradeoff: always-open-PR vs direct-push

**Alternativa descartada:** push direto para `main` com regra de "não tocar ao mesmo tempo".
- Problema: não há enforcement. Depende de boa vontade.
- Risco: dois pushes simultâneos com `git push --force` ou rebase acidental.

**Decisão adotada:** branch protection em `main` + sempre abrir PR de `session/` branch.
- Vantagem: o Actions é o único que pode fazer merge — enforcement automático.
- Custo: cada sessão precisa criar um branch. Aceitável porque é um comando simples.
- Custo adicional: o fast-path ainda requer um PR e um job de syntax check — mas isso é um
  mecanismo de segurança mínimo razoável.

### O Actions como árbitro neutro

Uma sessão não precisa saber se outras estão ativas — o workflow conta os branches em tempo real.
Se uma sessão começa enquanto outra está ativa, o próximo PR automaticamente ativa o full-path.
Quando a segunda sessão termina e o branch é deletado, o PR seguinte volta ao fast-path.

**Lição:** automação que observa estado do repositório é mais confiável do que coordenação
baseada em comentários manuais ou nomes de ferramentas.

### Artefatos criados nesta fase

- `.github/workflows/session-route.yml` — workflow de roteamento
- `AI_START_HERE.md` seção 5A — reescrita como protocolo operacional obrigatório
- `docs/WORKING_MODEL.md` seção 11 — reescrita como Multi-Session Protocol
- Cards Jira: PBCORE-44 (Epic), PBCORE-45 a PBCORE-50 (Tarefas)

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
| Ícones do mapa virando quadrados lavados | PNG final foi embrulhado em SVG no browser | Compor badges no build do PNG e usar `assets/rendered/*.png` direto no Cytoscape |

---

## Fase 14 — Stabilization of the architecture-map icon pipeline

### Context
The architecture-map PoC moved from generic node cards to round branded icons with a health badge and a secondary category badge.

### Symptom
After the secondary badge was added, the main icons regressed visually:
- the round PNG nodes looked washed out;
- some nodes appeared inside pale square cards again;
- the graph no longer matched the intended "logo bubble" look.

### Root cause
The graph was no longer using the final rendered PNG as the node artifact.
Instead, the PNG was wrapped in a second SVG layer in the browser so the secondary badge could be added there.

That browser-side composition was a bad fit for Cytoscape:
- the node lost the clean round PNG presentation;
- the rendered result looked like a square or faded card;
- browser cache made the regression look inconsistent between reloads.

### Final fix
- `scripts/build_architecture_map_icons.py` now bakes both badges into the final PNG.
- `poc/architecture-map/app.js` points Cytoscape directly to `assets/rendered/*.png`.
- `scripts/run_architecture_map_poc.ps1` refreshes runtime data and rebuilds icons before serving localhost.
- `app.js` appends a version token to the icon URL to reduce stale-cache confusion.

### Guardrail
For this PoC, the rendered PNG is the final icon artifact.
Do not wrap it in an extra SVG layer just to add overlays.
If badge composition changes in the future, change the icon build pipeline, not the Cytoscape node image path.

### Operational rule
When validating a visual icon change:
1. rebuild the rendered icons;
2. confirm `pinkblue-map.runtime.json` still carries `iconPath`;
3. confirm the node `background-image` resolves to `/assets/rendered/<name>.png`;
4. only then evaluate the visual result in the browser.

---

## Fase 15 - Notification policy hardening and grouped Telegram dispatch

### Context
The original notification flow mixed two concerns:
- internal change logging for the app state;
- external dispatch for Telegram/other channels.

At the same time, `detectar_novidades()` emitted one message per changed item.
That meant a record with several exams turning ready together could still fan out into noisy output.

### Product decision implemented
External notifications now follow a narrower operational policy:
- notify when a record first appears in the lab;
- notify when items from the same record transition to `Pronto`;
- group ready items by record in the same monitor cycle.

The app can still keep finer-grained internal messages, but Telegram no longer needs to mirror every micro-transition.

### Technical change
- `core.py` now builds a notification plan instead of sending raw status-change messages directly.
- Internal feed messages and external dispatch events are separated.
- External events carry signatures and pass through a short in-memory dedupe cache before dispatch.

### Why this matters
This does two things at once:
1. it reduces Telegram spam in the expected user flow;
2. it adds a second line of defense against repeated external sends if the same event is recomputed in close succession.

### Validation
`python -m unittest discover -s Testes -v`

The tests cover:
- one received event for a newly seen record;
- one grouped completion event when multiple items turn ready together;
- signature-based suppression of duplicate external dispatch.

---

## Fase 16 - Architecture map promoted from localhost PoC to app module

### Context
The architecture map started as a localhost-only PoC served by `http.server`.
That was enough for layout iteration, but not enough for consulting the map remotely.

### Final shape
The map is now exposed by the application itself:
- page route: `/ops-map/`
- live data route: `/ops-map/data/runtime.json`
- static assets route: `/ops-map-static/*`

The home page also gained an entry card for the map module.

### Important implementation detail
The cloud version does not depend on a manually refreshed `pinkblue-map.runtime.json`.
Instead:
- the app serves the HTML wrapper;
- the browser fetches live runtime data from `/ops-map/data/runtime.json`;
- the runtime payload is cached briefly in `web/ops_map.py`;
- the rendered PNG icons are served as static assets.

This keeps the old local PoC usable while making the feature available in Railway.

### Guardrail
Do not tie the cloud map to a pre-generated runtime file only.
For the hosted version, the runtime data must remain refreshable by the app itself, otherwise the visual drifts out of date quickly.

---

## Fase 17 - Core/platform discovery and incubator framing

### Context
After stabilizing the first delivery waves, the next need was not another feature spike.
It was clarity:

- what the platform must do next to stop relying on memory/files as its operational base;
- how to treat secrets, repo hygiene and observability without prematurely overengineering;
- how to describe the next incubated products without confusing them with the current Lab Monitor scope.

### What was consolidated
Two discovery notes were added under `docs/discovery/`:

- `2026-04-01-core-platform-foundations.md`
- `2026-04-01-pbinc-crm-financeiro.md`

These notes do not implement the next phase.
They define the shape of the next phase.

### Core/platform direction
The recommended next foundation is:

- `PostgreSQL on Railway` as the first official platform database;
- `SQLAlchemy 2.0 + Alembic + Pydantic Settings` as the persistence/config stack;
- session-based auth with minimal roles for the current server-rendered app;
- operational observability built around health endpoints, sync runs, notification events and `/ops-map/`.

Also clarified:

- Railway variables are the pragmatic next secret layer;
- Vault is a later maturity step, not the first mandatory move;
- `telegram_users.json`, runtime-mutated `config.json`, hardcoded fallbacks and tokenized git remotes are active debt, not acceptable steady state.

### Incubator direction
Two large future projects were framed without implementation:

- a veterinary CRM focused on relationship/segmentation/reactivation rather than replacing the core clinic system;
- a financial reconciler focused on matching SimplesVet expectations against real bank/PSP/adquirente settlements.

Both are intentionally defined as complementary to SimplesVet, not replacements for what it already does.

---

## Fase 18 - Card sandbox realigned to the exam list language and mobile ops-map tightened

### Context
The first card sandbox helped explore hierarchy and density, but it also drifted away from the
real interaction model of the Lab Monitor exam list.

At the same time, the hosted `/ops-map/` worked well on desktop but mobile still forced too much
scrolling before the graph appeared.

### What changed
- the card sandbox was kept as a separate module and exposed through `/sandboxes/cards/`;
- the main sandbox direction was rebuilt around stacked rows with horizontal reading, closer to the
  current exam list structure;
- the old side-by-side/square idea was preserved only as discovery, not as the active implementation track;
- the mobile version of `/ops-map/` was compressed to bring the graph closer to the first fold and
  cut duplicated explanation blocks.

### Why this matters
The sandbox now behaves like a safe visual lab:
- close enough to the product language to make approval meaningful;
- isolated enough to avoid contaminating the active interface with half-decided UX experiments.

The ops-map change matters for the same reason:
- mobile should reach the graph quickly;
- operational summary should support the graph, not delay access to it.

---

## Fase 19 - Platform workspace reframing and zero-cost persistence phase

### Context
The repository and part of the backlog were still telling an exam-first story,
while the user direction had already moved to a platform-first story:

- PinkBlue Vet as the platform;
- Lab Monitor as one module under it;
- future CRM and financial modules behind the same auth and shell;
- persistence and auth treated as shared capabilities, not exam-only features.

### What changed
- Jira scope was realigned so platform auth stays in `PBCORE-16`;
- `PBEXM-42` was narrowed to Lab Monitor integration with shared auth;
- a new structural track was opened in `PBCORE-60`;
- docs were updated to describe the repository as a platform workspace.

### Phase-1 persistence decision
For the current zero-cost phase, the recommended path shifted from
"go straight to managed Postgres" to a simpler bridge:

- `SQLite`
- `SQLAlchemy`
- `Alembic`
- `Pydantic Settings`
- file stored on `Railway Volume`

### Why this was chosen
This choice minimizes friction while still solving the immediate problems:

- survive redeploys;
- support shared auth;
- persist operator settings;
- enable incremental sync without full re-scrape;
- keep a clean migration path toward a future managed relational database.

### Guardrail
This is a phase decision, not a final forever architecture.
The long-term discoveries for richer persistence, deploy segmentation, and
broader infra remain valid and intentionally stay open in Jira.

---

## Fase 20 - Plataforma compartilhada executavel: auth, persistencia e shell comum

### Context
Depois da discovery inicial da plataforma, a necessidade deixou de ser apenas "decidir a direcao".
Precisavamos colocar uma primeira camada real no ar sem aumentar custo e sem quebrar o modulo estavel.

### O que entrou de verdade
- `pb_platform/settings.py` centralizou configuracao operacional da plataforma;
- `pb_platform/storage.py` introduziu um store compartilhado em `SQLite` via `sqlite3`;
- `pb_platform/security.py` passou a cuidar de hash de senha e tokens de sessao;
- `pb_platform/auth.py` passou a proteger a home, o Lab Monitor, o ops-map e as sandboxes;
- `web/app.py` ganhou login, logout, gestao simples de usuarios e rota de tolerancias;
- `web/state.py` passou a persistir config, snapshots, erros e checks por laboratorio;
- `notifiers/telegram.py` deixou de depender apenas de arquivo e passou a ler/escrever subscriptions pela store;
- `core.py` passou a deduplicar eventos externos tambem de forma persistente.

### Decisao pragmatica da fase 1
A discovery anterior apontava `SQLite + SQLAlchemy + Alembic` como boa ponte.
Na implementacao executavel, a escolha ficou ainda mais simples:

- `SQLite`
- `sqlite3` da stdlib
- schema inicial criado pela aplicacao
- sessao por cookie

### Por que simplificamos ainda mais
- entrava mais rapido;
- mantinha custo zero real;
- removia atrito de dependencia nova no momento em que o objetivo era validar auth + persistencia compartilhada;
- continuava compativel com uma migracao futura para stack mais robusto.

### Guardrail importante
Esta decisao nao invalida a trilha futura de `SQLAlchemy`, `Alembic` e `Postgres`.
Ela apenas evita overengineering na primeira camada funcional da plataforma.

### Persistencia que passou a existir
O store compartilhado agora cobre:
- usuarios;
- sessoes;
- subscriptions do Telegram;
- configuracoes persistidas do modulo;
- snapshots e metadados por laboratorio;
- log de eventos externos para dedupe;
- tolerancias por exame.

### Estrategia de sync
O app agora trata a base local persistida como fonte principal de operacao.
Os conectores passam a carregar contexto de sync para evitar depender sempre de uma revarredura cega,
e o BitLab ja usa `days_back` derivado do contexto persistido.

### Shell visual
A plataforma passou a ter um shell proprio para:
- login;
- home;
- administracao de acessos.

O shell do Lab Monitor continua separado, mas conectado visualmente ao restante da plataforma.

### Validacao
- `python -m py_compile` nos modulos centrais alterados;
- `python -m unittest discover -s Testes -v`;
- smoke autenticado das rotas principais da plataforma e do modulo.

---

## 2026-04-07 — Reorganização geral da plataforma

### Contexto
O projeto cresceu organicamente desde o início e acumulou inconsistências de nomenclatura,
estrutura de arquivos e organização de ferramentas. Esta sessão executou uma reorganização
geral com base em revisão completa do estado do workspace.

### Decisões executadas

**Git e GitHub:**
- Repositório renomeado de `monitor-exames-bitlab` → `pinkblue-vet`
- Auto-delete de branches após merge ativado no GitHub
- Tag `v1.0` criada em main como baseline da reorganização
- ~35 branches `session/*` acumuladas (já mergeadas via squash) foram deletadas local e remotamente
- Política: `git fetch --prune` no início de cada sessão; branches limpas automaticamente após merge

**Railway:**
- Projeto renomeado de `monitor-exames` → `pinkblue-vet`
- Serviços obsoletos deletados: `creative-miracle` e `monitor-exames-bitlab`
  (sem tráfego desde 29-30/03/2026, apenas variáveis RAILWAY_* automáticas)
- Serviço de produção `pinkblue-vet` mantido com volume persistente em `/data`

**Módulo Financeiro:**
- Consolidado sob `modules/financeiro/`: tui (ex-`tools/folha-tui/`),
  web (ex-`tools/folha-web/`), tests (ex-`Testes/test_financeiro_*.py`)
- `folha.bat` e `folha-web.bat` da raiz removidos
- `node_modules/` adicionado ao `.gitignore`

**Jira:**
- PBFIN descoberto como 4º projeto existente (não estava documentado)
- Card PBCORE-64: consolidação futura PBEXM + PBCORE + PBFIN → projeto único PB
- Card PBINC-24: discovery para base de conhecimento centralizada da plataforma
- Workflow definido para entrega: Backlog → Descoberta → Refinamento → Pronto pra dev → Em andamento → Em revisão → Concluído

**Vocabulário canônico estabelecido:**
Plataforma / Módulo / Repositório / Projeto Jira / Serviço / Sessão
Documentado em WORKING_MODEL.md seções 0 e 0A.

**Decisão de design do workspace documentada:**
Estrutura de entrada de IAs (CLAUDE.md/AGENTS.md → SESSION_PRIMER.md → AI_START_HERE.md)
é intencional e não deve ser simplificada sem card PBCORE.

### O que ficou pendente
- Consolidação Jira (PBCORE-64): criação do projeto PB + migração de cards (tarefa dedicada)
- Atualização do workflow Jira (adicionar etapa Refinamento nos projetos existentes)
- Pasta local ainda se chama `SimplesVet` — baixo impacto, pode ser renomeada a qualquer momento

---

## Fase 18 — Política de integridade Git entre local, remoto e worktrees

### Contexto

O protocolo já exigia `session/*` branch + PR para proteger `main`, mas ainda deixava uma lacuna:
sessões ativas podiam acumular trabalho útil apenas no ambiente local, sem upstream e sem regra
clara para worktrees temporárias.

Na prática isso criava três riscos:
- branch ativa existir só na máquina local;
- `main` local ficar tratada como área de trabalho em vez de referência alinhada ao remoto;
- worktrees extras virarem cópias "semi-oficiais" sem promoção controlada ao histórico principal.

### Decisão executada

Os documentos operacionais foram refinados para deixar explícito que:
- GitHub/remoto é a referência operacional para qualquer sessão ativa;
- `git fetch --prune origin` abre toda sessão;
- branch `session/*` com trabalho útil deve ser publicada com `git push -u` após o primeiro commit relevante ou antes de 30-60 min;
- branch local-only só é aceitável como spike curto, explicitamente temporário e documentado;
- `main` local deve acompanhar `origin/main` e não é branch de trabalho;
- worktree extra é ferramenta de paralelismo, não fonte de verdade;
- toda worktree temporária deve ser removida após merge, abandono ou arquivamento da sessão;
- antes de pausar/encerrar sessão, o mínimo é verificar `git status --short --branch`, `git branch -vv` e `git worktree list`.

### Documentos atualizados

- `SESSION_PRIMER.md`
- `AI_START_HERE.md`
- `docs/WORKING_MODEL.md`
- `README.md`

### Objetivo da mudança

Preservar o acordo já existente (`session/*` + PR + branch protection em `main`) e completar o
que faltava para integridade operacional: alinhamento entre ambiente local e remoto, handoff entre
sessões e uso disciplinado de worktrees.
