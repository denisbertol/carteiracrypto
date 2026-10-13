(() => {
  "use strict";

  const MODES = {
    operations: {
      title: "Incluir lançamentos com IA",
      lead: "Cole um texto, uma tabela ou envie um CSV ou uma imagem da corretora. A leitura aparece para conferência e só entra na carteira se você confirmar.",
      path: "/api/v1/ai/operations/preview",
      confirm: (count) => `Incluir ${count} ${count === 1 ? "lançamento" : "lançamentos"}`,
    },
    targets: {
      title: "Atualizar alvos com IA",
      lead: "Cole um texto, uma tabela ou envie um CSV com os preços alvo. Os alvos de compra só mudam depois da confirmação.",
      path: "/api/v1/ai/targets/preview",
      confirm: (count) => `Atualizar ${count} ${count === 1 ? "alvo" : "alvos"}`,
    },
  };

  let settingsDialog = null;
  let importDialog = null;
  let proposal = null;
  let mode = "operations";

  const ui = () => window.AppUI;

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined && text !== null) element.textContent = String(text);
    return element;
  }

  function newKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function statusLine(form, message, isError) {
    const status = form.querySelector("[data-form-status]");
    status.hidden = !message;
    status.textContent = message || "";
    status.classList.toggle("form-error", Boolean(isError));
  }

  function closeDialog(dialog) {
    if (!dialog) return;
    if (dialog.open && typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function showDialog(dialog) {
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function ensureSettingsDialog() {
    if (settingsDialog) return settingsDialog;
    const dialog = node("dialog", "modal");
    const form = node("form", "modal-form");
    form.dataset.form = "ai-settings";
    const head = node("div", "modal-head");
    head.append(node("h2", "section-title", "Configuração da IA"));
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => closeDialog(dialog));
    head.append(close);
    const key = node("input", "form-control");
    key.name = "api_key";
    key.type = "password";
    key.autocomplete = "off";
    key.spellcheck = false;
    key.placeholder = "Cole uma nova chave para substituir";
    const model = node("input", "form-control");
    model.name = "model";
    model.type = "text";
    model.autocomplete = "off";
    model.required = true;
    model.spellcheck = false;
    const hint = node("p", "muted");
    hint.dataset.aiHint = "true";
    const help = node("p", "muted");
    help.append(document.createTextNode("A chave fica no servidor e não volta para o navegador. Crie uma em "));
    const link = node("a", "", "Google AI Studio");
    link.href = "https://aistudio.google.com/apikey";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    help.append(link, document.createTextNode("."));
    const clearLabel = node("label", "checkbox-field");
    const clear = node("input");
    clear.type = "checkbox";
    clear.name = "clear_key";
    clearLabel.append(clear, document.createTextNode("Remover a chave salva"));
    const actions = node("div", "modal-actions");
    const cancel = node("button", "btn btn-ghost", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", () => closeDialog(dialog));
    const test = node("button", "btn btn-outline", "Testar conexão");
    test.type = "button";
    test.addEventListener("click", () => testSettings(form));
    actions.append(cancel, test, node("button", "btn btn-primary", "Salvar"));
    const status = node("p", "form-status", "");
    status.dataset.formStatus = "true";
    status.hidden = true;
    form.append(
      head,
      node("label", "field-label", "Chave da API Gemini"),
      key,
      hint,
      node("label", "field-label", "Modelo"),
      model,
      help,
      clearLabel,
      actions,
      status,
    );
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveSettings(form);
    });
    dialog.append(form);
    document.body.append(dialog);
    settingsDialog = dialog;
    return dialog;
  }

  async function loadSettings() {
    const { body } = await ui().request("/api/v1/ai/settings");
    return body;
  }

  async function openSettings(message) {
    const dialog = ensureSettingsDialog();
    const form = dialog.querySelector("form");
    form.reset();
    statusLine(form, message || "", Boolean(message));
    form.elements.model.value = "gemini-2.5-flash";
    const hint = form.querySelector("[data-ai-hint]");
    hint.textContent = "Nenhuma chave salva.";
    try {
      const settings = await loadSettings();
      form.elements.model.value = settings.model || "gemini-2.5-flash";
      hint.textContent = settings.configured
        ? `Chave salva, terminada em ${settings.key_hint}. Deixe o campo vazio para mantê-la.`
        : "Nenhuma chave salva.";
    } catch (error) {
      statusLine(form, error.message || "Não foi possível carregar a configuração.", true);
    }
    showDialog(dialog);
  }

  async function saveSettings(form) {
    if (form.dataset.saving === "true") return;
    const payload = { model: form.elements.model.value.trim(), clear_key: form.elements.clear_key.checked };
    const apiKey = form.elements.api_key.value.trim();
    if (apiKey) payload.api_key = apiKey;
    form.dataset.saving = "true";
    statusLine(form, "Salvando…");
    try {
      const { body } = await ui().request("/api/v1/ai/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      form.elements.api_key.value = "";
      form.elements.clear_key.checked = false;
      const hint = form.querySelector("[data-ai-hint]");
      hint.textContent = body.configured
        ? `Chave salva, terminada em ${body.key_hint}.`
        : "Nenhuma chave salva.";
      statusLine(form, "Configuração salva.");
    } catch (error) {
      statusLine(form, error.message || "Não foi possível salvar a configuração.", true);
    } finally {
      form.dataset.saving = "false";
    }
  }

  async function testSettings(form) {
    if (form.dataset.testing === "true" || form.dataset.saving === "true") return;
    const apiKey = form.elements.api_key.value.trim();
    if (apiKey) {
      statusLine(form, "Salvando chave antes de testar…");
      await saveSettings(form);
      if (form.querySelector("[data-form-status]").classList.contains("form-error")) return;
    }
    form.dataset.testing = "true";
    statusLine(form, "Testando conexão com o Gemini…");
    try {
      const { body } = await ui().request("/api/v1/ai/test", { method: "POST" });
      statusLine(form, body.message || "Conexão com o Gemini bem-sucedida!");
    } catch (error) {
      statusLine(form, error.message || "Não foi possível testar a conexão.", true);
    } finally {
      form.dataset.testing = "false";
    }
  }

  function ensureImportDialog() {
    if (importDialog) return importDialog;
    const dialog = node("dialog", "modal ai-modal");
    const form = node("form", "modal-form");
    const head = node("div", "modal-head");
    const title = node("h2", "section-title", "");
    title.dataset.aiTitle = "true";
    const close = node("button", "icon-button", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fechar");
    close.addEventListener("click", () => closeDialog(dialog));
    head.append(title, close);
    const lead = node("p", "muted");
    lead.dataset.aiLead = "true";
    const source = node("div", "ai-source");
    const text = node("textarea", "form-control");
    text.name = "material";
    text.placeholder = "Cole aqui o texto, a tabela ou o CSV";
    const file = node("input", "form-control");
    file.name = "upload";
    file.type = "file";
    file.accept = ".csv,.txt,.tsv,text/csv,text/plain,image/png,image/jpeg,image/webp,image/gif";
    source.append(text, file);
    const preview = node("div", "ai-preview");
    preview.dataset.aiPreview = "true";
    preview.hidden = true;
    const actions = node("div", "modal-actions");
    const cancel = node("button", "btn btn-ghost", "Cancelar");
    cancel.type = "button";
    cancel.addEventListener("click", () => closeDialog(dialog));
    const read = node("button", "btn btn-outline", "Ler com IA");
    read.type = "submit";
    const confirm = node("button", "btn btn-primary", "Confirmar");
    confirm.type = "button";
    confirm.dataset.aiConfirm = "true";
    confirm.hidden = true;
    confirm.addEventListener("click", () => applyProposal(form));
    actions.append(cancel, read, confirm);
    const status = node("p", "form-status", "");
    status.dataset.formStatus = "true";
    status.hidden = true;
    form.append(head, lead, source, preview, actions, status);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      readMaterial(form);
    });
    dialog.append(form);
    document.body.append(dialog);
    importDialog = dialog;
    return dialog;
  }

  async function openImport(nextMode) {
    mode = nextMode;
    proposal = null;
    try {
      const settings = await loadSettings();
      if (!settings.configured) {
        await openSettings("Salve a chave do Gemini para usar a leitura com IA.");
        return;
      }
    } catch (error) {
      await openSettings(error.message || "Não foi possível carregar a configuração da IA.");
      return;
    }
    const dialog = ensureImportDialog();
    const form = dialog.querySelector("form");
    const spec = MODES[mode];
    form.reset();
    form.querySelector("[data-ai-title]").textContent = spec.title;
    form.querySelector("[data-ai-lead]").textContent = spec.lead;
    form.querySelector("[data-ai-preview]").hidden = true;
    form.querySelector("[data-ai-preview]").replaceChildren();
    form.querySelector("[data-ai-confirm]").hidden = true;
    statusLine(form, "");
    showDialog(dialog);
  }

  function renderProposal(form, body) {
    proposal = body;
    const preview = form.querySelector("[data-ai-preview]");
    preview.replaceChildren();
    if (body.summary) preview.append(node("p", "", body.summary));
    const items = body.items || [];
    const table = node("table", "data-table");
    const head = node("tr");
    const headers = mode === "operations"
      ? ["Data", "Tipo", "Ativo", "Quantidade", "Preço", "Taxa", "Situação"]
      : ["Ativo", "Alvo atual", "Novo alvo", "Ação", "Situação"];
    headers.forEach((label) => head.append(node("th", "", label)));
    const thead = node("thead");
    thead.append(head);
    const tbody = node("tbody");
    items.forEach((item) => tbody.append(mode === "operations" ? operationRow(item) : targetRow(item)));
    if (!items.length) {
      const row = node("tr");
      const cell = node("td", "empty-cell", "Nenhum item reconhecido.");
      cell.colSpan = headers.length;
      row.append(cell);
      tbody.append(row);
    }
    table.append(thead, tbody);
    const scroll = node("div", "table-scroll");
    scroll.append(table);
    preview.append(scroll);
    const skipped = body.skipped || [];
    if (skipped.length) {
      const list = node("ul", "ai-skipped");
      skipped.forEach((item) => {
        const line = item.reason ? `${item.description}: ${item.reason}` : item.description;
        list.append(node("li", "", line));
      });
      preview.append(node("p", "muted", "Não incluídos"), list);
    }
    preview.hidden = false;
    const ready = items.filter((item) => item.ready).length;
    const confirm = form.querySelector("[data-ai-confirm]");
    confirm.hidden = ready === 0;
    confirm.textContent = MODES[mode].confirm(ready);
    statusLine(form, ready ? "Confira a leitura antes de confirmar." : "Nada pronto para gravar. Ajuste o material e leia de novo.", ready === 0);
  }

  function operationRow(item) {
    const row = node("tr");
    const values = [
      item.occurred_at ? ui().formatDate(item.occurred_at) : "—",
      item.kind_label || "—",
      item.symbol || "—",
      item.quantity ? ui().formatNumber(item.quantity, 8) : "—",
      item.unit_price_usd ? ui().formatPrice(item.unit_price_usd) : "—",
      item.fee_usdt && Number(item.fee_usdt) ? ui().formatNumber(item.fee_usdt, 6) : "—",
      item.ready ? (item.reason || "Pronto") : (item.reason || "Não será incluído"),
    ];
    values.forEach((value, index) => {
      const cell = node("td", index === values.length - 1 && !item.ready ? "ai-blocked" : "", value);
      row.append(cell);
    });
    return row;
  }

  function targetRow(item) {
    const row = node("tr");
    const action = item.action === "create" ? "Criar" : item.action === "update" ? "Atualizar" : "—";
    const values = [
      item.symbol || "—",
      item.current_price_usd ? ui().formatPrice(item.current_price_usd) : "—",
      item.price_usd ? ui().formatPrice(item.price_usd) : "—",
      action,
      item.ready ? (item.reason || "Pronto") : (item.reason || "Não será atualizado"),
    ];
    values.forEach((value, index) => {
      const cell = node("td", index === values.length - 1 && !item.ready ? "ai-blocked" : "", value);
      row.append(cell);
    });
    return row;
  }

  async function readMaterial(form) {
    if (form.dataset.saving === "true") return;
    const data = new FormData();
    data.append("text", form.elements.material.value || "");
    const file = form.elements.upload.files && form.elements.upload.files[0];
    if (file) data.append("upload", file);
    if (!form.elements.material.value.trim() && !file) {
      statusLine(form, "Cole um texto ou escolha um arquivo.", true);
      return;
    }
    form.dataset.saving = "true";
    statusLine(form, "Lendo com o Gemini…");
    try {
      const { body } = await ui().request(MODES[mode].path, { method: "POST", body: data });
      renderProposal(form, body);
    } catch (error) {
      if (error.code === "AI_NOT_CONFIGURED") {
        closeDialog(importDialog);
        await openSettings(error.message);
        return;
      }
      if (error.code === "AI_CREDITS_DEPLETED") {
        statusLine(form, `${error.message} Clique na engrenagem ⚙ no topo para atualizar a chave.`, true);
      } else {
        statusLine(form, error.message || "Não foi possível ler o material.", true);
      }
    } finally {
      form.dataset.saving = "false";
    }
  }

  async function applyProposal(form) {
    if (form.dataset.saving === "true" || !proposal) return;
    const ready = (proposal.items || []).filter((item) => item.ready);
    if (!ready.length) return;
    form.dataset.saving = "true";
    const confirm = form.querySelector("[data-ai-confirm]");
    confirm.disabled = true;
    let saved = 0;
    try {
      for (const item of ready) {
        statusLine(form, `Gravando ${saved + 1} de ${ready.length}…`);
        if (mode === "operations") await saveOperation(item);
        else await saveTarget(item);
        saved += 1;
      }
      closeDialog(importDialog);
      if (window.Portfolio) await window.Portfolio.load();
      if (mode === "operations" && window.Operations) {
        const panel = document.querySelector('[data-tab-panel="lancamentos"]');
        window.Operations.invalidate(panel);
      }
      if (mode === "targets" && window.Targets) await window.Targets.init();
    } catch (error) {
      const written = saved ? ` ${saved} já ${saved === 1 ? "foi gravado" : "foram gravados"}.` : "";
      statusLine(form, `${error.message || "Não foi possível gravar."}${written}`, true);
      if (saved && window.Portfolio) await window.Portfolio.load();
    } finally {
      form.dataset.saving = "false";
      confirm.disabled = false;
    }
  }

  async function saveOperation(item) {
    const payload = {
      kind: item.kind,
      asset_id: item.asset_id,
      occurred_at: item.occurred_at,
      quantity: item.quantity,
      fee_usdt: item.fee_usdt || "0",
    };
    if (item.unit_price_usd) payload.unit_price_usd = item.unit_price_usd;
    if (item.note) payload.note = item.note;
    await ui().request("/api/v1/operations", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": newKey() },
      body: JSON.stringify(payload),
    });
  }

  async function saveTarget(item) {
    const payload = { price_usd: item.price_usd, active: item.active };
    if (item.orientation) payload.orientation = item.orientation;
    if (item.action === "create") {
      payload.asset_id = item.asset_id;
      payload.kind = "buy";
      await ui().request("/api/v1/price-targets", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": newKey() },
        body: JSON.stringify(payload),
      });
      return;
    }
    await ui().request(`/api/v1/price-targets/${item.target_id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        "If-Match": String(item.version),
        "Idempotency-Key": newKey(),
      },
      body: JSON.stringify(payload),
    });
  }

  function gearButton() {
    const button = ui().button("⚙", "icon-button", () => openSettings());
    button.setAttribute("aria-label", "Configurar IA");
    button.title = "Configurar IA";
    return button;
  }

  document.addEventListener("auth:signed-out", () => {
    closeDialog(settingsDialog);
    closeDialog(importDialog);
    proposal = null;
  });
  document.addEventListener("auth:expired", () => {
    closeDialog(settingsDialog);
    closeDialog(importDialog);
    proposal = null;
  });

  window.AiImport = Object.freeze({
    gearButton,
    openSettings,
    openOperations: () => openImport("operations"),
    openTargets: () => openImport("targets"),
  });
})();
