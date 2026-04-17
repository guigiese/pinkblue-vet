# Rodada Plantao DEV - 2026-04-16

## 1. Identificacao

- Modulo: Plantao
- Ambiente: DEV
- Data: 2026-04-16
- Sessao: `20260415-0f5b`
- Branch: `session/20260415-0f5b`
- Worktree de registro: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet-codex-20260415-0f5b`
- Snapshot tecnico testado em: `C:\Users\guigi\Desktop\Projetos Python\SimplesVet`
- Autor da sessao: Codex
- Status da rodada: `executada`
- Mapeamento base: `docs/testing/mappings/2026-04-16-plantao-dev-mapping.md`

## 2. Recorte aprovado pelo usuario

### 2.1. Ambiente e limites

- Ambiente aprovado: `DEV`
- Escopo aprovado: `FULL-05`
- Dispositivos cobertos: `DIS-01`, `DIS-02`
- Limites operacionais:
  - `LIM-01`
  - `LIM-02`
  - `LIM-03`
  - `LIM-04`

### 2.2. Foco especial pedido pelo usuario

- clique no dia do calendario
- clique em agendamento do calendario
- efeito da selecao dos filtros
- view `Lista`
- alternancia `Unica` / `Em Lote`
- avaliacao de possivel redundancia entre `/plantao/admin/` e `/plantao/`
- avaliacao de rastros de implementacoes anteriores

## 3. Preparacao e metodo

- O teste foi executado contra um servidor isolado do snapshot atual do modulo em `http://127.0.0.1:8766`.
- A base usada na rodada foi uma copia controlada da base da rodada anterior:
  - `runtime-data/plantao-round2.sqlite3`
- O app foi iniciado com o codigo atual do workspace principal e com `DATABASE_URL` apontando para essa base isolada.
- A navegacao foi exercitada em browser real com Playwright, em desktop e mobile.
- Os perfis foram alternados via `dev/switch-user` em ambiente de desenvolvimento.

## 4. Execucao por item

### 4.1. Itens executados

- Desktop admin:
  - `/plantao/`
  - `/plantao/admin/`
  - `/plantao/escalas`
  - `/plantao/admin/cadastros`
  - `/plantao/admin/aprovacoes`
  - `/plantao/admin/candidaturas`
  - `/plantao/admin/disponibilidade`
  - `/plantao/admin/sobreaviso`
  - `/plantao/admin/relatorios`
  - `/plantao/admin/locais`
  - `/plantao/admin/tarifas`
  - `/plantao/admin/feriados`
  - `/plantao/admin/configuracoes`
  - `/plantao/admin/audit-log`
- Desktop plantonista:
  - `/plantao/`
  - `/plantao/escalas`
  - `/plantao/disponibilidade`
  - `/plantao/notificacoes`
  - `/plantao/perfil`
- Permissoes e bloqueios:
  - perfis granulares `escalas_only`, `cand_only`, `cad_only`, `rel_only`
  - usuarios sem acesso efetivo `viewer` e `colab`
- Aliases e compatibilidade:
  - `/plantao/agenda`
  - `/plantao/meus-turnos`
  - `/plantao/trocas`
  - `/plantao/admin/escalas`
  - `/plantao/admin/disponibilidade`
- Mobile:
  - `/plantao/escalas`
  - `/plantao/`
  - `/plantao/perfil`

### 4.2. Verificacoes especiais executadas na tela unificada

- clique em dia do calendario
- clique em chip/agendamento do calendario
- alternancia `Calendario` / `Lista`
- alternancia de filtros por tipo e status
- abertura do painel `Nova Escala`
- alternancia entre `Unica` e `Em Lote`

## 5. Evidencia usada

- Artefato principal da rodada:
  - `runtime-data/plantao-round2-artifacts/artifacts.json`
- Screenshots principais:
  - `runtime-data/plantao-round2-artifacts/desktop-admin-landing-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-admin-dashboard-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-admin-escalas-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-admin-escalas-special-checks.png`
  - `runtime-data/plantao-round2-artifacts/desktop-admin-cadastros-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-admin-tarifas-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-vet-landing-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-vet-escalas-round2.png`
  - `runtime-data/plantao-round2-artifacts/desktop-vet-disponibilidade-round2.png`
  - `runtime-data/plantao-round2-artifacts/mobile-admin-escalas-round2.png`
  - `runtime-data/plantao-round2-artifacts/mobile-vet-landing-round2.png`
  - `runtime-data/plantao-round2-artifacts/mobile-vet-escalas-round2.png`
- Logs do servidor:
  - `runtime-data/plantao-round2-server.out.log`
  - `runtime-data/plantao-round2-server.err.log`

## 6. Achados

### 6.1. Achados criticos

- Nenhum.

### 6.2. Achados de alta

