# Manual de uso — Fechamento de Folha PinkBlue Vet

## Como abrir

No terminal, a partir da raiz do projeto:

```bat
folha           ← abre a competência 2026-04 (padrão)
folha 2026-03   ← abre outra competência
```

Ou diretamente:
```bat
npx --prefix modules\financeiro\tui ts-node --project modules\financeiro\tui\tsconfig.json modules\financeiro\tui\src\index.tsx 2026-04
```

---

## Fluxo resumido

```
1. Coloque os arquivos no pool
2. Indexe o pool (tecla i na tela Pool)
3. Processe cada arquivo com IA (tecla p)
4. Revise e corrija o que a IA extraiu
5. Aceite as extrações (tecla a)
6. Feche a folha (menu → Fechar folha)
7. Veja os resultados (menu → Ver resultados)
```

---

## Passo 1 – Organize os arquivos de entrada

Coloque cada arquivo no bucket correspondente dentro de:
```
runtime-data/financeiro/competencias/YYYY-MM/pool/inbox/
```

| Bucket          | O que colocar                                          |
|-----------------|--------------------------------------------------------|
| `contabilidade/`| PDF da folha calculada pela contabilidade (CLT)        |
| `simplesvet/`   | Export de comissões ou vendas do SimplesVet (.xlsx)    |
| `ponto/`        | Export bruto do relógio de ponto                       |
| `whatsapp/`     | Texto exportado do WhatsApp com batidas / horários     |
| `imagens/`      | Fotos de ponto, recibos, comprovantes                  |
| `manual/`       | Planilhas Excel ou CSV montadas manualmente            |
| `outros/`       | Qualquer evidência que não se encaixe acima            |

> **Dica de nomeação:** use nomes descritivos, ex.:
> `simplesvet/base-comissoes-abr2026.xlsx`
> `whatsapp/batidas-ana-paula-abr2026.txt`

---

## Passo 2 – Indexe o pool

1. Abra a TUI: `folha`
2. Selecione **Pool de evidências**
3. Pressione `i` — o sistema percorre o `inbox/`, calcula hash, infere o perfil de cada arquivo e monta a fila de normalização

Após indexar você verá cada arquivo com seu **perfil** atribuído:
- `folha_contabilidade_pdf` — PDF de folha
- `comissao_itemizada` — planilha de comissões
- `whatsapp_texto` — texto de WhatsApp
- `ponto_bruto` — ponto bruto
- `imagem_ocr` — imagem (requer revisão humana)
- `planilha_manual` — planilha manual

---

## Passo 3 – Processe com IA

Para cada arquivo de texto/planilha:

1. Selecione o arquivo com `↑` `↓`
2. Pressione `p` — a IA lê o conteúdo e extrai lançamentos

A IA retorna para cada linha:
- colaborador identificado
- categoria do lançamento
- valor e/ou quantidade
- data (quando disponível)
- nível de confiança (`high`, `medium`, `low`)
- nota de dúvida (quando houver)

> **Limitação atual:** arquivos binários (PDF, imagens) não são processados
> automaticamente — precisam ser inseridos manualmente ou aguardar integração OCR.

---

## Passo 4 – Revise e corrija

Após o processamento, você entra na tela de **Revisão**:

```
↑↓   navegar entre as entradas extraídas
e    editar a entrada selecionada
a    aceitar todas as entradas e salvar
x    rejeitar tudo (nenhum lançamento salvo)
q    voltar à lista
```

Na **edição** de uma entrada:
```
↑↓         mudar de campo
Enter      começar a editar o campo atual
s          salvar e voltar à revisão
Esc        cancelar e voltar
```

Para `colaborador_id` e `categoria`, aparece um menu de opções.
Para `valor`, `quantidade`, `data` e `descrição`, aparece um campo de texto livre.

> **Quando editar:** sempre que a IA errar o colaborador, a categoria ou o valor.
> Entradas com `confidence: low` merecem atenção especial.

---

## Passo 5 – Feche a folha

Após revisar e aceitar as extrações, as entradas são salvas em `lancamentos.json`.

Para fechar:
1. Volte ao menu principal
2. Selecione **Fechar folha**
3. O motor Python calcula cada colaborador e gera os arquivos de saída

---

## Passo 6 – Veja os resultados

Na tela **Resultados**:
```
↑↓     navegar entre colaboradores
Enter  ver detalhamento completo do colaborador
r      recalcular (refaz o fechamento)
q      voltar
```

O detalhamento mostra cada provento com o cálculo aplicado:
- para comissão com piso: base, comissão calculada, piso elegível, qual foi usado
- para horista: horas × valor-hora
- descontos separados por categoria

---

## Arquivos gerados

Após fechar, os resultados ficam em:

```
runtime-data/financeiro/competencias/YYYY-MM/saida/
  resultado.json        resultado estruturado completo
  resultado.md          relatório legível
  resultado.csv         tabela resumida (para Excel)
  memoria_calculo.csv   trilha de cada linha de cálculo (auditoria)
```

---

## Inserção manual de lançamentos

Quando não há arquivo para processar, edite diretamente:
```
runtime-data/financeiro/competencias/YYYY-MM/lancamentos.json
```

Exemplo de lançamento:
```json
{
  "colaborador_id": "kivia",
  "categoria": "producao_vet",
  "data": "2026-04-15",
  "valor": 820.00,
  "descricao": "Produção 15/04",
  "fonte": "manual"
}
```

---

## Configurar IA (Claude)

Para usar o processamento de IA, configure a variável de ambiente antes de abrir a TUI:

```bat
set ANTHROPIC_API_KEY=sk-ant-api03-...
folha
```

Ou adicione ao seu perfil de usuário para não precisar repetir.

---

## Modos de remuneração suportados

| Modo                      | Como configurar em colaboradores.json                   |
|---------------------------|----------------------------------------------------------|
| `valor_importado`         | `"modo": "valor_importado"` — salário CLT bruto         |
| `horista`                 | `"modo": "horista", "config": {"valor_hora": 18}`       |
| `comissao_percentual`     | `percentual_comissao` + `base_categories`               |
| `comissao_com_piso_diario`| `percentual_comissao` + `piso_diario` + `escalas.json`  |

Para piso diário de veterinário, adicione em `escalas.json`:
```json
{
  "data": "2026-04-01",
  "colaborador_id": "kivia",
  "tipo": "responsavel",
  "piso_minimo": 250
}
```
O piso só é aplicado nos dias em que o vet aparece como `responsavel` na escala.

---

## Criar nova competência

```bat
python -m modules.financeiro init-competencia runtime-data/financeiro/competencias/2026-05 2026-05
```

Depois edite os arquivos gerados:
- `colaboradores.json` — lista de colaboradores e modos
- `lancamentos.json` — lançamentos manuais iniciais
- `escalas.json` — escalas de plantão (para veterinários)
