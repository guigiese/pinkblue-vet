# AI Testing Standard

Documento canonico para sessoes de teste assistidas por IA na plataforma PinkBlue Vet.

Este documento define o processo estavel e reutilizavel entre modulos.
Ele nao deve depender de detalhes de um modulo especifico.

## 1. Objetivo

Padronizar como a IA deve:

- mapear um modulo antes dos testes;
- propor ao usuario o que pode ser testado;
- receber e registrar o recorte aprovado;
- executar os testes aprovados;
- classificar e registrar achados;
- lidar com riscos, ambiguidades e acoes sensiveis;
- decidir quando pedir confirmacao adicional;
- tratar a eventual abertura de cards Jira.

## 2. Modelo de artefatos

### 2.1. Artefato canonico

Artefato duravel de processo:

- `docs/testing/AI_TESTING_STANDARD.md`

Este arquivo contem as regras estaveis que valem para qualquer modulo.

### 2.2. Artefato de mapeamento

Cada ciclo de teste pode ter um mapeamento previo reutilizavel.

O mapeamento deve registrar:

- o estado observado do modulo;
- o inventario relevante para teste;
- os cenarios possiveis;
- os pacotes sugeridos pela IA;
- os riscos e restricoes identificados;
- o escopo completo possivel de execucao.

O mapeamento existe para orientar uma ou mais rodadas de teste.

### 2.3. Artefato de rodada

Cada execucao de teste deve gerar uma rodada.

A rodada deve registrar:

- o mapeamento usado como base;
- o recorte aprovado pelo usuario;
- o que foi efetivamente executado;
- o resultado de cada item executado;
- os achados;
- as evidencias;
- as pendencias;
- os proximos passos.

### 2.4. Sem documento fixo por modulo

Por padrao, nao deve existir documento permanente de teste por modulo.

Motivo:

- os modulos podem mudar rapido;
- o mapeamento deve refletir o estado atual;
- a base reutilizavel do processo deve ficar no canonico, nao em descricoes estaticas de modulo.

## 3. Principios operacionais

### 3.1. Isolamento de sessao

Quando houver trabalho paralelo em andamento:

- a sessao de teste deve ocorrer em worktree isolado;
- a sessao deve ter branch propria;
- a IA nao deve disputar o mesmo workspace usado por outra IA ou por outra frente ativa.

### 3.2. Mapeamento previo obrigatorio

Antes de executar qualquer rodada, a IA deve trabalhar a partir de um mapeamento valido.

Esse mapeamento pode ser:

- novo;
- reutilizado;
- atualizado parcialmente.

### 3.3. Sem abertura automatica de card

Durante as rodadas de teste:

- a IA nao deve criar cards Jira automaticamente;
- a criacao de qualquer card depende de aprovacao explicita do usuario.

### 3.4. Processo orientado por aprovacao

A IA pode sugerir, priorizar e recomendar.
A decisao final sobre o recorte da rodada pertence ao usuario.

## 4. Criticidade dos achados

Os achados devem ser classificados apenas nestes niveis:

- `critico`
- `alta`
- `media`
- `baixa`

A criticidade deve refletir impacto, risco e urgencia.

## 5. Fluxo macro da sessao de testes

Fluxo esperado:

1. ler este documento canonico;
2. localizar mapeamento anterior, se houver;
3. verificar com o usuario se o mapeamento deve ser reutilizado, atualizado ou refeito;
4. produzir ou atualizar o mapeamento;
5. apresentar proposta objetiva de rodada;
6. obter aprovacao explicita do usuario;
7. executar apenas o recorte aprovado;
8. registrar resultados por item;
9. reportar achados por criticidade;
10. pedir aprovacao antes de qualquer criacao de card Jira.

## 6. Mapeamento

O mapeamento nao executa testes.
Ele existe para entender o modulo e preparar a rodada.

O mapeamento deve, no minimo, levantar:

- artefatos relevantes;
- telas, rotas ou superficies;
- perfis de usuario;
- dispositivos ou contextos de uso;
- tipos de teste possiveis;
- fluxos ponta a ponta possiveis;
- cenarios executaveis;
- dependencias;
- limitacoes;
- riscos e ambiguidades;
- itens ja conhecidos.

Se existir documentacao tecnica ou de negocio claramente ligada ao modulo em escopo,
a IA deve le-la antes do mapeamento.

Essa leitura deve se limitar a documentacao claramente ligada ao modulo em escopo.

