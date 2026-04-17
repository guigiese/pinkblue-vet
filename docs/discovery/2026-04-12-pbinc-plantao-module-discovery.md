# Discovery: Módulo Plantão — Gestão de Escalas de Veterinários Plantonistas
**Data:** 2026-04-12
**Status:** Em descoberta
**Jira Epic:** PBINC-25

---

## Contexto

Novo módulo da plataforma PinkBlue Vet para gerenciar a escala de veterinários e auxiliares veterinários plantonistas da clínica Pink Blue Passo de Torres.

**Objetivo central:** dar autonomia aos plantonistas para gerenciar suas próprias escalas, reduzir carga operacional dos gestores e manter rastreabilidade total de todas as movimentações.

---

## Capacidades solicitadas

### Auth isolado (PBINC-28)
- Cadastro público com e-mail + senha + tipo (vet/auxiliar)
- Status inicial: `pendente` — tela bloqueada aguardando aprovação
- Gestores (usuários da plataforma com role `gestor_plantao`) aprovam ou rejeitam
- Após aprovação: acesso apenas ao módulo Plantão (`/plantao/*`)

### Publicação de escalas pelos gestores (PBINC-29)
- Gestores publicam datas + posições (ex: 1 veterinário + 1 auxiliar)
- Calendário visual mensal
- Suporte a múltiplos locais (início: Pink Blue Passo de Torres)

### Candidatura e lista pública (PBINC-30)
- Plantonistas se candidatam às posições abertas
- Lista pública mostra candidatos com status `PROVISÓRIO` até aprovação do gestor
- Após aprovação: status muda para `CONFIRMADO`
- Sistema bloqueia candidatura duplicada na mesma data/horário

### Cancelamento, troca e substituição (PBINC-31)
- Prazo mínimo configurável (padrão: 24 horas úteis antes do início)
- Após início do turno: qualquer alteração bloqueada
- **Troca direta:** A solicita troca com B (que tem outro turno) → B aceita → sistema executa
- **Substituição:** A disponibiliza turno → qualquer colega elegível aceita → A sai, novo entra
- Gestor notificado de todas as trocas

### Escala de sobreaviso/emergência (PBINC-32)
- Clínica fechada mas plantão de emergência disponível
- Sem limite de participantes, mas com hierarquia de prioridade
- #1 da lista = principal (primeiro a ser chamado)
- Gestor pode reordenar manualmente
- Se #1 cancela: #2 promove automaticamente para principal
- Pode coexistir com plantão presencial na mesma data (ex: plantão 8h-20h + sobreaviso 20h-8h)

### Auditoria e relatórios (PBINC-33)
- Log completo de todas as ações em `plantao_audit_log`
- Relatório de escalas por período
- Relatório de participação por plantonista (contagem de turnos)
- Relatório de cancelamentos e trocas
- Dashboard com alertas: datas sem vagas preenchidas, sobreaviso sem participantes

### Gestão de locais e configurações (PBINC-34)
- Locais cadastráveis em `plantao_locais`
- Configurações do módulo em `app_kv` com prefixo `plantao_`:
  - `plantao_prazo_cancelamento_horas_uteis` (padrão: 24)
  - `plantao_max_candidaturas_provisorias_por_vaga` (padrão: 3)
  - `plantao_notif_sobreaviso_dias_antecedencia` (padrão: 3)
  - `plantao_permitir_troca_sem_aprovacao_gestor` (padrão: false)

---

## Modelagem de dados (rascunho)

```
plantao_locais          — locais da clínica (multi-clínica)
plantao_perfis          — plantonistas cadastrados (separados de users)
plantao_sessoes         — sessões de auth dos plantonistas
plantao_datas           — datas de plantão publicadas
plantao_posicoes        — vagas por data (tipo: vet/auxiliar)
plantao_candidaturas    — candidaturas às posições
plantao_trocas          — solicitações de troca entre plantonistas
plantao_sobreaviso      — adesões ao sobreaviso com ordem de prioridade
plantao_audit_log       — log imutável de todas as ações
```

---

## Funcionalidades adicionais sugeridas (PBINC-35)

### Alta prioridade (MVP)
1. **Notificações in-app:** badge + lista de notificações para candidaturas aprovadas/recusadas, trocas solicitadas
2. **Perfil com CRMV:** campo obrigatório para veterinários; contato para emergências

### Média prioridade (Fase 2)
3. **Calendário visual interativo:** CSS Grid + HTMX, vistas mensal e semanal
4. **Limite de turnos por período:** gestor configura máximo X turnos/mês por plantonista; sistema bloqueia automaticamente

### Baixa prioridade (Fase 3+)
5. **Escala rotativa automática de sobreaviso:** sistema sugere #1 baseado em quem foi menos vezes principal
6. **Indicador de disponibilidade prévia:** plantonista sinaliza dias livres mesmo sem vaga publicada
7. **Avaliação pós-turno:** gestor registra observação + nota após encerramento

### Fora do escopo (MVP e além)
- Integração com Google Calendar/iCal
- App mobile nativo
- Biometria/geolocalização para check-in
- Apuração de comissão (responsabilidade do módulo financeiro)

