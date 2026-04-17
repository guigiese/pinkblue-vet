# Plano de Execução — Waves 1 a 5
**Data:** 2026-04-17  
**Escopo:** Todos os bugs e dívidas técnicas priorizados  
**Execução:** Sessão única de IA — seguir blocos na ordem definida

---

## Setup da sessão (antes de qualquer bloco)

```bash
# 1. Gerar session-id
python -c "import secrets; from datetime import date; print(f'{date.today().strftime(\"%Y%m%d\")}-{secrets.token_hex(2)}')"

# 2. Atualizar refs locais
git fetch --prune origin

# 3. Criar branch
git checkout -b session/20260417-XXXX

# 4. Confirmar servidor local sobe
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

Criar um único card de sessão no Jira ou usar PBVET-58 (auditoria estrutural) como âncora se nenhum card de sessão for criado.

---

## Bloco A — Segurança (PBVET-13) `[CRÍTICO — executar primeiro]`

**Cards:** PBVET-13  
**Estimativa:** 30 min  
**Risco:** Alto (não há rollback fácil de git history); baixo risco operacional pois Railway já tem as env vars

### Passos

1. **Remover `.secrets` do tracking git**
   ```bash
   git rm --cached .secrets
   echo ".secrets" >> .gitignore  # verificar se já está
   git add .gitignore
   git commit -m "security: remover .secrets do tracking git (PBVET-13)"
   ```

2. **`deploy.py` — remover UUIDs hardcoded**
   - Linhas 20-22: remover `default="215d2612-..."` e similares
   - Se env var ausente, imprimir erro claro e abortar

3. **`pb_platform/settings.py` — fallback de DB**
   - Linhas 67-70: remover string `postgresql+psycopg2://pinkblue:change-me-dev@...` como fallback
   - Manter fallback para SQLite apenas quando `is_dev=True`

4. **`pb_platform/auth.py` — CSRF secret estável**
   - Linha 26: CSRF_SECRET não deve reger a cada restart
   - Gerar uma vez no módulo: `_CSRF_SECRET = settings.csrf_secret or os.environ.get("PB_CSRF_SECRET") or _generate_stable_secret()`
   - `_generate_stable_secret()` escreve em `runtime-data/.csrf_secret` se ainda não existe

5. **Validação pós-fix:** `git log --oneline -3` confirma commit. Servidor sobe normalmente.

---

## Bloco B — Bugs em produção Wave 1 (PBVET-196, PBVET-200)

**Cards:** PBVET-196, PBVET-200  
**Estimativa:** 45 min  
**Risco:** Médio (PBVET-196 é iterativo — requer monitoramento pós-deploy)

### PBVET-196 — BitLab HTML nulo

**Arquivo:** `labs/bitlab.py`

1. **Adicionar logging estruturado em `enrich_resultados()`** (linhas 825-882):
   - Logar `item_id`, `payload_size`, `is_empty`, `parse_rows_count` por item
   - Distinguir "payload vazio" de "parse falhou com payload presente"

2. **Garantir fallback PDF ativo** nas funções `buscar_resultado_payload()` / `buscar_resultado_html()` (linhas 533-565):
   - Se `html_payload` retorna `len < 100` bytes, tentar `buscar_resultado_pdf()`
   - Adicionar log explícito quando fallback é acionado

3. **Expandir seletores em `parse_resultado()`** (linhas 621-811):
   - Após `find_all("div", style=True)` retornar vazio, tentar `find("table")` como fallback de parsing
   - Tentativa de decode sem zlib se decode falhar (linha 630-633)

4. **Arquivo core.py** — este fix está relacionado a PBVET-198; ver Bloco D

**Nota iterativa:** Após deploy, monitorar um ciclo completo de polling. Se HTML ainda vier nulo do lado do BitLab, o log mostrará e a investigação continua no próximo sprint.

### PBVET-200 — Nexio data futura

**Arquivo:** `labs/nexio.py`

1. **Linhas 231-237** — item-level `released_at_hint`:
   ```python
   # Substituir lógica fallback errada:
   # raw_date = exame["data_liberacao"] or exame["data_prometida"]
   # Por:
   data_lib = exame.get("data_liberacao", "").strip()
   if data_lib and re.match(r"^\d{2}/\d{2}/\d{4}$", data_lib):
       released_at_hint = datetime.strptime(data_lib, "%d/%m/%Y").strftime("%Y-%m-%d")
   else:
       released_at_hint = ""  # Sem fallback para data_prometida
   ```

