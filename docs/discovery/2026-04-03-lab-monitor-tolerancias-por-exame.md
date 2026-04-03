# Lab Monitor — Tolerâncias Persistentes por Exame

Data: 2026-04-03
Escopo Jira: `PBEXM-31`

## Objetivo

Permitir cadastrar, por exame, os limiares usados para classificar:

- `Atenção`
- `Crítico`

com persistência real entre deploys e atualizações.

## Regra funcional proposta

- valor padrão de `Atenção`: `100%`
- valor padrão de `Crítico`: `120%`
- cada exame pode sobrescrever esses dois percentuais
- a regra é aplicada sobre a referência efetivamente escolhida para o paciente:
  - espécie
  - sexo
  - faixa etária quando existir

## O que a UI futura deve permitir

1. Buscar o exame por nome padronizado.
2. Ver os defaults do sistema.
3. Sobrescrever `Atenção` e `Crítico`.
4. Remover a sobrescrita e voltar ao padrão.
5. Ver quando e por quem a regra foi alterada.

## Modelo de dados recomendado

Tabela/configuração persistente:

- `exam_thresholds`
  - `id`
  - `exam_slug`
  - `display_name`
  - `warning_multiplier`
  - `critical_multiplier`
  - `updated_at`
  - `updated_by`

## Dependências reais

Esta entrega depende de persistência oficial do produto. No estado atual do módulo:

- `config.json` é útil para ajustes operacionais locais, mas não é persistência confiável entre deploys;
- Railway grátis sem volume não atende ao requisito desta funcionalidade;
- portanto a solução correta depende da trilha de plataforma:
  - `PBCORE-14`
  - `PBCORE-15`

## Decisão desta rodada

Não implementar a funcionalidade agora no produto.

Motivo:

- o requisito explícito é sobreviver a deploys;
- implementar isso hoje só em arquivo local produziria uma falsa sensação de persistência.

## Recorte recomendado quando a persistência estiver pronta

1. modelo persistente
2. serviço de leitura/escrita das tolerâncias
3. integração com o cálculo de criticidade
4. tela administrativa simples
5. auditoria mínima de mudança
