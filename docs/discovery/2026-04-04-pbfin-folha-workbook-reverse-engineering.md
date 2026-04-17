# Discovery - Engenharia reversa da planilha de folha

Data: 2026-04-04
Escopo Jira: `PBFIN-2`

## Fonte analisada

Planilha local usada hoje para fechamento da folha e comissoes.

Observacoes relevantes da fonte:
- 28 abas no total;
- mistura de abas visiveis em uso atual e abas ocultas historicas;
- parte da logica esta consolidada por pessoa, parte por funcao, parte em bases operacionais;
- ha blocos reaproveitados dentro da mesma aba, com evolucao de raciocinio ao longo do tempo;
- datas aparecem em varios pontos como serial date do Excel;
- varios totais estao com precisao de ponto flutuante sem arredondamento final.

## Leitura estrutural das abas

### 1. Fechamento consolidado

#### `Geral`

E a aba mais proxima do output final mensal.

Colunas observadas:
- `Data`
- `Pessoa`
- `Fixo`
- `Comissao`
- `Avulso`
- `H. Extra`
- `Vale`
- `Arred`
- `Total`
- `Compras`
- `Total`
- `Provisao`
- `Obs`
- `Provisoes`

Interpretacao:
- cada linha representa um fechamento por pessoa em um periodo;
- o consolidado mistura componentes fixos, variaveis, descontos e ajustes;
- `Vale` aparece com sinal negativo;
- `Arred` e `Provisao` indicam ajuste manual/contabil para fechar numero final;
- `Compras` parece ser um desconto ou controle separado por consumo interno;
- `Obs` e `Provisoes` guardam justificativas ou status do fechamento.

Conclusao:
- esta aba e o benchmark de saida esperado do MVP;
- o MVP deve conseguir reproduzir um resumo por colaborador com estas categorias.

### 2. Veterinarios por comissao com piso

#### `Com.Vet`

Racional encontrado:
- calculo diario por data;
- comparacao entre minimo de plantao e comissao apurada;
- pagamento do maior valor entre piso/minimo e comissao;
- bloco final com ajustes, descontos e total final.

Sinais importantes:
- colunas com `Min. Plantao`, `Minimo`, `Comissao`, `Resultante`;
- linhas finais com `Adicional ref. Diferença`, `Descontos`, `Resultante`, `Acerto por fora`, `Compras`, `Ajuste`, `Total final`.

Conclusao:
- o modelo de `comissao_com_piso_diario` do MVP esta alinhado com esta logica;
- ainda faltam no MVP alguns componentes finais dessa aba:
  - `acerto por fora`
  - `compras`
  - `ajuste`
  - separacao por veterinario dentro do mesmo fechamento.

### 3. Tosadora com base operacional detalhada

#### `Carina Tosadora`

Racional encontrado:
- calculo por dia com horas e quantidade de tosas;
- valor-hora/valor-dia;
- bloco final com itens trabalhistas e total;
- mistura de producao operacional com verbas tipo rescisorias/provisionadas.

Linhas finais relevantes:
- `HE (60%)`
- `HE (100%)`
- `13º`
- `Férias`
- `FGTS`
- `Comissão`
- `Total`

Conclusao:
- esta aba nao e so comissao de tosa;
- ela combina jornada, adicionais e reflexos trabalhistas;
- para o MVP, isso sugere separar:
  - eventos de jornada;
  - eventos de producao/comissao;
  - verbas calculadas derivadas.

### 4. Horista / auxiliar com base em ponto manual

#### `Júlia Auxiliar Vet`

Racional encontrado:
- horas calculadas por dia a partir de chegada, saida e almoco;
- valor-hora pode mudar por lancamento;
- existe bloco de totalizacao de horas e totais por faixa;
- resultado final e um total monetario do periodo.

Campos observados:
- `Data`
- `Chegada`
- `Saída`
- `Almoço`
- `Observações`
- `Vlr. Hora`
- `Vlt. Tot.`

Mais abaixo:
- blocos com multiplas entradas/saidas por dia;
- totalizacao por faixas de hora;
- linha `Total`.

Conclusao:
- o MVP precisa aceitar tanto horas ja consolidadas quanto batidas cruas;
- no curto prazo, da para alimentar o MVP com `quantidade` de horas consolidadas;
- no medio prazo, vale ter parser para ponto bruto e WhatsApp.

### 5. Base operacional de tosa

#### `Com.Tosa` e `Com.Tosa (2)`

Essas abas parecem ser a base operacional mais rica para comissao de tosa.

Colunas observadas:
- identificacao da venda e baixa;
- forma de pagamento;
- funcionario;
- cliente e animal;
- grupo e produto/servico;
- bruto, desconto, liquido;
- `%desconto`;
- `Comissão`;
- `Pessoa`.

Conclusao:
- a comissao de tosa hoje ja nasce quase pronta por item;
- o campo `Pessoa` parece identificar a favorecida da comissao;
- o valor em `AE` ja parece a comissao por linha;
- estas abas sao candidatas fortes a importacao sem IA no MVP2.

### 6. Base operacional geral

