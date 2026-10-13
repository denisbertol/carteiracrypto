"use strict";

// Run with PLAYWRIGHT_MODULE and CHROME_BIN when Playwright uses a shared runtime.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");

const monitoringScript = path.join(__dirname, "..", "app", "static", "monitoring.js");
const portfolioScript = path.join(__dirname, "..", "app", "static", "portfolio.js");
const chartsScript = path.join(__dirname, "..", "app", "static", "charts.js");
const operationsScript = path.join(__dirname, "..", "app", "static", "operations.js");
const targetsScript = path.join(__dirname, "..", "app", "static", "targets.js");
const styleSheet = path.join(__dirname, "..", "app", "static", "style.css");
const indexTemplate = path.join(__dirname, "..", "app", "templates", "index.html");
let browser;

before(async () => {
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_BIN || undefined });
});

after(async () => {
  if (browser) await browser.close();
});

async function fixture(existingContext) {
  const context = existingContext || await browser.newContext({ viewport: { width: 360, height: 800 } });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  await page.setContent('<main><section id="monitoring-panel"></section><section id="notifications-panel"></section></main>');
  await page.evaluate(() => {
    window.__cycleReplies = [];
    window.__cycleNotifications = {};
    window.__historyItems = [];
    window.__requests = [];
    window.__timers = [];
    let nextTimerId = 0;
    window.setTimeout = (callback, delay) => {
      const task = { id: ++nextTimerId, callback, delay: Number(delay), cancelled: false };
      window.__timers.push(task);
      return task.id;
    };
    window.clearTimeout = (id) => {
      const task = window.__timers.find((item) => item.id === id);
      if (task) task.cancelled = true;
    };
    window.__fireTimer = (minimumDelay = 0) => {
      const task = window.__timers.find((item) => !item.cancelled && item.delay >= minimumDelay);
      if (!task) throw new Error("Nenhum timer pendente encontrado.");
      task.cancelled = true;
      task.callback();
      return task.delay;
    };
    window.AppAuth = { hasSession: () => true };
    window.Portfolio = { load: async () => {} };
    window.AppUI = {
      element(tag, className, text) {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined && text !== null) element.textContent = String(text);
        return element;
      },
      formatMoney: (value) => `$${value}`,
      formatPercent: (value) => `${value}%`,
      formatDate: (value) => String(value),
      async request(requestPath, options = {}) {
        window.__requests.push({ path: requestPath, method: options.method || "GET" });
        if (requestPath === "/api/v1/monitoring/cycles") {
          const next = window.__cycleReplies.shift();
          if (!next) throw new Error("Resposta de ciclo não configurada no teste.");
          const result = {
            body: next.body,
            response: { headers: { get: (name) => name === "Retry-After" ? next.retryAfter || null : null } },
          };
          if (next.deferred) {
            return new Promise((resolve) => { window.__finishDeferredCycle = () => resolve(result); });
          }
          if (next.throw) {
            const error = new Error("Ciclo bloqueado");
            error.body = next.body;
            error.retryAfter = next.retryAfter;
            throw error;
          }
          return result;
        }
        if (requestPath.startsWith("/api/v1/monitoring/cycles/")) {
          throw new Error("Consulta de ciclo inesperada.");
        }
        if (requestPath.startsWith("/api/v1/notifications?limit=100&cycle_id=")) {
          const cycleId = decodeURIComponent(requestPath.split("cycle_id=")[1]);
          const result = { body: { items: window.__cycleNotifications[cycleId] || [] } };
          if (window.__deferNotificationFetch) {
            return new Promise((resolve) => { window.__finishNotificationFetch = () => resolve(result); });
          }
          return result;
        }
        if (requestPath.startsWith("/api/v1/notifications?limit=50")) {
          return { body: { items: window.__historyItems, next_cursor: null } };
        }
        if (requestPath.endsWith("/read")) {
          const id = requestPath.split("/")[4];
          const item = window.__historyItems.find((candidate) => candidate.id === id);
          if (item) item.read_at = new Date().toISOString();
          return { body: {} };
        }
        if (requestPath.endsWith("/displayed")) return { body: {} };
        throw new Error(`Rota inesperada: ${requestPath}`);
      },
    };
  });
  await page.addScriptTag({ path: monitoringScript });
  return { context, page };
}

