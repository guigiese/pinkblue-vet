# SimplesVet: mapeamento observacional de comissionamento

Data: 2026-04-04
Card: PBFIN-2
Sessão: 20260404-261d

## Objetivo

Mapear, em modo estritamente observacional, onde ficam as informações de
comissionamento no SimplesVet e qual é o caminho mais seguro para extraí-las
para o MVP local de fechamento de folha.

## Guardrails operacionais

- Navegação em modo leitura.
- Consultas, relatórios e downloads são permitidos.
- Nenhuma ação mutável deve ser executada sem descrição prévia e aprovação
  explícita do usuário.
- Erros, bloqueios ou negativas do sistema não devem ser contornados de forma
  insistente.
- Credenciais, cookies e tokens não entram em arquivos versionados, docs ou Jira.

## Estrutura visível no menu

Itens relevantes encontrados no dashboard:

- Atendimento clínico
- Clientes
- Agenda
- Vendas
- Comissionamento
- Inteligência / Produtividade
- Cadastros
- Internação
- Estoque e serviços
- Financeiro
- Configuração
- Fiscal

Submenus relevantes:

- Comissionamento > Comissões em aberto
  - `/v2/comercial/comissao/fechamento`
- Comissionamento > Extratos
  - `/v2/comercial/comissao/extratos`
- Comissionamento > Minhas comissões
  - `/v2/comercial/comissao/minhascomissoes`
- Inteligência > Produtividade
  - `/v2/inteligencia/produtividade`

## Estrutura técnica observada

O front `v2` é uma SPA. No bundle principal, o cliente HTTP usa:

- `BASE_API = https://api.simples.vet/`
- `baseURL = BASE_API + "app"`

Inferência operacional:

- as chamadas relevantes do módulo de comissão saem para
  `https://api.simples.vet/app/`

## Endpoints validados em leitura

Todos abaixo responderam com `GET` e sem necessidade de ação mutável:

- `/v1/comercial/comissoes/parametros`
- `/v1/comercial/comissoes/comissionados`
- `/v1/comercial/comissoes/resumos`
- `/v1/comercial/comissoes/extratos`
- `/v1/comercial/comissoes/extratos/{id}`
- `/v1/comercial/venda/parametros`

Endpoints que existem no front, mas exigem cuidado adicional:

- `/v1/comercial/comissoes/relatorios`
- `/v1/comercial/comissoes/extratos/relatorios`

Observação:

- ambos responderam com `Tipo de relatório não informado.` quando chamados sem o
  parâmetro `tipo`, o que confirma superfície de relatório, mas ainda sem mapa
  completo dos tipos aceitos

## Achados de negócio

Parâmetros globais de comissão observados:

- `base_calculo = L` (`Líquido`)
- `ciclo_fechamento = SEM`
- `comissaovendabaixada = S`
- `exibe_comissoes = S`
- `imprime_comissoes = S`

Comissionados ativos retornados por
`/v1/comercial/comissoes/comissionados?comissionados=S&status=A&limite=NULL`:

- Amanda de Souza Bernardo
- Ana Paula da Silva Clerot
- Clara Driemeyer Guimarães
- Cleber Augusto de Macedo
- Kivia Hesse
- Leonardo Glicerio Daros D'Avila
- Leonel de Jesus Macedo Dias

Perfis observados no payload:

- veterinários aparecem com perfil `Veterinário Plantonista`

Resumo de comissões em aberto:

- `GET /v1/comercial/comissoes/resumos` devolve total em aberto por pessoa
- em 2026-04-04, sem filtros adicionais, havia valores em aberto para parte dos
  comissionados ativos

Extratos fechados:

- `GET /v1/comercial/comissoes/extratos` devolve histórico paginado
- o payload já traz dados úteis para folha:
  - `usuario`
  - `valorbruto`
  - `acrescimo`
  - `desconto`
  - `valor`
  - `observacao`
  - `data_fechamento`
  - `status`
  - `lancamento.conta`
  - `lancamento.forma_pagamento`

Exemplo de semântica observada no campo `observacao`:

- complemento para cobrir piso
- diferença para piso
- acertos por fora dos plantões
- consumo de itens da clínica

Isso é particularmente útil porque o sistema já parece registrar no extrato
final parte dos mesmos ajustes manuais que hoje entram na planilha.

## Filtros que responderam

Em `extratos`, o filtro por usuário respondeu corretamente:

- `GET /v1/comercial/comissoes/extratos?usuario_id=<id>`

Também houve resposta com filtros de período e status:

- `data_inicial`
- `data_final`
- `status`

Em `resumos`, os filtros tentados ainda não se mostraram consistentes o bastante
para inferir toda a gramática do endpoint. O comportamento prático confirmado é:

- a chamada sem filtros retorna o panorama de em aberto
- a lista de comissionados ativos vem de `/comissionados`

## Caminho mais seguro para o MVP de folha

Para histórico fechado:

1. listar comissionados ativos
2. mapear os IDs dos veterinários relevantes
3. extrair extratos por `usuario_id` e período
4. normalizar para eventos canônicos de folha

Para competência ainda em aberto:

1. usar `resumos` como visão rápida de saldo aberto por pessoa
2. complementar com revisão manual até mapear a granularidade item a item

## Riscos e limites atuais

- O front contém endpoints mutáveis para criar extratos, atualizar comissão e
  remover comissão. Esses endpoints não devem ser chamados sem aprovação
  explícita.
- A lista de comissões em aberto por item ainda não foi totalmente mapeada; a
  UI mostra essa visão, mas a gramática completa dos filtros ainda precisa ser
  confirmada.
- Os endpoints de relatório exigem o parâmetro `tipo`; os tipos exatos ainda
  precisam ser descobertos via inspeção adicional do bundle/UI.

## Próximo passo recomendado

Automatizar um conector read-only do SimplesVet para:

- autenticar localmente
- listar comissionados ativos
- extrair extratos por período e usuário
- gravar a resposta bruta no `chaos pool`
- converter os extratos em eventos canônicos do módulo financeiro
