const DATA_URL = window.__PB_CARD_SANDBOX_DATA_URL || "/sandboxes/cards/data/runtime.json";

const variantTabs = document.getElementById("variant-tabs");
const samplePills = document.getElementById("sample-pills");
const heroNotes = document.getElementById("hero-notes");
const variantStage = document.getElementById("variant-stage");
const variantTitle = document.getElementById("variant-title");
const variantNote = document.getElementById("variant-note");
const detailPanel = document.getElementById("detail-panel");

const VARIANTS = [
  {
    id: "rail-clean",
    name: "V1 · Rail clean",
    note: "Barra lateral discreta, data em mono leve e contagem bem direta.",
    cardClass: "crit-rail density-compact date-style-inline status-solid critical-rail-only counts-inline timeline-inline",
  },
  {
    id: "rail-soft",
    name: "V2 · Rail soft",
    note: "Mantem a barra lateral, mas transforma data e meta em chips mais suaves.",
    cardClass: "crit-rail density-compact date-style-soft status-solid critical-rail-only counts-badges timeline-inline",
  },
  {
    id: "rail-split",
    name: "V3 · Rail split",
    note: "Status fica mais presente e as contagens ganham cluster proprio sem estourar a altura.",
    cardClass: "crit-rail density-airy date-style-inline status-solid critical-rail-only counts-badges timeline-badges",
  },
  {
    id: "rail-chip-date",
    name: "V4 · Rail + date chip",
    note: "Data vira ancora visual mais clara, mantendo a criticidade so na lateral.",
    cardClass: "crit-rail density-airy date-style-chip status-solid critical-rail-only counts-inline timeline-badges",
  },
  {
    id: "triangle-trailing",
    name: "V5 · Triangle trailing",
    note: "Criticidade vai para um triangulo fixo no canto superior, sem deslocar o status.",
    cardClass: "crit-none density-compact date-style-inline status-solid critical-trailing counts-inline timeline-inline",
  },
  {
    id: "triangle-inline",
    name: "V6 · Triangle inline",
    note: "Triangulo segue ao lado do status para testar proximidade sem confusao de semantica.",
    cardClass: "crit-none density-compact date-style-soft status-solid critical-inline counts-badges timeline-inline",
  },
  {
    id: "triangle-ghost",
    name: "V7 · Triangle ghost",
    note: "Status mais leve e triangulo com mais responsabilidade visual.",
    cardClass: "crit-none density-compact date-style-inline status-ghost critical-trailing counts-inline timeline-badges",
  },
  {
    id: "triangle-badge",
    name: "V8 · Triangle badge",
    note: "Triangulo recebe base sutil para testar legibilidade sem virar badge textual.",
    cardClass: "crit-none density-airy date-style-chip status-ghost critical-badge counts-badges timeline-inline",
  },
  {
    id: "border-quiet",
    name: "V9 · Border quiet",
    note: "Borda inteira do card assume a semantica da criticidade, com interior mais limpo.",
    cardClass: "crit-border density-compact date-style-inline status-solid critical-hidden counts-inline timeline-inline",
  },
  {
    id: "border-date-chip",
    name: "V10 · Border + chip",
    note: "Borda critica com data em chip e clusters mais compactos na ultima linha.",
    cardClass: "crit-border density-airy date-style-chip status-solid critical-hidden counts-badges timeline-inline",
  },
  {
    id: "hybrid-minimal",
    name: "V11 · Hybrid minimal",
    note: "Barra lateral mais um triangulo pequeno para ver se a redundancia ajuda ou atrapalha.",
    cardClass: "crit-hybrid density-compact date-style-soft status-ghost critical-trailing counts-inline timeline-badges",
  },
  {
    id: "balanced-finalist",
    name: "V12 · Balanced finalist",
    note: "Versao mais equilibrada para comparar com a linha atual antes de levar ao produto.",
    cardClass: "crit-rail density-compact date-style-inline status-solid critical-inline counts-badges timeline-inline meta-quiet",
  },
];