#### `Base Vendas`

E a base mais ampla de vendas/servicos da clinica.

Contem:
- servicos e produtos;
- funcionario ligado a venda;
- cliente, animal e item;
- bruto, desconto e liquido;
- observacoes comerciais/operacionais.

Conclusao:
- esta aba e uma boa fonte para reconciliar producao, mas nao e o fechamento em si;
- ela pode alimentar regras futuras para comissao de vets, banho, tosa e falhas de cobranca.

### 7. Base itemizada de comissoes clinicas

#### `Base Comissões`

E uma base derivada mais proxima do calculo de comissao veterinaria.

Campos observados:
- `Mês ref.`
- `Data`
- `Venda`
- `Código`
- `Item`
- `Cliente`
- `Baixa`
- `Base`
- `Percentual`
- `Comissão`

Conclusao:
- esta aba parece ser uma ponte ideal entre operacao e folha;
- para veterinarios, ela e melhor fonte do que a `Base Vendas`;
- o MVP pode importar diretamente essa estrutura como eventos de comissao.

### 8. Ponto bruto

#### `Ponto`

Export cru do relogio/ponto.

Sinais:
- colunas tecnicas como `No`, `Mchn`, `EnNo`, `Mode`, `IOMd`, `DateTime`;
- blocos auxiliares por pessoa/data;
- varios `#NUM!`, sugerindo formulas parciais ou arrasto de planilha.

Conclusao:
- esta aba e fonte bruta, nao output;
- ela deve entrar no sistema como evidência, nao como fechamento pronto;
- faz sentido deixar para IA/parser depois, nao para o MVP1 imediato.

### 9. Rescisoes

#### `Rescisões`, `Rescisão Maria` e outras abas de rescisao

Racional encontrado:
- fluxo separado do fechamento mensal normal;
- mistura de verbas rescisorias, debitos, devolucao de multa e meios de pagamento;
- em `Rescisão Maria` existe reaproveitamento de logica de ponto + verbas finais.

Conclusao:
- rescisao deve ser tratada como fluxo proprio;
- nao deve contaminar o fechamento mensal padrao no mesmo motor sem separacao de tipo.

## Leitura funcional do processo atual

A planilha sugere este processo mental hoje:

1. usar bases operacionais para calcular variaveis por modalidade;
2. consolidar o valor por pessoa em abas especificas;
3. levar esse numero para a aba `Geral`;
4. aplicar descontos, compras, provisoes e ajustes;
5. fechar manualmente o total final;
6. tratar rescisoes em fluxo separado.

## Saidas esperadas do futuro sistema

Pelo comportamento da planilha, o sistema precisa gerar pelo menos:

- resumo por colaborador e periodo;
- detalhamento dos componentes do bruto;
- detalhamento dos descontos;
- trilha da origem de cada numero;
- avisos do que foi manual, provisao ou ajuste;
- modo separado para rescisao.

## Mapeamento inicial para o MVP atual

Mapeamento sugerido do workbook para o modelo canonico:

- `Fixo` -> `valor_importado` ou `fixo`
- `Comissão` -> `comissao_calculada`
- `Avulso` -> `bonus_manual` ou `credito_manual`
- `H. Extra` -> `hora_extra`
- `Vale` -> `adiantamento`
- `Compras` -> `consumo_em_aberto`
- `Arred` -> `ajuste_manual`
- `Provisão` / `Provisões` -> `provisao` ou anotacao de fechamento
- `Base Comissões` -> eventos de `base_comissao` ou `comissao_calculada`
- `Com.Tosa` -> eventos de `comissao_tosa_item`
- `Ponto` -> evidência bruta de jornada

## Implicacoes para a evolucao do MVP

### O que ja esta bem alinhado

- calculo por `valor_importado`;
- calculo por `horista`;
- calculo por `comissao_percentual`;
- calculo por `comissao_com_piso_diario`;
- saida resumida por colaborador.

### O que ainda falta para aderir melhor a planilha real

- categoria nativa de `hora_extra`;
- categoria nativa de `ajuste_manual`;
- categoria nativa de `provisao`;
- importacao de bases itemizadas (`Base Comissões`, `Com.Tosa`);
- suporte explicito a fechamento de rescisao;
- agrupamento de multiplos blocos/origens por colaborador no mesmo periodo;
- leitura de datas do Excel e de fontes cruas como ponto/WhatsApp.

## Proposta de ordem de ataque

1. usar a aba `Geral` como referencia de validacao do resultado final;
2. alimentar manualmente o MVP com os colaboradores do periodo atual;
3. importar primeiro as bases mais estruturadas:
   - `Base Comissões`
   - `Com.Tosa`
4. deixar `Ponto` e prints/WhatsApp para uma etapa assistida por IA;
5. criar um fluxo separado de `rescisao`.

## Decisao sugerida

Para sair rapido com algo funcional:

- manter o MVP1 com entrada manual em JSON;
- usar esta planilha como mapa de dominio e referencia de conferência;
- importar automaticamente apenas o que ja estiver muito estruturado;
- tratar o resto como evidência bruta para revisao humana.
