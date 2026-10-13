(() => {
  "use strict";

  const splash = document.getElementById("splash");
  const video = document.getElementById("splash-video");
  const progressBar = document.getElementById("splash-progress-bar");
  const progressTrack = document.querySelector(".splash-progress-track");
  const statusText = document.getElementById("splash-status-text");

  let active = false;
  let finishTimer = null;
  let closeTimer = null;
  let startedAt = 0;
  const MIN_SPLASH_MS = 2500;

  function setProgress(percent, message) {
    const clamped = Math.max(0, Math.min(100, Math.round(percent)));
    if (progressBar) {
      progressBar.style.width = `${clamped}%`;
    }
    if (progressTrack) {
      progressTrack.setAttribute("aria-valuenow", String(clamped));
    }
    if (statusText && typeof message === "string") {
      statusText.textContent = message;
    }
  }

  function start() {
    if (!splash || !video) return;
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    active = true;
    startedAt = Date.now();
    if (finishTimer) { clearTimeout(finishTimer); finishTimer = null; }
    if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }

    splash.classList.remove("is-leaving");
    splash.hidden = false;
    splash.setAttribute("aria-hidden", "false");
    document.body.classList.add("has-splash");

    setProgress(15, "Iniciando sessão e conectando…");

    try {
      video.currentTime = 0;
      video.volume = 0.5;
    } catch (_e) {}

    video.playsInline = true;
    const playPromise = video.play();
    if (playPromise && playPromise.catch) {
      playPromise.catch(() => {
        video.muted = true;
        const retry = video.play();
        if (retry && retry.catch) {
          retry.catch(() => {
            // Continua exibindo a barra de carregamento mesmo se vídeo falhar
          });
        }
      });
    }
  }

  function finish() {
    if (!active || !splash) return;
    setProgress(100, "Carteira pronta!");

    const elapsed = Date.now() - startedAt;
    const delay = Math.max(450, MIN_SPLASH_MS - elapsed);
    finishTimer = setTimeout(() => {
      close();
    }, delay);
  }

  function error(message) {
    if (!active || !splash) return;
    setProgress(100, message || "Erro ao carregar dados.");
    finishTimer = setTimeout(() => {
      close();
    }, 1200);
  }

  function close() {
    if (!splash) return;
    active = false;
    if (finishTimer) { clearTimeout(finishTimer); finishTimer = null; }
    if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }

    splash.classList.add("is-leaving");
    splash.setAttribute("aria-hidden", "true");
    document.body.classList.remove("has-splash");

    if (video) {
      try {
        video.pause();
      } catch (_e) {}
    }

    closeTimer = setTimeout(() => {
      splash.hidden = true;
      splash.classList.remove("is-leaving");
      if (progressBar) progressBar.style.width = "0%";
    }, 420);
  }

  document.addEventListener("keydown", (event) => {
    if ((event.key === "Escape" || event.key === " ") && active) {
      close();
    }
  });

  if (splash) {
    splash.addEventListener("click", () => {
      if (active) close();
    });
  }

  if (video) {
    // Se o vídeo atingir o fim antes dos dados terminarem, mantém em loop suave
    video.addEventListener("ended", () => {
      if (active) {
        video.currentTime = 0;
        video.play().catch(() => {});
      }
    });
  }

  window.SplashLoader = Object.freeze({
    start,
    setProgress,
    finish,
    error,
    close,
    isActive: () => active,
  });
})();