const state = {
  runtime: null,
  selectedVariant: 0,
  selectedProtocol: 0,
};

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function statusTone(status) {
  switch (status) {
    case "Pronto":
      return "status-ready";
    case "Parcial":
      return "status-partial";
    case "Em Andamento":
      return "status-progress";
    case "Analisando":
      return "status-analysis";
    case "Recebido":
      return "status-received";
    default:
      return "status-progress";
  }
}

function statusIcon(status) {
  switch (status) {
    case "Pronto":
      return `
        <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
        </svg>`;
    case "Parcial":
      return `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><circle cx="10" cy="10" r="8"></circle></svg>`;
    case "Recebido":
      return `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12z"></path></svg>`;
    default:
      return `<svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd"></path></svg>`;
  }
}

function criticalIcon(level) {
  if (!level) {
    return `<span aria-hidden="true"></span>`;
  }

  return `
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
    </svg>
  `;
}

function buildCounts(protocol) {
  const total = protocol.items.length;
  const counts = protocol.statusCounts || {};
  const parts = [{ label: `${total} exame${total === 1 ? "" : "s"}`, tone: "neutral" }];

  ["Pronto", "Em Andamento", "Analisando", "Recebido"].forEach((status) => {
    if (!counts[status]) {
      return;
    }
    const suffix = status === "Pronto" ? "pronto" : status === "Em Andamento" ? "and." : status.toLowerCase();
    parts.push({ label: `${counts[status]} ${suffix}`, tone: statusTone(status) });
  });

  return parts;
}

function buildTimeline(protocol) {
  if (protocol.daysOpen !== null && protocol.daysOpen !== undefined) {
    return [
      {
        label: `${protocol.daysOpen}d em aberto`,
        stale: protocol.daysOpen > 7,
      },
    ];
  }

  if (protocol.releaseAt) {
    return [{ label: `lib. ${protocol.releaseAt}` }];
  }

  return [];
}

function patientTitle(protocol) {
  return protocol.tutorName
    ? `${protocol.patientName} · ${protocol.tutorName}`
    : protocol.patientName;
}

function protocolReasonLabel(reason) {
  switch (reason) {
    case "partial-warning":
      return "Parcial real";
    case "critical-ready":
      return "Critico real";
    case "nexio-single":
      return "Nexio real";
    case "large-protocol":
      return "Protocolo amplo";
    case "warning-ready":
      return "Atencao real";
    default:
      return "Amostra";
  }
}

function renderCountCluster(parts) {
  return `
    <div class="counts-cluster">
      ${parts
        .map(
          (part) => `
            <span class="count-chip ${part.tone || ""}">${escapeHtml(part.label)}</span>
          `
        )
        .join("")}
    </div>
  `;
}

function renderTimelineCluster(parts) {
  if (!parts.length) {
    return "";
  }

  return `
    <div class="timeline-cluster">
      ${parts
        .map(
          (part) => `
            <span class="timeline-chip ${part.stale ? "is-stale" : ""}">${escapeHtml(part.label)}</span>
          `
        )
        .join("")}
    </div>
  `;
}

function renderStatusBadge(protocol, variant) {
  const ghost = variant.cardClass.includes("status-ghost") ? "status-ghost" : "status-solid";
  return `
    <span class="status-badge ${ghost} ${statusTone(protocol.status)}">
      ${statusIcon(protocol.status)}
      ${escapeHtml(protocol.status)}
    </span>
  `;
}

function renderProtocolCard(protocol, variant, index) {
  const critClass = protocol.criticality ? `crit-${protocol.criticality}` : "crit-none";
  const counts = renderCountCluster(buildCounts(protocol));
  const timeline = renderTimelineCluster(buildTimeline(protocol));
  const selected = state.selectedProtocol === index ? "is-selected" : "";

  return `
    <button type="button"
            class="protocol-card ${variant.cardClass} ${critClass} ${selected}"
            data-protocol-index="${index}">
      <div class="card-row row-top">
        <span class="date-stamp">${escapeHtml(protocol.date)}</span>
        <div class="top-right">
          ${renderStatusBadge(protocol, variant)}
          <span class="critical-slot ${protocol.criticality ? `is-${protocol.criticality}` : ""}">
            ${criticalIcon(protocol.criticality)}
          </span>
        </div>
      </div>

      <div class="card-row row-identity">
        <div class="identity-block">
          <div class="identity-line">
            <strong>${escapeHtml(patientTitle(protocol))}</strong>
          </div>
        </div>
      </div>

      <div class="card-row row-meta">
        <div class="meta-left">
          <span class="lab-chip">${escapeHtml(protocol.labName)}</span>
          <span class="protocol-chip">${escapeHtml(protocol.protocol)}</span>
        </div>
        <div class="meta-right">
          ${counts}
          ${timeline}
        </div>
      </div>
    </button>
  `;
}

