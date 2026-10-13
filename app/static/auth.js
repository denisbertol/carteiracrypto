(() => {
  "use strict";

  const emailInput = document.getElementById("login-email");
  const passwordInput = document.getElementById("login-password");
  const loginForm = document.getElementById("login-form");
  if (!emailInput || !passwordInput || !loginForm) return;

  const statusText = document.getElementById("session-status");
  const errorText = document.getElementById("auth-error");
  const logoutButton = document.getElementById("logout-button");
  const appContent = document.getElementById("app-content");
  const supabaseUrl = document.querySelector('meta[name="supabase-url"]')?.content?.replace(/\/$/, "");
  const publishableKey = document.querySelector('meta[name="supabase-publishable-key"]')?.content;

  const session = {
    tokens: null,
    refreshInFlight: null,
    refreshTimer: null,
    generation: 0,
  };

  function authUrl(path) {
    return `${supabaseUrl}/auth/v1/${path}`;
  }

  function notify(name) {
    document.dispatchEvent(new CustomEvent(name));
  }

  function clearPrivateState() {
    if (window.Monitoring && typeof window.Monitoring.stop === "function") {
      window.Monitoring.stop();
    }
    if (window.Targets && typeof window.Targets.clear === "function") {
      window.Targets.clear();
    }
    if (window.Portfolio && typeof window.Portfolio.clear === "function") {
      window.Portfolio.clear();
    }
    if (appContent) appContent.replaceChildren();
  }

  function renderSignedOut(message) {
    loginForm.hidden = false;
    if (logoutButton) logoutButton.hidden = true;
    if (statusText) statusText.textContent = message || "Entre para consultar sua carteira.";
  }

  function expireSession() {
    const hadSession = session.tokens !== null;
    session.generation += 1;
    session.tokens = null;
    session.refreshInFlight = null;
    if (session.refreshTimer !== null) {
      clearTimeout(session.refreshTimer);
      session.refreshTimer = null;
    }
    clearPrivateState();
    renderSignedOut("Sessão expirada. Entre novamente.");
    if (hadSession) notify("auth:expired");
  }

  function saveTokens(payload, generation = session.generation) {
    if (generation !== session.generation) return false;
    if (!payload || typeof payload.access_token !== "string" || typeof payload.refresh_token !== "string") {
      throw new Error("Resposta de sessão inválida.");
    }
    const absoluteExpiry = Number(payload.expires_at) * 1000;
    const expiresIn = Number(payload.expires_in);
    session.tokens = {
      accessToken: payload.access_token,
      refreshToken: payload.refresh_token,
      expiresAt: Number.isFinite(absoluteExpiry) && absoluteExpiry > 0
        ? absoluteExpiry
        : Date.now() + (Number.isFinite(expiresIn) ? expiresIn : 3600) * 1000,
    };
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    const refreshDelay = Math.max(0, session.tokens.expiresAt - Date.now() - 60000);
    session.refreshTimer = setTimeout(() => {
      refreshSession().catch(() => expireSession());
    }, refreshDelay);
    return true;
  }

  async function authRequest(path, payload) {
    if (!supabaseUrl || !publishableKey) throw new Error("Autenticação não configurada.");
    const response = await fetch(authUrl(path), {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      headers: {
        apikey: publishableKey,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Não foi possível autenticar a sessão.");
    return response.json();
  }

  async function refreshSession() {
    if (session.refreshInFlight) return session.refreshInFlight;
    if (!session.tokens || !session.tokens.refreshToken) return false;
    const refreshToken = session.tokens.refreshToken;
    const generation = session.generation;
    const inFlight = (async () => {
      try {
        const payload = await authRequest("token?grant_type=refresh_token", {
          refresh_token: refreshToken,
        });
        if (generation !== session.generation || session.tokens?.refreshToken !== refreshToken) {
          return false;
        }
        return saveTokens(payload, generation);
      } catch (_error) {
        if (generation === session.generation) expireSession();
        return false;
      } finally {
        if (session.refreshInFlight === inFlight) session.refreshInFlight = null;
      }
    })();
    session.refreshInFlight = inFlight;
    return inFlight;
  }

  async function currentAccessToken() {
    if (!session.tokens) return null;
    if (session.tokens.expiresAt <= Date.now() + 60000) {
      const refreshed = await refreshSession();
      if (!refreshed) return null;
    }
    return session.tokens?.accessToken || null;
  }

  async function authenticatedFetch(url, options) {
    const generation = session.generation;
    const token = await currentAccessToken();
    if (!token || generation !== session.generation) throw new Error("Sessão expirada.");
    const requestOptions = { ...(options || {}), cache: "no-store", credentials: "omit" };
    const headers = new Headers(requestOptions.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    requestOptions.headers = headers;
    const response = await fetch(url, requestOptions);
    if (generation !== session.generation) throw new Error("Sessão encerrada.");
    if (response.status !== 401) return response;

    const refreshed = await refreshSession();
    if (!refreshed || generation !== session.generation) throw new Error("Sessão expirada.");
    const retryHeaders = new Headers((options && options.headers) || {});
    retryHeaders.set("Authorization", `Bearer ${session.tokens.accessToken}`);
    const retry = await fetch(url, {
      ...(options || {}),
      headers: retryHeaders,
      cache: "no-store",
      credentials: "omit",
    });
    if (generation !== session.generation) throw new Error("Sessão encerrada.");
    if (retry.status === 401) {
      expireSession();
      throw new Error("Sessão expirada.");
    }
    return retry;
  }

  async function signOut() {
    const tokens = session.tokens;
    session.generation += 1;
    session.tokens = null;
    session.refreshInFlight = null;
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    session.refreshTimer = null;
    clearPrivateState();
    renderSignedOut("Você saiu da sua conta.");
    notify("auth:signed-out");
    if (tokens && supabaseUrl && publishableKey) {
      try {
        await fetch(authUrl("logout"), {
          method: "POST",
          cache: "no-store",
          credentials: "omit",
          headers: {
            apikey: publishableKey,
            Authorization: `Bearer ${tokens.accessToken}`,
          },
        });
      } catch (_error) {
        // Clearing the in-memory session is sufficient when logout is offline.
      }
    }
  }

  async function signIn(email, password) {
    if (errorText) {
      errorText.hidden = true;
      errorText.textContent = "";
    }
    session.generation += 1;
    const generation = session.generation;
    session.tokens = null;
    session.refreshInFlight = null;
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    session.refreshTimer = null;
    clearPrivateState();
    try {
      const payload = await authRequest("token?grant_type=password", { email, password });
      passwordInput.value = "";
      if (!saveTokens(payload, generation)) return;
      loginForm.hidden = true;
      if (logoutButton) logoutButton.hidden = false;
      if (statusText) statusText.textContent = "Sessão autenticada.";
      clearPrivateState();
      notify("auth:authenticated");
    } catch (_error) {
      passwordInput.value = "";
      if (generation !== session.generation) return;
      if (errorText) {
        errorText.textContent = "Não foi possível entrar. Confira suas credenciais e tente novamente.";
        errorText.hidden = false;
      }
    }
  }

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    signIn(emailInput.value.trim(), passwordInput.value);
  });

  const devLogin = document.getElementById("dev-login");
  if (devLogin) {
    devLogin.addEventListener("click", () => {
      signIn(devLogin.dataset.email || "", devLogin.dataset.password || "");
    });
  }

  if (logoutButton) logoutButton.addEventListener("click", () => signOut());
  renderSignedOut();

  window.AppAuth = Object.freeze({
    fetch: authenticatedFetch,
    logout: signOut,
    hasSession: () => session.tokens !== null,
  });
})();