2. **Linhas 244-250** — record-level: mesma lógica

3. **Linhas 327-336** — `snapshot_between()`: mesma lógica

---

## Bloco C — Dívidas Lab Monitor Wave 3 (PBVET-43, PBVET-40, PBVET-33, PBVET-198/201/202)

**Cards:** PBVET-43, PBVET-40, PBVET-33, PBVET-198, PBVET-201, PBVET-202  
**Estimativa:** 90 min  
**Risco:** Médio (timezone afeta exibição em toda plataforma; domínio de status afeta core.py)

### PBVET-43 — Timezone

**Arquivos:** `web/state.py`, `core.py`

1. **`web/state.py`** — adicionar função de localização:
   ```python
   from zoneinfo import ZoneInfo  # Python 3.9+
   
   _TZ_BR = ZoneInfo("America/Sao_Paulo")
   
   def _to_brasilia(iso_str: str) -> datetime | None:
       if not iso_str:
           return None
       dt = datetime.fromisoformat(iso_str)
       if dt.tzinfo is None:
           dt = dt.replace(tzinfo=timezone.utc)
       return dt.astimezone(_TZ_BR)
   ```

2. **Atualizar `_format_date()` e `_format_time()`** (linhas 125-153) para usar `_to_brasilia()` antes de formatar

3. **`core.py`** — substituir `datetime.now()` por `datetime.now(tz=timezone.utc)` nos logs internos

### PBVET-40 — Backfill Nexio

**Arquivo:** `labs/nexio.py`

1. **Refatorar `snapshot_between()` (linhas 309-338):**
   - Duas buscas (data_recepcao, data_liberacao) com merge por `numero` de exame usando `seen_ids: set`
   - Adicionar try/except em cada busca para não perder a segunda se a primeira falhar

2. **`core.py` linhas 189-201:** Adicionar `print(f"[backfill:{lab_id}] {len(batch)} registros [{start_dt} a {end_dt}]")`

### PBVET-33 — Notifier legado

**Arquivo:** `core.py` (loader de notifiers)

1. **Antes do loop que carrega notifiers (~linha 510-514):**
   ```python
   seen_notifier_ids: set[str] = set()
   for n_cfg in notifiers_cfg:
       nid = n_cfg.get("id", "")
       if nid in seen_notifier_ids:
           print(f"[warning] notifier duplicado ignorado: {nid}")
           continue
       seen_notifier_ids.add(nid)
       # ... carregar notifier
   ```

2. Auditar `config.json` — verificar se há entradas duplicadas em `"notifiers"`. Remover se houver.

### PBVET-198 / PBVET-201 / PBVET-202 — Domínio de status (implementar juntos)

**Arquivo principal:** `core.py` (`_apply_operational_status_rules`, linhas 331-347)

1. **Adicionar `publication_status` aos itens:**
   ```python
   if normalized == "Pronto" and not _item_has_usable_result(item):
       item["status"] = "Pronto"           # Manter o que lab reporta
       item["publication_status"] = "processing"
       item["result_issue"] = "ready-without-result"
   else:
       item["status"] = normalized
       item["publication_status"] = "ready" if normalized == "Pronto" else "unavailable"
       item.pop("result_issue", None)
   ```

2. **`Inconsistente` fica reservado** para contradições reais (item com dois status opostos de uma mesma requisição)

3. **`web/state.py` `_item_group_status()` (linhas 221-225):**
   - Se `publication_status == "processing"`: mostrar como "Em Andamento" com ícone de aviso
   - Se `publication_status == "ready"` e `status == "Pronto"`: mostrar como "Pronto"

---

## Bloco D — Platform Core Wave 2 (PBVET-36, PBVET-47, PBVET-49, PBVET-46, PBVET-15)

**Estimativa total:** 3–4 horas  
**Ordem interna:** PBVET-36 → PBVET-47 → PBVET-49 → PBVET-46 → PBVET-15

### PBVET-36 — Persistência após deploy

**Arquivos:** `pb_platform/storage.py`, `web/app.py`

1. **`storage.py` `bootstrap_legacy_runtime()`:** Só carregar `config.json` se `app_kv` estiver vazio (primeira init)
2. **`web/app.py` lifespan:** Adicionar cleanup de sessões expiradas:
   ```python
   store._cleanup_expired_sessions()  # novo método
   users = store.list_users()
   print(f"[Startup] {len(users)} usuários, banco OK")
   ```
