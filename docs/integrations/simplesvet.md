# SimplesVet

Fonte canônica de contexto operacional do SimplesVet para IAs e integrações da
plataforma PinkBlue.

Objetivo:

- reduzir redescoberta do sistema a cada nova sessão;
- centralizar guardrails, superfícies conhecidas e aprendizados duráveis;
- servir como ponto de entrada antes de qualquer acesso ao sistema.

## 1. Regras de operação

- Tratar o SimplesVet como sistema de produção.
- O modo padrão é observacional/read-only.
- Consultas, inspeção visual, relatórios e downloads são permitidos.
- Qualquer ação que possa alterar dados, estado operacional ou financeiro exige:
  - descrição explícita do que será alterado;
  - em qual tela, módulo ou endpoint;
  - por que a alteração é necessária;
  - aprovação expressa do usuário antes da execução.
- Erros, negativas e bloqueios do sistema não devem ser contornados de forma
  insistente.
- Credenciais, cookies e tokens nunca entram em arquivos versionados, docs ou
  Jira.

## 2. Como usar este documento

Leia este arquivo antes de acessar o SimplesVet.

Se a tarefa exigir profundidade adicional:

- consulte as notas em `docs/discovery/` ligadas ao SimplesVet;
- ao terminar, traga de volta para este arquivo apenas o que for durável e útil
  para futuras sessões.

Regra de qualidade:

- este arquivo deve continuar curto, objetivo e orientado a execução;
- se crescer demais, ele continua como índice e fonte principal, e os detalhes
  vão para anexos ou notas de discovery.

## 3. Estrutura conhecida do sistema

Menus relevantes já observados:

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

Submenus já confirmados como úteis:

- Comissionamento > Comissões em aberto
- Comissionamento > Extratos
- Comissionamento > Minhas comissões
- Inteligência > Produtividade

## 4. Estrutura técnica conhecida

Superfícies web relevantes:

- app principal: `https://app.simples.vet/`
- login: `https://app.simples.vet/login/login.php`
- front SPA de comissionamento: `/v2/comercial/comissao/*`

Infra técnica observada no front de comissão:

- o front `v2` é uma SPA;
- o cliente HTTP do bundle resolve para `https://api.simples.vet/app/`;
- o sistema usa cookies de sessão/autorização no domínio SimplesVet.

## 5. Comissionamento: o que já está validado

Endpoints `GET` já validados em leitura:

- `/v1/comercial/comissoes/parametros`
- `/v1/comercial/comissoes/comissionados`
- `/v1/comercial/comissoes/resumos`
- `/v1/comercial/comissoes/extratos`
- `/v1/comercial/comissoes/extratos/{id}`
- `/v1/comercial/venda/parametros`

Utilidade prática dos retornos:

- `comissionados` lista usuários ativos e perfis ligados à comissão;
- `resumos` fornece panorama de comissão em aberto;
- `extratos` entrega histórico fechado com dados úteis para folha;
- `extratos?usuario_id=<id>` já respondeu corretamente em modo read-only.

Campos úteis já observados em `extratos`:

- usuário
- valor bruto
- acréscimo
- desconto
- valor líquido
- observação
- data de fechamento
- conta
- forma de pagamento

Observações de negócio já vistas no payload:

- complemento para cobrir piso
- diferença para piso
- acertos por fora dos plantões
- consumo de itens da clínica

## 6. Caminho preferencial para integração

Para módulos internos que precisem de comissões:

1. autenticar localmente sem persistir credenciais no repositório;
2. listar comissionados ativos;
3. extrair extratos por período e por `usuario_id`;
4. gravar o bruto da resposta em armazenamento local controlado;
5. normalizar esses dados para o modelo canônico do módulo consumidor.

Princípio:

- usar IA para classificar, reconciliar e sugerir quando houver caos documental;
- usar regras determinísticas para cálculo final e fechamento.

## 7. O que ainda não está fechado

- gramática completa da visão de comissões em aberto por item;
- tipos aceitos pelos endpoints de relatório;
- mapeamento de outros módulos relevantes além de comissionamento e produtividade;
- desenho final do conector local reutilizável para todos os projetos.

## 8. Protocolo de atualização

Sempre que uma sessão aprender algo novo e durável sobre o SimplesVet:

1. registrar a descoberta operacional no card Jira ativo;
2. se necessário, criar nota de apoio em `docs/discovery/`;
3. consolidar aqui o aprendizado estável, em formato curto e reutilizável;
4. nunca registrar credenciais, tokens ou dados sensíveis desnecessários.

## 9. Referências atuais

- descoberta de comissionamento:
  - `docs/discovery/2026-04-04-pbfin-simplesvet-comissionamento-mapping.md`
