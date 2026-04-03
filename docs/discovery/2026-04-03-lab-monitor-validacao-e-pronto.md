# Lab Monitor — Validação de Regressão e Critério de Pronto

Data: 2026-04-03
Escopo Jira: `PBEXM-6`, `PBEXM-7`, `PBEXM-8`

## O que define o MVP como pronto

O módulo de exames é considerado operacionalmente pronto quando todos estes pontos estiverem verdadeiros ao mesmo tempo:

1. O dashboard, a listagem de exames, laboratórios, canais, notificações e configurações respondem sem erro.
2. A listagem de exames mostra histórico útil mínimo de 60 dias.
3. Os agrupadores usam data/hora de recebimento como data principal.
4. O agrupador mostra última liberação quando ela existir.
5. Resultados prontos podem ser expandidos inline sem depender de intervenção manual prévia.
6. Dados enriquecidos essenciais aparecem no painel quando disponíveis na origem:
   - tutor
   - espécie/sexo
   - idade
   - raça
   - referências corretas por espécie/sexo e, quando aplicável, idade
7. Notificações externas seguem a política operacional atual:
   - recebimento no laboratório
   - conclusão em lote por protocolo
8. Dashboard e aba Exames usam nomenclatura coerente de status.
9. Conectores BitLab e Nexio continuam operacionais após deploy/restart.
10. A suíte automatizada principal passa sem regressão.

## Checklist de regressão executado nesta rodada

- `python -m unittest discover -s Testes -v`
- renderização das parciais:
  - `/labmonitor/partials/exames`
  - `/labmonitor/partials/lab_counts`
  - `/labmonitor/partials/ultimos_liberados`
  - `/labmonitor/notificacoes`
- validação real do BitLab:
  - resultados inline
  - referências por espécie/sexo
  - hemograma com `%` + absoluto
- validação real do Nexio:
  - metadata enriquecida
  - descrição legível baseada no diagnóstico
- checagem funcional do dashboard:
  - cards totalizadores
  - últimos liberados
  - indicador operacional substituindo a barra antiga

## Evidências mínimas esperadas sempre que esta frente for revalidada

- testes automatizados passando
- produção respondendo `200` nas rotas principais
- ao menos um caso real de BitLab validado
- ao menos um caso real de Nexio validado
- verificação manual do dashboard e da lista de exames após deploy

## Gaps que não bloqueiam o pronto operacional atual

- persistência oficial entre deploys para configurações operacionais
- cadastro persistente de tolerâncias por exame
- preferência opcional de layout lado-a-lado

Esses pontos continuam válidos como evolução do módulo, mas não impedem o MVP atual de operar com segurança.