3. **`storage.py`:** Adicionar `_cleanup_expired_sessions()` que deleta da tabela `user_sessions` onde `expires_at < now()`
4. **Nota:** Integração Alembic no startup é desejável mas risco médio — adiar para sessão dedicada

### PBVET-47 — Modularizar web/app.py

**Estrutura a criar:**
```
web/
├── app.py         (~200 linhas: lifespan, middleware, mounts, includes)
├── shared.py      (novo: _render() helper, imports comuns)
└── routers/
    ├── __init__.py
    ├── auth.py    (linhas 148-269 do app.py atual)
    ├── admin.py   (linhas 274-510)
    ├── platform.py (linhas 516-580)
    └── labmonitor.py (linhas 583-1009, já usa APIRouter)
```

**Passos:**

1. Criar `web/shared.py` com `_render()`, `settings`, imports compartilhados
2. Extrair `web/routers/auth.py` com `make_router(templates)` — rotas login/logout/cadastro
3. Extrair `web/routers/admin.py` — rotas /admin/usuarios, /admin/permissoes, /admin/perfis
4. Extrair `web/routers/platform.py` — rotas /, /ops-map, /sandboxes
5. Extrair `web/routers/labmonitor.py` — mover `router = APIRouter(prefix="/labmonitor")` e todas @router.*
6. `web/app.py` passa a apenas fazer includes e configurar middleware
7. Testar startup + navegar para cada rota após cada extração

**Risco de import circular:** Evitar importar de `web.app` dentro dos routers. Passar deps como parâmetros.

### PBVET-49 — Monitor worker

**Arquivos:** `core.py`, `web/app.py`, `workers/monitor_worker.py` (criar)

1. **Extrair `_monitor_iteration(state)` de `run_monitor_loop()`** — função que executa um ciclo
2. **Criar `workers/monitor_worker.py`:**
   ```python
   """Entrypoint standalone do monitor — sem dependência do servidor web."""
   from core import _monitor_iteration
   from pb_platform.storage import PlatformStore
   
   def main():
       store = PlatformStore()
       while True:
           _monitor_iteration(state=None)
           time.sleep(60)
   
   if __name__ == "__main__":
       main()
   ```
3. **`web/app.py`:** Adicionar env var `MONITOR_EMBEDDED` (default True); se False, não iniciar thread
4. **`Procfile`:** Documentar `worker: python -m workers.monitor_worker` como opção futura

### PBVET-46 — RBAC mínimo

**Arquivo:** `pb_platform/rbac.py` (criar), `pb_platform/storage.py`, `pb_platform/auth.py`

1. **Criar `pb_platform/rbac.py`** com `PermissionRegistry`:
   - `register(module, perm_id, label, implies=[])` 
   - `all_perms()` retorna lista completa
   - Simples dict — sem overhead

2. **Subdividir `manage_labmonitor`:**
   - Adicionar `manage_labmonitor_labs` (gerenciar conectores/labs)
   - Adicionar `manage_labmonitor_settings` (gerenciar configs/notifiers/thresholds)
   - `manage_labmonitor` implica ambos (cascata já existe)

3. **`web/app.py` lifespan:** Registrar permissões dos módulos

4. **`pb_platform/auth.py` `required_permission()`:** Consultar registry para módulos desconhecidos

### PBVET-15 — Limpeza de estrutura (escopo reduzido)

**Apenas os movimentos seguros nesta wave:**

1. **Mover `labs/` → `modules/lab_monitor/labs/`**
   - `git mv labs modules/lab_monitor/labs`
   - Atualizar imports em `core.py` e `web/app.py`

2. **Mover `notifiers/` → `modules/lab_monitor/notifiers/`**
   - `git mv notifiers modules/lab_monitor/notifiers`
   - Atualizar imports em `core.py`

3. **Mover `notification_settings.py` → `modules/lab_monitor/settings.py`**
   - Atualizar imports em `core.py`

4. **Remover legados:**
   - `telegram_users.json` — dados migrados para BD
   - `estado_exames.json` — estado legado, não usado

5. **`core.py` e `monitor.py` permanecem na raiz** por ora (PBVET-47/49 já cobrem isso)

---

## Bloco E — Platform Shell Wave 4 (PBVET-177, PBVET-188, PBVET-182)

**Estimativa:** 60 min  
**Risco:** Baixo (CSS/HTML, sem lógica de negócio)

### PBVET-177 — Logo padrão