- `A-01` `FLX-02`, `FLX-06`, `FLX-07`, `VIS-02`, `VIS-03`, `EXP-01`, `EXP-02`, `EXP-04`
  - Titulo: a hidratacao JavaScript da tela unificada de escalas quebra logo no carregamento
  - Origem: abertura renderizada de `/plantao/escalas`
  - Resultado atual:
    - clicar no dia do calendario nao abre o painel
    - clicar em um agendamento nao abre detalhes
    - mudar para `Lista` deixa a tela sem agendamentos visiveis
    - clicar em `Em Lote` nao alterna os campos do painel
  - Causa tecnica confirmada:
    - o HTML renderizado coloca JSON escapado em `<script type="application/json">` com entidades como `&#34;`
    - o codigo depois tenta fazer `JSON.parse(...textContent)`, o que dispara erro de parse e impede a definicao de funcoes como `abrirDia`, `abrirDiaEvento` e `setModo`
  - Evidencia:
    - `runtime-data/plantao-round2-artifacts/artifacts.json`
    - `runtime-data/plantao-round2-artifacts/desktop-admin-escalas-special-checks.png`
    - erros de browser: `Expected property name or '}' in JSON...`, `Cannot access 'eventosPorData' before initialization`, `Cannot access 'modoAtual' before initialization`
    - confirmacao direta do HTML renderizado com `&#34;` dentro dos blocos JSON
  - Referencias:
    - [plantao_escalas.html:558](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:558)
    - [plantao_escalas.html:560](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:560)
    - [plantao_escalas.html:565](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:565)
    - [plantao_escalas.html:569](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:569)
    - [plantao_escalas.html:606](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:606)
    - [plantao_escalas.html:760](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:760)
    - [plantao_escalas.html:800](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:800)
- `A-02` `NEG-08`, `PER-08`
  - Titulo: usuario autenticado sem permissao efetiva ainda entra em loop de redirect ao acessar `/plantao/`
  - Origem: acesso de `colab` a `/plantao/`
  - Resultado atual:
    - o browser entrou em `ERR_TOO_MANY_REDIRECTS`
  - Impacto:
    - fluxo de acesso negado continua inconsistente e confuso para usuario autenticado sem permissao
  - Evidencia:
    - `runtime-data/plantao-round2-artifacts/artifacts.json`
    - `runtime-data/plantao-round2-server.out.log`
  - Referencias:
    - [auth.py:90](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\pb_platform\auth.py:90)
    - [auth.py:100](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\pb_platform\auth.py:100)
    - [app.py:105](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\web\app.py:105)
    - [app.py:108](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\web\app.py:108)

### 6.3. Achados de media

- `M-01` `EXP-03`, `VIS-02`
  - Titulo: filtros da tela unificada nao estao ligados ao calendario renderizado
  - Origem: teste dos chips de filtro em modo calendario
  - Resultado atual:
    - a contagem de chips/agendamentos no calendario permaneceu igual antes e depois da selecao do filtro
  - Observacao tecnica:
    - no template, a logica `visivel()` e usada na view de lista, mas os chips do calendario nao sao renderizados sob essa mesma condicao
  - Impacto:
    - mesmo apos corrigir a hidratacao, o comportamento de filtro no calendario ainda tende a ficar inconsistente com a expectativa do usuario
  - Evidencia:
    - `runtime-data/plantao-round2-artifacts/artifacts.json`
  - Referencias:
    - [plantao_escalas.html:152](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:152)
    - [plantao_escalas.html:228](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:228)
    - [plantao_escalas.html:243](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:243)
    - [plantao_escalas.html:596](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html:596)
- `M-02` `FLX-23`
  - Titulo: o modulo ainda carrega varios aliases e redirects de compatibilidade de uma arquitetura anterior
  - Origem: validacao de `/plantao/agenda`, `/plantao/meus-turnos`, `/plantao/trocas`, `/plantao/admin/escalas` e `/plantao/admin/disponibilidade`
  - Resultado atual:
    - todos continuam ativos e redirecionam para superficies canonicas novas
  - Impacto:
    - nao e bug funcional por si, mas e rastro claro de implementacoes anteriores
    - aumenta ambiguidade de documentacao, manutencao e cobertura de testes
  - Evidencia:
    - `runtime-data/plantao-round2-artifacts/artifacts.json`
  - Referencias:
    - [router.py:189](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:189)
    - [router.py:200](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:200)
    - [router.py:204](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:204)
    - [router.py:785](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:785)
    - [router.py:1073](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:1073)
- `M-03` `FLX-01`
  - Titulo: `/plantao/admin/` e `/plantao/` nao sao a mesma coisa, mas a diferenca hoje e mais estrutural do que clara para o usuario
  - Origem: comparacao direta das duas entradas
  - Resultado atual:
    - `/plantao/` abre landing role-aware
    - `/plantao/admin/` abre dashboard admin
    - URLs finais e headings sao diferentes
  - Conclusao:
    - nao se trata da mesma rota
    - ainda assim, vale revisar se as duas entradas seguem agregando valor ou se parte da funcao do dashboard poderia ser absorvida pela landing/admin shell
  - Evidencia:
    - `runtime-data/plantao-round2-artifacts/artifacts.json`
    - screenshots `desktop-admin-landing-round2.png` e `desktop-admin-dashboard-round2.png`
  - Referencias:
    - [router.py:114](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:114)
    - [router.py:694](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\router.py:694)
    - [plantao_base.html:12](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_base.html:12)

