const kindLabels = {
  system: "Sistema",
  platform: "Plataforma",
  site: "Site",
  ai: "IA",
  external: "Externo",
};

const healthLabels = {
  healthy: "Saudável",
  warning: "Atenção",
  problem: "Problema",
  dormant: "Dormente",
};

const kindColors = {
  system: "#0c7a69",
  platform: "#2f6fed",
  site: "#7c3aed",
  ai: "#d2672d",
  external: "#5f6b71",
};

const healthColors = {
  healthy: "#0f9d58",
  warning: "#d58512",
  problem: "#c0392b",
  dormant: "#7f8c8d",
};

const state = {
  map: null,
  cy: null,
  selectedKinds: new Set(),
  selectedHealths: new Set(),
  query: "",
};

const overview = document.getElementById("overview");
const watchlist = document.getElementById("watchlist");
const detailPanel = document.getElementById("detail-panel");
const graphElement = document.getElementById("graph");
const kindFilters = document.getElementById("kind-filters");
const healthFilters = document.getElementById("health-filters");
const searchInput = document.getElementById("search-input");
const heroNotes = document.getElementById("hero-notes");
const metaMode = document.getElementById("meta-mode");
const metaRefresh = document.getElementById("meta-refresh");
const metaCoverage = document.getElementById("meta-coverage");
const metaWatch = document.getElementById("meta-watch");
const metaRailway = document.getElementById("meta-railway");
const metaRailwayNote = document.getElementById("meta-railway-note");

void init();

async function init() {
  const map = await loadMap();
  state.map = normalizeMap(map);
  state.selectedKinds = new Set(state.map.kinds);
  state.selectedHealths = new Set(state.map.healths);

  renderHeroMeta();
  renderFilterRow(kindFilters, state.map.kinds, state.selectedKinds, kindLabels);
  renderFilterRow(healthFilters, state.map.healths, state.selectedHealths, healthLabels);
  bindToolbar();
  buildGraph();
  applyFilters();
  renderDefaultDetail();
}

async function loadMap() {
  const sources = ["./data/pinkblue-map.runtime.json", "./data/pinkblue-map.v1.json"];
  for (const source of sources) {
    const response = await fetch(source, { cache: "no-store" });
    if (response.ok) {
      return response.json();
    }
  }
  throw new Error("Não foi possível carregar os dados do mapa.");
}

