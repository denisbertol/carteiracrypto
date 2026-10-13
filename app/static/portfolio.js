(() => {
  "use strict";

  const root = document.getElementById("app-content");
  if (!root) return;

  const TABS = [
    ["resumo", "Resumo"],
    ["lancamentos", "Lançamentos"],
    ["alocacao", "Alocação"],
    ["alvos", "Alvos e alertas"],
  ];
  const CASH_SYMBOLS = ["USDT", "USDC"];

  function isCashSymbol(symbol) {
    return CASH_SYMBOLS.includes(symbol);
  }

  const COLUMNS = [
    { key: "asset", label: "Ativo", fixed: true },
    { key: "value", label: "Saldo" },
    { key: "variation", label: "Variação" },
    { key: "price", label: "Preço atual" },
    { key: "average", label: "Preço médio" },
    { key: "buyTarget", label: "Preço alvo" },
    { key: "wallet", label: "% Carteira" },
    { key: "ideal", label: "% Ideal" },
    { key: "signal", label: "Sinal" },
    { key: "quantity", label: "Quant." },
    { key: "options", label: "Opções", fixed: true, unsortable: true },
  ];
  const PERIODS = [["30d", "Últimos 30 dias", 30], ["90d", "Últimos 90 dias", 90], ["12m", "Últimos 12 meses", 365], ["all", "Desde o início", null]];
  const STORAGE_COLUMNS = "carteira.hiddenColumns";
  const STORAGE_CHART = "carteira.chartPrefs";

  let loadVersion = 0;
  let snapshot = null;
  let shell = null;
  let activeTab = "resumo";
  let sortState = { key: "value", dir: "desc" };
  let hiddenColumns = new Set(readStored(STORAGE_COLUMNS, []));
  let chartPrefs = { granularity: "daily", period: "30d", ...readStored(STORAGE_CHART, {}) };
  let groupCollapsed = false;
  let backfillStarted = false;
  let chartObserver = null;
  let openPopover = null;

  function readStored(key, fallback) {
    try {
      const value = JSON.parse(window.localStorage.getItem(key));
      return value === null || value === undefined ? fallback : value;
    } catch (_error) {
      return fallback;
    }
  }

  function store(key, value) {
    try { window.localStorage.setItem(key, JSON.stringify(value)); } catch (_error) { /* Preferences are optional. */ }
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function button(label, className, onClick) {
    const control = element("button", className, label);
    control.type = "button";
    if (onClick) control.addEventListener("click", onClick);
    return control;
  }

  function num(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function formatMoney(value) {
    const number = num(value);
    return number === null ? "—" : number.toLocaleString("pt-BR", { style: "currency", currency: "USD" });
  }

  function formatPrice(value) {
    const number = num(value);
    if (number === null) return "—";
    const digits = Math.abs(number) >= 1 ? 2 : 6;
    return number.toLocaleString("pt-BR", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: digits });
  }

  function formatNumber(value, digits = 8) {
    const number = num(value);
    return number === null ? "—" : number.toLocaleString("pt-BR", { maximumFractionDigits: digits });
  }

  function formatPercent(value, digits = 2) {
    const number = num(value);
    return number === null ? "—" : `${number.toLocaleString("pt-BR", { minimumFractionDigits: Math.min(2, digits), maximumFractionDigits: digits })}%`;
  }

  function formatDate(value) {
    if (!value) return "horário indisponível";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? "horário indisponível" : date.toLocaleString("pt-BR");
  }

  function trendClass(value) {
    const number = num(value);
    if (number === null || number === 0) return "";
    return number > 0 ? "is-positive" : "is-negative";
  }

  function percentBadge(value) {
    const number = num(value);
    const badge = element("span", `badge ${number === null ? "badge-muted" : number >= 0 ? "badge-up" : "badge-down"}`);
    badge.textContent = number === null ? "—" : `${formatPercent(number)} ${number >= 0 ? "▲" : "▼"}`;
    return badge;
  }

  async function request(path, options) {
    const response = await window.AppAuth.fetch(path, options);
    let body = null;
    const type = response.headers.get("content-type") || "";
    if (type.includes("application/json")) {
      try { body = await response.json(); } catch (_error) { body = null; }
    }
    if (!response.ok) {
      const detail = body && body.detail && body.detail.error;
      let message = detail && typeof detail.message === "string" ? detail.message : "";
      if (!message && body && body.detail) {
        if (typeof body.detail === "string") {
          message = body.detail;
        } else if (Array.isArray(body.detail) && body.detail.length > 0 && body.detail[0].msg) {
          message = body.detail[0].msg;
        }
      }
      if (!message) {
        message = response.status === 429
          ? "Limite temporário atingido. Aguarde antes de tentar novamente."
          : response.status === 503
            ? "Serviço temporariamente indisponível. Tente novamente."
            : "Não foi possível concluir a solicitação.";
      }
      const error = new Error(message);
      error.status = response.status;
      error.code = detail && detail.code;
      error.retryAfter = response.headers.get("Retry-After");
      error.body = body;
      throw error;
    }
    return { body, response };
  }

  function section(title, description, className = "card section-card") {
    const card = element("section", className);
    const heading = element("div", "section-heading");
    heading.append(element("h2", "section-title", title));
    if (description) heading.append(element("p", "muted", description));
    card.append(heading);
    return card;
  }

  function makeTable(headers, rows, emptyMessage) {
    const wrapper = element("div", "table-scroll");
    const table = element("table", "data-table");
    const thead = element("thead");
    const headerRow = element("tr");
    headers.forEach((label) => headerRow.append(element("th", "", label)));
    thead.append(headerRow);
    const tbody = element("tbody");
    if (!rows.length) {
      const row = element("tr");
      const cell = element("td", "empty-cell", emptyMessage);
      cell.colSpan = headers.length;
      row.append(cell);
      tbody.append(row);
    } else {
      rows.forEach((values) => {
        const row = element("tr");
        values.forEach((value, index) => {
          const cell = element("td");
          cell.dataset.label = headers[index];
          if (value instanceof Node) cell.append(value);
          else cell.textContent = value === null || value === undefined ? "—" : String(value);
          row.append(cell);
        });
        tbody.append(row);
      });
    }
    table.append(thead, tbody);
    wrapper.append(table);
    return wrapper;
  }

  function freshnessLabel(value) {
    const labels = {
      fresh: "Atualizada",
      available: "Atualizada",
      stale: "Desatualizada",
      incomplete: "Parcial",
      unavailable: "Indisponível",
    };
    return labels[value] || "Estado desconhecido";
  }

  function closePopover() {
    if (!openPopover) return;
    openPopover.remove();
    openPopover = null;
  }

  function showPopover(anchor, content) {
    const wasOpen = openPopover && openPopover.dataset.owner === anchor.dataset.popoverId;
    closePopover();
    if (wasOpen) return;
    if (!anchor.dataset.popoverId) anchor.dataset.popoverId = String(Math.random()).slice(2);
    const popover = element("div", "popover");
    popover.dataset.owner = anchor.dataset.popoverId;
    popover.setAttribute("role", "menu");
    popover.append(content);
    document.body.append(popover);
    const bounds = anchor.getBoundingClientRect();
    const width = popover.offsetWidth;
    const left = Math.min(Math.max(8, bounds.right - width), document.documentElement.clientWidth - width - 8);
    popover.style.left = `${left + window.scrollX}px`;
    popover.style.top = `${bounds.bottom + 6 + window.scrollY}px`;
    openPopover = popover;
  }

  function menuList(items) {
    const list = element("div", "menu-list");
    items.forEach(([label, action]) => {
      const item = button(label, "menu-item", () => { closePopover(); action(); });
      item.setAttribute("role", "menuitem");
      list.append(item);
    });
    return list;
  }

  document.addEventListener("click", (event) => {
    if (!openPopover) return;
    if (openPopover.contains(event.target)) return;
    if (event.target.closest(`[data-popover-id="${openPopover.dataset.owner}"]`)) return;
    closePopover();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closePopover(); });

  function openOperationForm(symbol) {
    if (window.Operations && typeof window.Operations.openForm === "function") window.Operations.openForm(symbol);
  }

  function exportMenu(btnClass = "btn btn-outline") {
    const trigger = button("Exportar ▾", btnClass);
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.addEventListener("click", () => {
      const list = element("div", "menu-list");
      [
        ["/api/v1/exports/results.csv", "Resultados (CSV)"],
        ["/api/v1/exports/allocations.csv", "Alocação (CSV)"],
        ["/api/v1/exports/operations.csv", "Operações (CSV)"],
        ["/api/v1/exports/assets.csv", "Ativos (CSV)"],
      ].forEach(([path, label]) => {
        const link = element("a", "menu-item", label);
        link.href = path;
        link.dataset.authenticatedExport = "true";
        link.setAttribute("role", "menuitem");
        list.append(link);
      });
      showPopover(trigger, list);
    });
    return trigger;
  }

  function showTab(key) {
    activeTab = key;
    closePopover();
    if (!shell) return;
    Object.entries(shell.tabs).forEach(([tabKey, tab]) => {
      const selected = tabKey === key;
      tab.classList.toggle("is-active", selected);
      tab.setAttribute("aria-selected", String(selected));
      shell.panels[tabKey].hidden = !selected;
    });
    if (key === "lancamentos" && window.Operations && typeof window.Operations.show === "function") {
      window.Operations.show(shell.panels.lancamentos);
    }
    if (key === "resumo" && snapshot) drawEvolution();
  }

  function ensureShell() {
    if (shell) return shell;
    root.replaceChildren();
    const bar = element("div", "tabbar");
    const nav = element("nav", "tabs");
    nav.setAttribute("aria-label", "Seções da carteira");
    nav.setAttribute("role", "tablist");
    const tabs = {};
    const panels = {};
    TABS.forEach(([key, label]) => {
      const tab = button(label, "tab", () => showTab(key));
      tab.setAttribute("role", "tab");
      tab.dataset.tab = key;
      tabs[key] = tab;
      nav.append(tab);
      const panel = element("section", "tab-panel");
      panel.dataset.tabPanel = key;
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-label", label);
      panels[key] = panel;
    });
    bar.append(nav);

    const status = element("div", "status-strip");
    const unread = element("div", "unread-alerts");
    unread.id = "unread-alerts";
    unread.hidden = true;
    const targets = section("Alvos de preço", "Cadastre alvos independentes por ativo.");
    targets.id = "targets-panel";
    const monitoring = section("Monitoramento", "Os ciclos são executados enquanto esta sessão permanecer aberta.");
    monitoring.id = "monitoring-panel";
    panels.alvos.append(unread, targets, monitoring);

    root.append(bar, ...Object.values(panels), status);
    shell = { tabs, panels, status };
    showTab(activeTab);
    if (window.Targets && typeof window.Targets.init === "function") window.Targets.init();
    if (window.Monitoring && typeof window.Monitoring.start === "function") window.Monitoring.start();
    return shell;
  }

  function renderStatus(data) {
    const strip = shell.status;
    strip.className = `status-strip freshness-${data.freshness || "unavailable"}`;
    strip.replaceChildren();
    const text = element("div", "status-text");
    text.append(element("strong", "", `Cotações: ${freshnessLabel(data.freshness)}`));
    if (data.quote_snapshot_at) text.append(element("span", "muted", `Última coleta: ${formatDate(data.quote_snapshot_at)}`));
    text.append(element("span", "muted", `Painel calculado em ${formatDate(data.computed_at)}`));
    strip.append(text, button("Atualizar", "btn btn-ghost btn-small", () => load()));
  }

  function kpiCard(title, value, valueClass, badges, details) {
    const card = element("article", "card kpi-card");
    const head = element("div", "kpi-head");
    head.append(element("h2", "kpi-title", title));
    card.append(head);
    if (value !== null) {
      const line = element("div", "kpi-line");
      line.append(element("p", `kpi-value ${valueClass || ""}`.trim(), value));
      badges.forEach((badge) => line.append(badge));
      card.append(line);
    } else {
      const line = element("div", "kpi-pills");
      badges.forEach((badge) => line.append(badge));
      card.append(line);
    }
    if (details.length) {
      const list = element("dl", "kpi-details");
      details.forEach(([label, detail, detailClass]) => {
        const item = element("div");
        item.append(element("dt", "", label), element("dd", detailClass || "", detail));
        list.append(item);
      });
      card.append(list);
    }
    return card;
  }

  function renderKpis(data) {
    const totals = data.portfolio.totals || {};
    const evolution = data.evolution || {};
    const balance = num(totals.balance_usd);
    const invested = num(totals.invested_usd ?? evolution.invested_usd);
    const realized = num(totals.realized_net_usd);
    const unrealized = num(totals.unrealized_usd);
    const result = unrealized === null || realized === null ? null : realized + unrealized;
    const growth = balance !== null && invested > 0 ? ((balance - invested) / invested) * 100 : null;

    const grid = element("div", "kpi-grid");
    grid.append(
      kpiCard("Patrimônio total", balance === null ? "Parcial" : formatMoney(balance), "", [percentBadge(growth)], [
        ["Valor investido", formatMoney(invested)],
        ["Em caixa (USDT)", `${formatMoney(totals.cash_usdt)}${num(totals.cash_percent) !== null ? ` · ${formatPercent(totals.cash_percent, 1)}` : ""}`],
      ]),
      kpiCard("Resultado", result === null ? "Parcial" : formatMoney(result), trendClass(result), [], [
        ["Ganho de capital", formatMoney(unrealized), trendClass(unrealized)],
        ["Realizado líquido", formatMoney(realized), trendClass(realized)],
      ]),
    );
    return grid;
  }

  function seriesFor(points) {
    const list = (points || []).map((point) => ({
      day: point.day,
      invested: num(point.invested_usd) || 0,
      value: num(point.value_usd),
    }));
    if (!list.length) return [];
    const period = PERIODS.find(([key]) => key === chartPrefs.period) || PERIODS[0];
    let filtered = list;
    if (period[2]) {
      const last = new Date(`${list[list.length - 1].day}T00:00:00Z`);
      last.setUTCDate(last.getUTCDate() - (period[2] - 1));
      const cutoff = last.toISOString().slice(0, 10);
      filtered = list.filter((item) => item.day >= cutoff);
    }
    if (chartPrefs.granularity === "monthly") {
      const months = new Map();
      filtered.forEach((item) => {
        const key = item.day.slice(0, 7);
        const current = months.get(key);
        if (!current || item.value !== null || current.value === null) months.set(key, item);
      });
      filtered = [...months.values()];
    }
    const monthly = chartPrefs.granularity === "monthly";
    return filtered.map((item) => {
      const date = new Date(`${item.day}T00:00:00Z`);
      return {
        ...item,
        gain: item.value === null ? null : item.value - item.invested,
        label: monthly
          ? date.toLocaleDateString("pt-BR", { month: "short", year: "2-digit", timeZone: "UTC" }).replace(". de ", "/").replace(" de ", "/")
          : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "UTC" }),
        tooltipLabel: monthly
          ? `Fim de ${date.toLocaleDateString("pt-BR", { month: "long", year: "numeric", timeZone: "UTC" })}`
          : date.toLocaleDateString("pt-BR", { day: "2-digit", month: "long", year: "numeric", timeZone: "UTC" }),
      };
    });
  }

  function drawEvolution() {
    if (!shell || !shell.chartHost || !window.Charts) return;
    const host = shell.chartHost;
    const series = seriesFor(snapshot && snapshot.evolution && snapshot.evolution.points);
    if (!series.length) {
      host.replaceChildren(element("p", "chart-empty muted", "Ainda não há histórico para exibir. Registre um depósito para começar."));
      return;
    }
    window.Charts.renderEvolution(host, series);
  }

  function selectControl(label, options, value, onChange) {
    const wrapper = element("label", "chart-select");
    wrapper.append(element("span", "visually-hidden", label));
    const control = element("select", "form-control form-control-small");
    options.forEach(([optionValue, optionLabel]) => {
      const option = element("option", "", optionLabel);
      option.value = optionValue;
      control.append(option);
    });
    control.value = value;
    control.addEventListener("change", () => onChange(control.value));
    wrapper.append(control);
    return wrapper;
  }

  function evolutionCard(data) {
    const card = element("section", "card chart-card");
    const head = element("div", "chart-head");
    head.append(element("h2", "section-title", "Evolução do patrimônio"));
    const controls = element("div", "chart-controls");
    controls.append(
      selectControl("Período", PERIODS.map(([key, label]) => [key, label]), chartPrefs.period, (value) => {
        chartPrefs.period = value;
        store(STORAGE_CHART, chartPrefs);
        drawEvolution();
      }),
      selectControl("Agrupamento", [["daily", "Diário"], ["monthly", "Mensal"]], chartPrefs.granularity, (value) => {
        chartPrefs.granularity = value;
        if (value === "monthly" && (chartPrefs.period === "30d" || chartPrefs.period === "90d")) {
          chartPrefs.period = "12m";
          card.querySelector("select").value = "12m";
        }
        store(STORAGE_CHART, chartPrefs);
        drawEvolution();
      }),
    );
    head.append(controls);
    const legend = element("div", "chart-legend");
    [["legend-invested", "Valor aplicado"], ["legend-gain", "Ganho de capital"], ["legend-loss", "Perda"]].forEach(([className, label]) => {
      const item = element("span", "chart-legend-item");
      item.append(element("span", `legend-dot ${className}`), document.createTextNode(label));
      legend.append(item);
    });
    const host = element("div", "chart-host");
    card.append(head, legend, host);

    const backfill = data.evolution && data.evolution.backfill;
    const note = element("p", "chart-note muted");
    note.hidden = true;
    if (backfill && backfill.pending_assets > 0) {
      note.hidden = false;
      note.textContent = backfill.provider_configured
        ? "Importando o histórico de preços da CoinGecko…"
        : "Histórico anterior indisponível: configure a CoinGecko para importar até 365 dias de preços.";
    } else if ((data.evolution && data.evolution.points || []).some((point) => point.value_usd === null)) {
      note.hidden = false;
      note.textContent = "Barras esmaecidas: dias sem cotação registrada; só o valor aplicado é conhecido.";
    }
    card.append(note);
    shell.chartHost = host;
    shell.chartNote = note;
    if (chartObserver) chartObserver.disconnect();
    if ("ResizeObserver" in window) {
      let lastWidth = 0;
      chartObserver = new ResizeObserver((entries) => {
        const width = Math.round(entries[0].contentRect.width);
        if (width && width !== lastWidth) {
          lastWidth = width;
          drawEvolution();
        }
      });
      chartObserver.observe(host);
    }
    return card;
  }

  function allocationSlices(data) {
    const totals = data.portfolio.totals || {};
    const recommended = new Map();
    const items = data.allocation && Array.isArray(data.allocation.items) ? data.allocation.items : [];
    items.forEach((item) => {
      if (item.symbol) recommended.set(item.symbol, num(item.target_percent));
    });
    const slices = (data.portfolio.positions || [])
      .filter((position) => num(position.current_value_usd) > 0)
      .map((position) => ({
        label: position.symbol,
        value: num(position.current_value_usd),
        recommended: recommended.has(position.symbol) ? recommended.get(position.symbol) : null,
      }));
    if (num(totals.cash_usdt) > 0) {
      slices.push({
        label: "USDT",
        value: num(totals.cash_usdt),
        recommended: recommended.has("USDT") ? recommended.get("USDT") : null,
      });
    }
    return slices.sort((a, b) => b.value - a.value);
  }

  function walletCard(data) {
    const card = element("section", "card chart-card");
    const head = element("div", "chart-head");
    head.append(element("h2", "section-title", "Ativos na carteira"));
    card.append(head);
    const host = element("div", "donut-host");
    const slices = allocationSlices(data);
    if (!slices.length) {
      host.append(element("p", "chart-empty muted", "Nenhum ativo com valor atual para exibir."));
    } else if (window.Charts) {
      window.Charts.renderDonut(host, slices, `${slices.length} ${slices.length === 1 ? "posição" : "posições"}`);
    }
    card.append(host);
    if (data.portfolio.totals && data.portfolio.totals.complete === false) {
      card.append(element("p", "chart-note muted", "Ativos sem cotação ficam fora do gráfico até a próxima coleta."));
    }
    return card;
  }

  function assetRows(data) {
    const totals = data.portfolio.totals || {};
    const balance = num(totals.balance_usd);
    const idealByAsset = new Map();
    const allocationItems = (data.allocation && Array.isArray(data.allocation.items)) ? data.allocation.items : [];
    allocationItems.forEach((item) => idealByAsset.set(item.asset_id, item));
    const buyTargetByAsset = new Map();
    (Array.isArray(data.buy_targets) ? data.buy_targets : []).forEach((target) => {
      const price = num(target.price_usd);
      const current = buyTargetByAsset.get(target.asset_id);
      if (price !== null && (current === undefined || price > current)) buyTargetByAsset.set(target.asset_id, price);
    });
    const rows = (data.portfolio.positions || []).map((position) => {
      const average = num(position.average_price_usd);
      const price = num(position.quote_usd);
      const value = num(position.current_value_usd);
      const ideal = idealByAsset.get(position.asset_id);
      idealByAsset.delete(position.asset_id);
      return {
        symbol: position.symbol,
        name: position.name,
        cash: isCashSymbol(position.symbol),
        quantity: num(position.quantity),
        average,
        price,
        freshness: position.quote_freshness || position.quote_status,
        variation: average && price !== null ? (price / average - 1) * 100 : null,
        value,
        wallet: balance && value !== null ? (value / balance) * 100 : null,
        ideal: ideal ? num(ideal.target_percent) : null,
        buyTarget: buyTargetByAsset.get(position.asset_id) ?? null,
      };
    });
    const cashIdeal = [...idealByAsset.values()].find((item) => item.symbol === "USDT");
    if (cashIdeal) idealByAsset.delete(cashIdeal.asset_id);
    if (!rows.some((row) => row.symbol === "USDT")) rows.push({
      symbol: "USDT",
      name: "Tether USD · caixa",
      cash: true,
      quantity: num(totals.cash_usdt),
      average: null,
      price: 1,
      freshness: "available",
      variation: null,
      value: num(totals.cash_usdt),
      wallet: num(totals.cash_percent),
      ideal: cashIdeal ? num(cashIdeal.target_percent) : null,
      buyTarget: cashIdeal ? (buyTargetByAsset.get(cashIdeal.asset_id) ?? null) : null,
    });
    const quoteByAsset = new Map((Array.isArray(data.quotes) ? data.quotes : []).map((quote) => [quote.asset_id, quote]));
    idealByAsset.forEach((item) => {
      const quote = quoteByAsset.get(item.asset_id);
      const price = quote ? num(quote.price_usd) : null;
      const cash = isCashSymbol(item.symbol);
      rows.push({
        symbol: item.symbol, name: item.name, cash, quantity: 0, average: null, price,
        freshness: price === null ? null : (quote.freshness || null), variation: null, value: 0, wallet: 0,
        ideal: num(item.target_percent), unheld: !cash,
        buyTarget: buyTargetByAsset.get(item.asset_id) ?? null,
      });
    });
    rows.forEach((row) => {
      row.signal = tradeSignal(row);
    });
    return rows;
  }

  function sortRows(rows) {
    const { key, dir } = sortState;
    const factor = dir === "asc" ? 1 : -1;
    const valueOf = (row) => (key === "asset" ? row.symbol : row[key]);
    return [...rows].sort((a, b) => {
      if (Boolean(a.cash) !== Boolean(b.cash)) return a.cash ? 1 : -1;
      const left = valueOf(a);
      const right = valueOf(b);
      if (left === null || left === undefined) return 1;
      if (right === null || right === undefined) return -1;
      if (typeof left === "string") return left.localeCompare(right) * factor;
      return (left - right) * factor;
    });
  }

  function assetIcon(row) {
    const wrap = element("span", `asset-icon${row.cash ? " is-cash" : ""}`);
    const img = element("img", "asset-logo");
    img.alt = "";
    img.src = `/static/icons/${encodeURIComponent(row.symbol)}.svg`;
    img.addEventListener("error", () => {
      img.remove();
      wrap.textContent = row.symbol.slice(0, 4);
    });
    wrap.append(img);
    return wrap;
  }

  function assetCell(row) {
    const cell = element("div", "asset-cell");
    cell.append(assetIcon(row));
    const text = element("div", "asset-text");
    text.append(element("strong", "", row.symbol), element("span", "muted", row.unheld ? `${row.name} · sem posição` : row.name));
    cell.append(text);
    return cell;
  }

  function tradeSignal(row) {
    const doubled = row.average > 0 && row.price !== null && row.price >= row.average * 2;
    const belowIdeal = row.ideal !== null && row.wallet !== null && row.wallet < row.ideal;
    const atOrBelowTarget = row.buyTarget !== null && row.price !== null && row.price <= row.buyTarget;
    if (doubled) return "vender";
    if (belowIdeal && atOrBelowTarget) return "comprar";
    return "aguardar";
  }

  function signalBadge(row) {
    const signal = tradeSignal(row);
    const labels = { comprar: "Comprar", vender: "Vender", aguardar: "Aguardar" };
    return element("span", `signal signal-${signal}`, labels[signal]);
  }

  function priceCell(row) {
    const cell = element("div", "price-cell");
    cell.append(element("span", "", formatPrice(row.price)));
    if (!row.cash && row.freshness && row.freshness !== "available" && row.freshness !== "fresh") {
      cell.append(element("span", `quote-flag quote-${row.freshness}`, freshnessLabel(row.freshness)));
    }
    return cell;
  }

  function optionsCell(row) {
    const trigger = button("⋯", "icon-button");
    trigger.setAttribute("aria-label", `Opções de ${row.symbol}`);
    trigger.setAttribute("aria-haspopup", "menu");
    trigger.addEventListener("click", () => showPopover(trigger, menuList([
      ["Ver lançamentos", () => {
        if (window.Operations) window.Operations.setFilter(row.symbol);
        showTab("lancamentos");
      }],
      ["Adicionar lançamento", () => openOperationForm(row.symbol)],
      ["Alvos de preço", () => showTab("alvos")],
    ])));
    return trigger;
  }

  function cellContent(column, row) {
    switch (column.key) {
      case "asset": return assetCell(row);
      case "quantity": return formatNumber(row.quantity, row.cash ? 2 : 8);
      case "average": return row.cash ? "—" : formatPrice(row.average);
      case "price": return priceCell(row);
      case "buyTarget": return row.cash ? "—" : formatPrice(row.buyTarget);
      case "variation": {
        if (row.variation === null) return "—";
        return percentBadge(row.variation);
      }
      case "value": return formatMoney(row.value);
      case "wallet": return formatPercent(row.wallet);
      case "ideal": return row.ideal === null ? "—" : formatPercent(row.ideal);
      case "signal": return signalBadge(row);
      case "options": return optionsCell(row);
      default: return "—";
    }
  }

  function assetTable(rows) {
    const columns = COLUMNS.filter((column) => column.fixed || !hiddenColumns.has(column.key));
    const wrapper = element("div", "asset-table-wrap");
    const table = element("table", "asset-table");
    const thead = element("thead");
    const headRow = element("tr");
    columns.forEach((column) => {
      const th = element("th");
      th.dataset.column = column.key;
      if (column.unsortable) {
        th.textContent = column.label;
      } else {
        const active = sortState.key === column.key;
        const sortButton = button(`${column.label} ${active ? (sortState.dir === "asc" ? "↑" : "↓") : "⇅"}`, `sort-button${active ? " is-active" : ""}`, () => {
          sortState = { key: column.key, dir: active && sortState.dir === "desc" ? "asc" : "desc" };
          renderResumo(snapshot);
        });
        th.setAttribute("aria-sort", active ? (sortState.dir === "asc" ? "ascending" : "descending") : "none");
        th.append(sortButton);
      }
      headRow.append(th);
    });
    thead.append(headRow);
    const tbody = element("tbody");
    sortRows(rows).forEach((row) => {
      const tr = element("tr", row.cash ? "is-cash-row" : row.unheld ? "is-unheld-row" : "");
      columns.forEach((column) => {
        const td = element("td");
        td.dataset.column = column.key;
        td.dataset.label = column.label;
        const content = cellContent(column, row);
        if (content instanceof Node) td.append(content);
        else td.textContent = content;
        tr.append(td);
      });
      tbody.append(tr);
    });
    table.append(thead, tbody);
    wrapper.append(table);
    return wrapper;
  }

  function applyColumnPreference(data) {
    const saved = data && Array.isArray(data.hidden_columns) ? data.hidden_columns : null;
    if (!saved) return;
    const allowed = new Set(COLUMNS.filter((column) => !column.fixed).map((column) => column.key));
    hiddenColumns = new Set(saved.filter((key) => allowed.has(key)));
    store(STORAGE_COLUMNS, [...hiddenColumns]);
  }

  async function saveColumnPreference() {
    const hidden = [...hiddenColumns];
    store(STORAGE_COLUMNS, hidden);
    try {
      await request("/api/v1/ui/columns", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ hidden_columns: hidden }),
      });
      if (snapshot) snapshot.hidden_columns = hidden;
    } catch (_error) {
      // A próxima carga da carteira restaura a seleção gravada na conta.
    }
  }

  function columnEditor(trigger) {
    const form = element("div", "column-editor");
    form.append(element("p", "column-editor-title", "Colunas visíveis"));
    COLUMNS.filter((column) => !column.fixed).forEach((column) => {
      const label = element("label", "checkbox-field");
      const input = element("input");
      input.type = "checkbox";
      input.checked = !hiddenColumns.has(column.key);
      input.addEventListener("change", () => {
        if (input.checked) hiddenColumns.delete(column.key);
        else hiddenColumns.add(column.key);
        saveColumnPreference();
        renderResumo(snapshot, { keepPopover: true });
      });
      label.append(input, element("span", "", column.label));
      form.append(label);
    });
    showPopover(trigger, form);
  }

  function groupStat(label, value, className) {
    const stat = element("div", "group-stat");
    stat.append(element("span", "group-stat-label", label));
    if (value instanceof Node) stat.append(value);
    else stat.append(element("strong", className || "", value));
    return stat;
  }

  function assetsGroup(data) {
    const totals = data.portfolio.totals || {};
    const rows = assetRows(data);
    const held = rows.filter((row) => !row.cash && !row.unheld);
    const cost = num(totals.crypto_cost_usd);
    const unrealized = num(totals.unrealized_usd);
    const variation = cost > 0 && unrealized !== null ? (unrealized / cost) * 100 : null;
    const cashRow = rows.find((row) => row.cash);

    const group = element("section", "card asset-group");
    const header = element("div", "group-header");
    const title = element("div", "group-title");
    title.append(element("span", "group-icon", "◈"), element("h3", "", "Criptomoedas"));
    const stats = element("div", "group-stats");
    stats.append(
      groupStat("Ativos", String(held.length)),
      groupStat("Valor total", totals.balance_usd === null ? "Parcial" : formatMoney(totals.balance_usd)),
      groupStat("Variação", percentBadge(variation)),
      groupStat("Ganho de capital", formatMoney(unrealized), trendClass(unrealized)),
      groupStat("Em caixa", `${formatPercent(cashRow && cashRow.wallet)} / ${cashRow && cashRow.ideal !== null ? formatPercent(cashRow.ideal) : "—"}`),
    );
    const toggle = button(groupCollapsed ? "▾" : "▴", "icon-button group-toggle");
    toggle.setAttribute("aria-label", groupCollapsed ? "Expandir criptomoedas" : "Recolher criptomoedas");
    toggle.setAttribute("aria-expanded", String(!groupCollapsed));
    header.append(title, stats, toggle);

    const body = element("div", "group-body");
    body.hidden = groupCollapsed;
    body.append(assetTable(rows));
    const footer = element("div", "group-footer");
    const columnsButton = button("Editar colunas", "btn btn-ghost btn-small");
    columnsButton.dataset.popoverId = "column-editor";
    columnsButton.addEventListener("click", () => columnEditor(columnsButton));
    footer.append(
      button("Lançamentos", "btn btn-ghost btn-small", () => {
        if (window.Operations) window.Operations.setFilter("");
        showTab("lancamentos");
      }),
      columnsButton,
      button("+ Adicionar lançamento", "btn btn-outline btn-small", () => openOperationForm()),
    );
    body.append(footer);
    toggle.addEventListener("click", () => {
      groupCollapsed = !groupCollapsed;
      body.hidden = groupCollapsed;
      toggle.textContent = groupCollapsed ? "▾" : "▴";
      toggle.setAttribute("aria-expanded", String(!groupCollapsed));
      toggle.setAttribute("aria-label", groupCollapsed ? "Expandir criptomoedas" : "Recolher criptomoedas");
    });
    group.append(header, body);
    return { group, count: held.length };
  }

  function renderResumo(data, options = {}) {
    const panel = shell.panels.resumo;
    if (!options.keepPopover) closePopover();
    if (!data.portfolio) {
      panel.replaceChildren(element("p", "inline-notice", "Nenhuma carteira encontrada. Registre um depósito em USDT para começar."));
      return;
    }
    const charts = element("div", "charts-grid");
    charts.append(evolutionCard(data), walletCard(data));
    const { group, count } = assetsGroup(data);
    const heading = element("h2", "assets-heading");
    heading.append(document.createTextNode("Meus ativos "), element("span", "muted", `(${count})`));
    const attribution = element("p", "attribution");
    attribution.append(document.createTextNode("Dados de mercado fornecidos por "));
    const provider = element("a", "", "CryptoPrices");
    provider.href = "https://cryptoprices.cc/";
    provider.target = "_blank";
    provider.rel = "noopener noreferrer";
    attribution.append(provider, document.createTextNode("."));
    panel.replaceChildren(renderKpis(data), heading, group, charts, attribution);
    if (!panel.hidden) drawEvolution();
  }

  function renderAllocation(data) {
    const panel = shell.panels.alocacao;
    const allocation = data.allocation;
    const card = section(
      "Alocação e rebalanceamento",
      allocation && allocation.version
        ? `Versão ${allocation.version} · vigente desde ${formatDate(allocation.effective_at)}`
        : "Nenhuma meta de alocação cadastrada.",
    );
    if (allocation && allocation.complete === false) {
      card.append(element("p", "inline-notice", "Valores parciais enquanto houver cotações indisponíveis."));
    }
    const allocationItems = allocation && Array.isArray(allocation.items) ? [...allocation.items].sort((a, b) => {
      const left = num(a.deviation_percent);
      const right = num(b.deviation_percent);
      if (left === null && right === null) return 0;
      if (left === null) return 1;
      if (right === null) return -1;
      return left - right;
    }) : [];
    card.append(makeTable(
      ["Ativo", "Meta", "Valor atual", "Posição ideal", "Ajuste", "Desvio"],
      allocationItems.map((item) => [
        element("strong", "", `${item.symbol || ""} ${item.name || ""}`.trim()),
        formatPercent(item.target_percent),
        formatMoney(item.current_value_usd),
        formatMoney(item.ideal_value_usd),
        formatMoney(item.adjustment_usd),
        formatPercent(item.deviation_percent),
      ]),
      "Nenhuma meta de alocação disponível.",
    ));
    panel.replaceChildren(card);
  }

  async function runBackfill() {
    const evolution = snapshot && snapshot.evolution;
    const backfill = evolution && evolution.backfill;
    if (backfillStarted || !backfill || !backfill.provider_configured || !(backfill.pending_assets > 0)) return;
    backfillStarted = true;
    const version = loadVersion;
    try {
      for (let attempt = 0; attempt < 10; attempt += 1) {
        const { body } = await request("/api/v1/history/backfill", { method: "POST" });
        if (!body || body.state !== "completed" || !(body.pending_assets > 0)) break;
        if (body.imported_assets + body.failed_assets === 0) break;
      }
    } catch (_error) {
      // Failed imports are retried by the server after its cooldown, on a later session.
    }
    if (version === loadVersion && window.AppAuth.hasSession()) await load();
  }

  async function load(options = {}) {
    if (!window.AppAuth || !window.AppAuth.hasSession()) return;
    const isPostLogin = Boolean(options && options.isPostLogin);
    const version = ++loadVersion;
    const status = document.getElementById("session-status");
    ensureShell();
    root.classList.add("is-loading");
    if (status) status.textContent = "Carregando sua carteira…";

    if (isPostLogin && window.SplashLoader) {
      window.SplashLoader.start();
      window.SplashLoader.setProgress(20, "Conectando à sua carteira…");
    }

    try {
      if (isPostLogin && window.SplashLoader) {
        window.SplashLoader.setProgress(45, "Carregando ativos e posições…");
      }
      // This authenticated read creates an empty portfolio on first login; the
      // following aggregate read is the single consistent financial snapshot.
      await request("/api/v1/assets");

      if (isPostLogin && window.SplashLoader) {
        window.SplashLoader.setProgress(70, "Consultando cotações e mercado…");
      }
      const result = await request("/api/v1/dashboard");
      if (version !== loadVersion || !window.AppAuth.hasSession()) {
        if (isPostLogin && window.SplashLoader) window.SplashLoader.close();
        return;
      }

      if (isPostLogin && window.SplashLoader) {
        window.SplashLoader.setProgress(90, "Consolidando métricas e alocação…");
      }

      const previousRevision = snapshot && snapshot.portfolio_revision;
      snapshot = result.body;
      applyColumnPreference(snapshot);
      renderStatus(snapshot);
      renderResumo(snapshot);
      renderAllocation(snapshot);
      if (previousRevision !== null && previousRevision !== undefined && previousRevision !== snapshot.portfolio_revision
        && window.Operations && typeof window.Operations.invalidate === "function") {
        window.Operations.invalidate(activeTab === "lancamentos" ? shell.panels.lancamentos : null);
      }
      if (status) status.textContent = "";

      if (isPostLogin && window.SplashLoader) {
        window.SplashLoader.finish();
      }

      runBackfill();
    } catch (error) {
      if (version !== loadVersion || !window.AppAuth.hasSession()) {
        if (isPostLogin && window.SplashLoader) window.SplashLoader.close();
        return;
      }
      if (isPostLogin && window.SplashLoader) {
        window.SplashLoader.error("Erro ao carregar a carteira.");
      }
      shell.panels.resumo.replaceChildren(element("p", "inline-error", error.message || "Não foi possível carregar a carteira."));
      if (status) status.textContent = "Não foi possível carregar os dados. Tente atualizar o painel.";
    } finally {
      if (version === loadVersion) root.classList.remove("is-loading");
    }
  }

  async function downloadExport(link) {
    const response = await window.AppAuth.fetch(link.href);
    if (!response.ok) throw new Error("Não foi possível gerar o arquivo CSV.");
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const download = element("a");
    download.href = objectUrl;
    download.download = link.href.split("/").pop() || "export.csv";
    document.body.append(download);
    download.click();
    download.remove();
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-authenticated-export]");
    if (!link) return;
    event.preventDefault();
    closePopover();
    downloadExport(link).catch((error) => {
      const status = document.getElementById("session-status");
      if (status) status.textContent = error.message || "Falha ao exportar o arquivo.";
    });
  });

  function reset() {
    loadVersion += 1;
    snapshot = null;
    shell = null;
    activeTab = "resumo";
    backfillStarted = false;
    closePopover();
    if (chartObserver) chartObserver.disconnect();
    chartObserver = null;
    if (window.SplashLoader && typeof window.SplashLoader.close === "function") {
      window.SplashLoader.close();
    }
  }

  document.addEventListener("auth:authenticated", () => {
    load({ isPostLogin: true });
  });
  document.addEventListener("auth:signed-out", () => { reset(); root.replaceChildren(); });
  document.addEventListener("auth:expired", reset);

  window.Portfolio = Object.freeze({
    load,
    showTab,
    revision: () => (snapshot ? snapshot.portfolio_revision : null),
    clear: () => { reset(); root.replaceChildren(); },
    exportMenu: (btnClass) => exportMenu(btnClass),
  });
  window.AppUI = Object.freeze({
    element, request, formatMoney, formatPrice, formatDate, formatPercent, formatNumber, makeTable, section, button,
  });
})();