O mapeamento nao deve assumir que a documentacao do modulo esta atualizada.

Alem dos itens acima, o mapeamento deve obrigatoriamente realizar duas verificacoes adicionais:

**Consistencia de contratos entre camadas**: Para cada componente inspecionado, verificar se identificadores nomeados — IDs de conector, chaves de permissao, nomes de perfil, strings de roteamento — sao os mesmos no arquivo de configuracao, na camada de armazenamento, no roteador e nos templates. Qualquer divergencia deve ser registrada como item `CNT` no inventario (ver secao 9), mesmo que o sistema funcione aparentemente bem no caminho feliz.

**Qualidade de experiencia do usuario**: Registrar sinais de problemas de usabilidade observados nos artefatos inspecionados — vocabulario inconsistente, campos aparentemente redundantes, trocas de tela evitaveis, affordances enganosas. Esses sinais devem ser registrados como itens `UXQ` no inventario para avaliacao durante a rodada.

## 7. Reuso de mapeamento

Se ja existir mapeamento anterior, a IA deve informar isso ao usuario e oferecer tres caminhos:

- reutilizar o mapeamento anterior;
- atualizar parcialmente o mapeamento anterior;
- gerar um novo mapeamento completo.

O mapeamento anterior deve ser tratado com cautela se houver sinais de mudanca relevante, como:

- mudanca de branch;
- mudanca de ambiente;
- mudanca importante no codigo;
- mudanca de escopo;
- mudanca dos perfis ou dispositivos alvo.

## 8. Resposta em tela e arquivo completo

O mapeamento deve gerar duas saidas:

- um arquivo completo de mapeamento;
- um resumo curto em tela para decisao do usuario.

O resumo em tela deve mostrar, de forma objetiva:

- entendimento do modulo;
- o que foi mapeado;
- o que pode ser testado;
- o que a IA sugere rodar;
- o que depende de decisao do usuario;
- referencia para o arquivo completo.

## 9. Inventario selecionavel

Depois do mapeamento, a IA deve transformar a descoberta em itens selecionaveis pelo usuario.

Esses itens devem ter identificadores curtos e claros.

Exemplos de grupos de identificadores:

- `ART` para artefatos
- `PER` para perfis
- `DIS` para dispositivos
- `TIP` para tipos de teste
- `FLX` para fluxos
- `CEN` para cenarios
- `EXP` para exploracao guiada
- `NEG` para inconsistencia ou cenarios negativos
- `BND` para limites e bordas
- `VIS` para revisao visual
- `PKG` para pacotes sugeridos
- `FULL` para escopos completos
- `LIM` para limites operacionais
- `RST` para riscos ou restricoes
- `KI` para known issues
- `WA` para excecoes ou workarounds aceitos temporariamente
- `CNT` para contratos entre camadas (consistencia de identificadores entre config, storage, router e template — verificado no mapeamento)
- `UXQ` para qualidade de experiencia do usuario (campo sem necessidade aparente, acao que exige troca de tela evitavel, vocabulario inconsistente, affordance enganosa, aparencia que confunde, etc.)

Os identificadores devem existir para facilitar a resposta do usuario e o rastreamento da execucao.

## 10. Nivel de confianca

A IA pode usar nivel de confianca para itens mapeados.

Isso nao pode virar muleta para deixar de mapear algo ao alcance dela.
A IA deve tentar confirmar tudo que puder.

Quando um item ficar como `inferido` ou `precisa validar com o usuario`, ele deve trazer:

- descricao;
- motivo da duvida;
- pergunta objetiva para o usuario responder.

## 11. Sugestoes pre-prontas da IA

A IA nao deve apenas listar possibilidades.
Ela deve sugerir opcoes prontas de execucao.

Essas sugestoes podem incluir:

- pacotes minimos;
- pacotes por perfil;
- pacotes por tipo de teste;
- pacotes por criticidade;
- escopos completos;
- sugestoes de rerun apos correcoes.

A IA deve sempre sugerir, quando fizer sentido, vetores de:

- exploracao guiada;
- inconsistencia ou negativo;
- limites e bordas;
- revisao visual;
- permissao;
- qualidade de experiencia do usuario (UXQ) — obrigatorio em qualquer modulo com telas interativas;
- contratos entre camadas (CNT) — obrigatorio sempre que o modulo tiver conectores, permissoes, perfis ou identificadores nomeados compartilhados entre camadas.