function normalizeMap(map) {
  const nodes = map.nodes.map((node) => {
    const source = node.source || {};
    const metricsText = (node.metrics || [])
      .map((metric) => `${metric.label} ${metric.value}`)
      .join(" ");
    const signalsText = (node.signals || []).join(" ");
    const statusLine = compactText(node.statusLine || "", 38);
    return {
      ...node,
      kindColor: kindColors[node.kind] || "#132126",
      healthColor: healthColors[node.health] || "#7f8c8d",
      surfaceColor: surfaceColorFor(node.health),
      iconUri: iconDataUri(node),
      iconUriRaw: iconDataUri(node, false),
      sourceKind: source.kind || "manual",
      sourceLabel: source.label || "Manual",
      checkedAtDisplay: map.meta?.generatedAtDisplay || "",
      displayLabel: [node.name, statusLine].filter(Boolean).join("\n"),
      searchText: [
        node.name,
        node.subtitle,
        node.statusLine,
        node.healthReason,
        metricsText,
        signalsText,
        ...(node.tags || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase(),
    };
  });

  const edges = map.edges.map((edge) => ({
    ...edge,
    lineColor: healthColors[edge.health] || "#7f8c8d",
    lineStyle: edge.health === "dormant" ? "dashed" : "solid",
    displayLabel: compactText(edge.label || "", 28),
  }));

  const kinds = Array.from(new Set(nodes.map((node) => node.kind)));
  const healths = Array.from(new Set(nodes.map((node) => node.health)));
  return { ...map, nodes, edges, kinds, healths };
}

function compactText(text, maxLength) {
  if (!text || text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function surfaceColorFor(health) {
  return {
    healthy: "#f7fdf9",
    warning: "#fff8ee",
    problem: "#fff2f0",
    dormant: "#f4f6f7",
  }[health] || "#ffffff";
}

function iconDataUri(node, escaped = true) {
  const svg = buildNodeIconSvg(node);
  return escaped ? svgToDataUri(svg) : svg;
}

function svgToDataUri(svg) {
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function buildNodeIconSvg(node) {
  const specs = {
    workspace: { bg: "#64748b", glyph: glyphWorkspace() },
    codex: { bg: "#111827", glyph: glyphCodex() },
    claude: { bg: "#d97706", glyph: glyphClaude() },
    github: { bg: "#181717", glyph: glyphGithub() },
    jira: { bg: "#0052cc", glyph: glyphJira() },
    railway: { bg: "#111111", glyph: glyphRailway() },
    site: { bg: "#2563eb", glyph: glyphSite() },
    labmonitor: { bg: "#0c7a69", glyph: glyphLabMonitor() },
    telegram: { bg: "#26a5e4", glyph: glyphTelegram() },
    whatsapp: { bg: "#25d366", glyph: glyphWhatsapp() },
    bitlab: { bg: "#1d4ed8", glyph: glyphBitlab() },
    nexio: { bg: "#7c3aed", glyph: glyphNexio() },
  };

  const spec = specs[node.iconKey] || specs.workspace;
  const healthDot = healthColors[node.health] || "#7f8c8d";
  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72">
      <rect x="4" y="4" width="64" height="64" rx="20" fill="${spec.bg}" />
      <circle cx="56" cy="16" r="7" fill="${healthDot}" stroke="rgba(255,255,255,0.92)" stroke-width="3" />
      ${spec.glyph}
    </svg>
  `;
}

function glyphWorkspace() {
  return `
    <rect x="18" y="21" width="36" height="22" rx="4" fill="none" stroke="#fff" stroke-width="4" />
    <path d="M24 49h24M30 43h12" stroke="#fff" stroke-width="4" stroke-linecap="round" />
  `;
}

function glyphCodex() {
  return `
    <path d="M36 16l5 12 12 5-12 5-5 12-5-12-12-5 12-5z" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" />
  `;
}

function glyphClaude() {
  return `
    <path d="M26 50c0-12 6-22 14-28 2 8 6 12 10 14-4 2-8 6-10 14-4-1-8-1-14 0z" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" />
  `;
}

function glyphGithub() {
  return `
    <circle cx="24" cy="22" r="5" fill="none" stroke="#fff" stroke-width="4" />
    <circle cx="48" cy="20" r="5" fill="none" stroke="#fff" stroke-width="4" />
    <circle cx="48" cy="48" r="5" fill="none" stroke="#fff" stroke-width="4" />
    <path d="M29 22h14M48 25v18M29 24c7 2 11 6 14 12" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" />
  `;
}

function glyphJira() {
  return `
    <rect x="18" y="20" width="12" height="30" rx="3" fill="none" stroke="#fff" stroke-width="4" />
    <rect x="36" y="20" width="18" height="12" rx="3" fill="none" stroke="#fff" stroke-width="4" />
    <rect x="36" y="38" width="18" height="12" rx="3" fill="none" stroke="#fff" stroke-width="4" />
  `;
}

function glyphRailway() {
  return `
    <path d="M18 44c0-9 7-16 16-16 3 0 6 1 8 2 2-4 6-6 10-6 7 0 12 5 12 12 0 7-5 12-12 12H30c-7 0-12-5-12-12z" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" />
    <path d="M27 48l6-8 5 4 7-10" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
  `;
}

function glyphSite() {
  return `
    <circle cx="36" cy="36" r="16" fill="none" stroke="#fff" stroke-width="4" />
    <path d="M20 36h32M36 20c4 5 6 10 6 16s-2 11-6 16M36 20c-4 5-6 10-6 16s2 11 6 16" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" />
  `;
}

function glyphLabMonitor() {
  return `
    <path d="M28 18h16M31 18v9l-8 17a8 8 0 0 0 7 12h12a8 8 0 0 0 7-12l-8-17v-9" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M26 42h6l4-5 4 8h6" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
  `;
}

function glyphTelegram() {
  return `
    <path d="M16 36l37-15-9 30-11-8-8 7 2-12z" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" />
  `;
}

function glyphWhatsapp() {
  return `
    <path d="M36 18c10 0 18 7 18 17s-8 17-18 17c-3 0-6-1-8-2l-10 3 3-9c-2-3-3-6-3-9 0-10 8-17 18-17z" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round" />
    <path d="M31 30c2 6 6 9 10 11" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" />
  `;
}

function glyphBitlab() {
  return `
    <path d="M30 18h12M32 18v10l-7 14a8 8 0 0 0 7 12h8a8 8 0 0 0 7-12l-7-14V18" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M27 40h18" stroke="#fff" stroke-width="4" stroke-linecap="round" />
  `;
}

function glyphNexio() {
  return `
    <path d="M26 48h22M34 26l10 10M24 40l10-10 10 10" fill="none" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
    <circle cx="36" cy="26" r="6" fill="none" stroke="#fff" stroke-width="4" />
  `;
}

function buildGraph() {
  state.cy = cytoscape({
    container: graphElement,
    elements: [
      ...state.map.nodes.map((node) => ({
        data: node,
        position: node.position,
      })),
      ...state.map.edges.map((edge) => ({
        data: edge,
      })),
    ],
    layout: { name: "preset", fit: false },
    wheelSensitivity: 0.15,
    style: [
      {
        selector: "node",
        style: {
          shape: "round-rectangle",
          label: "data(displayLabel)",
          "background-color": "data(surfaceColor)",
          "background-image": "data(iconUri)",
          "background-fit": "contain",
          "background-clip": "none",
          "background-width": 54,
          "background-height": 54,
          "background-position-x": "50%",
          "background-position-y": "26%",
          "border-color": "data(kindColor)",
          "border-width": 3,
          "text-wrap": "wrap",
          "text-max-width": 136,
          "text-valign": "bottom",
          "text-margin-y": -10,
          "text-halign": "center",
          color: "#132126",
          "font-family": "IBM Plex Sans",
          "font-size": 11,
          "font-weight": 600,
          "line-height": 1.2,
          width: 172,
          height: 136,
          padding: 12,
          "overlay-opacity": 0,
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-width": 5,
          "shadow-blur": 18,
          "shadow-color": "data(healthColor)",
          "shadow-opacity": 0.2,
        },
      },
      {
        selector: "edge",
        style: {
          label: "data(displayLabel)",
          "curve-style": "bezier",
          width: 4,
          "line-color": "data(lineColor)",
          "target-arrow-color": "data(lineColor)",
          "target-arrow-shape": "triangle",
          "line-style": "data(lineStyle)",
          color: "#58676d",
          "font-family": "IBM Plex Mono",
          "font-size": 8.5,
          "text-background-color": "#fffaf2",
          "text-background-opacity": 1,
          "text-background-padding": 3,
          "text-rotation": "autorotate",
          "text-margin-y": -10,
          "overlay-opacity": 0,
        },
      },
      {
        selector: "edge:selected",
        style: {
          width: 6,
          "text-background-color": "#132126",
          color: "#ffffff",
        },
      },
      {
        selector: ".is-hidden",
        style: {
          display: "none",
        },
      },
    ],
  });

  state.cy.on("select", "node", (event) => {
    renderNodeDetail(event.target.data());
  });

  state.cy.on("select", "edge", (event) => {
    renderEdgeDetail(event.target.data());
  });

  state.cy.on("unselect", () => {
    if (state.cy.$(":selected").length === 0) {
      renderDefaultDetail();
    }
  });

  window.architectureMapCy = state.cy;
}

function bindToolbar() {
  searchInput.addEventListener("input", (event) => {
    state.query = event.target.value.trim().toLowerCase();
    applyFilters();
  });

  document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;
      if (action === "fit") {
        fitVisibleElements();
      }

      if (action === "reload") {
        window.location.reload();
      }

      if (action === "reset") {
        searchInput.value = "";
        state.query = "";
        state.selectedKinds = new Set(state.map.kinds);
        state.selectedHealths = new Set(state.map.healths);
        renderFilterRow(kindFilters, state.map.kinds, state.selectedKinds, kindLabels);
        renderFilterRow(healthFilters, state.map.healths, state.selectedHealths, healthLabels);
        applyFilters();
        renderDefaultDetail();
      }
    });
  });
}

function renderFilterRow(container, items, selectedSet, labels) {
  container.innerHTML = "";

  items.forEach((item) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `chip ${selectedSet.has(item) ? "is-active" : "is-muted"}`;
    button.textContent = labels[item] || item;
    button.addEventListener("click", () => {
      if (selectedSet.has(item)) {
        selectedSet.delete(item);
      } else {
        selectedSet.add(item);
      }

      renderFilterRow(container, items, selectedSet, labels);
      applyFilters();
    });
    container.appendChild(button);
  });
}

function applyFilters() {
  const visibleNodeIds = new Set();

  state.cy.nodes().forEach((node) => {
    const data = node.data();
    const matchesKind = state.selectedKinds.has(data.kind);
    const matchesHealth = state.selectedHealths.has(data.health);
    const matchesQuery = !state.query || data.searchText.includes(state.query);
    const visible = matchesKind && matchesHealth && matchesQuery;

    node.toggleClass("is-hidden", !visible);
    if (visible) {
      visibleNodeIds.add(node.id());
    }
  });

  state.cy.edges().forEach((edge) => {
    const visible =
      visibleNodeIds.has(edge.data("source")) &&
      visibleNodeIds.has(edge.data("target"));
    edge.toggleClass("is-hidden", !visible);
  });

  renderOverview();
  renderWatchlist();
  fitVisibleElements();
}

function fitVisibleElements() {
  const visibleElements = state.cy.elements().not(".is-hidden");
  if (visibleElements.length > 0) {
    state.cy.fit(visibleElements, 42);
  }
}

function renderHeroMeta() {
  const meta = state.map.meta || {};
  const railwayNode = state.map.nodes.find((node) => node.id === "railway");

  metaMode.textContent = state.map.mode || "local-manual";
  metaRefresh.textContent = `Último refresh: ${meta.generatedAtDisplay || "manual"}`;
  metaCoverage.textContent = meta.sourceCoverage || "Sem cobertura";
  metaWatch.textContent = `${meta.watchNodeCount || 0} item(ns) em atenção neste snapshot`;
  metaRailway.textContent = railwayNode?.statusLine || "Sem dados";
  metaRailwayNote.textContent = railwayNode?.healthReason || "Sem detalhe do Railway";

  heroNotes.innerHTML = (meta.notes || [])
    .map((note) => `<span class="hero-note">${escapeHtml(note)}</span>`)
    .join("");
}

function renderOverview() {
  const visibleNodes = state.cy.nodes().not(".is-hidden");
  const visibleEdges = state.cy.edges().not(".is-hidden");
  const liveNodes = visibleNodes.filter((node) =>
    ["live-http", "live-api", "local"].includes(node.data("sourceKind"))
  ).length;
  const attentionNodes = visibleNodes.filter((node) =>
    ["warning", "problem", "dormant"].includes(node.data("health"))
  ).length;
  const protocolMetric = state.map.nodes
    .find((node) => node.id === "lab-monitor")
    ?.metrics?.find((metric) => metric.label === "Protocolos")?.value || "N/A";
  const telegramUsers = state.map.nodes
    .find((node) => node.id === "telegram")
    ?.metrics?.find((metric) => metric.label === "Users")?.value || "0";

  const stats = [
    {
      label: "Artefatos visíveis",
      value: `${visibleNodes.length}/${state.map.nodes.length}`,
      note: "Nós visíveis considerando busca e filtros ativos.",
    },
    {
      label: "Conexões visíveis",
      value: String(visibleEdges.length),
      note: "Relações entre artefatos que seguem no recorte atual.",
    },
    {
      label: "Cobertura ao vivo",
      value: `${liveNodes}/${visibleNodes.length || 1}`,
      note: "Parte do recorte atual já puxada por sonda pública ou API.",
    },
    {
      label: "Protocolos monitorados",
      value: String(protocolMetric),
      note: `Telegram com ${telegramUsers} inscrito(s) no snapshot mais recente.`,
    },
    {
      label: "Itens em atenção",
      value: String(attentionNodes),
      note: "Inclui alertas, problemas e caminhos dormentes do mapa.",
    },
  ];

  overview.innerHTML = stats
    .map(
      (stat) => `
        <article class="stat-card">
          <span class="detail-label">${escapeHtml(stat.label)}</span>
          <strong>${escapeHtml(stat.value)}</strong>
          <p>${escapeHtml(stat.note)}</p>
        </article>
      `
    )
    .join("");
}

function renderWatchlist() {
  const candidates = state.cy
    .nodes()
    .not(".is-hidden")
    .map((node) => node.data())
    .filter((node) => ["warning", "problem", "dormant"].includes(node.health));

  if (!candidates.length) {
    watchlist.innerHTML = `
      <article class="watch-card">
        <div class="watch-card-header">
          <div>
            <p class="section-kicker">Watchlist</p>
            <h3>Sem itens críticos no recorte atual</h3>
          </div>
          <span class="status-pill is-healthy">Saudável</span>
        </div>
        <p>Os sinais ativos deste recorte estão estáveis. Use filtros ou clique nos artefatos para inspecionar limites e dependências.</p>
      </article>
    `;
    return;
  }

  watchlist.innerHTML = candidates
    .map(
      (node) => `
        <article class="watch-card" data-node-id="${escapeHtml(node.id)}">
          <div class="watch-card-header">
            <div>
              <p class="section-kicker">${escapeHtml(kindLabels[node.kind] || node.kind)}</p>
              <h3>${escapeHtml(node.name)}</h3>
            </div>
            <span class="status-pill ${healthClassName(node.health)}">${escapeHtml(
              healthLabels[node.health] || node.health
            )}</span>
          </div>
          <p>${escapeHtml(node.healthReason || node.statusLine || "")}</p>
        </article>
      `
    )
    .join("");

  watchlist.querySelectorAll("[data-node-id]").forEach((card) => {
    card.addEventListener("click", () => {
      selectNode(card.dataset.nodeId);
    });
  });
}

function selectNode(nodeId) {
  const node = state.cy.getElementById(nodeId);
  if (!node || !node.length) {
    return;
  }
  state.cy.elements().unselect();
  node.select();
  state.cy.fit(node, 80);
}

function renderDefaultDetail() {
  const meta = state.map.meta || {};
  const highlightedNodes = state.map.nodes.filter((node) =>
    ["warning", "problem", "dormant"].includes(node.health)
  );

  detailPanel.innerHTML = `
    <div class="detail-header">
      <p class="section-kicker">Seleção</p>
      <h3>Visão geral do mapa</h3>
      <p class="detail-note">
        Este painel combina snapshot manual com sinais vivos de HTTP público e API do Railway.
        Selecione um nó ou conexão para ver motivo do status, limites, métricas e links úteis.
      </p>
    </div>
    <div class="detail-stack">
      <section class="detail-section">
        <span class="detail-label">Snapshot atual</span>
        <div class="detail-grid">
          ${detailCell("Atualizado em", meta.generatedAtDisplay || "Manual")}
          ${detailCell("Cobertura", meta.sourceCoverage || "N/A")}
          ${detailCell("Itens em atenção", String(meta.watchNodeCount || 0))}
          ${detailCell("Modo", state.map.mode || "local-manual")}
        </div>
      </section>
      <section class="detail-section">
        <span class="detail-label">Como ler</span>
        <ul class="default-list">
          <li>Ícones identificam os artefatos principais em vez de formas genéricas.</li>
          <li>A borda do nó indica o tipo do artefato.</li>
          <li>O ponto de status no ícone e os chips mostram saúde atual.</li>
          <li>No detalhe você vê de onde veio o sinal: manual, HTTP público, API ou sessão local.</li>
        </ul>
      </section>
      <section class="detail-section">
        <span class="detail-label">Watchlist atual</span>
        <ul class="default-list">
          ${highlightedNodes
            .map(
              (node) =>
                `<li><strong>${escapeHtml(node.name)}</strong>: ${escapeHtml(node.healthReason || node.statusLine)}</li>`
            )
            .join("")}
        </ul>
      </section>
    </div>
  `;
}

function renderNodeDetail(node) {
  const incoming = state.map.edges.filter((edge) => edge.target === node.id);
  const outgoing = state.map.edges.filter((edge) => edge.source === node.id);

  detailPanel.innerHTML = `
    <div class="detail-header">
      <p class="section-kicker">${escapeHtml(kindLabels[node.kind] || node.kind)}</p>
      <div class="detail-title-row">
        <img class="detail-icon" src="${node.iconUri}" alt="${escapeHtml(node.name)}">
        <div>
          <h3>${escapeHtml(node.name)}</h3>
          <p class="detail-note">${escapeHtml(node.subtitle || "")}</p>
        </div>
      </div>
      <div class="detail-links">
        <span class="status-pill ${healthClassName(node.health)}">${escapeHtml(
          healthLabels[node.health] || node.health
        )}</span>
        <span class="source-pill ${sourceClassName(node.sourceKind)}">${escapeHtml(
          node.sourceLabel || "Manual"
        )}</span>
      </div>
      <p class="detail-note">${escapeHtml(node.healthReason || node.statusLine || "")}</p>
      <div class="detail-tags">
        ${(node.tags || []).map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}
      </div>
    </div>
    <div class="detail-stack">
      <section class="detail-section">
        <span class="detail-label">Snapshot</span>
        <div class="detail-grid">
          ${detailCell("Status", node.statusLine || "N/A")}
          ${detailCell("Owner", node.owner || "N/A")}
          ${detailCell("Atualizado", node.checkedAtDisplay || "N/A")}
          ${detailCell("Fonte", node.sourceLabel || "Manual")}
          ${detailCell("Uso", node.usage?.value || "Não rastreado")}
          ${detailCell("Limite", node.limit?.value || "Sem watch específico")}
        </div>
      </section>
      <section class="detail-section">
        <span class="detail-label">Métricas</span>
        ${renderMetrics(node.metrics)}
      </section>
      <section class="detail-section">
        <span class="detail-label">Sinais que sustentam este status</span>
        ${renderSignals(node.signals)}
      </section>
      <section class="detail-section">
        <span class="detail-label">Links rápidos</span>
        <div class="detail-links">
          ${renderLinks(node.links)}
          ${renderIssueLinks(node.issues)}
        </div>
      </section>
      <section class="detail-section">
        <span class="detail-label">Entradas</span>
        <ul class="default-list">
          ${
            incoming.length
              ? incoming
                  .map(
                    (edge) =>
                      `<li><strong>${escapeHtml(
                        nodeName(edge.source)
                      )}</strong> → ${escapeHtml(node.name)}: ${escapeHtml(edge.label)}</li>`
                  )
                  .join("")
              : '<li class="empty-text">Nenhuma relação de entrada mapeada.</li>'
          }
        </ul>
      </section>
      <section class="detail-section">
        <span class="detail-label">Saídas</span>
        <ul class="default-list">
          ${
            outgoing.length
              ? outgoing
                  .map(
                    (edge) =>
                      `<li><strong>${escapeHtml(
                        node.name
                      )}</strong> → ${escapeHtml(nodeName(edge.target))}: ${escapeHtml(edge.label)}</li>`
                  )
                  .join("")
              : '<li class="empty-text">Nenhuma relação de saída mapeada.</li>'
          }
        </ul>
      </section>
    </div>
  `;
}

function renderEdgeDetail(edge) {
  detailPanel.innerHTML = `
    <div class="detail-header">
      <p class="section-kicker">Conexão</p>
      <h3>${escapeHtml(nodeName(edge.source))} → ${escapeHtml(nodeName(edge.target))}</h3>
      <div class="detail-links">
        <span class="status-pill ${healthClassName(edge.health)}">${escapeHtml(
          healthLabels[edge.health] || edge.health
        )}</span>
      </div>
      <p class="detail-note">${escapeHtml(edge.label)}</p>
    </div>
    <div class="detail-stack">
      <section class="detail-section">
        <span class="detail-label">Snapshot</span>
        <div class="detail-grid">
          ${detailCell("Tipo", edge.kind || "N/A")}
          ${detailCell("Check", edge.check || "N/A")}
          ${detailCell("Origem", nodeName(edge.source))}
          ${detailCell("Destino", nodeName(edge.target))}
        </div>
      </section>
      <section class="detail-section">
        <span class="detail-label">Leitura operacional</span>
        <div class="detail-cell">
          <div class="detail-value">${escapeHtml(edge.notes || "Sem observação registrada.")}</div>
        </div>
      </section>
      <section class="detail-section">
        <span class="detail-label">Issues vinculadas</span>
        <div class="detail-links">
          ${renderIssueLinks(edge.issues)}
        </div>
      </section>
    </div>
  `;
}

function renderMetrics(metrics = []) {
  if (!metrics.length) {
    return '<div class="empty-panel">Nenhuma métrica adicional registrada para este artefato.</div>';
  }

  return `
    <div class="metric-grid">
      ${metrics
        .map(
          (metric) => `
            <div class="metric-card">
              <span class="detail-label">${escapeHtml(metric.label)}</span>
              <strong>${escapeHtml(metric.value)}</strong>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderSignals(signals = []) {
  if (!signals.length) {
    return '<div class="empty-panel">Sem sinais adicionais registrados.</div>';
  }

  return `
    <ul class="default-list">
      ${signals.map((signal) => `<li>${escapeHtml(signal)}</li>`).join("")}
    </ul>
  `;
}

function renderLinks(links = []) {
  if (!links.length) {
    return '<span class="empty-text">Sem link rápido disponível.</span>';
  }

  return links
    .map(
      (link) => `
        <a class="link-pill" href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">
          ${escapeHtml(link.label)}
        </a>
      `
    )
    .join("");
}

function renderIssueLinks(issueKeys = []) {
  if (!issueKeys?.length) {
    return "";
  }

  return issueKeys
    .map(
      (issueKey) => `
        <a class="link-pill" href="https://guigiese.atlassian.net/browse/${encodeURIComponent(
          issueKey
        )}" target="_blank" rel="noreferrer">${escapeHtml(issueKey)}</a>
      `
    )
    .join("");
}

function detailCell(label, value) {
  return `
    <div class="detail-cell">
      <span class="detail-label">${escapeHtml(label)}</span>
      <div class="detail-value ${value && String(value).includes("/") ? "mono" : ""}">${escapeHtml(
        value || "N/A"
      )}</div>
    </div>
  `;
}

function nodeName(nodeId) {
  return state.map.nodes.find((node) => node.id === nodeId)?.name || nodeId;
}

function healthClassName(health) {
  return `is-${health}`;
}

function sourceClassName(sourceKind) {
  return `is-${sourceKind || "manual"}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