async function cyclePosts(page, count) {
  await page.waitForFunction((expected) =>
    window.__requests.filter((request) => request.path === "/api/v1/monitoring/cycles").length >= expected,
  count);
}

test("blocked antes da reserva, cooldown e config_required controlam o próximo ciclo", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const now = Date.now();
      window.__cycleReplies.push(
        { body: { state: "blocked", reason: "not_due", cycle_id: null, next_due_at: new Date(now + 300000).toISOString() } },
        { throw: true, retryAfter: "120", body: { state: "blocked", reason: "provider_cooldown", next_retry_at: new Date(now + 120000).toISOString() } },
        { body: { state: "blocked", reason: "config_required", cycle_id: null } },
        { body: { state: "blocked", reason: "not_due", cycle_id: null, next_due_at: new Date(now + 300000).toISOString() } },
      );
      window.Monitoring.start();
    });
    await cyclePosts(page, 1);
    await page.waitForFunction(() => window.__timers.some((timer) => !timer.cancelled && timer.delay > 1000));
    const first = await page.evaluate(() => window.__timers.find((timer) => !timer.cancelled && timer.delay > 1000)?.delay);
    assert.ok(first >= 299000 && first <= 300000, `primeiro delay: ${first}`);
    await page.evaluate(() => window.__fireTimer(1000));
    await cyclePosts(page, 2);
    await page.waitForFunction(() => window.__timers.some((timer) => !timer.cancelled && timer.delay > 1000));
    const second = await page.evaluate(() => window.__timers.find((timer) => !timer.cancelled && timer.delay > 1000)?.delay);
    assert.ok(second >= 119000 && second <= 120000, `cooldown: ${second}`);
    await page.evaluate(() => window.__fireTimer(1000));
    await cyclePosts(page, 3);
    assert.equal(await page.evaluate(() => window.__timers.filter((timer) => !timer.cancelled).length), 0);
    await page.evaluate(() => document.dispatchEvent(new Event("monitoring:configuration-changed")));
    await cyclePosts(page, 4);
  } finally {
    await context.close();
  }
});

test("suspensão durante a requisição preserva a lacuna e retoma ao mostrar a aba", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const due = new Date(Date.now() + 300000).toISOString();
      window.__cycleReplies.push(
        { deferred: true, body: { state: "blocked", reason: "not_due", cycle_id: null, next_due_at: due } },
        { body: { state: "blocked", reason: "not_due", cycle_id: null, next_due_at: due } },
      );
      window.__hiddenForTest = false;
      Object.defineProperty(document, "hidden", { configurable: true, get: () => window.__hiddenForTest });
      window.Monitoring.start();
    });
    await cyclePosts(page, 1);
    await page.evaluate(() => {
      window.__hiddenForTest = true;
      document.dispatchEvent(new Event("visibilitychange"));
      window.__finishDeferredCycle();
    });
    await page.waitForFunction(() => document.querySelector("[data-monitoring-status]")?.textContent.includes("Aba suspensa"));
    assert.equal(await page.evaluate(() => window.__timers.filter((timer) => !timer.cancelled).length), 0);
    await page.evaluate(() => {
      window.__hiddenForTest = false;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await cyclePosts(page, 2);
  } finally {
    await context.close();
  }
});

test("toast usa notification_id, ACK visível e histórico lido não vira toast", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const cycleId = "10000000-0000-4000-8000-000000000001";
      const item = {
        id: "20000000-0000-4000-8000-000000000001",
        cycle_id: cycleId,
        created_at: new Date(Date.now() + 1000).toISOString(),
        displayed_at: null,
        read_at: null,
        asset: { symbol: "BTC" },
        target: { kind: "buy", price_usd: "60000" },
        quote: { price_usd: "59000", distance_percent: "1.67" },
      };
      window.__historyItems = [item];
      window.__cycleNotifications[cycleId] = [item];
      window.__cycleReplies.push({ body: { state: "completed", cycle_id: cycleId, next_due_at: new Date(Date.now() + 300000).toISOString() } });
      window.Monitoring.start();
    });
    await page.waitForFunction(() => document.querySelectorAll(".toast").length === 1);
    assert.match(await page.locator(".toast").innerText(), /BTC.*Compra/);
    await page.waitForFunction(() => window.__requests.some((request) => request.path.endsWith("/displayed")));
    await page.getByRole("button", { name: "Marcar como lida" }).click();
    await page.waitForFunction(() => window.__requests.some((request) => request.path.endsWith("/read")));
    assert.equal(await page.locator(".toast").count(), 1);
    assert.equal(await page.getByText("Lida", { exact: true }).count(), 1);
  } finally {
    await context.close();
  }
});

test("notificação histórica permanece na central sem toast retroativo", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const cycleId = "10000000-0000-4000-8000-000000000004";
      const oldItem = {
        id: "20000000-0000-4000-8000-000000000004",
        cycle_id: cycleId,
        created_at: new Date(Date.now() - 86400000).toISOString(),
        displayed_at: null,
        read_at: null,
        asset: { symbol: "ETH" },
        target: { kind: "sell", price_usd: "3000" },
        quote: { price_usd: "3010", distance_percent: "0.33" },
      };
      window.__historyItems = [oldItem];
      window.__cycleNotifications[cycleId] = [oldItem];
      window.__cycleReplies.push({ body: { state: "completed", cycle_id: cycleId, next_due_at: new Date(Date.now() + 300000).toISOString() } });
      window.Monitoring.start();
    });
    await page.waitForFunction(() => window.__requests.some((request) => request.path.includes("cycle_id=")));
    assert.equal(await page.locator(".toast").count(), 0);
    assert.match(await page.locator(".notification-history").innerText(), /ETH.*Venda/);
  } finally {
    await context.close();
  }
});

test("perda de rede durante o ciclo não exibe alerta antigo e retoma sem retroatividade", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const cycleId = "10000000-0000-4000-8000-000000000002";
      window.__cycleNotifications[cycleId] = [{
        id: "20000000-0000-4000-8000-000000000002",
        cycle_id: cycleId,
        created_at: new Date(Date.now() + 1000).toISOString(),
        displayed_at: null,
        asset: { symbol: "BTC" },
        target: { kind: "buy", price_usd: "60000" },
        quote: { price_usd: "59000", distance_percent: "1.67" },
      }];
      window.__cycleReplies.push(
        { deferred: true, body: { state: "completed", cycle_id: cycleId, next_due_at: new Date(Date.now() + 300000).toISOString() } },
        { body: { state: "blocked", reason: "not_due", cycle_id: null, next_due_at: new Date(Date.now() + 300000).toISOString() } },
      );
      window.__onlineForTest = true;
      Object.defineProperty(navigator, "onLine", { configurable: true, get: () => window.__onlineForTest });
      window.Monitoring.start();
    });
    await cyclePosts(page, 1);
    await page.evaluate(() => {
      window.__onlineForTest = false;
      window.dispatchEvent(new Event("offline"));
      window.__finishDeferredCycle();
    });
    await page.waitForFunction(() => document.querySelector("[data-monitoring-status]")?.textContent.includes("Sem conexão"));
    assert.equal(await page.locator(".toast").count(), 0);
    assert.equal(await page.evaluate(() => window.__requests.filter((request) => request.path.endsWith("/displayed")).length), 0);
    await page.evaluate(() => {
      window.__onlineForTest = true;
      window.dispatchEvent(new Event("online"));
    });
    await cyclePosts(page, 2);
    assert.equal(await page.locator(".toast").count(), 0);
  } finally {
    await context.close();
  }
});

test("suspensão durante a busca da notificação também impede toast retroativo", async () => {
  const { context, page } = await fixture();
  try {
    await page.evaluate(() => {
      const cycleId = "10000000-0000-4000-8000-000000000005";
      window.__cycleNotifications[cycleId] = [{
        id: "20000000-0000-4000-8000-000000000005",
        cycle_id: cycleId,
        created_at: new Date(Date.now() + 1000).toISOString(),
        displayed_at: null,
        asset: { symbol: "BTC" },
        target: { kind: "buy", price_usd: "60000" },
        quote: { price_usd: "59000", distance_percent: "1.67" },
      }];
      window.__deferNotificationFetch = true;
      window.__hiddenForTest = false;
      Object.defineProperty(document, "hidden", { configurable: true, get: () => window.__hiddenForTest });
      window.__cycleReplies.push({ body: {
        state: "completed", cycle_id: cycleId,
        next_due_at: new Date(Date.now() + 300000).toISOString(),
      } });
      window.Monitoring.start();
    });
    await page.waitForFunction(() => typeof window.__finishNotificationFetch === "function");
    await page.evaluate(() => {
      window.__hiddenForTest = true;
      document.dispatchEvent(new Event("visibilitychange"));
      window.__hiddenForTest = false;
      document.dispatchEvent(new Event("visibilitychange"));
      window.__finishNotificationFetch();
    });
    await page.waitForFunction(() => document.querySelector("[data-monitoring-status]")?.textContent.includes("lacuna"));
    assert.equal(await page.locator(".toast").count(), 0);
    assert.equal(await page.evaluate(() => window.__requests.filter((request) => request.path.endsWith("/displayed")).length), 0);
  } finally {
    await context.close();
  }
});

test("duas abas respeitam bloqueio in_progress sem duplicar alerta", async () => {
  const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
  try {
    const first = await fixture(context);
    const second = await fixture(context);
    await first.page.evaluate(() => {
      window.__cycleReplies.push({ body: {
        state: "completed",
        cycle_id: "10000000-0000-4000-8000-000000000003",
        next_due_at: new Date(Date.now() + 300000).toISOString(),
      } });
      window.Monitoring.start();
    });
    await second.page.evaluate(() => {
      window.__cycleReplies.push({ body: {
        state: "blocked", reason: "in_progress", cycle_id: null,
        next_retry_at: new Date(Date.now() + 20000).toISOString(),
      } });
      window.Monitoring.start();
    });
    await cyclePosts(first.page, 1);
    await cyclePosts(second.page, 1);
    await second.page.waitForFunction(() => window.__timers.some((timer) => !timer.cancelled && timer.delay > 1000));
    assert.match(await second.page.locator("[data-monitoring-status]").innerText(), /outra aba/);
    assert.equal(await second.page.locator(".toast").count(), 0);
    const retry = await second.page.evaluate(() => window.__timers.find((timer) => !timer.cancelled && timer.delay > 1000)?.delay);
    assert.ok(retry >= 19000 && retry <= 20000, `próxima tentativa: ${retry}`);
  } finally {
    await context.close();
  }
});