---

## Roadmap sugerido

| Fase | Escopo |
|---|---|
| **MVP** | Auth isolado, publicação de escalas, candidatura + lista pública, cancelamento/troca/substituição, sobreaviso, auditoria básica, 3 relatórios principais, gestão de locais, notificações in-app, perfil com CRMV |
| **Fase 2** | Calendário visual, limite de turnos por período, escala rotativa de sobreaviso |
| **Fase 3** | Avaliação pós-turno, disponibilidade prévia, integrações externas |

---

## Modelagem de dados revisada (pós-adaptação 2026-04-12)

```
plantao_locais          — locais da clínica (multi-clínica)
plantao_perfis          — plantonistas cadastrados (separados de users)
plantao_sessoes         — sessões de auth dos plantonistas
plantao_tarifas         — valor-hora por tipo_perfil + dia_semana + subtipo [NOVO]
plantao_feriados        — feriados nacional/estadual/municipal por local [EXPANDIDO]
plantao_datas           — datas de plantão publicadas (+ campo subtipo) [EXPANDIDO]
plantao_posicoes        — vagas por data (tipo: vet/auxiliar)
plantao_candidaturas    — candidaturas + valor_hora_snapshot + valor_base_calculado [EXPANDIDO]
plantao_trocas          — solicitações de troca entre plantonistas
plantao_sobreaviso_adesoes — adesões ao sobreaviso com ordem de prioridade
plantao_notificacoes    — notificações in-app por plantonista
plantao_audit_log       — log imutável de todas as ações
```

## Regras de remuneração

**Veterinários:**
- Valor-hora varia por dia da semana (e por feriado)
- Piso mínimo = valor_hora_dia × horas_turno
- Remuneração real = MAX(piso, comissão apurada pelo módulo financeiro via SimplesVet)
- snapshot registrado no momento da confirmação da candidatura

**Auxiliares:**
- Valor-hora fixo (atualmente R$15/h, configurável)
- Sem variação por dia da semana
- Sem comissionamento — valor calculado é o valor final

## Integração futura com módulo financeiro

- Endpoint preparado: `GET /plantao/api/fechamento?data_inicio=&data_fim=&local_id=`
- Chave de identidade entre sistemas: `plantonista.email`
- Regra: `pagamento_vet = MAX(valor_base_calculado, comissao_simplesvet)`
- O módulo financeiro NUNCA escreve dados no módulo Plantão
- Handshake documentado como comentário no PBINC-25

## Cards Jira

### Discovery
| Card | Tema |
|---|---|
| PBINC-25 | Epic: Módulo Plantão |
| PBINC-27 | [Discovery] Arquitetura e modelagem de dados |
| PBINC-28 | [Discovery] Auth isolado: cadastro e aprovação |
| PBINC-29 | [Discovery] Publicação de escalas pelos gestores |
| PBINC-30 | [Discovery] Candidatura, lista pública e aprovação |
| PBINC-31 | [Discovery] Cancelamento, troca e substituição |
| PBINC-32 | [Discovery] Escala de disponibilidade e sobreaviso |
| PBINC-33 | [Discovery] Auditoria e relatórios |
| PBINC-34 | [Discovery] Gestão de locais e configurações |
| PBINC-35 | [Discovery] Funcionalidades sugeridas e análise de mercado |

### Implementação (Pronto pra incubar)
| Card | Tema |
|---|---|
| PBINC-36 | IMPL-01: Schema completo do banco (atualizado pós-adaptação) |
| PBINC-37 | IMPL-02: Auth completo |
| PBINC-38 | IMPL-03: Permissões e guards |
| PBINC-39 | IMPL-04: Shell visual |
| PBINC-40 | IMPL-05: Aprovação de cadastros |
| PBINC-41 | IMPL-06: Publicação de escalas (atualizado pós-adaptação) |
| PBINC-42 | IMPL-07: Candidatura e lista pública |
| PBINC-43 | IMPL-08: Cancelamento e horas úteis (atualizado pós-adaptação) |
| PBINC-44 | IMPL-09: Troca e substituição |
| PBINC-45 | IMPL-10: Sobreaviso |
| PBINC-46 | IMPL-11: Notificações in-app |
| PBINC-47 | IMPL-12: Auditoria e relatórios (atualizado pós-adaptação) |
| PBINC-48 | IMPL-13: Segurança |
| PBINC-49 | IMPL-14: Configurações e locais |
| PBINC-50 | IMPL-15: Estrutura de arquivos |
| PBINC-51 | IMPL-16: Edge cases e bugs potenciais |
| PBINC-52 | IMPL-17: Plano de execução e ordem |

### Adaptação pós-revisão (Pronto pra incubar)
| Card | Tema |
|---|---|
| PBINC-53 | IMPL-18: Tarifas de remuneração por dia da semana e tipo |
| PBINC-54 | IMPL-19: Subtipos de turno (regular/substituição/feriado) |
| PBINC-55 | IMPL-20: Feriados regionais + gerador automático de escala mensal |
| PBINC-56 | IMPL-21: Contrato de integração com módulo financeiro |
