# Lab Monitor — Aba de Notificações V1

Data: 2026-04-03
Escopo Jira: `PBEXM-26`

## O que entrou nesta primeira versão

A aba de notificações passou a controlar apenas o que hoje faz sentido operacionalmente no módulo:

- evento `recebimento no laboratório`
- evento `conclusão em lote`
- habilitar/desabilitar cada evento externo
- editar o template da mensagem de cada evento
- visualizar quais variáveis podem ser usadas
- visualizar uma prévia do texto resultante

## O que ficou explicitamente fora

- regras por laboratório
- regras por canal
- janela temporal configurável de agregação
- histórico persistido de envios
- persistência garantida entre deploys

## Motivo do recorte

Este recorte entrega valor imediato sem simular uma plataforma de notificações que o módulo ainda não tem.

Ele acompanha a política atual já definida no `PBEXM-16`:

- notificar no recebimento
- notificar na conclusão em lote

## Persistência

No estado atual do módulo, a configuração fica salva no arquivo de configuração do app.

Isso é suficiente para:

- uso operacional local
- testes reais no ambiente atual
- validação de UX e de placeholders

Mas ainda não é a solução final para deploys/rebuilds. A persistência durável continua dependente da trilha de plataforma.