async function dashboardFixture() {
  const context = await browser.newContext({ viewport: { width: 360, height: 800 } });
  const page = await context.newPage();
  page.setDefaultTimeout(8000);
  const html = fs.readFileSync(indexTemplate, "utf8")
    .replace(/<script src="\/static\/[^\"]+" defer><\/script>/g, "")
    .replace(/<link rel="stylesheet" href="\/static\/style\.css">/, "");
  await page.setContent(html);
  await page.addStyleTag({ path: styleSheet });
  await page.evaluate(() => {
    const assetId = "30000000-0000-4000-8000-000000000001";
    window.__backend = {
      requests: [],
      assets: [{ id: assetId, symbol: "BTC", name: "Bitcoin", active: true }],
      targets: [],
      settings: { version: 1, proximity_percent: "10.00", interval_seconds: 300, retention_days: 30 },
      mappings: {
        coverage: { total_assets: 1, valid_assets: 0, pending_assets: 1, unsupported_assets: 0 },
        items: [{ asset_id: assetId, symbol: "BTC", name: "Bitcoin", status: "pending", version: 0, provider_coin_id: null }],
      },
      dashboard: {
        portfolio: {
          revision: 1,
          totals: { balance_usd: "30000", cash_usdt: "0", realized_net_usd: "0", unrealized_usd: "100" },
          positions: [
            { asset_id: assetId, symbol: "BTC", name: "Bitcoin", quantity: "0.5", average_price_usd: "59000", quote_usd: "60000", quote_freshness: "stale", remaining_cost_usd: "29500", current_value_usd: "30000", unrealized_usd: "500" },
            { asset_id: "30000000-0000-4000-8000-000000000002", symbol: "ETH", name: "Ethereum", quantity: "1", average_price_usd: "3000", quote_usd: null, quote_freshness: "unavailable", remaining_cost_usd: "3000", current_value_usd: null, unrealized_usd: null },
          ],
        },
        allocation: { version: 1, effective_at: "2026-10-02T12:00:00Z", complete: true, items: [] },
        quotes: [
          { symbol: "BTC", name: "Bitcoin", price_usd: "60000", freshness: "stale", source: "CoinGecko", quoted_at: "2026-10-02T12:00:00Z" },
          { symbol: "ETH", name: "Ethereum", price_usd: null, freshness: "unavailable", source: null, quoted_at: null },
        ],
        computed_at: "2026-10-02T13:00:00Z", quote_snapshot_at: "2026-10-02T12:00:00Z", freshness: "stale",
      },
      forceConflict: false,
    };
    window.AppAuth = {
      hasSession: () => true,
      async fetch(input, options = {}) {
        const url = new URL(String(input), "http://local.test");
        const route = url.pathname;
        const method = options.method || "GET";
        const state = window.__backend;
        state.requests.push({ route, method, headers: options.headers || {}, body: options.body || null });
        let status = 200;
        let body = {};
        if (route === "/api/v1/assets") body = { items: state.assets };
        else if (route === "/api/v1/dashboard") body = state.dashboard;
        else if (route === "/api/v1/price-targets" && method === "GET") body = { items: state.targets };
        else if (route === "/api/v1/price-targets" && method === "POST") {
          const value = JSON.parse(options.body);
          const target = { ...value, id: `t-${state.targets.length + 1}`, version: 1 };
          state.targets.push(target);
          body = target;
          status = 201;
        } else if (route.startsWith("/api/v1/price-targets/") && method === "PATCH") {
          const target = state.targets.find((item) => route.endsWith(item.id));
          Object.assign(target, JSON.parse(options.body));
          target.version += 1;
          body = target;
        } else if (route.startsWith("/api/v1/price-targets/") && method === "DELETE") {
          const index = state.targets.findIndex((item) => route.endsWith(item.id));
          if (index !== -1) state.targets.splice(index, 1);
          body = { id: route.split("/").pop(), deleted: true };
        } else if (route === "/api/v1/monitoring/settings" && method === "GET") body = state.settings;
        else if (route === "/api/v1/monitoring/settings" && method === "PATCH") {
          Object.assign(state.settings, JSON.parse(options.body));
          state.settings.version += 1;
          body = state.settings;
        } else if (route === "/api/v1/monitoring/mappings" && method === "GET") body = state.mappings;
        else if (route.startsWith("/api/v1/monitoring/mappings/") && method === "PUT") {
          if (state.forceConflict) {
            state.forceConflict = false;
            status = 409;
            body = { detail: { error: { message: "Versão alterada por outra sessão." } } };
          } else {
            const mapping = state.mappings.items[0];
            Object.assign(mapping, JSON.parse(options.body), { status: "valid", version: mapping.version + 1 });
            state.mappings.coverage = { total_assets: 1, valid_assets: 1, pending_assets: 0, unsupported_assets: 0 };
            body = mapping;
          }
        } else if (route === "/api/v1/monitoring/cycles" && method === "POST") {
          body = { state: "blocked", reason: "config_required", cycle_id: null };
        } else if (route === "/api/v1/notifications" && method === "GET") {
          body = { items: [], next_cursor: null };
        } else {
          throw new Error(`Rota inesperada no navegador: ${method} ${route}`);
        }
        return new Response(JSON.stringify(body), {
          status, headers: { "Content-Type": "application/json" },
        });
      },
    };
    document.getElementById("login-form").hidden = true;
    document.getElementById("logout-button").hidden = false;
  });
  await page.addScriptTag({ path: chartsScript });
  await page.addScriptTag({ path: portfolioScript });
  await page.addScriptTag({ path: operationsScript });
  await page.addScriptTag({ path: targetsScript });
  await page.addScriptTag({ path: monitoringScript });
  await page.evaluate(() => window.Portfolio.load());
  await page.waitForFunction(() => document.querySelectorAll('[data-form="create-target"]').length === 1);
  return { context, page };
}

