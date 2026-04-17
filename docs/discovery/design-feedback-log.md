# Design Feedback Log — Módulo Plantão

Registro acumulativo de questões levantadas pelo usuário durante o desenvolvimento.
Cada entrada contém: o problema observado, o motivo provável de ter surgido, e a premissa
de design que deveria ter evitado o problema. Será refinado em documentação definitiva.

---

## 2026-04-14

### 1. Badge "Gestor" e botão "Painel Administrativo" na landing

**Observado:** O usuário considerou esses elementos desnecessários e poluídos visualmente.

**Por que surgiu:** A tela inicial foi construída como "hub de boas-vindas" e tentou contextualizar o papel do usuário com labels explícitas e um CTA de atalho para o admin.

**Premissa de design:** O papel do usuário não precisa ser anunciado com um badge. A navegação lateral já revela quais seções ele tem acesso — isso é autoexplicativo. Labels de role (Gestor, Vet, Aux) só fazem sentido em contextos onde múltiplos papéis coexistem numa mesma lista (ex: uma tabela de candidaturas). Botões de atalho tipo "Ir para painel admin" são redundantes quando a sidebar já tem o link.

---

### 2. Calendário parece clicável mas não faz nada (tela admin de escalas)

**Observado:** O grid do calendário em `/plantao/admin/escalas` usa hover e cores que sugerem interatividade, mas clicar em uma célula não tem efeito.

**Por que surgiu:** O calendário admin foi construído como visualização estática de escalas, com um pequeno botão "+" no canto inferior direito das células como único ponto de ação. O padrão visual (hover, cursor implícito) criou a expectativa de que clicar no dia inteiro abriria algo.

**Premissa de design:** Se um elemento tem `hover:bg-*` ele precisa ter uma ação. Em calendários, a expectativa universal é que clicar num dia abre o detalhe daquele dia. O botão "+" no canto de cada célula é um padrão desktop que não funciona bem em mobile e é invisível para quem não sabe que ele existe. A ação de detalhar um dia deve ser atribuída à célula inteira.

---

### 3. "Minha Agenda" retorna página em branco para todos os usuários

**Observado:** A rota `/plantao/agenda` renderiza uma tela sem conteúdo para todos os perfis.

**Por que surgiu:** Dois fatores combinados:
- (a) Não há escalas cadastradas no banco — o calendário renderiza corretamente mas vazio, o que parece uma tela quebrada.
- (b) Um bug de permissão: `manage_plantao` não implica `plantao_access` na cascade de `get_user_permissions`. Gestores sem role admin falham no guard `_exige_plantonista` que verifica `plantao_access`, sendo redirecionados silenciosamente.

**Premissa de design:** Telas de calendário sem dados devem ter um estado vazio explícito e orientado à ação (ex: "Nenhuma escala publicada este mês — [Criar escalas]" para gestores, "Nenhuma escala disponível este mês" para plantonistas). Estado vazio invisível parece bug. Quanto à permissão: toda permissão de gestão de um módulo deve implicar automaticamente o acesso básico de usuário daquele módulo.

---

### 4. Visões de gestor e plantonista são telas separadas

**Observado:** O usuário propôs unificar `/plantao/admin/escalas` e `/plantao/agenda` em uma única tela adaptável por perfil.

**Por que surgiu:** Foram construídas duas telas independentes — uma focada na gestão (criar/publicar escalas) e outra no consumo (ver meus turnos, candidatar). A separação faz sentido técnico mas cria experiências divergentes para o mesmo contexto: o calendário de escalas.

**Premissa de design:** Quando gestor e colaborador estão olhando para o mesmo objeto (o calendário de escalas de um mês), a tela deve ser a mesma. O que muda são as ações disponíveis — camadas adicionais renderizadas condicionalmente por permissão. Isso reduz o número de rotas, elimina duplicação de lógica de calendário e permite que um gestor veja a perspectiva do plantonista sem trocar de tela.

---

### 5. Controle de acesso percebido como "por tela"

**Observado:** O usuário sentiu que as permissões liberam acesso a páginas, não a ações.

**Por que surgiu:** O modelo atual já tem grupos de ações (`plantao_gerir_escalas`, `plantao_aprovar_candidaturas`, etc.) mas eles são apresentados no admin de usuários por nomes técnicos e mapeados para rotas. A percepção de "libera por tela" vem da UI de administração de usuários, não do modelo subjacente.

**Premissa de design:** Permissões devem ser apresentadas com nomes funcionais centrados no que o usuário pode fazer, não no que ele pode acessar. Ex: "Gerir escalas de plantão" é melhor que "plantao_gerir_escalas". Os grupos devem ser visíveis e compreensíveis para quem configura, não só para quem desenvolve.

---

### 6. Locais: somente criação, sem edição, arquivamento ou exclusão

**Observado:** A tela de locais só permite incluir novos registros. Não é possível editar nem remover.

**Por que surgiu:** O CRUD de locais foi implementado parcialmente — apenas o "C" do Create. Edit/Delete foram postergados.

**Premissa de design:** Todo cadastro de entidade deve ter CRUD completo na primeira entrega utilizável. Para exclusão, o padrão correto é: (1) apagar fisicamente só se a entidade não tiver vínculos; (2) caso contrário, oferecer "arquivar/desativar"; (3) ambas as ações são reversíveis; (4) existe um filtro para consultar arquivados. Esse padrão deve ser aplicado consistentemente a locais, usuários e qualquer outra entidade cadastral do sistema.

---

### 7. Botões "Nova Escala" e "+" na tela admin de escalas não respondem

**Observado:** Ao clicar em "Nova Escala" ou "+" nas células do calendário, nada acontece.

**Por que surgiu:** Bug JavaScript na função `setModo(modo)`. O seletor
`document.querySelector('#painel-escala .rounded-2xl button:first-child')` retorna `null` porque o botão "Criar Escala" tem a classe `.rounded-2xl` em si mesmo, não num elemento pai — o seletor busca um `button` descendente de `.rounded-2xl`, que não existe. O `null.textContent = ...` lança TypeError ao carregar a página e em cada chamada subsequente a `setModo`. Como o painel é tornado visível antes de `setModo` ser chamado dentro de `abrirPainelEscala`, o painel pode aparecer brevemente mas a experiência é quebrada.

**Premissa de design:** Seletores CSS dinâmicos em JavaScript são frágeis quando dependem de classes utilitárias do Tailwind (que podem mudar com refatorações). Elementos que precisam ser referenciados por JS devem ter IDs explícitos. Qualquer função JS crítica para a interação principal de uma tela deve ser testada com `console.log` antes de ser considerada pronta.

---

### 8. Padrão de defaults de formulário não reflete a realidade operacional

**Observado:** O painel de criação de escala abre com 1 vaga de vet e 0 de auxiliar. O usuário espera 1 vet + 1 aux por padrão.

**Por que surgiu:** O default foi definido tecnicamente (1 e 0) sem considerar o padrão operacional real da clínica.

**Premissa de design:** Defaults de formulário devem refletir o caso mais comum na operação real. Para o módulo Plantão da PinkBlue Vet: 1 vet + 1 aux é a composição padrão de qualquer turno. Defaults errados geram erros silenciosos (usuário cria com 0 aux sem perceber) e atrito desnecessário.
