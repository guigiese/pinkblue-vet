# PinkBlue Vet — Guia de Design & Layout

> Fonte de verdade para cores, tipografia, componentes e decisões de UX da plataforma.
> Atualizar aqui ANTES de codificar qualquer mudança visual.

---

## 1. Cores de Marca

| Token          | Hex        | Tailwind (config)    | Uso                                    |
|----------------|------------|----------------------|----------------------------------------|
| `brand-pink`   | `#F0289B`  | `bg-brand-pink`      | Ações primárias, logo, nav ativa       |
| `brand-dark`   | `#C52180`  | `bg-brand-dark`      | Hover de botões primários              |
| `brand-light`  | `#FDE8F4`  | `bg-brand-light`     | Fundo de item ativo na nav             |
| `brand-blue`   | `#28C8FF`  | `text-brand-blue`    | Destaques informativos (futuro)        |

### Configuração Tailwind (ambos os shells)

```javascript
tailwind.config = {
  theme: {
    extend: {
      colors: {
        brand: {
          pink:  '#F0289B',
          dark:  '#C52180',
          light: '#FDE8F4',
          blue:  '#28C8FF',
        }
      }
    }
  }
}
```

> Este bloco **deve estar ANTES** do `<script src="https://cdn.tailwindcss.com">` em `platform_base.html` e `base.html`.

---

## 2. Shells de Layout

A plataforma tem dois shells:

| Shell              | Arquivo                          | Usado por                     |
|--------------------|----------------------------------|-------------------------------|
| Platform Base      | `web/templates/platform_base.html` | Módulo Plantão, páginas gerais |
| Lab Monitor Base   | `web/templates/base.html`          | Módulo Lab Monitor             |

Ambos têm:
- Header sticky com logo PB + nome da plataforma + menu de conta (avatar dropdown)
- Sidebar lateral fixa de 240 px no desktop; drawer mobile com hamburger
- `max-w-7xl` no conteúdo principal — **nenhum template filho deve limitar a largura internamente**

### Regra de largura de conteúdo

> **Proibido** usar `max-w-*` dentro de `{% block content %}` de qualquer template.  
> O `max-w-7xl` do shell já garante a largura máxima.  
> Containers internos (cards, formulários) devem usar `w-full` ou preencher o espaço disponível.

---

## 3. Menu de Conta (Header)

Implementado em `platform_base.html` como avatar dropdown.

- **Trigger**: botão com inicial do email + seta (desktop mostra email truncado)
- **Itens**: Meu cadastro (se `plantao_access`), Gestão de acessos (se `manage_users`), separador, **Sair**
- **Bloco extensível**: `{% block header_account_links %}` para itens extras por módulo
- Fecha ao clicar fora (listener `document.click`)

---

## 4. Sidebar (Plantão)

Definida em `modules/plantao/templates/plantao_base.html`.

Seções:
1. **Início** — link para `/plantao/` (landing role-aware)
2. **Gestão** — Escalas, Candidaturas, Disponibilidade, Cadastros (permissões granulares)
3. **Config** — Locais, Tarifas, Feriados, Configurações (apenas `manage_plantao`)
4. **Análise** — Relatórios (apenas `manage_plantao` ou `plantao_ver_relatorios`)
5. **Notificações** — separado por divisor

Estado ativo: `bg-brand-light text-brand-pink` no link + `text-brand-pink` no ícone.

---

## 5. Sidebar (Lab Monitor)

Definida em `web/templates/base.html`.

Seções:
- Dashboard, Exames (se `labmonitor_access`)
- Laboratórios, Canais, Notificações, Tolerâncias, Configurações (se `manage_labmonitor`)

Estado ativo: `bg-brand-light text-brand-pink`.

---

## 6. Botões

| Tipo             | Classes                                           |
|------------------|---------------------------------------------------|
| Primário         | `bg-brand-pink hover:bg-brand-dark text-white`   |
| Secundário       | `border border-gray-200 bg-white text-gray-600 hover:bg-gray-50` |
| Destrutivo       | `text-red-600 hover:bg-red-50`                   |
| Ghost            | `text-gray-600 hover:bg-gray-100`                |

---

## 7. Painel Flutuante (Floating Panel)

Padrão para edição/criação sem sair da página (usado em Escalas, futuro em Locais).

- `fixed inset-y-0 right-0 z-50 w-full max-w-lg bg-white shadow-2xl border-l border-gray-200`
- Sempre controlado via `style.display = 'flex'` / `style.display = 'none'` (evita conflito Tailwind `hidden` + `flex`)
- Overlay: `fixed inset-0 z-40 bg-black/20`
- Fecha com `Escape`

---

## 8. Decisões Registradas

| Data       | Decisão                                                                 |
|------------|-------------------------------------------------------------------------|
| 2026-04-15 | Cores de marca definidas: pink #F0289B, blue #28C8FF                   |
| 2026-04-15 | `max-w-*` proibido dentro de `{% block content %}` de templates filhos  |
| 2026-04-15 | Botão "Sair" movido para avatar dropdown no header (PBVET-182)          |
| 2026-04-15 | Painéis flutuantes usam `style.display`, nunca `classList` toggle       |
| 2026-04-15 | Sidebar Plantão remove "Dashboard" duplicado; landing é role-aware      |