Essas sugestoes devem ser priorizadas especialmente em telas com interacoes mais propensas a problemas.

## 12. Escopo completo

O mapeamento deve definir de forma clara o que significa executar o modulo de forma completa.

Esse escopo completo pode ser apresentado em variacoes como:

- completo funcional;
- completo visual;
- completo de permissoes;
- completo ponta a ponta;
- completo combinado.

"Executar completo" nao deve ser tratado como instrucao ambigua.

## 13. Aprovacao do usuario

Depois do mapeamento, a IA deve apresentar ao usuario uma proposta objetiva de rodada.

Essa proposta deve permitir selecao explicita de:

- ambiente;
- perfis;
- dispositivos;
- fluxos;
- cenarios;
- pacotes sugeridos;
- escopo completo, se aplicavel;
- limites operacionais.

O recorte aprovado deve ser registrado com status claros, como:

- `aprovado`
- `nao aprovado`
- `bloqueado`
- `nao aplicavel`

## 14. Regras de risco e confirmacao

Se houver ambiguidade relevante, risco alto, acao sensivel ou possibilidade de impacto operacional,
a IA deve parar e pedir confirmacao explicita.

Isso vale especialmente quando houver:

- mutacao de dados;
- mudanca de estado operacional;
- risco clinico, financeiro, de permissao ou de exposicao indevida;
- achado critico cuja continuidade do teste possa agravar impacto;
- duvida real sobre efeitos colaterais da acao.

PRD esta fora do escopo deste processo por enquanto.

Nesses casos, a IA deve explicar de forma objetiva:

- o que pretende fazer;
- onde pretende fazer;
- qual e o risco;
- qual e o impacto esperado;
- quais efeitos colaterais podem existir.

## 15. Execucao da rodada

A rodada deve ser executada apenas dentro do recorte aprovado.

Para cada item executado, a IA deve registrar status adequados, como:

- `selecionado`
- `executado`
- `nao executado`
- `bloqueado`
- `abortado`
- `retestado`
- `aprovado`
- `reprovado`

### 15.1. Distincao obrigatoria entre back-end e UI

A IA deve deixar explicito, para cada fluxo relevante, qual foi o nivel real de validacao:

- `back-end validado`
- `UI validada`
- `back-end e UI validados`

Um endpoint funcional nao pode ser reportado como substituto silencioso de uma interface funcional.

Se a acao funcionou apenas por chamada direta de endpoint, mas nao pela tela, isso deve ser tratado como problema de UI ou de integracao, nao como fluxo aprovado.

### 15.2. Cobertura minima de telas interativas

Toda tela interativa incluida na rodada deve passar, no minimo, por estas verificacoes quando forem aplicaveis:

- abertura renderizada real da tela;
- espera curta apos a carga inicial para verificar o estado depois da hidratacao do JavaScript;
- observacao de `console errors` e `page errors`;
- acionamento dos CTAs primarios e controles principais da tela;
- verificacao se o estado exibido e realmente vazio ou se esta quebrado;
- registro explicito de qualquer bloqueio que tenha impedido essas validacoes.

Se alguma dessas verificacoes nao puder ser feita, a limitacao deve ser declarada no resultado da rodada.

### 15.3. Telas dirigidas por JavaScript

Em telas cujo comportamento depende de JavaScript no cliente, Alpine, Reactividade, componentes dinamicos ou serializacao de dados para scripts:

- a IA deve validar o estado inicial;
- a IA deve validar o estado apos a hidratacao;
- a IA deve checar erros de parse, inicializacao ou funcoes ausentes;
- a IA nao deve considerar a tela aprovada apenas porque o HTML inicial apareceu por instantes.

Estados do tipo "pisca e some", "renderiza e limpa", "botao sem resposta" ou "painel nao abre" devem ser tratados como falhas reais de interface.

## 16. Evidencia visual

Para validacao visual, tela renderizada observada pela IA ja basta.

A IA nao deve tratar leitura de codigo, HTML ou CSS como substituto silencioso de observacao visual real.

Se a tela nao puder ser observada de forma suficiente, a limitacao deve ser declarada explicitamente.

### 16.1. Validacao visual nao substitui validacao funcional

Uma tela visualmente renderizada nao deve ser considerada operacional apenas porque parece correta.

Sempre que houver formulario, calendario, drawer, modal, CTA principal, toggle, wizard ou qualquer superficie acionavel, a IA deve tentar interagir com os elementos centrais da tela dentro do escopo aprovado.

