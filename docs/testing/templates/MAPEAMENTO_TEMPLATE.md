# Mapeamento Template

Use este template para registrar o mapeamento de um modulo antes de qualquer rodada de testes.

Arquivo sugerido:

- `docs/testing/mappings/YYYY-MM-DD-<modulo>-<ambiente>-mapping.md`

## 1. Identificacao

- Modulo:
- Ambiente:
- Data:
- Sessao:
- Branch:
- Worktree:
- Autor da sessao:
- Status do mapeamento: `novo` | `reutilizado` | `atualizado`
- Mapeamento anterior usado como base:

## 2. Contexto lido

### 2.1. Documentacao do modulo

- Documentacao tecnica lida:
- Documentacao de negocio lida:
- Documentacao adicional relevante lida:

### 2.2. Artefatos inspecionados

- Arquivos principais:
- Rotas principais:
- Templates ou componentes principais:
- Outros artefatos relevantes:

## 3. Entendimento do modulo

- Objetivo do modulo:
- Problema que o modulo resolve:
- Perfis de usuario aparentes:
- Principais capacidades aparentes:
- Limites do entendimento atual:

## 4. Resumo operacional para retorno em tela

Copiar daqui a versao curta a ser mostrada ao usuario.

### 4.1. Entendimento do modulo

- 

### 4.2. O que foi mapeado

- Perfis:
- Telas e rotas:
- Fluxos:
- Componentes ou artefatos relevantes:

### 4.3. O que pode ser testado depois

- 

### 4.4. O que a IA sugere rodar primeiro

- 

### 4.5. O que depende de decisao do usuario

- 

### 4.6. Arquivo completo

- Caminho deste arquivo:

## 5. Inventario mapeado

Use IDs curtos e claros.

### 5.1. Artefatos

- `ART-01`:
- `ART-02`:

### 5.2. Perfis

- `PER-01`:
- `PER-02`:

### 5.3. Dispositivos ou contextos de uso

- `DIS-01`:
- `DIS-02`:

### 5.4. Tipos de teste possiveis

- `TIP-01`:
- `TIP-02`:

### 5.5. Fluxos

- `FLX-01`:
- `FLX-02`:

### 5.6. Cenarios

- `CEN-01`:
- `CEN-02`:

### 5.7. Contratos entre camadas

Listar os identificadores nomeados verificados e registrar qualquer divergencia encontrada.

- `CNT-01`: (ex.: ID de conector em config.json vs. chave em CONNECTORS dict vs. lab_id property)
- `CNT-02`: (ex.: chave de permissao em ALL_PERMISSIONS vs. DEFAULT_ROLE_PERMISSIONS vs. template admin)

### 5.8. Qualidade de experiencia do usuario

Listar sinais de problemas de usabilidade observados nos artefatos inspecionados.

- `UXQ-01`: (ex.: campo redundante, vocabulario inconsistente, acao que exige troca de tela evitavel)
- `UXQ-02`:

## 6. Vetores de teste sugeridos

Listar apenas sugestoes. Nao executar nada aqui.

### 6.1. Exploracao guiada

- `EXP-01`:
- `EXP-02`:

### 6.2. Inconsistencia ou negativo

- `NEG-01`:
- `NEG-02`:

### 6.3. Limites e bordas

- `BND-01`:
- `BND-02`:

### 6.4. Revisao visual

- `VIS-01`:
- `VIS-02`:

### 6.5. Contratos entre camadas

- `CNT-01`:
- `CNT-02`:

### 6.6. Qualidade de experiencia do usuario

- `UXQ-01`:
- `UXQ-02`:

## 7. Sugestoes pre-prontas da IA

### 7.1. Pacotes sugeridos

- `PKG-01`:
- `PKG-02`:

### 7.2. Escopos completos

- `FULL-01`:
- `FULL-02`:

## 8. Riscos, restricoes e limites operacionais

### 8.1. Riscos e restricoes

- `RST-01`:
- `RST-02`:

### 8.2. Limites operacionais selecionaveis

- `LIM-01`:
- `LIM-02`:

## 9. Known issues e excecoes conhecidas

- `KI-01`:
- `KI-02`:
- `WA-01`:

## 10. Nivel de confianca

Para itens `inferido` ou `precisa validar com o usuario`, sempre preencher descricao, motivo e pergunta.

### 10.1. Itens confirmados

- ID:
  - Descricao:

### 10.2. Itens inferidos

- ID:
  - Descricao:
  - Motivo da duvida:
  - Pergunta objetiva para o usuario:

### 10.3. Itens que precisam validar com o usuario

- ID:
  - Descricao:
  - Motivo da duvida:
  - Pergunta objetiva para o usuario:

## 11. O que precisa da aprovacao do usuario

- Ambiente:
- Perfis:
- Dispositivos:
- Fluxos:
- Cenarios:
- Pacotes sugeridos:
- Escopo completo:
- Limites operacionais:

## 12. Decisao sobre reuso futuro

- Este mapeamento pode ser reutilizado em reruns?
- Em quais condicoes ele deixa de ser confiavel?
- Sinais que exigem atualizacao parcial:
- Sinais que exigem novo mapeamento completo:
