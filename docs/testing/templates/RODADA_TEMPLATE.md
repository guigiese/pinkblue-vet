# Rodada Template

Use este template para registrar uma rodada de testes baseada em um mapeamento ja existente.

Arquivo sugerido:

- `docs/testing/runs/YYYY-MM-DD-<modulo>-<ambiente>-run.md`

## 1. Identificacao

- Modulo:
- Ambiente:
- Data:
- Sessao:
- Branch:
- Worktree:
- Autor da sessao:
- Status da rodada: `planejada` | `aprovada` | `em execucao` | `executada` | `encerrada`
- Mapeamento base:

## 2. Recorte aprovado pelo usuario

Registrar apenas o que foi aprovado para esta rodada.

### 2.1. Ambiente e limites

- Ambiente aprovado:
- Limites operacionais aprovados:

### 2.2. Itens aprovados

- `PER-`:
- `DIS-`:
- `TIP-`:
- `FLX-`:
- `CEN-`:
- `EXP-`:
- `NEG-`:
- `BND-`:
- `VIS-`:
- `PKG-`:
- `FULL-`:

### 2.3. Itens fora da rodada

- Nao aprovados:
- Bloqueados:
- Nao aplicaveis:

## 3. Plano de execucao

- Objetivo desta rodada:
- Ordem planejada de execucao:
- Dependencias para executar:
- Riscos esperados:
- Criterio de parada esperado:

## 4. Execucao por item

Para cada item executado, registrar status e observacao.

### 4.1. Itens executados

- ID:
  - Tipo:
  - Status:
  - Perfis envolvidos:
  - Dispositivo:
  - Resultado resumido:
  - Observacoes:

### 4.2. Itens nao executados

- ID:
  - Motivo:

### 4.3. Itens bloqueados ou abortados

- ID:
  - Motivo:
  - Depende de decisao do usuario?:

## 5. Evidencia visual usada

- Tela renderizada observada:
- Limitacoes de observacao visual:
- Itens visuais cobertos:

## 6. Achados

Cada achado deve ser rastreavel ao item de origem.

### 6.1. Achados criticos

- `ACH-001`:
  - Criticidade:
  - Origem:
  - Perfil:
  - Dispositivo:
  - Contexto:
  - Descricao:
  - Impacto:
  - Evidencia:
  - Recomendacao:

### 6.2. Achados de alta

- `ACH-002`:
  - Criticidade:
  - Origem:
  - Perfil:
  - Dispositivo:
  - Contexto:
  - Descricao:
  - Impacto:
  - Evidencia:
  - Recomendacao:

### 6.3. Achados de media

- `ACH-003`:
  - Criticidade:
  - Origem:
  - Perfil:
  - Dispositivo:
  - Contexto:
  - Descricao:
  - Impacto:
  - Evidencia:
  - Recomendacao:

### 6.4. Achados de baixa

- `ACH-004`:
  - Criticidade:
  - Origem:
  - Perfil:
  - Dispositivo:
  - Contexto:
  - Descricao:
  - Impacto:
  - Evidencia:
  - Recomendacao:

## 7. Inconsistencias documentais

Registrar comportamentos aparentemente corretos e aplicaveis que nao constem ou divirjam da documentacao lida.

- `DOC-01`:
  - Origem:
  - Comportamento observado:
  - Divergencia documental:
  - Sugestao de follow-up:

## 8. Known issues e repeticoes

- Itens ja conhecidos revisitados:
- Itens confirmados como persistentes:
- Itens corrigidos e retestados:

## 9. Diagnostico da rodada

- Sintese geral:
- Estado observado do modulo nesta rodada:
- Principais riscos:
- Principais confiancas:
- O que ainda precisa validar:

## 10. Proximos passos

- Ajustes recomendados:
- Reruns recomendados:
- Follow-ups de documentacao:
- Necessidade de aprovacao adicional:
- Recomendacao sobre Jira:
