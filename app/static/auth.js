(() => {
  "use strict";

  const emailInput = document.getElementById("login-email");
  const passwordInput = document.getElementById("login-password");
  const loginForm = document.getElementById("login-form");
  const loginContainer = document.getElementById("login-container");
  if (!emailInput || !passwordInput || !loginForm) return;

  const statusText = document.getElementById("session-status");
  const errorText = document.getElementById("auth-error");
  const logoutButton = document.getElementById("logout-button");
  const headerSettingsBtn = document.getElementById("header-settings-btn");
  const googleBtn = document.getElementById("google-login-btn");
  const togglePasswordBtn = document.getElementById("toggle-password");
  const appContent = document.getElementById("app-content");
  const googleClientId = document.querySelector('meta[name="google-client-id"]')?.content;

  const session = {
    tokens: null,
    refreshInFlight: null,
    refreshTimer: null,
    generation: 0,
  };

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
    if (window.SplashLoader && typeof window.SplashLoader.close === "function") {
      window.SplashLoader.close();
    }
    if (appContent) appContent.replaceChildren();
  }

  function renderSignedOut(message) {
    if (loginContainer) loginContainer.hidden = false;
    loginForm.hidden = false;
    if (logoutButton) logoutButton.hidden = true;
    if (headerSettingsBtn) headerSettingsBtn.hidden = true;
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
        : Date.now() + (Number.isFinite(expiresIn) ? expiresIn : 86400) * 1000,
    };
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    const refreshDelay = Math.max(0, session.tokens.expiresAt - Date.now() - 60000);
    session.refreshTimer = setTimeout(() => {
      refreshSession().catch(() => expireSession());
    }, refreshDelay);
    return true;
  }

  async function postJson(endpoint, data) {
    const response = await fetch(endpoint, {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const message = errData.detail?.error?.message || errData.detail?.error || "Erro na autenticação.";
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return response.json();
  }

  async function refreshSession() {
    if (session.refreshInFlight) return session.refreshInFlight;
    if (!session.tokens || !session.tokens.refreshToken) return false;
    const refreshToken = session.tokens.refreshToken;
    const generation = session.generation;
    const inFlight = (async () => {
      try {
        const payload = await postJson("/api/v1/auth/refresh", {
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
    session.generation += 1;
    session.tokens = null;
    session.refreshInFlight = null;
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    session.refreshTimer = null;
    clearPrivateState();
    renderSignedOut("Você saiu da sua conta.");
    notify("auth:signed-out");
  }

  async function signIn(email, password) {
    if (errorText) {
      errorText.hidden = true;
      errorText.textContent = "";
    }
    const submitBtn = loginForm.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn ? submitBtn.textContent : "Entrar";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Entrando…";
    }
    session.generation += 1;
    const generation = session.generation;
    session.tokens = null;
    session.refreshInFlight = null;
    if (session.refreshTimer !== null) clearTimeout(session.refreshTimer);
    session.refreshTimer = null;
    clearPrivateState();
    try {
      const payload = await postJson("/api/v1/auth/login", { email, password });
      passwordInput.value = "";
      if (!saveTokens(payload, generation)) {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = originalBtnText;
        }
        return;
      }
      if (loginContainer) loginContainer.hidden = true;
      loginForm.hidden = true;
      if (logoutButton) logoutButton.hidden = false;
      if (headerSettingsBtn) headerSettingsBtn.hidden = false;
      if (statusText) statusText.textContent = "Sessão autenticada.";
      clearPrivateState();
      notify("auth:authenticated");
    } catch (error) {
      passwordInput.value = "";
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
      if (generation !== session.generation) return;
      if (errorText) {
        errorText.textContent = error.message || "Não foi possível entrar. Confira suas credenciais.";
        errorText.hidden = false;
      }
    }
  }

  async function signInWithGoogle() {
    if (errorText) {
      errorText.hidden = true;
      errorText.textContent = "";
    }
    if (googleBtn) {
      googleBtn.disabled = true;
      googleBtn.classList.add("is-loading");
    }
    const redirectTo = `${window.location.origin}/`;
    try {
      let url = "";
      if (googleClientId) {
        const params = new URLSearchParams({
          client_id: googleClientId,
          redirect_uri: redirectTo,
          response_type: "code",
          scope: "openid email profile",
          access_type: "online",
          prompt: "select_account",
        });
        url = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
      } else {
        const res = await fetch(`/api/v1/auth/google/url?redirect_uri=${encodeURIComponent(redirectTo)}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail?.error?.message || "Google OAuth não configurado no servidor.");
        }
        const data = await res.json();
        url = data.url;
      }
      window.location.assign(url);
    } catch (err) {
      if (googleBtn) {
        googleBtn.disabled = false;
        googleBtn.classList.remove("is-loading");
      }
      if (errorText) {
        errorText.textContent = err.message || "Não foi possível iniciar o login com o Google.";
        errorText.hidden = false;
      }
    }
  }

  async function checkUrlSession() {
    const searchParams = new URLSearchParams(window.location.search || "");
    const errorParam = searchParams.get("error");
    const errorDesc = searchParams.get("error_description");

    if (errorParam || errorDesc) {
      window.history.replaceState(null, document.title, window.location.pathname);
      if (errorText) {
        errorText.textContent = errorDesc ? decodeURIComponent(errorDesc).replace(/\+/g, " ") : `Erro OAuth: ${errorParam}`;
        errorText.hidden = false;
      }
      return false;
    }

    const code = searchParams.get("code");
    if (code) {
      window.history.replaceState(null, document.title, window.location.pathname);
      if (statusText) statusText.textContent = "Concluindo login com Google…";
      const redirectTo = `${window.location.origin}/`;
      try {
        const payload = await postJson("/api/v1/auth/google", {
          code: code,
          redirect_uri: redirectTo,
        });
        session.generation += 1;
        if (saveTokens(payload, session.generation)) {
          if (loginContainer) loginContainer.hidden = true;
          loginForm.hidden = true;
          if (logoutButton) logoutButton.hidden = false;
          if (headerSettingsBtn) headerSettingsBtn.hidden = false;
          if (statusText) statusText.textContent = "Sessão autenticada.";
          clearPrivateState();
          notify("auth:authenticated");
          return true;
        }
      } catch (err) {
        if (errorText) {
          errorText.textContent = err.message || "Falha na validação do login Google.";
          errorText.hidden = false;
        }
      }
    }

    return false;
  }

  loginForm.addEventListener("submit", (event) => {
    event.preventDefault();
    signIn(emailInput.value.trim(), passwordInput.value);
  });

  if (googleBtn) {
    googleBtn.addEventListener("click", () => signInWithGoogle());
  }

  if (togglePasswordBtn && passwordInput) {
    togglePasswordBtn.addEventListener("click", () => {
      const isPassword = passwordInput.type === "password";
      passwordInput.type = isPassword ? "text" : "password";
      const eyeShow = togglePasswordBtn.querySelector(".eye-show");
      const eyeHide = togglePasswordBtn.querySelector(".eye-hide");
      if (eyeShow && eyeHide) {
        eyeShow.hidden = isPassword;
        eyeHide.hidden = !isPassword;
      }
    });
  }

  const devLogin = document.getElementById("dev-login");
  if (devLogin) {
    devLogin.addEventListener("click", () => {
      signIn(devLogin.dataset.email || "", devLogin.dataset.password || "");
    });
  }

  if (logoutButton) logoutButton.addEventListener("click", () => signOut());
  if (headerSettingsBtn) {
    headerSettingsBtn.addEventListener("click", () => {
      if (window.AiImport && typeof window.AiImport.openSettings === "function") {
        window.AiImport.openSettings();
      }
    });
  }

  checkUrlSession().then((hasSession) => {
    if (!hasSession && !session.tokens) {
      renderSignedOut();
    }
  });

  window.AppAuth = Object.freeze({
    fetch: authenticatedFetch,
    logout: signOut,
    hasSession: () => session.tokens !== null,
    signInWithGoogle,
  });
})();