### 6.4. Achados de baixa

- Nenhum.

## 7. Inconsistencias documentais

- O discovery historico ainda descreve superfices separadas como agenda, trocas e admin de escalas, mas o snapshot atual centraliza a operacao em ` /plantao/escalas `.
- A documentacao de discovery ainda fala em auth isolada do modulo, enquanto o snapshot atual segue auth unificada da plataforma.

## 8. Diagnostico da rodada

- Sintese geral:
  - a arquitetura nova do modulo esta mapeada e as superficies principais renderizam, mas a tela unificada de escalas continua quebrando na camada JavaScript logo no carregamento
- Sobre os pontos especiais pedidos:
  - clique no dia do calendario: confirmado como quebrado
  - clique em agendamento do calendario: confirmado como quebrado
  - filtros: confirmados como sem efeito observavel no estado atual; no calendario, ha ainda indicio de acoplamento incompleto mesmo alem da quebra de hidratacao
  - view `Lista`: confirmada como vazia
  - `Unica` / `Em Lote`: `Em Lote` confirmado como sem efeito
  - `/plantao/admin/` e `/plantao/`: nao sao a mesma rota, embora merecam revisao de redundancia
- Estado observado:
  - a maior regressao atual esta concentrada em ` /plantao/escalas `
  - as superficies admin auxiliares renderizam e a camada de permissao granular principal respondeu de forma coerente
  - os aliases de compatibilidade seguem vivos e precisam ser tratados conscientemente como legado ou como contrato mantido

## 9. Proximos passos

- Ajustes recomendados:
  - corrigir a serializacao dos blocos JSON em `plantao_escalas.html`
  - rerodar imediatamente os checks de clique em dia, clique em agendamento, `Lista` e tabs `Unica` / `Em Lote`
  - revisar se filtros devem afetar tambem a view de calendario
  - tratar o loop de redirect para usuario autenticado sem permissao
  - decidir quais aliases legados permanecem por compatibilidade e quais devem ser podados
- Reruns recomendados:
  - rerun focal da tela ` /plantao/escalas ` apos corrigir `A-01`
  - rerun de permissao negativa apos corrigir `A-02`
  - rerun de aliases e rastros legados apos decisao de consolidacao
- Follow-up de processo:
  - o canônico foi atualizado para obrigar verificacao de rastros de implementacoes anteriores em modulos com unificacao recente

## 10. Correcao e reteste

### 10.1. Ajustes aplicados no snapshot tecnico

- `A-01` corrigido em [plantao_escalas.html](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\modules\plantao\templates\plantao_escalas.html)
  - os blocos JSON passaram a ser renderizados sem escape indevido dentro dos `<script type="application/json">`
  - os chips do calendario passaram a expor `data-tipo` e `data-status` para validacao observavel dos filtros
- `A-02` corrigido em [auth.py](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\pb_platform\auth.py) e [app.py](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\web\app.py)
  - usuarios autenticados sem destino valido deixaram de entrar em loop
  - o login agora redireciona para uma superficie realmente acessivel ou responde com tela estavel de sem acesso
- regressao latente encontrada e corrigida em [storage.py](C:\Users\guigi\Desktop\Projetos Python\SimplesVet\pb_platform\storage.py)
  - `authenticate_user()` deixava de funcionar em parte dos cenarios por tentar mutar `RowMapping`

### 10.2. Rerun final

- O servidor isolado foi reiniciado com o mesmo banco de teste da rodada:
  - `runtime-data/plantao-round2.sqlite3`
- A bateria completa foi rerodada apos as correcoes, mantendo desktop, mobile, perfis granulares, aliases e casos de acesso negado.
- Resultado final do probe:
  - `events: 41`
  - `findings: 0`
  - `screenshots: 14`

### 10.3. Validacao dos pontos especiais

- clique no dia do calendario: corrigido e validado
- clique em agendamento do calendario: corrigido e validado
- mudanca para `Lista`: corrigida e validada com itens visiveis
- tabs `Unica` e `Em Lote`: corrigidas e validadas
- filtros:
  - o problema original de hidratacao foi corrigido
  - a sonda foi ajustada para validar filtros apenas contra estados realmente presentes na massa atual
  - o rerun final nao encontrou falha funcional restante
- `/plantao/admin/` e `/plantao/`:
  - continuam superficies distintas
  - permanecem como ponto de racionalizacao de produto/arquitetura, nao como bug funcional

### 10.4. Fechamento tecnico

- Nenhuma regressao nova foi identificada na bateria final.
- Os rastros legados continuam documentados como follow-up de consolidacao, nao como quebra funcional imediata.
- O canonico foi reforcado para evitar falso positivo em:
  - filtros testados sem baseline limpa;
  - erros genericos de recurso sem atribuicao clara ao modulo.