test("alvos, limite e cobertura funcionam em 360 px com cotações antigas identificadas", async () => {
  const { context, page } = await dashboardFixture();
  try {
    assert.match(await page.locator("#app-content").innerText(), /Desatualizada/);
    assert.match(await page.locator("#app-content").innerText(), /Indisponível/);
    assert.equal(await page.locator('a[href="https://cryptoprices.cc/"]').count(), 1);
    await page.getByRole("tab", { name: "Alvos e alertas" }).click();
    assert.match(await page.locator(".coverage-summary").innerText(), /1 pendentes/);

    const create = page.locator('[data-form="create-target"]');
    await create.locator('[name="price_usd"]').fill("90,00");
    await create.getByRole("button", { name: "Adicionar alvo" }).click();
    await page.waitForFunction(() => window.__backend.targets.length === 1);
    await page.locator('[data-form="update-target"]').first().waitFor();
    await create.locator('[name="price_usd"]').fill("120");
    await create.locator('[name="kind"]').selectOption("sell");
    await create.getByRole("button", { name: "Adicionar alvo" }).click();
    await page.waitForFunction(() => window.__backend.targets.length === 2);
    await page.waitForFunction(() => document.querySelectorAll('[data-form="update-target"]').length === 2);
    const first = page.locator('[data-form="update-target"][data-target-id="t-1"]');
    await first.locator('[name="active"]').uncheck();
    await first.getByRole("button", { name: "Salvar alterações" }).click();
    await page.waitForFunction(() => window.__backend.targets[0].active === false);
    const targets = await page.evaluate(() => window.__backend.targets);
    assert.deepEqual(targets.map((target) => [target.kind, target.price_usd, target.active]), [
      ["buy", "90.00", false], ["sell", "120", true],
    ]);

    const settings = page.locator('[data-form="settings"]');
    await settings.locator('[name="proximity_percent"]').fill("0,00");
    await settings.getByRole("button", { name: "Salvar limite" }).click();
    await page.waitForFunction(() => window.__backend.settings.version === 2);
    await page.waitForFunction(() => document.querySelector('[data-form="settings"]')?.dataset.version === "2");
    await settings.locator('[name="proximity_percent"]').fill("100,00");
    await settings.getByRole("button", { name: "Salvar limite" }).click();
    await page.waitForFunction(() => window.__backend.settings.version === 3);
    await page.waitForFunction(() => document.querySelector('[data-form="settings"]')?.dataset.version === "3");
    assert.equal(await page.evaluate(() => window.__backend.settings.proximity_percent), "100.00");

    const mapping = page.locator('[data-form="mapping"]');
    await mapping.locator('[name="provider_coin_id"]').fill("bitcoin");
    await mapping.getByRole("button", { name: "Salvar mapeamento" }).click();
    await page.waitForFunction(() => window.__backend.mappings.items[0].status === "valid");
    await page.waitForFunction(() => document.querySelector(".coverage-summary")?.textContent.includes("1/1 ativos"));
    assert.match(await page.locator(".coverage-summary").innerText(), /1\/1 ativos/);
    await page.evaluate(() => { window.__backend.forceConflict = true; });
    await mapping.locator('[name="provider_coin_id"]').fill("bitcoin-new");
    await mapping.getByRole("button", { name: "Salvar mapeamento" }).click();
    await page.getByText("Versão alterada por outra sessão.").waitFor();
    const mutationRequests = await page.evaluate(() => window.__backend.requests.filter((request) =>
      ["POST", "PATCH", "PUT"].includes(request.method) && request.route !== "/api/v1/monitoring/cycles"));
    assert.ok(mutationRequests.every((request) => request.headers["Idempotency-Key"]));
    assert.ok(mutationRequests.filter((request) => request.method !== "POST").every((request) => request.headers["If-Match"]));
    const width = await page.evaluate(() => document.documentElement.scrollWidth);
    assert.ok(width <= 360, `a página ultrapassou o viewport: ${width}px`);
    const toastDoesNotBlock = await page.evaluate(() => {
      const host = document.createElement("div");
      host.className = "toast-region";
      host.append(document.createElement("article"));
      document.body.append(host);
      const result = getComputedStyle(host).pointerEvents === "none";
      host.remove();
      return result;
    });
    assert.ok(toastDoesNotBlock, "o toast não deve interceptar cliques nos formulários");
    if (process.env.BROWSER_SCREENSHOT_PATH) {
      await page.screenshot({ path: process.env.BROWSER_SCREENSHOT_PATH, fullPage: true });
    }
  } finally {
    await context.close();
  }
});