function renderSamplePills() {
  samplePills.innerHTML = state.runtime.protocols
    .map(
      (protocol, index) => `
        <button type="button"
                class="sample-pill ${state.selectedProtocol === index ? "is-active" : ""}"
                data-sample-index="${index}">
          ${escapeHtml(protocolReasonLabel(protocol.sampleReason))} · ${escapeHtml(protocol.patientName)}
        </button>
      `
    )
    .join("");

  samplePills.querySelectorAll("[data-sample-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedProtocol = Number(button.dataset.sampleIndex);
      render();
    });
  });
}

function renderVariantTabs() {
  variantTabs.innerHTML = VARIANTS.map(
    (variant, index) => `
      <button type="button"
              class="variant-tab ${state.selectedVariant === index ? "is-active" : ""}"
              data-variant-index="${index}">
        ${escapeHtml(variant.name)}
      </button>
    `
  ).join("");

  variantTabs.querySelectorAll("[data-variant-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedVariant = Number(button.dataset.variantIndex);
      render();
    });
  });
}

function renderHeroNotes() {
  const notes = [
    ...(state.runtime.notes || []),
    state.runtime.source === "live-state"
      ? "Protocolos carregados do estado vivo do Lab Monitor."
      : "Fallback seguro em uso ate existir estado vivo no ambiente.",
    "Especie/sexo seguem fora do payload atual e ficaram separados em discovery.",
  ];

  heroNotes.innerHTML = notes
    .map((note) => `<span class="hero-note"><strong>Nota</strong>${escapeHtml(note)}</span>`)
    .join("");
}

function renderDefaultDetail() {
  detailPanel.innerHTML = `
    <div class="empty-state">
      <p class="detail-label">Selecao</p>
      <p class="detail-empty">
        Clique em qualquer card para abrir o protocolo completo, com itens, status e resultados disponiveis.
      </p>
    </div>
  `;
}

