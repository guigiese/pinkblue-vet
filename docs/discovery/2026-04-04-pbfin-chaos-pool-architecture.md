# Discovery - Arquitetura do chaos pool para folha

Data: 2026-04-04
Escopo Jira: `PBFIN-2`

## Objetivo

Montar uma arquitetura onde o fechamento da folha dependa o minimo possivel de operacao manual.

Direcao:
- entradas caoticas entram sem grande friccao;
- conectores e arquivos convivem no mesmo fluxo;
- IA estrutura e classifica;
- calculo final permanece deterministico e auditavel;
- humano revisa excecoes, nao cada numero bruto.

## Principio central

Nao usar IA para fechar a folha diretamente.

Usar IA para:
- identificar que tipo de evidencia cada arquivo representa;
- extrair campos relevantes;
- normalizar para um schema canonico;
- apontar incertezas e lacunas;
- sugerir classificacao e vinculo por colaborador.

Usar regras deterministicas para:
- aplicar piso, percentual, hora, adicionais e descontos;
- consolidar por colaborador;
- gerar valores finais;
- comparar resultado atual versus benchmark conhecido.

## Fluxo proposto

### Etapa 1. Entrada unica de evidencias

Cada competencia mensal vira um workspace proprio.

Estrutura sugerida:

```text
competencias/YYYY-MM/
  periodo.json
  colaboradores.json
  lancamentos.json
  fontes_brutas.json
  pool/
    inbox/
      contabilidade/
      simplesvet/
      ponto/
      whatsapp/
      imagens/
      manual/
      outros/
    evidencias_indexadas.json
    fila_normalizacao.json
    conectores.json
    regras_normalizacao.json
    normalized/
    archive/
    rejected/
```

Regra:
- qualquer coisa entra no `pool/inbox`;
- o sistema indexa e classifica por perfil;
- so depois disso vira evento canonico.

### Etapa 2. Indexacao

O indexador faz:
- hash do arquivo;
- bucket de origem;
- mime type;
- tamanho e data de modificacao;
- perfil sugerido de extracao;
- objetivo do prompt de normalizacao;
- fila de trabalho para IA.

Isso reduz o trabalho humano para apenas:
- largar arquivos no lugar certo;
- eventualmente corrigir bucket quando o arquivo estiver muito ambiguo.

### Etapa 3. Normalizacao assistida por IA

Cada perfil de evidencia gera um schema alvo.

Perfis iniciais:
- `folha_contabilidade_pdf`
- `simplesvet_export`
- `comissao_itemizada`
- `ponto_bruto`
- `whatsapp_texto`
- `imagem_ocr`
- `planilha_manual`
- `generico`

Saida esperada da IA:
- JSON estrito por schema;
- `confidence`;
- `warnings`;
- `needs_human_review`;
- `source_trace` com o arquivo original.

### Etapa 4. Canonical event store

Tudo o que vier da IA precisa convergir para um schema unico de eventos.

Schema conceitual minimo:
- `competencia`
- `colaborador_id`
- `tipo_evento`
- `subtipo`
- `data_referencia`
- `valor`
- `quantidade`
- `valor_unitario`
- `origem`
- `arquivo_origem`
- `confidence`
- `observacoes`
- `status_validacao`

Exemplos de `tipo_evento`:
- `fixo`
- `hora_trabalhada`
- `hora_extra`
- `comissao_item`
- `comissao_diaria`
- `adiantamento`
- `consumo_interno`
- `falha_veterinaria`
- `ajuste_manual`
- `provisao`
- `rescisao`

### Etapa 5. Motor de calculo

O motor le apenas eventos canonicos.

Ele nao precisa saber se a origem veio de:
- PDF;
- export do SimplesVet;
- print;
- WhatsApp;
- planilha manual.

Ele so recebe eventos normalizados e aplica:
- regra do colaborador;
- parametros de remuneracao;
- descontos e adicionais;
- consolidacao final.

### Etapa 6. Revisao por excecao

O ideal nao e revisar todo mundo todo mes.

