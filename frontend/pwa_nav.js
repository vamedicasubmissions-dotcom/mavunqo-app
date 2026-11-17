/**
 * MAVUNQO Standalone / Home-Screen Navigation & Pull-to-Refresh
 * Adds 1-tap Back + Refresh controls and touch swipe-down Pull-to-Refresh
 * so saved Home Screen / Desktop App shortcuts never get stuck.
 */
(function () {
  if (window.__mavunqoPwaNavInit) return;
  window.__mavunqoPwaNavInit = true;

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
    const navActions = document.querySelector(".nav-actions");
    if (navActions) {
      if (!document.getElementById("mvqNavBackBtn") && window.location.pathname !== "/") {
        const backBtn = document.createElement("button");
        backBtn.id = "mvqNavBackBtn";
        backBtn.type = "button";
        backBtn.className = "btn btn-outline-white btn-sm";
        backBtn.title = "Go Back";
        backBtn.textContent = "←";
        backBtn.style.cssText = "padding: 0.25rem 0.55rem; font-weight: 800;";
        backBtn.onclick = triggerBack;
        navActions.insertBefore(backBtn, navActions.firstChild);
      }
      if (!document.getElementById("mvqNavRefreshBtn")) {
        const refBtn = document.createElement("button");
        refBtn.id = "mvqNavRefreshBtn";
        refBtn.type = "button";
        refBtn.className = "btn btn-outline-white btn-sm";
        refBtn.title = "Refresh Page";
        refBtn.textContent = "↻ Refresh";
        refBtn.style.cssText = "padding: 0.25rem 0.6rem; font-weight: 700;";
        refBtn.onclick = triggerRefresh;
        navActions.insertBefore(refBtn, navActions.firstChild);
      }
    } else if (!document.getElementById("mvqFloatingNav")) {
      const wrap = document.createElement("div");
      wrap.id = "mvqFloatingNav";
      wrap.style.cssText =
        "position:fixed;bottom:14px;left:14px;z-index:9990;display:flex;gap:6px;background:rgba(15,23,42,0.88);padding:5px 8px;border-radius:999px;box-shadow:0 4px 12px rgba(0,0,0,0.22);";
      wrap.innerHTML =
        '<button type="button" id="mvqFloatBack" style="background:none;border:none;color:#fff;font-weight:800;font-size:0.85rem;cursor:pointer;padding:2px 6px;">← Back</button>' +
        '<button type="button" id="mvqFloatRef" style="background:none;border:none;color:#38bdf8;font-weight:800;font-size:0.85rem;cursor:pointer;padding:2px 6px;">↻ Refresh</button>';
      document.body.appendChild(wrap);
      document.getElementById("mvqFloatBack").onclick = triggerBack;
      document.getElementById("mvqFloatRef").onclick = triggerRefresh;
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