function renderDetail(protocol) {
  if (!protocol) {
    renderDefaultDetail();
    return;
  }

  const counts = buildCounts(protocol)
    .map((part) => `<span class="meta-chip">${escapeHtml(part.label)}</span>`)
    .join("");

  const itemsHtml = protocol.items
    .map((item) => {
      const results = item.results && item.results.length
        ? `
          <table class="detail-result-table">
            <thead>
              <tr>
                <th>Parametro</th>
                <th>Resultado</th>
                <th>Referencia</th>
              </tr>
            </thead>
            <tbody>
              ${item.results
                .map(
                  (row) => `
                    <tr class="${row.alerta === "red" ? "result-alert-red" : row.alerta === "yellow" ? "result-alert-yellow" : ""}">
                      <td>${escapeHtml(row.nome)}</td>
                      <td>${escapeHtml(row.valor)}</td>
                      <td>${escapeHtml(row.referencia)}</td>
                    </tr>
                  `
                )
                .join("")}
            </tbody>
          </table>
        `
        : `<p class="detail-result-empty">Sem tabela de resultados embutida para este item no snapshot atual.</p>`;

      return `
        <article class="detail-item">
          <div class="detail-item-head">
            <div class="detail-item-title">
              <span class="item-alert-dot ${item.alert ? `is-${item.alert}` : ""}"></span>
              <strong>${escapeHtml(item.name)}</strong>
            </div>
            ${renderStatusBadge({ status: item.status }, { cardClass: "status-solid" })}
          </div>
          <p class="detail-item-sub">
            ${item.releaseAtDisplay ? `Liberado em ${escapeHtml(item.releaseAtDisplay)}` : "Sem horario de liberacao no item atual."}
          </p>
          ${results}
        </article>
      `;
    })
    .join("");

  detailPanel.innerHTML = `
    <div class="detail-header">
      <p class="detail-label">Protocolo completo</p>
      <div class="detail-title">
        <h3>${escapeHtml(protocol.patientName)}</h3>
        <p>${escapeHtml(protocol.tutorName || "Tutor nao mapeado")} · ${escapeHtml(protocol.labName)}</p>
      </div>
      <p class="detail-note">
        Esta area mostra o protocolo inteiro para validar como o card resumido se conecta ao detalhe real.
      </p>
    </div>

    <div class="detail-grid">
      <div class="detail-cell">
        <strong>Data</strong>
        <span>${escapeHtml(protocol.date)}</span>
      </div>
      <div class="detail-cell">
        <strong>Status</strong>
        <span>${escapeHtml(protocol.status)}</span>
      </div>
      <div class="detail-cell">
        <strong>Protocolo</strong>
        <span>${escapeHtml(protocol.protocol)}</span>
      </div>
      <div class="detail-cell">
        <strong>Criticidade</strong>
        <span>${escapeHtml(protocol.criticality || "Sem sinal geral")}</span>
      </div>
      <div class="detail-cell">
        <strong>Especie / sexo</strong>
        <span>${escapeHtml(protocol.speciesSex || "Ainda nao mapeados no payload atual")}</span>
      </div>
      <div class="detail-cell">
        <strong>Origem da amostra</strong>
        <span>${escapeHtml(protocolReasonLabel(protocol.sampleReason))}</span>
      </div>
    </div>

    <section class="detail-section">
      <span class="detail-label">Resumo operacional</span>
      <div class="meta-left">
        ${counts}
        ${protocol.daysOpen !== null && protocol.daysOpen !== undefined ? `<span class="meta-chip ${protocol.daysOpen > 7 ? "is-stale" : ""}">${escapeHtml(`${protocol.daysOpen}d em aberto`)}</span>` : ""}
        ${protocol.releaseAt ? `<span class="meta-chip">${escapeHtml(`lib. ${protocol.releaseAt}`)}</span>` : ""}
      </div>
      ${protocol.portalUrl ? `<a class="detail-protocol-link" href="${escapeHtml(protocol.portalUrl)}" target="_blank" rel="noopener">Abrir portal do protocolo</a>` : ""}
    </section>

    <section class="detail-section">
      <span class="detail-label">Itens do protocolo</span>
      <div class="detail-item-list">
        ${itemsHtml}
      </div>
    </section>
  `;
}

function renderStage() {
  const variant = VARIANTS[state.selectedVariant];
  const protocols = state.runtime.protocols;

  variantTitle.textContent = variant.name;
  variantNote.textContent = variant.note;

  variantStage.innerHTML = protocols
    .map((protocol, index) => renderProtocolCard(protocol, variant, index))
    .join("");

  variantStage.querySelectorAll("[data-protocol-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedProtocol = Number(button.dataset.protocolIndex);
      render();
    });
  });
}

function render() {
  renderVariantTabs();
  renderSamplePills();
  renderStage();
  renderDetail(state.runtime.protocols[state.selectedProtocol]);
}

function bindGalleryActions() {
  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.dataset.action === "previous") {
        state.selectedVariant = (state.selectedVariant - 1 + VARIANTS.length) % VARIANTS.length;
      }
      if (button.dataset.action === "next") {
        state.selectedVariant = (state.selectedVariant + 1) % VARIANTS.length;
      }
      render();
    });
  });
}

async function loadRuntime() {
  const response = await fetch(DATA_URL, { credentials: "same-origin" });
  if (!response.ok) {
    throw new Error(`Falha ao carregar sandbox: ${response.status}`);
  }
  return response.json();
}

async function init() {
  bindGalleryActions();

  try {
    state.runtime = await loadRuntime();
    renderHeroNotes();
    render();
  } catch (error) {
    variantTitle.textContent = "Falha ao carregar";
    variantNote.textContent = "Nao foi possivel montar o sandbox com os dados atuais.";
    variantStage.innerHTML = `
      <div class="empty-state">
        <p class="detail-empty">${escapeHtml(error.message || "Erro desconhecido")}</p>
      </div>
    `;
    renderDefaultDetail();
  }
}

init();
