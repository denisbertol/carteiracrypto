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
  const googleBtn = document.getElementById("google-login-btn");
  const togglePasswordBtn = document.getElementById("toggle-password");
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
    if (window.SplashLoader && typeof window.SplashLoader.close === "function") {
      window.SplashLoader.close();
    }
    if (appContent) appContent.replaceChildren();
  }

  function renderSignedOut(message) {
    if (loginContainer) loginContainer.hidden = false;
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
      const payload = await authRequest("token?grant_type=password", { email, password });
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
      if (statusText) statusText.textContent = "Sessão autenticada.";
      clearPrivateState();
      notify("auth:authenticated");
    } catch (_error) {
      passwordInput.value = "";
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
      }
      if (generation !== session.generation) return;
      if (errorText) {
        errorText.textContent = "Não foi possível entrar. Confira suas credenciais e tente novamente.";
        errorText.hidden = false;
      }
    }
  }

  function base64UrlEncode(arrayBuffer) {
    const bytes = new Uint8Array(arrayBuffer);
    let binary = "";
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function generateCodeVerifier() {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return base64UrlEncode(bytes.buffer);
  }

  async function generateCodeChallenge(verifier) {
    const encoder = new TextEncoder();
    const data = encoder.encode(verifier);
    const hash = await window.crypto.subtle.digest("SHA-256", data);
    return base64UrlEncode(hash);
  }

  async function signInWithGoogle() {
    if (!supabaseUrl || !publishableKey) {
      if (errorText) {
        errorText.textContent = "Autenticação não configurada.";
        errorText.hidden = false;
      }
      return;
    }
    if (googleBtn) {
      googleBtn.disabled = true;
      googleBtn.classList.add("is-loading");
    }
    const redirectTo = `${window.location.origin}/`;
    try {
      if (window.crypto && window.crypto.subtle) {
        const verifier = generateCodeVerifier();
        sessionStorage.setItem("sb_auth_verifier", verifier);
        const challenge = await generateCodeChallenge(verifier);
        const url = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirectTo)}&code_challenge=${encodeURIComponent(challenge)}&code_challenge_method=s256`;
        window.location.assign(url);
        return;
      }
    } catch (_err) {
      // Fallback sem PKCE se SubtleCrypto falhar
    }
    const url = `${supabaseUrl}/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(redirectTo)}`;
    window.location.assign(url);
  }

  async function checkUrlSession() {
    const searchParams = new URLSearchParams(window.location.search || "");
    const hashParams = new URLSearchParams(window.location.hash ? window.location.hash.substring(1) : "");
    const getParam = (key) => hashParams.get(key) || searchParams.get(key);

    const errorParam = getParam("error");
    const errorDesc = getParam("error_description");

    if (errorParam || errorDesc) {
      window.history.replaceState(null, document.title, window.location.pathname);
      if (errorText) {
        let desc = errorDesc ? decodeURIComponent(errorDesc).replace(/\+/g, " ") : "Falha na autenticação com o Google.";
        if (desc.toLowerCase().includes("redirect") && desc.toLowerCase().includes("not allowed")) {
          desc = "URL de redirecionamento não autorizada no Supabase. Adicione o domínio do Koyeb nas Redirect URLs do projeto.";
        }
        errorText.textContent = desc;
        errorText.hidden = false;
      }
      return false;
    }

    const accessToken = getParam("access_token");
    const refreshToken = getParam("refresh_token");
    const expiresIn = getParam("expires_in");

    if (accessToken && refreshToken) {
      window.history.replaceState(null, document.title, window.location.pathname);
      sessionStorage.removeItem("sb_auth_verifier");
      session.generation += 1;
      const generation = session.generation;
      const payload = {
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_in: expiresIn ? Number(expiresIn) : 3600,
      };
      if (saveTokens(payload, generation)) {
        if (loginContainer) loginContainer.hidden = true;
        loginForm.hidden = true;
        if (logoutButton) logoutButton.hidden = false;
        if (statusText) statusText.textContent = "Sessão autenticada.";
        clearPrivateState();
        notify("auth:authenticated");
        return true;
      }
    }

    const code = getParam("code");
    if (code) {
      window.history.replaceState(null, document.title, window.location.pathname);
      const verifier = sessionStorage.getItem("sb_auth_verifier");
      sessionStorage.removeItem("sb_auth_verifier");
      if (statusText) statusText.textContent = "Concluindo login com Google…";
      try {
        const body = verifier
          ? { auth_code: code, code_verifier: verifier }
          : { auth_code: code };
        const res = await fetch(`${supabaseUrl}/auth/v1/token?grant_type=pkce`, {
          method: "POST",
          headers: {
            apikey: publishableKey,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.msg || errData.error_description || "Não foi possível validar o código de autenticação.");
        }
        const data = await res.json();
        session.generation += 1;
        if (saveTokens(data, session.generation)) {
          if (loginContainer) loginContainer.hidden = true;
          loginForm.hidden = true;
          if (logoutButton) logoutButton.hidden = false;
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