O ideal e revisar apenas:
- eventos com `confidence` baixa;
- arquivos com perfil `ponto_bruto`, `imagem_ocr` ou `whatsapp_texto`;
- colaboradores com diferenca relevante contra benchmark;
- itens sem colaborador vinculado;
- valores fora de faixa esperada.

## Recomendacao de IA

### Recomendacao principal

Usar OpenAI via API, nao o app interativo do Codex, para o pipeline recorrente.

Motivo:
- o produto de API e a superficie pensada para construir fluxo proprio;
- o Responses API suporta loop agentico com ferramentas;
- a stack atual de modelos suporta imagem como entrada e Structured Outputs.

### Modelo sugerido

Recomendacao inferida das docs atuais:
- `gpt-5.4-mini` como modelo padrao de normalizacao;
- `gpt-5.4` como fallback para casos ambiguos ou lotes pequenos mais complexos.

Justificativa:
- `gpt-5.4-mini` foi posicionado pela OpenAI como mini forte para workloads de alto volume;
- aceita texto e imagem;
- suporta Structured Outputs;
- suporta ferramentas no Responses API.

### Onde a IA entra

Usos ideais:
- OCR inteligente de imagens de ponto;
- parse de PDFs da contabilidade;
- interpretacao de exports heterogeneos;
- parse de WhatsApp;
- classificacao de descontos e ajustes;
- vinculo de evidencias ao colaborador correto.

Usos nao ideais:
- decidir valor final da folha sem schema;
- compensar ausencia total de regra de negocio;
- fazer fechamento “magico” sem trilha auditavel.

## Recomendacao de stack do pipeline

### Camada local

Continuar local por enquanto:
- filesystem como caixa de entrada;
- JSON como store intermediaria;
- Python como orquestrador;
- sem web publica.

### Camada de IA

Proposta:
- Responses API;
- `text.format` com `json_schema`;
- upload de arquivos com `purpose=user_data` quando fizer sentido;
- lote por evidencia ou por bloco coerente.

### Camada de persistencia futura

Quando o fluxo estabilizar:
- migrar de JSON para SQLite;
- manter arquivos no filesystem;
- registrar no banco apenas metadados, eventos canonicos e revisoes.

## O que isso resolve no teu caso

### CLT

Entrada:
- PDF/planilha da contabilidade.

IA:
- extrai bruto, descontos, liquido, observacoes.

Motor:
- trata como `valor_importado` com descontos identificados.

### Horistas e pessoal por fora

Entrada:
- prints de ponto, planilhas, WhatsApp, export do relogio.

IA:
- transforma em eventos de jornada e horas.

Motor:
- aplica valor-hora, hora extra e descontos.

### Free por hora

Entrada:
- mensagens, planilhas ou logs de chamada.

IA:
- extrai data, horas, valor por hora e observacoes.

Motor:
- consolida horas e total.

### Veterinarios

Entrada:
- `Base Comissões`, `Com.Vet`, exports do SimplesVet.

IA:
- normaliza item por item ou dia por dia.

Motor:
- calcula comissao;
- compara com piso diario;
- aplica adicionais, descontos e falhas.

### Tosadora

Entrada:
- `Com.Tosa`, `Carina Tosadora`, exports de vendas.

IA:
- extrai itens de comissao e jornada quando houver.

Motor:
- consolida comissao e verbas complementares.

## Fases sugeridas

### MVP1

- entrada manual em JSON;
- calculo deterministico;
- benchmark contra `Geral`.

### MVP2

- chaos pool local;
- indexacao automatica;
- importacao automatica de `Base Comissões` e `Com.Tosa`;
- fila pronta para IA.

### MVP3

- normalizacao real por IA;
- revisao por excecao;
- reaproveitamento automatico de regras por colaborador.

### MVP4

- conectores diretos;
- agendamento por competencia;
- historico, comparativo e alertas de anomalia.

## Decisao proposta

Implementar desde ja a espinha dorsal correta:
- competencia com `pool`;
- indexador de evidencias;
- fila de normalizacao;
- calculo deterministico separado.

Isso te deixa livre para prototipar rapido agora sem jogar fora a base quando a IA entrar de verdade.
