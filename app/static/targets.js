(() => {
  "use strict";

  let assets = [];
  let targets = [];
  let settings = null;
  let mappings = [];
  let active = false;
  let openPopover = null;
  let editDialog = null;
  let createDialog = null;
  let proximityDialog = null;
  let deleteDialog = null;
  let targetSort = { key: "asset", dir: "asc" };
  let targetsCollapsed = false;

  const idempotencyKey = () => {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  };

  function node(tag, className, text) {
    return window.AppUI.element(tag, className, text);
  }

  function field(labelText, control) {
    const wrapper = node("label", "field");
    wrapper.append(node("span", "field-label", labelText), control);
    return wrapper;
  }

  function input(type, name, value, placeholder) {
    const control = node("input", "form-control");
    control.type = type;
    control.name = name;
    if (value !== undefined && value !== null) control.value = value;
    if (placeholder) control.placeholder = placeholder;
    if (type === "number") control.step = "any";
    if (name === "price_usd" || name === "proximity_percent") control.inputMode = "decimal";
    return control;
  }

  function select(name, options) {
    const control = node("select", "form-control");
    control.name = name;
    options.forEach(([value, label]) => {
      const option = node("option", "", label);
      option.value = value;
      control.append(option);
    });
    return control;
  }

  function button(label, className = "btn btn-primary") {
    const control = node("button", className, label);
    control.type = "submit";
    return control;
  }

  function statusLine(form, message, isError = false) {
    const status = form.querySelector("[data-form-status]");
    if (!status) return;
    status.textContent = message;
    status.classList.toggle("form-error", isError);
    status.classList.toggle("form-success", Boolean(message) && !isError);
    status.hidden = !message;
  }

  function normalizeDecimal(value) {
    return String(value || "").trim().replace(/\s/g, "").replace(",", ".");
  }

  function selectAssetOptions(includeUsdt = true) {
    return assets.filter((asset) => asset.active && (includeUsdt || asset.symbol.toUpperCase() !== "USDT"));
  }

  function assetSelect(name, includeUsdt = true) {
    const choices = selectAssetOptions(includeUsdt);
    const control = select(name, choices.map((asset) => [asset.id, `${asset.symbol} · ${asset.name}`]));
    if (!choices.length) control.disabled = true;
    return control;
  }

  function assetOf(target) {
    return assets.find((item) => item.id === target.asset_id) || null;
  }

  function formatPrice(value) {
    const number = Number(String(value).replace(",", "."));
    if (!Number.isFinite(number)) return "—";
    const digits = Math.abs(number) >= 1 ? 2 : 6;
    return number.toLocaleString("pt-BR", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: digits });
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
    const popover = node("div", "popover");
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
    const list = node("div", "menu-list");
    items.forEach(([label, action, className]) => {
      const item = node("button", `menu-item${className ? ` ${className}` : ""}`, label);
      item.type = "button";
      item.setAttribute("role", "menuitem");
      item.addEventListener("click", () => { closePopover(); action(); });
      list.append(item);
    });
    return list;
  }

  function sortedTargets() {
    const factor = targetSort.dir === "asc" ? 1 : -1;
    return [...targets].sort((left, right) => {
      const assetLeft = assetOf(left);
      const assetRight = assetOf(right);
      const value = (target) => {
        const asset = assetOf(target);
        if (targetSort.key === "kind") return target.kind === "buy" ? "Compra" : "Venda";
        if (targetSort.key === "price") return Number(target.price_usd);
        if (targetSort.key === "active") return target.active ? 1 : 0;
        return asset ? asset.symbol : "";
      };
      const a = value(left);
      const b = value(right);
      if (typeof a === "string") return a.localeCompare(b, "pt-BR") * factor || (assetLeft ? assetLeft.symbol : "").localeCompare(assetRight ? assetRight.symbol : "");
      return (a - b) * factor;
    });
  }

  function ensureEditDialog() {
    if (editDialog) return editDialog;
    const dialog = node("dialog", "modal");
    dialog.setAttribute("aria-labelledby", "target-dialog-title");
    const form = node("form", "modal-form");
    form.dataset.form = "update-target";
    form.method = "dialog";
    const head = node("div", "modal-head");
    const title = node("h2", "section-title", "Editar alvo");
    title.id = "target-dialog-title";
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => dialog.close());
    head.append(title, close);
    const kind = input("hidden", "kind", "buy");
    const price = input("text", "price_usd", "");
    price.required = true;
    const orientation = input("text", "orientation", "", "Orientação opcional");
    const enabled = input("checkbox", "active");
    const enabledLabel = node("label", "checkbox-field");
    enabledLabel.append(enabled, node("span", "", "Alvo ativo"));
    const actions = node("div", "modal-actions");
    const deleteBtn = node("button", "btn btn-outline btn-danger", "Excluir alvo");
    deleteBtn.type = "button";
    deleteBtn.addEventListener("click", () => {
      const currentTarget = targets.find((item) => item.id === form.dataset.targetId);
      if (currentTarget) {
        dialog.close();
        openDelete(currentTarget);
      }
    });
    actions.append(deleteBtn, button("Salvar alterações", "btn btn-primary"));
    form.append(
      head,
      node("p", "muted target-dialog-asset", ""),
      kind,
      field("Preço alvo em USD", price),
      field("Orientação", orientation),
      enabledLabel,
      actions,
      node("p", "form-status", ""),
    );
    form.lastElementChild.dataset.formStatus = "true";
    form.lastElementChild.hidden = true;
    dialog.append(form);
    document.body.append(dialog);
    editDialog = dialog;
    return dialog;
  }

  function openEdit(target) {
    const dialog = ensureEditDialog();
    const form = dialog.querySelector("form");
    const asset = assetOf(target);
    form.dataset.targetId = target.id;
    form.dataset.version = String(target.version);
    dialog.querySelector(".target-dialog-asset").textContent = asset ? `${asset.symbol} · ${asset.name}` : "Ativo";
    form.elements.kind.value = target.kind;
    form.elements.price_usd.value = target.price_usd;
    form.elements.orientation.value = target.orientation || "";
    form.elements.active.checked = target.active;
    statusLine(form, "");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  async function setActive(target, nextActive) {
    await window.AppUI.request(`/api/v1/price-targets/${target.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "If-Match": String(target.version),
        "Idempotency-Key": idempotencyKey(),
      },
      body: JSON.stringify({
        kind: target.kind,
        price_usd: target.price_usd,
        orientation: target.orientation || null,
        active: nextActive,
      }),
    });
    await load();
    document.dispatchEvent(new Event("monitoring:configuration-changed"));
    if (window.Portfolio && typeof window.Portfolio.load === "function") window.Portfolio.load();
  }

  function ensureDeleteDialog() {
    if (deleteDialog) return deleteDialog;
    const dialog = node("dialog", "modal");
    dialog.setAttribute("aria-labelledby", "target-delete-title");
    const form = node("form", "modal-form");
    form.method = "dialog";
    const head = node("div", "modal-head");
    const title = node("h2", "section-title", "Excluir alvo");
    title.id = "target-delete-title";
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => dialog.close());
    head.append(title, close);

    const message = node("p", "target-delete-message", "");
    const warning = node("p", "muted", "Esta ação remove o alvo do monitoramento e não pode ser desfeita.");

    const actions = node("div", "modal-actions");
    const cancelBtn = node("button", "btn btn-outline", "Cancelar");
    cancelBtn.type = "button";
    cancelBtn.addEventListener("click", () => dialog.close());

    const confirmBtn = node("button", "btn btn-danger", "Excluir alvo");
    confirmBtn.type = "button";
    confirmBtn.dataset.confirmDelete = "true";
    confirmBtn.addEventListener("click", async () => {
      const targetId = dialog.dataset.targetId;
      const version = dialog.dataset.version;
      if (!targetId) return;
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;
      statusLine(form, "Excluindo alvo…");
      try {
        await deleteTarget(targetId, version);
        dialog.close();
      } catch (error) {
        statusLine(form, error.message || "Não foi possível excluir o alvo.", true);
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      }
    });

    actions.append(cancelBtn, confirmBtn);

    const status = node("p", "form-status", "");
    status.dataset.formStatus = "true";
    status.hidden = true;

    form.append(head, message, warning, actions, status);
    dialog.append(form);
    document.body.append(dialog);
    deleteDialog = dialog;
    return dialog;
  }

  function openDelete(target) {
    const dialog = ensureDeleteDialog();
    const form = dialog.querySelector("form");
    const asset = assetOf(target);
    const assetName = asset ? `${asset.symbol} · ${asset.name}` : "este ativo";
    dialog.dataset.targetId = target.id;
    dialog.dataset.version = String(target.version);

    const message = dialog.querySelector(".target-delete-message");
    if (message) {
      message.textContent = `Deseja realmente excluir o alvo de ${assetName} (${formatPrice(target.price_usd)})?`;
    }

    const confirmBtn = dialog.querySelector('[data-confirm-delete="true"]');
    if (confirmBtn) confirmBtn.disabled = false;
    const cancelBtn = dialog.querySelector(".btn-outline");
    if (cancelBtn) cancelBtn.disabled = false;

    statusLine(form, "");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  async function deleteTarget(targetId, version) {
    await window.AppUI.request(`/api/v1/price-targets/${targetId}`, {
      method: "DELETE",
      headers: {
        "If-Match": String(version),
        "Idempotency-Key": idempotencyKey(),
      },
    });
    await load();
    document.dispatchEvent(new Event("monitoring:configuration-changed"));
    if (window.Portfolio && typeof window.Portfolio.load === "function") window.Portfolio.load();
  }

  const NEW_ASSET = "__new__";

  function ensureCreateDialog() {
    if (createDialog) return createDialog;
    const dialog = node("dialog", "modal");
    dialog.setAttribute("aria-labelledby", "target-create-title");
    const form = node("form", "modal-form");
    form.method = "dialog";
    const head = node("div", "modal-head");
    const title = node("h2", "section-title", "Adicionar alvo");
    title.id = "target-create-title";
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => dialog.close());
    head.append(title, close);

    const assetControl = select("asset_id", []);
    assetControl.required = true;
    const symbol = input("text", "symbol", "", "Ex.: DOGE");
    symbol.autocomplete = "off";
    const name = input("text", "name", "", "Ex.: Dogecoin");
    const newAsset = node("div", "form-grid");
    newAsset.dataset.newAssetFields = "true";
    newAsset.append(field("Símbolo", symbol), field("Nome", name));
    const price = input("text", "price_usd", "", "Ex.: 95000,00");
    price.required = true;
    const orientation = input("text", "orientation", "", "Orientação opcional");
    const enabled = input("checkbox", "active");
    enabled.checked = true;
    const enabledLabel = node("label", "checkbox-field");
    enabledLabel.append(enabled, node("span", "", "Alvo ativo"));
    const grid = node("div", "form-grid");
    grid.append(field("Ativo", assetControl), field("Preço alvo em USD", price), field("Orientação", orientation));
    const status = node("p", "form-status", "");
    status.dataset.formStatus = "true";
    status.hidden = true;
    const actions = node("div", "modal-actions");
    const cancel = node("button", "btn btn-ghost", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", () => dialog.close());
    actions.append(cancel, button("Salvar alvo", "btn btn-primary"));
    form.append(head, grid, newAsset, enabledLabel, status, actions);

    const syncNewAsset = () => {
      const creating = assetControl.value === NEW_ASSET;
      newAsset.hidden = !creating;
      symbol.required = creating;
      name.required = creating;
    };
    assetControl.addEventListener("change", syncNewAsset);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submitCreate(form);
    });
    dialog.syncNewAsset = syncNewAsset;
    dialog.append(form);
    document.body.append(dialog);
    createDialog = dialog;
    return dialog;
  }

  function openCreate() {
    const dialog = ensureCreateDialog();
    const form = dialog.querySelector("form");
    form.reset();
    const withTarget = new Set(targets.map((target) => target.asset_id));
    const choices = selectAssetOptions(false)
      .sort((left, right) => Number(withTarget.has(left.id)) - Number(withTarget.has(right.id)) || left.symbol.localeCompare(right.symbol));
    const control = form.elements.asset_id;
    control.replaceChildren();
    choices.forEach((asset) => {
      const option = node("option", "", `${asset.symbol} · ${asset.name}${withTarget.has(asset.id) ? " (já tem alvo)" : ""}`);
      option.value = asset.id;
      control.append(option);
    });
    const createOption = node("option", "", "+ Novo ativo");
    createOption.value = NEW_ASSET;
    control.append(createOption);
    control.value = choices.length ? choices[0].id : NEW_ASSET;
    form.elements.active.checked = true;
    dialog.syncNewAsset();
    statusLine(form, "");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  async function submitCreate(form) {
    if (form.dataset.saving === "true") return;
    form.dataset.saving = "true";
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    const values = formValues(form);
    try {
      let assetId = values.asset_id;
      if (assetId === NEW_ASSET) {
        const symbol = String(values.symbol || "").trim().toUpperCase();
        const name = String(values.name || "").trim();
        if (!/^[A-Z0-9]{1,15}$/.test(symbol)) throw new Error("Informe um símbolo com até 15 letras ou números.");
        if (!name) throw new Error("Informe o nome do ativo.");
        statusLine(form, "Cadastrando ativo…");
        const { body } = await window.AppUI.request("/api/v1/assets", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ external_id: symbol.toLowerCase(), symbol, name }),
        });
        assetId = body.asset.id;
      }
      statusLine(form, "Salvando alvo…");
      await window.AppUI.request("/api/v1/price-targets", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey() },
        body: JSON.stringify({
          asset_id: assetId,
          kind: "buy",
          price_usd: normalizeDecimal(values.price_usd),
          orientation: values.orientation || null,
          active: values.active === "on",
        }),
      });
      createDialog.close();
      await load();
      document.dispatchEvent(new Event("monitoring:configuration-changed"));
      if (window.Portfolio && typeof window.Portfolio.load === "function") window.Portfolio.load();
    } catch (error) {
      statusLine(form, error.message || "Não foi possível salvar o alvo.", true);
    } finally {
      form.dataset.saving = "false";
      if (submitButton) submitButton.disabled = false;
    }
  }

  function renderTargets(container) {
    const columns = [
      ["asset", "Ativo"],
      ["price", "Preço alvo"],
      ["orientation", "Orientação"],
      ["active", "Situação"],
    ];
    const wrapper = node("div", "asset-table-wrap");
    const table = node("table", "asset-table");
    const head = node("tr");
    columns.forEach(([key, label]) => {
      const th = node("th");
      th.dataset.column = key;
      const sorting = targetSort.key === key;
      const control = node("button", `sort-button${sorting ? " is-active" : ""}`, `${label} ${sorting ? (targetSort.dir === "asc" ? "↑" : "↓") : "⇅"}`);
      control.type = "button";
      control.addEventListener("click", () => {
        targetSort = { key, dir: sorting && targetSort.dir === "asc" ? "desc" : "asc" };
        render();
      });
      th.append(control);
      head.append(th);
    });
    const optionsHead = node("th", "", "Opções");
    optionsHead.dataset.column = "options";
    head.append(optionsHead);
    const thead = node("thead");
    thead.append(head);
    const tbody = node("tbody");
    if (!targets.length) {
      const empty = node("tr");
      const cell = node("td", "muted", "Nenhum alvo cadastrado.");
      cell.colSpan = 5;
      empty.append(cell);
      tbody.append(empty);
    }
    sortedTargets().forEach((target) => {
      const asset = assetOf(target);
      const row = node("tr");
      const cells = [
        ["asset", asset ? `${asset.symbol} · ${asset.name}` : "Ativo"],
        ["price", formatPrice(target.price_usd)],
        ["orientation", target.orientation || "—"],
        ["active", target.active ? "Ativo" : "Inativo"],
      ];
      cells.forEach(([key, text]) => {
        const cell = node("td");
        if (key === "asset") cell.append(targetAssetCell(asset));
        else if (key === "active") cell.append(node("span", `badge ${target.active ? "badge-up" : "badge-muted"}`, text));
        else cell.textContent = text;
        cell.dataset.column = key;
        cell.dataset.label = columns.find(([column]) => column === key)[1];
        row.append(cell);
      });
      const options = node("td");
      options.dataset.column = "options";
      const trigger = node("button", "icon-button", "⋯");
      trigger.type = "button";
      trigger.setAttribute("aria-label", `Opções de ${asset ? asset.symbol : "alvo"}`);
      trigger.setAttribute("aria-haspopup", "menu");
      trigger.addEventListener("click", () => showPopover(trigger, menuList([
        ["Editar", () => openEdit(target)],
        [target.active ? "Desativar" : "Ativar", () => setActive(target, !target.active).catch((error) => {
          const status = container.querySelector("[data-targets-status]");
          if (status) {
            status.hidden = false;
            status.textContent = error.message || "Não foi possível atualizar o alvo.";
            status.classList.add("form-error");
          }
        })],
        ["Excluir", () => openDelete(target), "menu-item-danger"],
      ])));
      options.append(trigger);
      row.append(options);
      tbody.append(row);
    });
    table.append(thead, tbody);
    wrapper.append(table);
    const status = node("p", "form-status", "");
    status.dataset.targetsStatus = "true";
    status.hidden = true;
    const addButton = node("button", "btn btn-outline btn-small", "+ Adicionar alvo");
    addButton.type = "button";
    addButton.addEventListener("click", openCreate);
    const aiButton = node("button", "btn btn-outline btn-small", "Atualizar alvos com IA");
    aiButton.type = "button";
    aiButton.addEventListener("click", () => {
      if (window.AiImport) window.AiImport.openTargets();
    });
    const proximityButton = node("button", "btn btn-ghost btn-small", "Editar faixa de proximidade");
    proximityButton.type = "button";
    proximityButton.addEventListener("click", openProximity);

    const activeCount = targets.filter((target) => target.active).length;
    const group = node("section", "card asset-group");
    const header = node("div", "group-header");
    const title = node("div", "group-title");
    title.append(node("span", "group-icon", "◈"), node("h3", "", "Alvos de compra"));
    const stats = node("div", "group-stats");
    stats.append(
      targetStat("Alvos", String(targets.length)),
      targetStat("Ativos", String(activeCount)),
    );
    const toggle = node("button", "icon-button group-toggle", targetsCollapsed ? "▾" : "▴");
    toggle.type = "button";
    toggle.setAttribute("aria-label", targetsCollapsed ? "Expandir alvos" : "Recolher alvos");
    toggle.setAttribute("aria-expanded", String(!targetsCollapsed));
    const body = node("div", "group-body");
    body.hidden = targetsCollapsed;
    const footer = node("div", "group-footer");
    footer.append(proximityButton, aiButton, addButton);
    body.append(wrapper, status, footer);
    toggle.addEventListener("click", () => {
      targetsCollapsed = !targetsCollapsed;
      body.hidden = targetsCollapsed;
      toggle.textContent = targetsCollapsed ? "▾" : "▴";
      toggle.setAttribute("aria-expanded", String(!targetsCollapsed));
      toggle.setAttribute("aria-label", targetsCollapsed ? "Expandir alvos" : "Recolher alvos");
    });
    header.append(title, stats, toggle);
    group.append(header, body);
    container.append(group);
  }

  function targetStat(label, value) {
    const stat = node("div", "group-stat");
    stat.append(node("span", "group-stat-label", label), node("strong", "", value));
    return stat;
  }

  function targetAssetCell(asset) {
    const symbol = asset ? asset.symbol : "?";
    const cell = node("div", "asset-cell");
    const wrap = node("span", "asset-icon");
    const img = node("img", "asset-logo");
    img.alt = "";
    img.src = `/static/icons/${encodeURIComponent(symbol)}.svg`;
    img.addEventListener("error", () => {
      img.remove();
      wrap.textContent = symbol.slice(0, 4);
    });
    wrap.append(img);
    const text = node("div", "asset-text");
    text.append(node("strong", "", symbol), node("span", "muted", asset ? asset.name : "Ativo"));
    cell.append(wrap, text);
    return cell;
  }

  function ensureProximityDialog() {
    if (proximityDialog) return proximityDialog;
    const dialog = node("dialog", "modal");
    dialog.setAttribute("aria-labelledby", "proximity-dialog-title");
    const form = node("form", "modal-form");
    form.dataset.form = "settings";
    form.method = "dialog";
    const head = node("div", "modal-head");
    const title = node("h2", "section-title", "Faixa de proximidade");
    title.id = "proximity-dialog-title";
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => dialog.close());
    head.append(title, close);
    const value = input("text", "proximity_percent", "", "0 a 100");
    value.required = true;
    const actions = node("div", "modal-actions");
    const cancel = node("button", "btn btn-ghost", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", () => dialog.close());
    actions.append(cancel, button("Salvar limite", "btn btn-primary"));
    form.append(
      head,
      field("Faixa de proximidade (%)", value),
      node("p", "muted", "De 0 a 100. O alerta de compra continua dependendo só do preço alvo."),
      actions,
      node("p", "form-status", ""),
    );
    form.lastElementChild.dataset.formStatus = "true";
    form.lastElementChild.hidden = true;
    dialog.append(form);
    document.body.append(dialog);
    proximityDialog = dialog;
    return dialog;
  }

  function openProximity() {
    const dialog = ensureProximityDialog();
    const form = dialog.querySelector("form");
    form.dataset.version = String(settings ? settings.version : 1);
    form.elements.proximity_percent.value = settings ? settings.proximity_percent : "10.00";
    statusLine(form, "");
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
    form.elements.proximity_percent.focus();
  }

  function render() {
    closePopover();
    const panel = document.getElementById("targets-panel");
    if (!panel) return;
    panel.replaceChildren();
    renderTargets(panel);
    if (window.Monitoring && typeof window.Monitoring.renderReadLog === "function") {
      window.Monitoring.renderReadLog();
    }
  }

  async function load() {
    if (!window.AppAuth || !window.AppAuth.hasSession()) return;
    active = true;
    const [assetResult, targetResult, settingsResult, mappingsResult] = await Promise.all([
      window.AppUI.request("/api/v1/assets"),
      window.AppUI.request("/api/v1/price-targets?limit=100"),
      window.AppUI.request("/api/v1/monitoring/settings"),
      window.AppUI.request("/api/v1/monitoring/mappings"),
    ]);
    if (!active || !window.AppAuth.hasSession()) return;
    assets = assetResult.body.items || [];
    targets = targetResult.body.items || [];
    settings = settingsResult.body;
    mappings = mappingsResult.body;
    render();
  }

  function formValues(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  async function submit(form) {
    if (form.dataset.saving === "true") return;
    form.dataset.saving = "true";
    const submitButton = form.querySelector('button[type="submit"]');
    if (submitButton) submitButton.disabled = true;
    const kind = form.dataset.form;
    const targetId = form.dataset.targetId;
    const assetId = form.dataset.assetId;
    const values = formValues(form);
    statusLine(form, "Salvando…");
    try {
      if (kind === "update-target") {
        await window.AppUI.request(`/api/v1/price-targets/${form.dataset.targetId}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "If-Match": form.dataset.version,
            "Idempotency-Key": idempotencyKey(),
          },
          body: JSON.stringify({
            kind: values.kind,
            price_usd: normalizeDecimal(values.price_usd),
            orientation: values.orientation || null,
            active: values.active === "on",
          }),
        });
      } else if (kind === "settings") {
        await window.AppUI.request("/api/v1/monitoring/settings", {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "If-Match": form.dataset.version,
            "Idempotency-Key": idempotencyKey(),
          },
          body: JSON.stringify({ proximity_percent: normalizeDecimal(values.proximity_percent) }),
        });
      } else if (kind === "mapping") {
        await window.AppUI.request(`/api/v1/monitoring/mappings/${form.dataset.assetId}`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "If-Match": form.dataset.version,
            "Idempotency-Key": idempotencyKey(),
          },
          body: JSON.stringify({ provider_coin_id: values.provider_coin_id }),
        });
      }
      await load();
      document.dispatchEvent(new Event("monitoring:configuration-changed"));
      if (kind === "update-target" && editDialog && editDialog.open) editDialog.close();
      if (kind === "settings" && proximityDialog && proximityDialog.open) proximityDialog.close();
      const refreshedForm = kind === "mapping"
        ? [...document.querySelectorAll('[data-form="mapping"]')].find((item) => item.dataset.assetId === assetId)
        : kind === "update-target"
          ? [...document.querySelectorAll('[data-form="update-target"]')].find((item) => item.dataset.targetId === targetId)
          : document.querySelector(`[data-form="${kind}"]`);
      if (refreshedForm) statusLine(refreshedForm, "Alterações salvas.");
    } catch (error) {
      let messageForm = form;
      if (error.status === 409) {
        try {
          await load();
          messageForm = kind === "mapping"
            ? [...document.querySelectorAll('[data-form="mapping"]')].find((item) => item.dataset.assetId === assetId)
            : kind === "update-target"
              ? [...document.querySelectorAll('[data-form="update-target"]')].find((item) => item.dataset.targetId === targetId)
              : document.querySelector(`[data-form="${kind}"]`);
        } catch (_reloadError) { /* Keep the conflict visible on the current form. */ }
      }
      if (messageForm && messageForm.isConnected) statusLine(messageForm, error.message || "Não foi possível salvar as alterações.", true);
    } finally {
      form.dataset.saving = "false";
      if (form.isConnected && submitButton) submitButton.disabled = false;
    }
  }

  document.addEventListener("click", (event) => {
    if (!openPopover) return;
    if (openPopover.contains(event.target)) return;
    if (event.target.closest(`[data-popover-id="${openPopover.dataset.owner}"]`)) return;
    closePopover();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closePopover(); });

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.dataset.form) return;
    event.preventDefault();
    submit(form);
  });

  document.addEventListener("auth:signed-out", () => {
    active = false;
    closePopover();
    if (editDialog && editDialog.open) editDialog.close();
    if (createDialog && createDialog.open) createDialog.close();
    if (proximityDialog && proximityDialog.open) proximityDialog.close();
    if (deleteDialog && deleteDialog.open) deleteDialog.close();
    assets = [];
    targets = [];
    settings = null;
    mappings = [];
  });
  document.addEventListener("auth:expired", () => {
    active = false;
    assets = [];
    targets = [];
    settings = null;
    mappings = [];
  });

  window.Targets = Object.freeze({ init: () => load().catch((error) => {
    const panel = document.getElementById("targets-panel");
    if (panel) panel.append(node("p", "inline-error", error.message || "Não foi possível carregar os alvos."));
  }), clear: () => { active = false; assets = []; targets = []; settings = null; mappings = []; } });
})();
