/**
 * MAVUNQO Standalone / Home-Screen Navigation & Pull-to-Refresh
 * Adds 1-tap Back + Refresh controls and touch swipe-down Pull-to-Refresh
 * so saved Home Screen / Desktop App shortcuts never get stuck.
 */
(function () {
  if (window.__mavunqoPwaNavInit) return;
  window.__mavunqoPwaNavInit = true;

  // Ensure PWA manifest link and Service Worker registration across all pages
  if (!document.querySelector('link[rel="manifest"]')) {
    const link = document.createElement("link");
    link.rel = "manifest";
    link.href = "/frontend/manifest.json";
    document.head.appendChild(link);
  }
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/frontend/sw.js", { scope: "/" }).catch(() => {});
    });
  }

  let deferredInstallPrompt = null;

  function isStandaloneMode() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function isIOSDevice() {
    return /iphone|ipad|ipod/i.test(navigator.userAgent || "") && !window.MSStream;
  }

  function getInstallLabel() {
    const lang = (localStorage.getItem("mavunqo_lang") || "en").toLowerCase();
    return lang === "es" ? "📲 Agregar a Inicio" : "📲 Add to Home Screen";
  }

  function showInstallGuideModal(mode) {
    const existing = document.getElementById("mvqInstallModal");
    if (existing) existing.remove();

    const lang = (localStorage.getItem("mavunqo_lang") || "en").toLowerCase();
    const isEs = lang === "es";

    const title = isEs ? "Instalar Mavunqo en tu Teléfono" : "Add Mavunqo to Your Home Screen";
    let stepsHtml = "";
    if (mode === "ios") {
      stepsHtml = isEs
        ? `<ol style="margin:0.75rem 0 0 1.2rem;padding:0;line-height:1.6;">
             <li>Toca el botón <strong>Compartir</strong> (el ícono con flecha hacia arriba) en Safari.</li>
             <li>Desliza hacia abajo y toca <strong>"Agregar a inicio"</strong>.</li>
             <li>Toca <strong>"Agregar"</strong> arriba a la derecha.</li>
           </ol>
           <p style="margin:0.75rem 0 0;padding:8px 10px;background:#f0fdfa;border-left:3px solid #0d9488;border-radius:6px;font-size:0.84rem;color:#0f172a;">
             <strong>¿Dónde queda el ícono?</strong> Aparecerá automáticamente en el siguiente espacio libre de tu pantalla de inicio (o deslizando hacia la última página).
           </p>`
        : `<ol style="margin:0.75rem 0 0 1.2rem;padding:0;line-height:1.6;">
             <li>Tap the <strong>Share</strong> button (square with up arrow) in Safari's toolbar.</li>
             <li>Scroll down and tap <strong>"Add to Home Screen"</strong>.</li>
             <li>Tap <strong>"Add"</strong> in the top-right corner.</li>
           </ol>
           <p style="margin:0.75rem 0 0;padding:8px 10px;background:#f0fdfa;border-left:3px solid #0d9488;border-radius:6px;font-size:0.84rem;color:#0f172a;">
             <strong>Where to find it:</strong> The icon drops into the next open spot on your Home Screen (check your last Home Screen page or swipe to the App Library).
           </p>`;
    } else {
      stepsHtml = isEs
        ? `<ol style="margin:0.75rem 0 0 1.2rem;padding:0;line-height:1.6;">
             <li>Abre el menú de tu navegador (<strong>⋮</strong> o <strong>⋯</strong>).</li>
             <li>Selecciona <strong>"Instalar aplicación"</strong> o <strong>"Agregar a la pantalla principal"</strong>.</li>
           </ol>
           <p style="margin:0.75rem 0 0;padding:8px 10px;background:#f0fdfa;border-left:3px solid #0d9488;border-radius:6px;font-size:0.84rem;color:#0f172a;">
             <strong>¿Dónde queda el ícono?</strong> En Android aparece en tu última pantalla de inicio y en el cajón de apps; en PC se guarda en tu Escritorio o menú de Aplicaciones.
           </p>`
        : `<ol style="margin:0.75rem 0 0 1.2rem;padding:0;line-height:1.6;">
             <li>Open your browser menu (<strong>⋮</strong> or <strong>⋯</strong>).</li>
             <li>Tap <strong>"Install app"</strong> or <strong>"Add to Home screen"</strong>.</li>
           </ol>
           <p style="margin:0.75rem 0 0;padding:8px 10px;background:#f0fdfa;border-left:3px solid #0d9488;border-radius:6px;font-size:0.84rem;color:#0f172a;">
             <strong>Where to find it:</strong> On Android it appears on your next open Home Screen page and in your App Drawer; on desktop it saves to your Desktop or Apps list.
           </p>`;
    }

    const overlay = document.createElement("div");
    overlay.id = "mvqInstallModal";
    overlay.style.cssText =
      "position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,0.55);display:flex;align-items:center;justify-content:center;padding:16px;";
    overlay.innerHTML = `
      <div style="background:#ffffff;color:#0f172a;max-width:380px;width:100%;border-radius:16px;padding:20px;box-shadow:0 16px 40px rgba(0,0,0,0.22);font-family:inherit;">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
          <strong style="font-size:1.05rem;">📲 ${title}</strong>
          <button type="button" id="mvqInstallModalClose" aria-label="Close" style="border:none;background:#f1f5f9;color:#0f172a;width:30px;height:30px;border-radius:999px;font-weight:700;cursor:pointer;">✕</button>
        </div>
        <div style="font-size:0.92rem;color:#334155;">${stepsHtml}</div>
        <button type="button" id="mvqInstallModalOk" style="margin-top:16px;width:100%;padding:10px 14px;border:none;border-radius:999px;background:#0d9488;color:#fff;font-weight:700;cursor:pointer;">
          ${isEs ? "Entendido" : "Got it"}
        </button>
      </div>
    `;
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) overlay.remove();
    });
    document.body.appendChild(overlay);
    document.getElementById("mvqInstallModalClose").onclick = function () { overlay.remove(); };
    document.getElementById("mvqInstallModalOk").onclick = function () { overlay.remove(); };
  }

  async function handleInstallClick() {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      try {
        const choice = await deferredInstallPrompt.userChoice;
        if (choice && choice.outcome === "accepted") {
          const btn = document.getElementById("mvqInstallAppBtn");
          if (btn) btn.style.display = "none";
        }
      } catch (_) {}
      deferredInstallPrompt = null;
      return;
    }
    showInstallGuideModal(isIOSDevice() ? "ios" : "generic");
  }

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredInstallPrompt = e;
    const btn = document.getElementById("mvqInstallAppBtn");
    if (btn && !isStandaloneMode()) {
      btn.style.display = "inline-flex";
    }
  });

  window.addEventListener("appinstalled", function () {
    deferredInstallPrompt = null;
    const btn = document.getElementById("mvqInstallAppBtn");
    if (btn) btn.style.display = "none";
    const es = (localStorage.getItem("mavunqo_lang") || "en").toLowerCase() === "es";
    const toast = document.createElement("div");
    toast.style.cssText =
      "position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:10001;background:#0f172a;color:#fff;padding:12px 18px;border-radius:12px;font-size:0.88rem;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,0.28);max-width:90vw;text-align:center;";
    toast.textContent = es
      ? "✅ ¡Instalado! Busca el ícono en tu pantalla de inicio o cajón de apps (en PC: Escritorio)."
      : "✅ Installed! Find the icon on your phone's Home Screen / App Drawer (or Desktop on PC).";
    document.body.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 6000);
  });

  function triggerRefresh() {
    window.location.reload();
  }

  function triggerBack() {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = "/";
    }
  }

  function injectButtons() {
    if (document.getElementById("mvqQuickNavBar")) return;
    if (!document.getElementById("mvqBannerAnimStyle")) {
      const st = document.createElement("style");
      st.id = "mvqBannerAnimStyle";
      st.textContent =
        "@keyframes mvqPulseGlow{0%,100%{box-shadow:0 0 0 0 rgba(234,88,12,0.65),0 4px 14px rgba(15,23,42,0.25);}50%{box-shadow:0 0 0 8px rgba(234,88,12,0),0 6px 18px rgba(234,88,12,0.45);}}";
      document.head.appendChild(st);
    }
    const navbar = document.querySelector(".navbar");
    const lang = (localStorage.getItem("mavunqo_lang") || "en").toLowerCase();
    const isEs = lang === "es";
    const isFr = lang === "fr";
    const pick = function (en, es, fr) { return isEs ? es : (isFr ? fr : en); };

    const bar = document.createElement("div");
    bar.id = "mvqQuickNavBar";
    bar.style.cssText =
      "display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:12px;padding:12px 18px;background:linear-gradient(90deg,#fef08a 0%,#fde047 55%,#99f6e4 100%);border-top:2px solid #0f172a;border-bottom:3px solid #0f172a;box-shadow:0 4px 14px rgba(15,23,42,0.12);";

    const bannerMsg = document.createElement("div");
    bannerMsg.id = "mvqBannerGreeting";
    bannerMsg.style.cssText =
      "display:inline-flex;align-items:center;gap:10px;font-size:0.95rem;font-weight:900;color:#0f172a;";
    bannerMsg.innerHTML =
      `<span style="display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;background:#0f172a;color:#fef08a;box-shadow:0 2px 6px rgba(15,23,42,0.3);">` +
      `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>` +
      `</span>` +
      `<span>${pick(
        "Mavunqo Express — Put our app on your Home Screen for 1-tap ordering & offline access!",
        "Mavunqo Express — ¡Instala la App en tu teléfono para pedir en 1 toque y navegar sin conexión!",
        "Mavunqo Express — Installez l'app sur votre écran d'accueil pour commander en 1 clic et hors ligne !"
      )}</span>`;
    bar.appendChild(bannerMsg);

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;flex-wrap:wrap;align-items:center;gap:8px;";

    if (window.location.pathname !== "/") {
      const backBtn = document.createElement("button");
      backBtn.id = "mvqNavBackBtn";
      backBtn.type = "button";
      backBtn.className = "btn btn-outline btn-sm";
      backBtn.title = pick("Go Back", "Volver", "Retour");
      backBtn.innerHTML =
        `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>` +
        `<span>${pick("Back", "Atrás", "Retour")}</span>`;
      backBtn.style.cssText =
        "display:inline-flex;align-items:center;gap:6px;padding:0.4rem 0.9rem;font-weight:700;border-radius:999px;";
      backBtn.onclick = triggerBack;
      actions.appendChild(backBtn);
    }

    const refBtn = document.createElement("button");
    refBtn.id = "mvqNavRefreshBtn";
    refBtn.type = "button";
    refBtn.className = "btn btn-outline btn-sm";
    refBtn.title = pick("Refresh Page", "Actualizar página", "Actualiser");
    refBtn.innerHTML =
      `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>` +
      `<span>${pick("Refresh", "Actualizar", "Actualiser")}</span>`;
    refBtn.style.cssText =
      "display:inline-flex;align-items:center;gap:6px;padding:0.4rem 0.9rem;font-weight:700;border-radius:999px;";
    refBtn.onclick = triggerRefresh;
    actions.appendChild(refBtn);

    if (!isStandaloneMode()) {
      const installBtn = document.createElement("button");
      installBtn.id = "mvqInstallAppBtn";
      installBtn.type = "button";
      installBtn.className = "btn btn-sm";
      installBtn.title = pick("Add Mavunqo to your phone's Home Screen", "Agregar Mavunqo a tu pantalla de inicio", "Ajouter Mavunqo à l'écran d'accueil");
      installBtn.innerHTML =
        `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><path d="M12 8v7"/><path d="M9 12l3 3 3-3"/></svg>` +
        `<span>${pick("Install Mavunqo", "Instalar Mavunqo", "Installer Mavunqo")}</span>` +
        `<span style="background:#facc15;color:#0f172a;font-size:0.7rem;font-weight:900;padding:2px 7px;border-radius:999px;letter-spacing:0.03em;text-transform:uppercase;">${pick("1-Tap", "1 Toque", "1 Clic")}</span>`;
      installBtn.style.cssText =
        "display:inline-flex;align-items:center;gap:8px;padding:0.55rem 1.25rem;font-size:0.95rem;font-weight:900;border-radius:999px;background:linear-gradient(135deg,#ea580c 0%,#dc2626 100%);color:#ffffff;border:2.5px solid #0f172a;cursor:pointer;animation:mvqPulseGlow 2s infinite;transition:transform 0.15s ease;";
      installBtn.onmouseenter = function () { installBtn.style.transform = "translateY(-1px)"; };
      installBtn.onmouseleave = function () { installBtn.style.transform = "translateY(0)"; };
      installBtn.onclick = handleInstallClick;
      actions.appendChild(installBtn);
    }

    const shareBtn = document.createElement("button");
    shareBtn.id = "mvqShareAppBtn";
    shareBtn.type = "button";
    shareBtn.className = "btn btn-outline btn-sm";
    shareBtn.title = pick("Share Mavunqo link or QR code", "Compartir enlace o código QR", "Partager le lien ou code QR");
    shareBtn.innerHTML =
      `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>` +
      `<span>${pick("Share", "Compartir", "Partager")}</span>`;
    shareBtn.style.cssText =
      "display:inline-flex;align-items:center;gap:6px;padding:0.4rem 0.9rem;font-weight:700;border-radius:999px;background:#ffffff;color:#0f172a;border:1.5px solid #0f172a;cursor:pointer;";
    shareBtn.onclick = async function () {
      const shareUrl = window.location.origin + "/";
      const shareText = pick(
        "Check out Mavunqo — local services, food, spas & vets in Sosúa & Puerto Plata:",
        "Mira Mavunqo — servicios locales, comida, spas y veterinarios en Sosúa y Puerto Plata:",
        "Découvrez Mavunqo — services locaux, restaurants, spas et vétérinaires à Sosúa & Puerto Plata :"
      );
      if (navigator.share) {
        try { await navigator.share({ title: "Mavunqo", text: shareText, url: shareUrl }); return; } catch (_) {}
      }
      const waShareUrl = "https://wa.me/?text=" + encodeURIComponent(shareText + " " + shareUrl);
      const modal = document.createElement("div");
      modal.style.cssText = "position:fixed;inset:0;z-index:10000;background:rgba(15,23,42,0.55);display:flex;align-items:center;justify-content:center;padding:16px;";
      modal.innerHTML = `
        <div style="background:#fff;color:#0f172a;max-width:360px;width:100%;border-radius:16px;padding:20px;box-shadow:0 16px 40px rgba(0,0,0,0.22);text-align:center;">
          <strong style="font-size:1.05rem;">${pick("Share Mavunqo", "Compartir Mavunqo", "Partager Mavunqo")}</strong>
          <div style="margin:12px auto;"><img src="/frontend/qr_sticker_mavunqo.svg" alt="Mavunqo QR" style="width:140px;height:140px;border-radius:10px;border:1px solid #e2e8f0;"></div>
          <div style="display:flex;flex-direction:column;gap:8px;">
            <a href="${waShareUrl}" target="_blank" rel="noopener noreferrer" style="padding:10px;border-radius:999px;background:#16a34a;color:#fff;font-weight:700;text-decoration:none;">💬 ${pick("Send via WhatsApp", "Enviar por WhatsApp", "Envoyer par WhatsApp")}</a>
            <button type="button" id="mvqCopyShareLink" style="padding:10px;border-radius:999px;background:#0d9488;color:#fff;font-weight:700;border:none;cursor:pointer;">🔗 ${pick("Copy Link", "Copiar Enlace", "Copier le lien")}</button>
            <button type="button" id="mvqCloseShareModal" style="padding:8px;border-radius:999px;background:#f1f5f9;color:#0f172a;font-weight:700;border:none;cursor:pointer;">${pick("Close", "Cerrar", "Fermer")}</button>
          </div>
        </div>`;
      modal.onclick = function (e) { if (e.target === modal) modal.remove(); };
      document.body.appendChild(modal);
      document.getElementById("mvqCopyShareLink").onclick = async function () {
        try { await navigator.clipboard.writeText(shareUrl); this.textContent = "✓ Copied!"; } catch (_) {}
      };
      document.getElementById("mvqCloseShareModal").onclick = function () { modal.remove(); };
    };
    actions.appendChild(shareBtn);

    const waBtn = document.createElement("a");
    waBtn.id = "mvqWhatsAppHelpBtn";
    waBtn.href = "https://wa.me/18299414894?text=" + encodeURIComponent(
      pick("Hi Mavunqo, I need help with the platform.", "Hola Mavunqo, necesito ayuda con la plataforma.", "Bonjour Mavunqo, j'ai besoin d'aide avec la plateforme.")
    );
    waBtn.target = "_blank";
    waBtn.rel = "noopener noreferrer";
    waBtn.className = "btn btn-outline btn-sm";
    waBtn.title = pick("Quick WhatsApp Support", "Soporte rápido por WhatsApp", "Support WhatsApp rapide");
    waBtn.innerHTML =
      `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>` +
      `<span>${pick("WhatsApp Help", "Ayuda WhatsApp", "Aide WhatsApp")}</span>`;
    waBtn.style.cssText =
      "display:inline-flex;align-items:center;gap:7px;padding:0.4rem 0.95rem;font-weight:700;border-radius:999px;border:1.5px solid #16a34a;color:#15803d;background:#f0fdf4;text-decoration:none;";
    actions.appendChild(waBtn);

    const statusPill = document.createElement("span");
    statusPill.id = "mvqOfflinePill";
    statusPill.style.cssText =
      "display:none;align-items:center;gap:6px;padding:0.35rem 0.9rem;font-size:0.8rem;font-weight:700;border-radius:999px;";
    actions.appendChild(statusPill);

    bar.appendChild(actions);

    function updateNetworkPill(justReconnected) {
      const es = (localStorage.getItem("mavunqo_lang") || "en").toLowerCase() === "es";
      if (!navigator.onLine) {
        statusPill.style.display = "inline-flex";
        statusPill.style.background = "#fef3c7";
        statusPill.style.color = "#92400e";
        statusPill.style.border = "1px solid #f59e0b";
        statusPill.innerHTML =
          `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="1" y1="1" x2="23" y2="23"/><path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55"/><path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>` +
          `<span>${es ? "Sin conexión (Modo Caché)" : "Offline (Cached View)"}</span>`;
      } else if (justReconnected) {
        statusPill.style.display = "inline-flex";
        statusPill.style.background = "#dcfce7";
        statusPill.style.color = "#166534";
        statusPill.style.border = "1px solid #22c55e";
        statusPill.innerHTML =
          `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>` +
          `<span>${es ? "Conectado de nuevo" : "Back Online"}</span>`;
        setTimeout(function () {
          if (navigator.onLine) statusPill.style.display = "none";
        }, 3000);
      } else {
        statusPill.style.display = "none";
      }
    }

    updateNetworkPill(false);
    window.addEventListener("offline", function () { updateNetworkPill(false); });
    window.addEventListener("online", function () { updateNetworkPill(true); });

    if (navbar && navbar.parentNode) {
      navbar.parentNode.insertBefore(bar, navbar.nextSibling);
    } else {
      document.body.insertBefore(bar, document.body.firstChild);
    }
  }

  function setupPullToRefresh() {
    let startY = 0;
    let pulling = false;
    let pullDist = 0;

    const pill = document.createElement("div");
    pill.id = "mvqPtrPill";
    pill.style.cssText =
      "position:fixed;top:-52px;left:50%;transform:translateX(-50%);z-index:9999;background:#0f172a;color:#fff;padding:7px 16px;border-radius:999px;font-size:0.82rem;font-weight:800;box-shadow:0 4px 14px rgba(0,0,0,0.25);transition:top 0.15s ease;pointer-events:none;";
    pill.textContent = "↓ Pull down to refresh";
    document.body.appendChild(pill);

    document.addEventListener(
      "touchstart",
      function (e) {
        if (window.scrollY > 2 || e.touches.length !== 1) return;
        const target = e.target;
        if (target && target.closest && target.closest(".leaflet-container")) return;
        startY = e.touches[0].clientY;
        pulling = true;
        pullDist = 0;
      },
      { passive: true }
    );

    document.addEventListener(
      "touchmove",
      function (e) {
        if (!pulling || e.touches.length !== 1) return;
        pullDist = e.touches[0].clientY - startY;
        if (pullDist > 18 && window.scrollY <= 2) {
          const topPos = Math.min(18, pullDist * 0.35 - 32);
          pill.style.top = topPos + "px";
          pill.textContent = pullDist > 75 ? "↻ Release to refresh" : "↓ Pull down to refresh";
        }
      },
      { passive: true }
    );

    document.addEventListener(
      "touchend",
      function () {
        if (!pulling) return;
        pulling = false;
        if (pullDist > 75 && window.scrollY <= 2) {
          pill.style.top = "18px";
          pill.textContent = "↻ Refreshing...";
          triggerRefresh();
        } else {
          pill.style.top = "-52px";
        }
        pullDist = 0;
      },
      { passive: true }
    );
  }

  function setupMobileLangDropdown() {
    const sw = document.querySelector(".lang-switch");
    if (!sw || sw.querySelector(".mvq-lang-select")) return;
    const btns = Array.from(sw.querySelectorAll(".lang-btn"));
    if (!btns.length) return;

    const sel = document.createElement("select");
    sel.className = "mvq-lang-select";
    sel.setAttribute("aria-label", "Language");

    btns.forEach(function (btn, idx) {
      const opt = document.createElement("option");
      const code = (btn.dataset && btn.dataset.lang) || btn.textContent.trim().toUpperCase();
      opt.value = String(idx);
      opt.textContent = "🌐 " + code;
      if (btn.classList.contains("active")) opt.selected = true;
      sel.appendChild(opt);
    });

    sel.addEventListener("change", function () {
      const targetBtn = btns[parseInt(sel.value, 10)];
      if (targetBtn) targetBtn.click();
    });

    // Keep select synced if active button changes programmatically
    btns.forEach(function (btn, idx) {
      btn.addEventListener("click", function () {
        sel.value = String(idx);
      });
    });

    sw.appendChild(sel);
  }

  function init() {
    injectButtons();
    setupMobileLangDropdown();
    setupPullToRefresh();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