**Arquivo:** `web/templates/platform_base.html` (linhas 43-50)

1. Linha 44: `bg-brand-pink` → `bg-rose-600`
2. Abaixo do span do avatar, adicionar sub-caption fixo "PinkBlue Vet" se `shell_caption` vazio
3. Verificar `pb_platform/settings.py`: `app_name = "PinkBlue Vet"`

### PBVET-188 — Lab Monitor UX

**Arquivo:** `web/templates/base.html` (linhas 82-142)

1. Linha 85 (`<aside`): adicionar `rounded-3xl border border-gray-200 bg-white p-3 shadow-sm`
2. Wrapper do grid (linha 82-83): usar `{% set _sidebar %}...{% endset %}` + grid condicional como em platform_base.html
3. Não tocar em cards de exame, interações JS ou estilos internos

### PBVET-182 — Account menu universal

**Arquivo:** `web/templates/platform_base.html` (linhas 54-101)

1. **Avatar iniciais:** `{{ (platform_user.nome.split()[0][0] ~ (platform_user.nome.split()[-1][0] if platform_user.nome.split()|length > 1 else '')) | upper if platform_user.nome else platform_user.email[0] | upper }}`

2. **Dropdown:** Remover condicional `plantao_access` do link "Meu cadastro". Meu cadastro visível sempre.

3. **Meu cadastro como painel flutuante:** Botão com `hx-get="/plantao/perfil?partial=1" hx-target="#modal-perfil" hx-trigger="click"`. Adicionar `<div id="modal-perfil" class="fixed inset-0 z-50 hidden ...">` antes de `</body>`.

4. **Adicionar "Alterar senha"** no dropdown: rota `/admin/alterar-senha` ou modal inline

5. **`modules/plantao/router.py`** — rota `/perfil`: adicionar `if request.query_params.get("partial")`: render sem `{% extends %}` (apenas conteúdo do form)

6. **`modules/plantao/templates/plantao_base.html`** — remover item "Meu perfil" do sidebar (já estará no header universal)

---

## Bloco F — Plantão Wave 5 (PBVET-103, PBVET-156)

**Estimativa:** 90 min  
**Risco:** Médio — PBVET-156 inclui migration Alembic (testar com DB local antes)

### PBVET-103 — Bugs bloqueantes

**Bug 1 — JS setModo** (`modules/plantao/templates/plantao_escalas.html`, linhas 803-810):

```javascript
function setModo(modo) {
  modoAtual = modo;
  const camposUnica = document.getElementById('campos-unica');
  const camposLote  = document.getElementById('campos-lote');
  const tabUnica    = document.getElementById('tab-unica');
  const tabLote     = document.getElementById('tab-lote');
  const btnCriar    = document.getElementById('btn-criar-escala');
  
  if (camposUnica) camposUnica.classList.toggle('hidden', modo !== 'unica');
  if (camposLote)  camposLote.classList.toggle('hidden', modo !== 'lote');
  // ... resto com null-check
}
```

**Bug 2 — cascade manage_plantao** (`modules/plantao/router.py`, linhas 93-110 `_exige_gestor()`):

```python
def _exige_gestor(request, permissao="manage_plantao"):
    user = attach_user_to_request(request)
    if not user:
        return RedirectResponse("/login")
    # manage_plantao implica plantao_access
    tem_acesso = has_permission(request, "plantao_access") or has_permission(request, "manage_plantao")
    tem_perm   = has_permission(request, permissao) or has_permission(request, "manage_plantao")
    if not tem_acesso or not tem_perm:
        return HTMLResponse("<h1>403</h1>", status_code=403)
    return user
```

**Bug 3 — badge Gestor:** Investigar durante execução em `admin/dashboard.html`. Remover se encontrado.

### PBVET-156 — Sobreaviso → Disponibilidade (internals)

**Ordem de execução (crítico: migration ANTES de código):**

1. **Criar migration Alembic:**
   ```bash
   alembic revision --autogenerate -m "rename plantao_sobreaviso to plantao_disponibilidade"
   ```
   Ou escrever migration manual:
   ```python
   def upgrade():
       op.rename_table("plantao_sobreaviso", "plantao_disponibilidade")
       op.execute("UPDATE plantao_datas SET tipo='disponibilidade' WHERE tipo='sobreaviso'")
   
   def downgrade():
       op.rename_table("plantao_disponibilidade", "plantao_sobreaviso")
       op.execute("UPDATE plantao_datas SET tipo='sobreaviso' WHERE tipo='disponibilidade'")
   ```
   ```bash
   alembic upgrade head
   ```

