# Financeiro - MVP de folha

Este modulo nasce como um MVP local para fechamento mensal da folha.

Objetivo imediato:
- consolidar dados manuais e pouco padronizados;
- aplicar regras simples por regime de remuneracao;
- gerar um fechamento auditavel e facil de iterar.
- preparar uma entrada caotica para futura normalizacao assistida por IA.

Principio do MVP1:
- IA entra depois para extrair e normalizar dados;
- o calculo precisa ficar deterministico;
- a saida final sempre deve permitir revisao humana.

Comandos:

```bash
python -m modules.financeiro init-periodo runtime-data/financeiro/fechamentos/2026-04 2026-04
python -m modules.financeiro init-competencia runtime-data/financeiro/competencias/2026-04 2026-04
python -m modules.financeiro indexar-pool runtime-data/financeiro/competencias/2026-04
python -m modules.financeiro fechar runtime-data/financeiro/fechamentos/2026-04
```

Arquivos esperados no periodo:
- `periodo.json`
- `colaboradores.json`
- `lancamentos.json`
- `escalas.json`
- `fontes_brutas.json`

Saidas geradas:
- `saida/resultado.json`
- `saida/resultado.csv`
- `saida/resultado.md`
- `saida/memoria_calculo.csv`

Estrutura de chaos pool criada por `init-competencia`:
- `pool/inbox/contabilidade`
- `pool/inbox/simplesvet`
- `pool/inbox/ponto`
- `pool/inbox/whatsapp`
- `pool/inbox/imagens`
- `pool/inbox/manual`
- `pool/inbox/outros`
- `pool/evidencias_indexadas.json`
- `pool/fila_normalizacao.json`
- `pool/regras_normalizacao.json`

Modos suportados no MVP1:
- `valor_importado`
- `horista`
- `comissao_percentual`
- `comissao_com_piso_diario`

Regra atual para `comissao_com_piso_diario`:
- a producao/comissao diaria do veterinario continua vindo de `lancamentos.json`;
- o direito ao piso minimo passa a vir de `escalas.json`;
- se existir `escalas.json`, o piso so e aplicado nas datas em que o veterinario
  aparece como `responsavel`;
- veterinarios de apoio no mesmo dia recebem apenas a comissao efetiva;
- se `escalas.json` estiver ausente, o motor entra em modo legado e aplica o piso
  diario em todas as datas do colaborador, com aviso no resultado.

Categorias de desconto suportadas:
- `adiantamento`
- `consumo_em_aberto`
- `falha_veterinaria`
- `desconto_manual`

Categorias adicionais de credito:
- `bonus_manual`
- `credito_manual`
- `reembolso`

Direcao recomendada:
- usar o pool como entrada unica de evidencias;
- indexar tudo automaticamente;
- normalizar com IA para um schema canonico;
- manter o calculo final deterministico.
