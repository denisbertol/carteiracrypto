(() => {
  "use strict";

  const KINDS = [
    ["buy", "Compra"],
    ["sell", "Venda"],
    ["deposit", "Depósito"],
    ["withdrawal", "Saque"],
    ["transfer", "Transferência"],
    ["fee", "Taxa avulsa"],
  ];
  const KIND_LABELS = Object.fromEntries(KINDS);
  const USDT_ONLY = new Set(["deposit", "withdrawal", "fee"]);
  const TRADES = new Set(["buy", "sell"]);

  let items = null;
  let filter = "";
  let loading = null;
  let dialog = null;
  let assets = [];
  let idempotencyKey = null;
  let editingOperation = null;

  const ui = () => window.AppUI;

  function newKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function normalizeDecimal(value) {
    return String(value || "").trim().replace(/\s/g, "").replace(/\.(?=.*[.,])/g, "").replace(",", ".");
  }

  function localDateTimeValue(date) {
    const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return shifted.toISOString().slice(0, 16);
  }

  function render(panel) {
    const { element, button } = ui();
    const card = element("section", "card section-card");
    const head = element("div", "panel-head");
    const heading = element("div", "section-heading");
    heading.append(element("h2", "section-title", "Lançamentos"), element("p", "muted", "Operações mais recentes primeiro (até 100)."));
    const tools = element("div", "panel-tools");
    const symbols = [...new Set((items || []).map((item) => item.symbol))].sort();
    const select = element("select", "form-control form-control-small");
    select.setAttribute("aria-label", "Filtrar por ativo");
    [["", "Todos os ativos"], ...symbols.map((symbol) => [symbol, symbol])].forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      select.append(option);
    });
    if (filter && !symbols.includes(filter)) {
      const option = element("option", "", filter);
      option.value = filter;
      select.append(option);
    }
    select.value = filter;
    select.addEventListener("change", () => { filter = select.value; render(panel); });
    const addOperation = button("+ Adicionar lançamento", "btn btn-primary btn-small", () => openForm(filter || undefined));
    const aiOperation = button("Incluir com IA", "btn btn-outline btn-small", () => {
      if (window.AiImport) window.AiImport.openOperations();
    });
    const exportBtn = window.Portfolio && typeof window.Portfolio.exportMenu === "function"
      ? window.Portfolio.exportMenu("btn btn-outline btn-small")
      : null;
    tools.append(select, ...(exportBtn ? [exportBtn] : []), aiOperation, addOperation);
    head.append(heading, tools);
    card.append(head);

    if (items === null) {
      card.append(element("p", "muted", "Carregando lançamentos…"));
    } else {
      const visible = items.filter((item) => !filter || item.symbol === filter);
      card.append(ui().makeTable(
        ["Data", "Tipo", "Ativo", "Quantidade", "Preço (USD)", "Taxa (USDT)", "Observação", "Ações"],
        visible.map((item) => {
          const editBtn = button("Editar", "btn btn-ghost btn-small", () => openEditForm(item));
          editBtn.setAttribute("aria-label", `Editar lançamento de ${item.symbol}`);
          return [
            ui().formatDate(item.occurred_at),
            element("span", `kind-tag kind-${item.kind}`, KIND_LABELS[item.kind] || item.kind),
            element("strong", "", item.symbol),
            ui().formatNumber(item.quantity),
            item.unit_price_usd ? ui().formatPrice(item.unit_price_usd) : "—",
            Number(item.fee_usdt) ? ui().formatNumber(item.fee_usdt, 6) : "—",
            item.note || [item.source_label, item.destination_label].filter(Boolean).join(" → ") || "—",
            editBtn,
          ];
        }),
        filter ? `Nenhum lançamento de ${filter}.` : "Nenhum lançamento registrado.",
      ));
    }
    panel.replaceChildren(card);
  }

  async function show(panel) {
    if (items !== null) {
      render(panel);
      return;
    }
    render(panel);
    if (!loading) {
      loading = ui().request("/api/v1/operations?limit=100")
        .then(({ body }) => { items = body.items || []; })
        .finally(() => { loading = null; });
    }
    try {
      await loading;
      if (panel.isConnected) render(panel);
    } catch (error) {
      if (panel.isConnected) panel.replaceChildren(ui().element("p", "inline-error", error.message || "Não foi possível carregar os lançamentos."));
    }
  }

  function field(labelText, control, name) {
    const wrapper = ui().element("label", "field");
    if (name) wrapper.dataset.field = name;
    wrapper.append(ui().element("span", "field-label", labelText), control);
    return wrapper;
  }

  function input(name, type = "text", placeholder = "") {
    const control = ui().element("input", "form-control");
    control.name = name;
    control.type = type;
    if (placeholder) control.placeholder = placeholder;
    if (type === "text" && !["note", "source_label", "destination_label", "symbol", "name", "external_id"].includes(name)) {
      control.inputMode = "decimal";
      control.autocomplete = "off";
    }
    return control;
  }

  function setStatus(form, message, isError) {
    const status = form.querySelector("[data-form-status]");
    status.textContent = message || "";
    status.hidden = !message;
    status.classList.toggle("form-error", Boolean(isError));
    status.classList.toggle("form-success", Boolean(message) && !isError);
  }

  function syncFields(form) {
    const kind = form.elements.kind.value;
    const assetSelect = form.elements.asset_id;
    const previous = assetSelect.value;
    const choices = assets.filter((asset) => asset.active && (
      USDT_ONLY.has(kind) ? asset.symbol === "USDT" : TRADES.has(kind) ? asset.symbol !== "USDT" : true
    ));
    assetSelect.replaceChildren(...choices.map((asset) => {
      const option = ui().element("option", "", `${asset.symbol} · ${asset.name}`);
      option.value = asset.id;
      return option;
    }));
    if (choices.some((asset) => asset.id === previous)) assetSelect.value = previous;
    assetSelect.disabled = USDT_ONLY.has(kind);
    form.querySelector('[data-field="unit_price_usd"]').hidden = !TRADES.has(kind);
    form.elements.unit_price_usd.required = TRADES.has(kind);
    form.querySelector('[data-field="fee_usdt"]').hidden = !(TRADES.has(kind) || kind === "transfer");
    form.querySelectorAll('[data-field="source_label"], [data-field="destination_label"]').forEach((node) => {
      node.hidden = kind !== "transfer";
    });
    form.querySelector('[data-field="quantity"] .field-label').textContent = USDT_ONLY.has(kind) ? "Valor (USDT)" : "Quantidade";
    form.querySelector("[data-new-asset]").hidden = !TRADES.has(kind) && kind !== "transfer";
    const empty = !choices.length;
    form.querySelector("[data-empty-assets]").hidden = !empty;
  }

  function buildDialog() {
    const { element, button } = ui();
    const node = element("dialog", "modal");
    node.setAttribute("aria-labelledby", "operation-dialog-title");
    const form = element("form", "modal-form");
    form.method = "dialog";
    const head = element("div", "modal-head");
    const title = element("h2", "section-title", "Adicionar lançamento");
    title.id = "operation-dialog-title";
    const close = button("✕", "icon-button", () => node.close());
    close.setAttribute("aria-label", "Fechar");
    head.append(title, close);

    const kind = element("select", "form-control");
    kind.name = "kind";
    KINDS.forEach(([value, label]) => {
      const option = element("option", "", label);
      option.value = value;
      kind.append(option);
    });
    const asset = element("select", "form-control");
    asset.name = "asset_id";
    const occurredAt = input("occurred_at", "datetime-local");
    occurredAt.required = true;
    const quantity = input("quantity", "text", "0,00");
    quantity.required = true;
    const price = input("unit_price_usd", "text", "0,00");
    const fee = input("fee_usdt", "text", "0");
    const source = input("source_label", "text", "Ex.: Binance");
    const destination = input("destination_label", "text", "Ex.: Ledger");
    const note = input("note", "text", "Opcional");

    const grid = element("div", "form-grid");
    grid.append(
      field("Tipo", kind),
      field("Ativo", asset),
      field("Data e hora", occurredAt),
      field("Quantidade", quantity, "quantity"),
      field("Preço unitário (USD)", price, "unit_price_usd"),
      field("Taxa (USDT)", fee, "fee_usdt"),
      field("Origem", source, "source_label"),
      field("Destino", destination, "destination_label"),
    );
    const noteField = field("Observação", note);
    noteField.classList.add("field-wide");
    grid.append(noteField);

    const emptyAssets = element("p", "inline-notice", "Nenhum ativo disponível para este tipo. Cadastre um ativo abaixo.");
    emptyAssets.dataset.emptyAssets = "true";
    emptyAssets.hidden = true;

    const newAsset = element("details", "new-asset");
    newAsset.dataset.newAsset = "true";
    newAsset.append(element("summary", "", "Cadastrar novo ativo"));
    const assetGrid = element("div", "form-grid");
    const symbol = input("symbol", "text", "Ex.: SOL");
    const name = input("name", "text", "Ex.: Solana");
    const externalId = input("external_id", "text", "Ex.: solana");
    assetGrid.append(field("Símbolo", symbol), field("Nome", name), field("ID na CoinGecko", externalId));
    const createAsset = button("Cadastrar ativo", "btn btn-ghost btn-small", () => submitAsset(form));
    newAsset.append(assetGrid, element("p", "muted", "Depois, confirme o mapeamento em Alvos e alertas › Cobertura de preços para receber cotações."), createAsset);

    const status = element("p", "form-status");
    status.dataset.formStatus = "true";
    status.hidden = true;
    const actions = element("div", "modal-actions");
    const deleteBtn = button("Excluir lançamento", "btn btn-ghost btn-small", () => confirmDelete(form));
    deleteBtn.type = "button";
    deleteBtn.dataset.deleteOperation = "true";
    deleteBtn.style.color = "var(--danger)";
    deleteBtn.style.marginRight = "auto";
    deleteBtn.hidden = true;
    const cancel = button("Cancelar", "btn btn-ghost", () => node.close());
    const submit = element("button", "btn btn-primary", "Salvar lançamento");
    submit.type = "submit";
    actions.append(deleteBtn, cancel, submit);

    form.append(head, grid, emptyAssets, newAsset, status, actions);
    node.append(form);
    kind.addEventListener("change", () => syncFields(form));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitOperation(form);
    });
    document.body.append(node);
    return node;
  }

  async function loadAssets() {
    const { body } = await ui().request("/api/v1/assets");
    assets = body.items || [];
  }

  async function openForm(symbol) {
    if (!window.AppAuth || !window.AppAuth.hasSession()) return;
    if (!dialog) dialog = buildDialog();
    editingOperation = null;
    const form = dialog.querySelector("form");
    form.reset();
    setStatus(form, "");
    idempotencyKey = newKey();
    dialog.querySelector("#operation-dialog-title").textContent = "Adicionar lançamento";
    form.querySelector('button[type="submit"]').textContent = "Salvar lançamento";
    const deleteBtn = form.querySelector('[data-delete-operation="true"]');
    if (deleteBtn) deleteBtn.hidden = true;
    const newAsset = form.querySelector("[data-new-asset]");
    if (newAsset) newAsset.hidden = false;

    form.elements.occurred_at.value = localDateTimeValue(new Date());
    try {
      await loadAssets();
    } catch (error) {
      setStatus(form, error.message || "Não foi possível carregar os ativos.", true);
    }
    const preset = assets.find((asset) => asset.symbol === symbol);
    form.elements.kind.value = preset && preset.symbol === "USDT" ? "deposit" : "buy";
    syncFields(form);
    if (preset && [...form.elements.asset_id.options].some((option) => option.value === preset.id)) {
      form.elements.asset_id.value = preset.id;
    }
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    form.elements.quantity.focus();
  }

  async function openEditForm(item) {
    if (!window.AppAuth || !window.AppAuth.hasSession()) return;
    if (!dialog) dialog = buildDialog();
    editingOperation = item;
    const form = dialog.querySelector("form");
    form.reset();
    setStatus(form, "");
    idempotencyKey = newKey();
    dialog.querySelector("#operation-dialog-title").textContent = `Editar lançamento (${item.symbol})`;
    form.querySelector('button[type="submit"]').textContent = "Salvar alterações";
    const deleteBtn = form.querySelector('[data-delete-operation="true"]');
    if (deleteBtn) deleteBtn.hidden = false;
    const newAsset = form.querySelector("[data-new-asset]");
    if (newAsset) newAsset.hidden = true;

    try {
      await loadAssets();
    } catch (error) {
      setStatus(form, error.message || "Não foi possível carregar os ativos.", true);
    }

    form.elements.kind.value = item.kind;
    syncFields(form);
    if ([...form.elements.asset_id.options].some((option) => option.value === item.asset_id)) {
      form.elements.asset_id.value = item.asset_id;
    }
    if (item.occurred_at) {
      const d = new Date(item.occurred_at);
      if (!Number.isNaN(d.getTime())) {
        form.elements.occurred_at.value = localDateTimeValue(d);
      }
    }
    form.elements.quantity.value = item.quantity || "";
    form.elements.unit_price_usd.value = item.unit_price_usd || "";
    form.elements.fee_usdt.value = item.fee_usdt !== null && item.fee_usdt !== undefined ? String(item.fee_usdt) : "0";
    form.elements.source_label.value = item.source_label || "";
    form.elements.destination_label.value = item.destination_label || "";
    form.elements.note.value = item.note || "";

    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    form.elements.quantity.focus();
  }

  async function submitAsset(form) {
    const values = {
      symbol: form.elements.symbol.value.trim().toUpperCase(),
      name: form.elements.name.value.trim(),
      external_id: form.elements.external_id.value.trim().toLowerCase(),
    };
    if (!values.symbol || !values.name || !values.external_id) {
      setStatus(form, "Preencha símbolo, nome e ID na CoinGecko para cadastrar o ativo.", true);
      return;
    }
    setStatus(form, "Cadastrando ativo…");
    try {
      const { body } = await ui().request("/api/v1/assets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      await loadAssets();
      syncFields(form);
      if (body && body.asset) form.elements.asset_id.value = body.asset.id;
      ["symbol", "name", "external_id"].forEach((name) => { form.elements[name].value = ""; });
      form.querySelector("[data-new-asset]").open = false;
      setStatus(form, `Ativo ${values.symbol} cadastrado.`);
    } catch (error) {
      setStatus(form, error.message || "Não foi possível cadastrar o ativo.", true);
    }
  }

  async function submitOperation(form) {
    if (form.dataset.saving === "true") return;
    const kind = form.elements.kind.value;
    const occurred = new Date(form.elements.occurred_at.value);
    if (Number.isNaN(occurred.getTime())) {
      setStatus(form, "Informe uma data válida.", true);
      return;
    }
    const assetId = USDT_ONLY.has(kind)
      ? (assets.find((asset) => asset.symbol === "USDT") || {}).id
      : form.elements.asset_id.value;
    if (!assetId) {
      setStatus(form, "Selecione um ativo.", true);
      return;
    }
    const payload = {
      kind,
      asset_id: assetId,
      occurred_at: occurred.toISOString(),
      quantity: normalizeDecimal(form.elements.quantity.value),
      fee_usdt: (TRADES.has(kind) || kind === "transfer") ? normalizeDecimal(form.elements.fee_usdt.value) || "0" : "0",
    };
    if (TRADES.has(kind)) payload.unit_price_usd = normalizeDecimal(form.elements.unit_price_usd.value);
    if (kind === "transfer") {
      payload.source_label = form.elements.source_label.value.trim() || null;
      payload.destination_label = form.elements.destination_label.value.trim() || null;
    }
    const note = form.elements.note.value.trim();
    if (note) payload.note = note;

    const headers = { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey };
    const revision = window.Portfolio && window.Portfolio.revision();
    if (revision !== null && revision !== undefined) headers["If-Match"] = String(revision);
    const submit = form.querySelector('button[type="submit"]');
    const deleteBtn = form.querySelector('[data-delete-operation="true"]');
    form.dataset.saving = "true";
    submit.disabled = true;
    if (deleteBtn) deleteBtn.disabled = true;
    setStatus(form, "Salvando…");

    const method = editingOperation ? "PATCH" : "POST";
    const endpoint = editingOperation ? `/api/v1/operations/${editingOperation.id}` : "/api/v1/operations";

    try {
      await ui().request(endpoint, { method, headers, body: JSON.stringify(payload) });
      idempotencyKey = newKey();
      items = null;
      editingOperation = null;
      dialog.close();
      if (window.Portfolio) await window.Portfolio.load();
      const panel = document.querySelector('[data-tab-panel="lancamentos"]');
      if (panel && !panel.hidden && items === null) await show(panel);
    } catch (error) {
      if (error.status === 409 && error.code === "REVISION_CONFLICT") {
        idempotencyKey = newKey();
        if (window.Portfolio) await window.Portfolio.load();
        setStatus(form, "A carteira mudou em outra sessão. Os dados foram atualizados; confira e salve novamente.", true);
      } else if (error.status === 422 || error.status === 409) {
        idempotencyKey = newKey();
        setStatus(form, error.message, true);
      } else {
        setStatus(form, error.message || "Não foi possível salvar o lançamento.", true);
      }
    } finally {
      form.dataset.saving = "false";
      submit.disabled = false;
      if (deleteBtn) deleteBtn.disabled = false;
    }
  }

  async function confirmDelete(form) {
    if (!editingOperation || form.dataset.saving === "true") return;
    const confirmed = window.confirm(
      `Deseja realmente excluir este lançamento de ${editingOperation.symbol}? O saldo e os resultados da carteira serão recalculados.`
    );
    if (!confirmed) return;

    const headers = { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey };
    const revision = window.Portfolio && window.Portfolio.revision();
    if (revision !== null && revision !== undefined) headers["If-Match"] = String(revision);

    const submit = form.querySelector('button[type="submit"]');
    const deleteBtn = form.querySelector('[data-delete-operation="true"]');
    form.dataset.saving = "true";
    submit.disabled = true;
    if (deleteBtn) deleteBtn.disabled = true;
    setStatus(form, "Excluindo…");

    try {
      await ui().request(`/api/v1/operations/${editingOperation.id}`, { method: "DELETE", headers });
      idempotencyKey = newKey();
      items = null;
      editingOperation = null;
      dialog.close();
      if (window.Portfolio) await window.Portfolio.load();
      const panel = document.querySelector('[data-tab-panel="lancamentos"]');
      if (panel && !panel.hidden && items === null) await show(panel);
    } catch (error) {
      idempotencyKey = newKey();
      setStatus(form, error.message || "Não foi possível excluir o lançamento.", true);
    } finally {
      form.dataset.saving = "false";
      submit.disabled = false;
      if (deleteBtn) deleteBtn.disabled = false;
    }
  }

  function invalidate(panel) {
    items = null;
    if (panel) show(panel);
  }

  function clear() {
    items = null;
    filter = "";
    assets = [];
    loading = null;
    editingOperation = null;
    if (dialog) {
      if (dialog.open) dialog.close();
      dialog.remove();
      dialog = null;
    }
  }

  document.addEventListener("auth:signed-out", clear);
  document.addEventListener("auth:expired", clear);

  window.Operations = Object.freeze({
    show,
    openForm,
    openEditForm,
    invalidate,
    clear,
    setFilter: (symbol) => { filter = symbol || ""; },
  });
})();