2. **`modules/plantao/schema.py`:** `"plantao_sobreaviso"` → `"plantao_disponibilidade"` (nome da tabela)

3. **`modules/plantao/queries.py`:**
   - `listar_sobreaviso_por_data()` → `listar_disponibilidade_por_data()`
   - `listar_sobreaviso_por_perfil()` → `listar_disponibilidade_por_perfil()`
   - KPI `sobreaviso_vazio` → `disponibilidade_vazia`

4. **`modules/plantao/actions.py`:**
   - `aderir_sobreaviso()` → `aderir_disponibilidade()`
   - `cancelar_sobreaviso()` → `cancelar_disponibilidade()`
   - Strings `tipo='sobreaviso'` → `tipo='disponibilidade'`

5. **`modules/plantao/router.py`:**
   - Linha 1080: `/admin/sobreaviso` → `/admin/disponibilidade`
   - Inverter alias: `/sobreaviso` → redirect para `/disponibilidade` (manter para compat)

6. **Templates:** `templates/admin/sobreaviso.html` → `templates/admin/disponibilidade.html`

7. **Atualizar chamadas em router.py** que referenciam funções renomeadas

---

## Checklist de validação pós-execução

- [ ] `git status --short --branch` — sem arquivos desacompanhados  
- [ ] Servidor sobe sem erros: `uvicorn web.app:app`  
- [ ] Login funciona, home redireciona corretamente  
- [ ] Lab Monitor carrega exames (polling manual ou verificação de snapshot em BD)  
- [ ] Plantão: criar escala via UI, verificar setModo sem erros no console  
- [ ] Plantão: usuário com `manage_plantao` sem `plantao_access` consegue acessar admin  
- [ ] `/plantao/disponibilidade` funciona, `/plantao/sobreaviso` redireciona  
- [ ] Avatar do header mostra iniciais corretas  
- [ ] Sidebar do Lab Monitor tem visual de card (rounded, shadow)  
- [ ] `.secrets` removido do tracking: `git ls-files .secrets` retorna vazio  
- [ ] Executar `python scripts/seed_maio_2026.py` para popular DB de teste  
- [ ] `python -m pytest Testes/ -q` — nenhum regression

---

## Cards de Jira a atualizar durante execução

Para cada bloco concluído, adicionar `[CLOSE-OUT]` comment e mover para `Concluído`:

| Bloco | Cards |
|---|---|
| A | PBVET-13 |
| B | PBVET-196, PBVET-200 |
| C | PBVET-43, PBVET-40, PBVET-33, PBVET-198, PBVET-201, PBVET-202 |
| D | PBVET-36, PBVET-47, PBVET-49, PBVET-46, PBVET-15 |
| E | PBVET-177, PBVET-188, PBVET-182 |
| F | PBVET-103, PBVET-156 |

---

## Notas para a IA executora

1. **Criar um único PR da sessão** cobrindo todos os blocos. Branch `session/YYYYMMDD-XXXX`.  
2. **Commit por bloco** para facilitar revisão: `feat(security): PBVET-13 ...`, `fix(bitlab): PBVET-196 ...`, etc.  
3. **PBVET-196 é iterativo** — o fix de logging/fallback resolve o tratamento, mas confirmar que BitLab parou de enviar HTML nulo requer monitoramento pós-deploy. Documentar isso no close-out.  
4. **PBVET-156 migration** — executar `alembic upgrade head` no DB local ANTES de subir o código. Em prod, a migration roda automaticamente no deploy (já tem `init_db()` na startup). Confirmar com `alembic current`.  
5. **PBVET-47 é o maior risco** — testar import após cada extração de router. Se um router não importar, reverter antes de continuar.  
6. **Ordem dos blocos é obrigatória** — Bloco D (PBVET-47) deve vir antes de PBVET-49 e PBVET-46 pois eles dependem da estrutura de routers estabelecida.

---

## Estimativa total

| Bloco | Tempo |
|---|---|
| Setup | 10 min |
| A — Segurança | 30 min |
| B — Bugs Wave 1 | 45 min |
| C — Lab Monitor Wave 3 | 90 min |
| D — Platform Core Wave 2 | 3h 30min |
| E — Platform Shell Wave 4 | 60 min |
| F — Plantão Wave 5 | 90 min |
| **Total** | **~8h** |