Se a superficie renderiza, mas falha ao salvar, abrir, expandir, navegar ou reagir a interacoes basicas, isso deve ser registrado como problema funcional, mesmo quando a aparencia estiver correta.

## 17. Achados e rastreabilidade

Cada achado deve ser rastreavel ate sua origem.

Sempre que possivel, o achado deve indicar:

- rodada;
- cenario;
- fluxo;
- perfil;
- dispositivo;
- contexto de execucao.

Se durante a rodada a IA identificar comportamento aparentemente correto e aplicavel,
mas ausente ou divergente da documentacao lida do modulo, isso deve ser:

- registrado como inconsistenca documental;
- apontado no resultado da rodada;
- sugerido como follow-up de documentacao.

### 17.1. Qualidade de experiencia do usuario (UXQ)

A IA deve avaliar a qualidade da experiencia do usuario durante o mapeamento e a rodada, independentemente de existir manual de design formal. Quando houver manual de design, historico de discovery, log de feedback ou criterios de UX associados ao modulo, esses materiais devem ser usados como referencia adicional — mas a ausencia deles nao cancela a avaliacao.

A avaliacao deve cobrir as seguintes dimensoes:

**Coerencia de vocabulario**: O mesmo conceito usa o mesmo nome em toda a interface? Nomes distintos para a mesma coisa (por exemplo, "papel", "perfil" e "funcao" se referindo ao mesmo conceito de nivel de acesso) devem ser registrados como achado UXQ.

**Redundancia de campos ou etapas**: Ha campos cujo preenchimento nao agrega valor aparente, ou etapas que poderiam ser eliminadas sem perda de funcionalidade? Formularios com informacoes que o sistema ja conhece e poderia inferir automaticamente devem ser registrados.

**Proximidade de acao**: O usuario e obrigado a navegar para outra tela para realizar algo que poderia ser feito na tela atual com ajuste minimo? Desvios de contexto desnecessarios devem ser registrados.

**Affordance de controles**: Elementos que parecem clicaveis mas nao sao, botoes sem resposta visual, links que abrem comportamentos inesperados, ou controles cuja funcao nao e clara a partir da aparencia devem ser registrados.

**Consistencia visual e de padroes**: Secoes distintas do modulo ou da plataforma que tratam o mesmo tipo de operacao com padroes visuais diferentes devem ser registradas. Isso inclui paginas que rompem o shell visual padrao da plataforma sem justificativa aparente.

**Feedback de estado**: Acoes sem confirmacao visual clara, estados de carregamento silenciosos, mensagens de erro ou sucesso que desaparecem antes de serem lidas, ou ausencia de feedback apos uma acao esperada devem ser registrados.

**Carga cognitiva**: Fluxos com mais decisoes ou passos do que o necessario, formularios com campos tecnicos desnecessariamente expostos ao usuario final, instrucoes confusas ou ausentes em pontos de decisao, e opcoes que so fazem sentido para quem ja conhece o sistema devem ser registrados.

Achados UXQ devem ser classificados com a mesma escala de criticidade dos achados funcionais. Um problema de UX que impede a conclusao de uma tarefa e `critico`; um que confunde mas nao bloqueia e `media` ou `baixa`.

A divergencia deve ser registrada mesmo que o fluxo tecnico ainda funcione corretamente.

### 17.2. Rastros de implementacoes anteriores

Durante o mapeamento e a rodada, a IA deve procurar rastros de iteracoes anteriores do modulo, especialmente quando houve unificacao, renomeacao ou substituicao de superficies.

Isso inclui, pelo menos:

- rotas antigas que hoje apenas redirecionam;
- aliases de compatibilidade ainda expostos ao usuario;
- templates sem uso claro ou aparentemente orfaos;
- endpoints que ainda devolvem para superficies antigas;
- duas entradas que parecem servir ao mesmo objetivo de negocio;
- nomenclatura antiga mantida na UI, na documentacao ou no roteamento.

Quando esses rastros existirem, a IA deve registrar:

- qual e a superficie canonica atual;
- quais caminhos legados ainda sobrevivem;
- se o rastro parece compatibilidade intencional ou divida tecnica;
- se ele cria ambiguidade para o usuario, para a documentacao ou para o teste;
- se faz sentido recomendar poda, consolidacao ou apenas documentacao.

