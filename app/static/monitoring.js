(() => {
  "use strict";

  const POLL_SECONDS = 300;
  let active = false;
  let suspended = false;
  let cycleInFlight = false;
  let runAfterInFlight = false;
  let forceAfterInFlight = false;
  let cycleTimer = null;
  let sessionStartedAt = 0;
  let lastGapAt = 0;
  let gapGeneration = 0;
  let historyItems = [];
  let readItems = [];
  let historyRequest = null;
  const liveNotificationIds = new Set();
  let channel = null;

  try {
    if ("BroadcastChannel" in window) {
      channel = new BroadcastChannel("carteira-monitoring-notifications");
      channel.addEventListener("message", (event) => {
        if (event.data && event.data.type === "displayed" && event.data.id) {
          liveNotificationIds.add(event.data.id);
        }
      });
    }
  } catch (_error) {
    channel = null;
  }

  function node(tag, className, text) {
    return window.AppUI.element(tag, className, text);
  }

  function idempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function clearTimer() {
    if (cycleTimer !== null) window.clearTimeout(cycleTimer);
    cycleTimer = null;
  }

  function panel() {
    return document.getElementById("monitoring-panel");
  }

  function setStatus(message, state = "info") {
    const target = panel();
    if (!target) return;
    let status = target.querySelector("[data-monitoring-status]");
    if (!status) {
      status = node("p", "monitoring-status");
      status.dataset.monitoringStatus = "true";
      target.append(status);
    }
    status.className = `monitoring-status state-${state}`;
    status.textContent = message;
  }

  function ensureControls() {
    const target = panel();
    if (!target || target.querySelector("[data-monitoring-controls]")) return;
    const controls = node("div", "monitoring-controls");
    controls.dataset.monitoringControls = "true";
    const cycleButton = node("button", "btn btn-primary", "Verificar agora");
    cycleButton.type = "button";
    cycleButton.addEventListener("click", () => {
      suspended = false;
      clearTimer();
      runCycle({ force: true });
    });
    controls.append(cycleButton);
    const gap = node("p", "muted", "A cobertura pausa quando esta aba fica suspensa ou perde conexão. Ao retomar, nenhum alerta retroativo é criado.");
    controls.append(gap);
    target.append(controls);
  }

  function wait(milliseconds) {
    return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
  }

  function scheduleFrom(payload, retryAfter) {
    if (!active || suspended || !window.AppAuth.hasSession() || document.hidden || !navigator.onLine) {
      clearTimer();
      return;
    }
    clearTimer();
    const candidates = [payload && payload.next_due_at, payload && payload.next_retry_at]
      .map((value) => value ? new Date(value).getTime() : NaN)
      .filter(Number.isFinite);
    if (retryAfter) {
      const seconds = Number(retryAfter);
      if (Number.isFinite(seconds) && seconds >= 0) candidates.push(Date.now() + seconds * 1000);
    }
    const nextAt = candidates.length ? Math.max(...candidates) : Date.now() + POLL_SECONDS * 1000;
    const delay = Math.max(1000, nextAt - Date.now());
    cycleTimer = window.setTimeout(() => {
      cycleTimer = null;
      runCycle();
    }, delay);
  }

  async function displayAcknowledgement(notificationId) {
    try {
      await window.AppUI.request(`/api/v1/notifications/${encodeURIComponent(notificationId)}/displayed`, { method: "POST" });
      liveNotificationIds.add(notificationId);
      if (channel) channel.postMessage({ type: "displayed", id: notificationId });
    } catch (_error) {
      // The notification remains in history and the server ACK is idempotent.
    }
  }

  function notificationText(item) {
    const asset = item.asset || {};
    const target = item.target || {};
    const quote = item.quote || {};
    return `${asset.symbol || "Ativo"} atingiu o alvo de compra: cotação ${window.AppUI.formatMoney(quote.price_usd)}, alvo ${window.AppUI.formatMoney(target.price_usd)}.`;
  }

  function renderToast(item) {
    if (document.hidden || !navigator.onLine) return;
    let host = document.getElementById("notification-toasts");
    if (!host) {
      host = node("div", "toast-region");
      host.id = "notification-toasts";
      host.setAttribute("aria-live", "polite");
      host.setAttribute("aria-label", "Novos alertas");
      document.body.append(host);
    }
    const toast = node("article", "toast", "");
    toast.setAttribute("role", "status");
    const title = node("strong", "", "Alvo atingido");
    const detail = node("p", "", notificationText(item));
    const time = node("time", "muted", window.AppUI.formatDate(item.created_at));
    toast.append(title, detail, time);
    host.append(toast);
    window.setTimeout(() => toast.remove(), 12000);
    ackWhenVisible(toast, item);
  }

  function ackWhenVisible(card, item) {
    if (item.displayed_at || document.hidden || !navigator.onLine) return;
    if (!("IntersectionObserver" in window)) {
      window.requestAnimationFrame(() => {
        if (card.isConnected && !document.hidden && navigator.onLine) displayAcknowledgement(item.id);
      });
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        observer.disconnect();
        displayAcknowledgement(item.id);
      }
    }, { threshold: 0.15 });
    observer.observe(card);
  }

  function renderAlerts(items) {
    const host = document.getElementById("unread-alerts");
    if (!host) return;
    host.replaceChildren();
    host.hidden = !items.length;
    if (!items.length) return;
    const list = node("div", "alert-list");
    list.dataset.alerts = "true";
    host.append(list);
    items.forEach((item) => {
      const card = node("article", "alert-item");
      const text = node("div", "alert-text");
      text.append(node("strong", "", "Alvo atingido"), node("p", "", notificationText(item)),
        node("time", "muted", window.AppUI.formatDate(item.created_at)));
      const readButton = node("button", "btn btn-secondary btn-small", "Marcar como lida");
      readButton.type = "button";
      readButton.addEventListener("click", async () => {
        readButton.disabled = true;
        try {
          await window.AppUI.request(`/api/v1/notifications/${encodeURIComponent(item.id)}/read`, { method: "POST" });
          await refreshHistory();
        } catch (error) {
          readButton.disabled = false;
          readButton.textContent = error.message || "Tente novamente";
        }
      });
      card.append(text, readButton);
      list.append(card);
      ackWhenVisible(card, item);
    });
  }

  function renderReadLog() {
    const monitoring = document.getElementById("monitoring-panel");
    const host = monitoring && monitoring.parentElement;
    if (!host) return;
    host.querySelectorAll("[data-read-log]").forEach((item) => item.remove());
    const box = node("section", "card read-log");
    box.dataset.readLog = "true";
    box.append(node("h3", "subsection-title", "Notificações lidas"));
    if (!readItems.length) {
      box.append(node("p", "muted", "Nenhuma notificação lida."));
    } else {
      const list = node("div", "read-log-list");
      readItems.forEach((item) => {
        const row = node("article", "read-log-item");
        row.append(
          node("p", "", notificationText(item)),
          node("time", "muted", `Lida em ${window.AppUI.formatDate(item.read_at || item.created_at)}`),
        );
        list.append(row);
      });
      box.append(list);
    }
    monitoring.after(box);
  }

  async function refreshHistory() {
    if (!active || !window.AppAuth.hasSession()) return;
    if (historyRequest) return historyRequest;
    historyRequest = (async () => {
      try {
        const response = await window.AppUI.request("/api/v1/notifications?limit=100");
        if (!active || !window.AppAuth.hasSession()) return;
        const items = response.body.items || [];
        historyItems = items.filter((item) => !item.read_at);
        readItems = items.filter((item) => item.read_at)
          .sort((left, right) => new Date(right.read_at) - new Date(left.read_at))
          .slice(0, 20);
        renderAlerts(historyItems);
        renderReadLog();
      } finally {
        historyRequest = null;
      }
    })();
    return historyRequest;
  }

  async function notifyForCycle(cycleId, expectedGapGeneration = gapGeneration) {
    if (!cycleId || gapGeneration !== expectedGapGeneration || !active || document.hidden || !navigator.onLine || !window.AppAuth.hasSession()) return;
    try {
      const response = await window.AppUI.request(`/api/v1/notifications?limit=100&cycle_id=${encodeURIComponent(cycleId)}`);
      if (gapGeneration !== expectedGapGeneration || !active || document.hidden || !navigator.onLine || !window.AppAuth.hasSession()) return;
      const newItems = (response.body.items || []).filter((item) => {
        const created = new Date(item.created_at).getTime();
        return item.cycle_id === cycleId && !item.displayed_at && Number.isFinite(created)
          && created >= sessionStartedAt && !liveNotificationIds.has(item.id);
      });
      newItems.reverse().forEach((item) => {
        liveNotificationIds.add(item.id);
        renderToast(item);
      });
    } catch (_error) {
      // A history refresh on the next successful cycle will recover the item.
    }
  }

  async function finishCycle(payload, expectedGapGeneration = gapGeneration) {
    const cycleId = payload && (payload.cycle_id || payload.id);
    if (window.Portfolio && typeof window.Portfolio.load === "function") {
      await window.Portfolio.load();
    }
    if (cycleId) await notifyForCycle(cycleId, expectedGapGeneration);
    await refreshHistory().catch(() => {});
  }

  async function pollCycle(cycleId) {
    const deadline = Date.now() + 30000;
    while (active && window.AppAuth.hasSession() && Date.now() < deadline) {
      await wait(2500);
      if (!active || !window.AppAuth.hasSession()) return null;
      try {
        const response = await window.AppUI.request(`/api/v1/monitoring/cycles/${encodeURIComponent(cycleId)}`);
        const cycle = response.body;
        if (!cycle || !["reserved", "running", "fetching", "evaluating", "pending"].includes(cycle.status)) return cycle;
      } catch (_error) {
        return null;
      }
    }
    return null;
  }

  function blockedMessage(reason, payload) {
    const labels = {
      config_required: "Monitoramento suspenso: configure o provedor e o mapeamento dos ativos antes de continuar.",
      provider_cooldown: "Aguardando o fim do intervalo de segurança do provedor.",
      provider_window_changed: "A janela de quota mudou; o acompanhamento aguardará a próxima tentativa permitida.",
      quota_exhausted: "A quota disponível foi atingida. O acompanhamento aguardará a próxima janela.",
      not_due: "A próxima verificação ainda não venceu.",
      in_progress: "Há um ciclo em andamento em outra aba.",
    };
    return labels[reason] || (payload && payload.next_retry_at
      ? `Próxima tentativa prevista para ${window.AppUI.formatDate(payload.next_retry_at)}.`
      : "A verificação está temporariamente bloqueada.");
  }

  async function runCycle(options = {}) {
    if (!active || !window.AppAuth.hasSession()) return;
    if (cycleInFlight) {
      runAfterInFlight = true;
      if (options.force) forceAfterInFlight = true;
      return;
    }
    if (document.hidden || !navigator.onLine) {
      lastGapAt = lastGapAt || Date.now();
      setStatus(document.hidden ? "Aba suspensa; nenhum ciclo foi executado durante a pausa." : "Sem conexão; a cobertura está interrompida.", "warning");
      return;
    }
    cycleInFlight = true;
    ensureControls();
    const gapGenerationAtStart = gapGeneration;
    const resumedAfterGap = lastGapAt > 0;
    setStatus(resumedAfterGap
      ? "Retomando após uma lacuna sem cobertura; sem alertas retroativos…"
      : "Consultando cotações e avaliando alvos…", "loading");
    try {
      const response = await window.AppUI.request("/api/v1/monitoring/cycles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_request_id: idempotencyKey(), force: Boolean(options.force) }),
      });
      const payload = response.body || {};
      if (payload.state === "blocked") {
        setStatus(blockedMessage(payload.reason, payload), payload.reason === "config_required" ? "warning" : "info");
        if (payload.reason === "config_required") suspended = true;
        else scheduleFrom(payload, response.response.headers.get("Retry-After"));
        return;
      }
      if (payload.state === "accepted" || payload.state === "running" || payload.status === "running") {
        const cycle = payload.cycle_id ? await pollCycle(payload.cycle_id) : null;
        if (cycle && ["completed", "partial", "failed"].includes(cycle.status)) {
          await finishCycle({ ...cycle, cycle_id: payload.cycle_id }, gapGenerationAtStart);
          setStatus(cycle.status === "failed"
            ? "O ciclo falhou; nenhuma cotação antiga gerou alerta."
            : resumedAfterGap ? "Ciclo retomado. O período de interrupção não foi coberto." : "Ciclo concluído.",
          cycle.status === "failed" ? "warning" : "success");
          scheduleFrom(cycle);
        } else {
          setStatus("O ciclo não terminou a tempo. A próxima verificação seguirá o horário do servidor.", "warning");
          scheduleFrom(payload);
        }
        return;
      }
      const state = payload.state || payload.status;
      if (["completed", "partial", "failed", "reused"].includes(state)) {
        await finishCycle(payload, gapGenerationAtStart);
        setStatus(state === "failed"
          ? "O ciclo falhou; nenhuma cotação antiga gerou alerta."
          : resumedAfterGap ? "Ciclo retomado. O período de interrupção não foi coberto."
            : state === "partial" ? "Ciclo concluído com ativos indisponíveis." : "Ciclo concluído.",
        state === "failed" || state === "partial" ? "warning" : "success");
      } else if (payload.cycle_id) {
        await notifyForCycle(payload.cycle_id, gapGenerationAtStart);
      }
      scheduleFrom(payload);
    } catch (error) {
      const payload = error.body || {};
      if (payload.state === "blocked") {
        setStatus(blockedMessage(payload.reason, payload), payload.reason === "config_required" ? "warning" : "info");
        if (payload.reason === "config_required") suspended = true;
        else scheduleFrom(payload, error.retryAfter);
      } else {
        const waitSeconds = Number(error.retryAfter);
        const retryDate = Number.isFinite(waitSeconds) && waitSeconds >= 0
          ? new Date(Date.now() + waitSeconds * 1000).toISOString()
          : null;
        setStatus(lastGapAt ? "Conexão retomada; o intervalo anterior ficou sem cobertura." : (error.message || "Falha no ciclo; o acompanhamento está interrompido."), "warning");
        scheduleFrom({ next_retry_at: retryDate }, error.retryAfter);
      }
    } finally {
      cycleInFlight = false;
      const interruptedDuringRun = gapGeneration !== gapGenerationAtStart;
      if (interruptedDuringRun && active) {
        setStatus(document.hidden
          ? "Aba suspensa; a cobertura foi interrompida."
          : !navigator.onLine
            ? "Sem conexão; a cobertura foi interrompida."
            : "Houve uma lacuna de cobertura; retomando sem alertas retroativos.", "warning");
      }
      if (!interruptedDuringRun && active && !document.hidden && navigator.onLine) lastGapAt = 0;
      const queueAnotherRun = runAfterInFlight || interruptedDuringRun;
      const queuedForce = forceAfterInFlight;
      runAfterInFlight = false;
      forceAfterInFlight = false;
      if (queueAnotherRun && active && !document.hidden && navigator.onLine) {
        clearTimer();
        window.setTimeout(() => runCycle({ force: queuedForce }), 0);
      }
    }
  }

  function start() {
    if (!window.AppAuth || !window.AppAuth.hasSession()) return;
    ensureControls();
    if (!active) {
      active = true;
      suspended = false;
      sessionStartedAt = Date.now();
      lastGapAt = 0;
      refreshHistory().catch(() => {});
      runCycle();
    }
  }

  function stop() {
    active = false;
    suspended = false;
    cycleInFlight = false;
    clearTimer();
    liveNotificationIds.clear();
    historyItems = [];
    readItems = [];
    runAfterInFlight = false;
    sessionStartedAt = 0;
    lastGapAt = 0;
    const host = document.getElementById("notification-toasts");
    if (host) host.remove();
  }

  document.addEventListener("visibilitychange", () => {
    if (!active) return;
    if (document.hidden) {
      clearTimer();
      gapGeneration += 1;
      lastGapAt = lastGapAt || Date.now();
      setStatus("Aba suspensa; a cobertura foi interrompida.", "warning");
    } else if (lastGapAt) {
      suspended = false;
      setStatus("Retomando após uma lacuna sem cobertura…", "warning");
      runCycle();
    }
  });

  window.addEventListener("offline", () => {
    if (!active) return;
    clearTimer();
    gapGeneration += 1;
    lastGapAt = lastGapAt || Date.now();
    setStatus("Sem conexão; a cobertura foi interrompida.", "warning");
  });
  window.addEventListener("online", () => {
    if (!active || document.hidden) return;
    suspended = false;
    setStatus("Conexão retomada; o período sem rede não foi coberto.", "warning");
    runCycle();
  });
  document.addEventListener("auth:signed-out", stop);
  document.addEventListener("auth:expired", stop);
  document.addEventListener("monitoring:configuration-changed", () => {
    if (!active || !window.AppAuth.hasSession()) return;
    suspended = false;
    clearTimer();
    runCycle();
  });

  window.Monitoring = Object.freeze({ start, stop, renderReadLog });
})();
