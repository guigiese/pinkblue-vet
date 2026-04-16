## IAs - Não tocar nesse arquivo ##

A partir daqui, e apenas nessa sessão, seguiremos com o mesmo acordo de tratativa de antes, sobre interatividade, interpretação e construção conjunta, mas tenho um adendo: durante essas nossas interações eu quero que vc procure entender o motivo das minhas solicitações e/ou dúvidas, tente identificar pq a questão que eu levantei surgiu. O motivo disso é que depois eu quero que vc seja capaz de criar uma documentação que oriente premissas de desenvolvimento para as IAs não cometerem os mesmos erros/inconsistências de design e layout. Ainda não sei como será essa documentação, inclusive irei solicitar posteriormente um auxilio seu, mas para não perdesmos nada, vá registrando tudo isso em um arquivo para ser refinado posteriormente. Ok? alguma dúvida?


Você é um engenheiro de testes Python experiente.

Contexto:
- Repositório Python com módulo `modules/plantao`.
- Módulo Plantão usa FastAPI, SQLAlchemy e `unittest` para testes.
- Os testes existentes ficam em `Testes/` e seguem estilo `unittest.TestCase`.

Objetivo:
Escreva um arquivo de teste completo para o módulo Plantão:
- `Testes/test_plantao.py`

Escopo:
- `modules/plantao/actions.py`
- `modules/plantao/router.py`
- regras de negócio de plantão: criação, publicação, cancelamento, candidaturas, aprovações, trocas, notificações e permissões.

Requisitos:
- Use `import unittest`
- Use `from unittest.mock import patch, MagicMock`
- Crie pelo menos:
  - testes de fluxo feliz para `criar_data_plantao`, `publicar_data_plantao`, `cancelar_data_plantao`
  - testes de permissão para `_exige_plantonista` e `_exige_gestor`
  - testes de candidaturas (`criar_candidatura`, `aprovar_candidatura`, `lista_espera`)
  - testes de troca de turno (`criar_troca`, `aceitar_troca`, `recusar_troca`)
  - testes de notificações e jobs quando aplicável
- Para banco de dados, use mocks na engine/connection e valide chamadas SQL básicas ou retornos simulados.
- Mantenha os testes isolados, sem dependência de banco real.
- Termine com `unittest.main()`

Detalhes extras:
- Inclua casos de erro: recurso não encontrado, permissão negada, candidatos duplicados, data não publicada.
- Se possível, espelhe o estilo dos arquivos `Testes/test_platform_auth.py` e `Testes/test_platform_storage.py`.




Ajude a planejar uma melhoria de layout no módulo de plantão. "Minha Agenda" e "Escalas" devem ser unificadas, ambas devem usar o mesmo calendário que deve estar visível para qualquer perfil. O que muda é que perfis de gestão/admin poderão ver as escalas de todos, cadastrar, publicar e editar escalas, ver as que estão pendentes e as que estão preenchidas, enquanto os Vets e Auxiliares somente poderão ver as suas próprias escalas e as escalas em aberto compatíveis com o seu perfil de acesso (deve ter a opção indivdualizada dessas escalas para ser atribuída pelo módulo de aecssos). Os recursos de filtros, legendas, botões, navegação no calendário, seleção de local (que quando tiver apenas um, deve trazer esse já selecionado por padrão). A opção de alterar a visualização entre calendário e lista deve funcionar. O botão de "+" dentro dos dias do calendário não deve mais existir, o quadro do dia no calendário deve ser clicável e no menu flutuante que se abrir deve conter os detalhes abertos daquele dia (opção de criar escala no dia, as escalas por publicar, as escalas publicadas, as escalas preenchidas, etc.), cada registro deve ser clicável e retornar a tela de edição daquela escala, tudo conforme permissionamento. No formato lisa as escalas serão retornadas listadas em ordem cronológica a contar do dia atual, visíveis de acordo com as permissões, usando cores de sua legenda e tendo alguns botóes de ações rápidas, como de publicar (para escalas não publicadas), de cancelar (apenas para gestores/adm ref escalas não aderidas), de desistir (para escalas ainda dentro do período de desistência), de aderir (para escalas publicadas e sem adesão), entre outros possíveis que vc pode avaliar. Dentro do quadrado de cada mês essas mesmas escalas podem constar (cada uma em seu referido dia) também com esses mesmos botões só que em versão mais simples e compacta. É importante verificar como o calendário seria exibido em versão mobile. Caso não seja viável do ponto de vista de UI e UX, a versão de celular pode exibir sempre como lista.
A tela de acessos (perfis, usuários, etc) deve passar a ser encarada como um módulo cross, que é construído separadamente, mas que afeta os demais módulos.