## 18. Known issues e baseline

### 18.1. Known issues

O processo deve permitir registrar problemas ja conhecidos para que a IA nao os trate como novidade em toda rodada.

### 18.2. Baseline de regressao

O processo deve permitir definir um conjunto minimo de verificacoes para reruns e regressos.

Esse baseline pode incluir, conforme o modulo:

- acesso;
- navegacao principal;
- fluxo principal;
- permissoes basicas;
- validacao visual rapida.

Quando o modulo tiver telas interativas relevantes, o baseline deve incluir tambem:

- pelo menos uma validacao real de CTA primario por superficie principal;
- verificacao de erros de console/page error nas telas JS-driven;
- verificacao pos-hidratacao em telas que carregam dados dinamicamente.
- para filtros de exclusao ou combinacao, captura explicita da baseline sem filtro antes da interacao;
- escolha de filtros que tenham efeito observavel na massa atual ou declaracao clara de que o item ficou `nao validado`.

Erros de console e de rede so devem virar achado quando forem acionaveis e atribuiveis ao modulo em escopo.

Se o erro for apenas um recurso nao carregado sem identificacao suficiente, a IA deve:

- tentar corroborar o recurso afetado;
- checar se o erro pertence de fato ao modulo em teste;
- evitar registrar o item como bug sem essa atribuicao.

Quando o modulo tiver passado por unificacao ou reorganizacao recente de telas, o baseline deve incluir tambem:

- validacao explicita da superficie canonica;
- validacao dos aliases e redirects legados ainda existentes;
- verificacao se entradas duplicadas continuam agregando valor ou so mantem ruido tecnico;
- registro claro do que deve permanecer por compatibilidade e do que deveria ser podado.

## 19. Criterio de parada

Se surgir bloqueio relevante durante a execucao, a IA deve deixar claro qual e a situacao:

- a rodada pode continuar com seguranca;
- a rodada deve continuar apenas em areas seguras;
- a rodada deve ser interrompida;
- a rodada depende de decisao do usuario.

## 20. Diagnostico da rodada

Ao final da execucao, a IA deve consolidar um diagnostico da rodada.

Esse diagnostico da rodada e a sintese do estado observado no modulo a partir dos testes executados naquela rodada especifica.

Ele nao substitui o mapeamento.

## 21. Politica de Jira

### 21.1. Uso do Jira

O Jira continua sendo artefato operacional de rastreamento da sessao, nao substituto do mapeamento nem da rodada.

### 21.2. Abertura de card

A IA pode recomendar atencao imediata com base na criticidade, mas nao deve abrir card sem aprovacao explicita do usuario.

## 22. Diretriz de generalidade

As regras deste documento devem permanecer genericas o suficiente para servir a diferentes modulos.

Ao aplicar este padrao:

- a IA pode adaptar os exemplos;
- a IA pode ajustar a taxonomia dos itens;
- a IA pode ajustar os pacotes sugeridos;
- a IA pode ajustar a granularidade dos cenarios.

Essas adaptacoes nao devem violar os principios deste canonico.

## 23. Governanca dos artefatos de teste

`docs/testing/**` e a fonte oficial de verdade para o processo de testes assistidos por IA neste repositorio.

### 23.1. Leitura obrigatoria

Antes de iniciar qualquer tarefa de mapeamento, QA, validacao de modulo ou rodada de testes, a IA deve ler:

- este arquivo;
- os mapeamentos anteriores relevantes em `docs/testing/mappings/`;
- as rodadas anteriores relevantes em `docs/testing/runs/`.

### 23.2. Registro obrigatorio

Ao executar esse processo, a IA deve manter o historico governado no repositorio principal:

- todo novo mapeamento deve criar ou atualizar um arquivo em `docs/testing/mappings/`;
- toda rodada executada deve criar ou atualizar um arquivo em `docs/testing/runs/`;
- toda mudanca de processo deve atualizar este canônico.

### 23.3. Regra de promocao

Se a IA trabalhar em worktree isolado, branch paralela ou ambiente temporario:

- os arquivos de `docs/testing/**` produzidos ali nao devem ser tratados como oficiais por si so;
- a promocao para oficial deve ocorrer por integracao controlada no repositorio principal;
- preferir commit docs-only quando a promocao envolver apenas o historico e o canônico;
- evitar manter versoes concorrentes do canônico, dos mapeamentos ou das rodadas em arvores paralelas por longos periodos.
