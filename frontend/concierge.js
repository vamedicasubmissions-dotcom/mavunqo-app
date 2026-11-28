/**
 * Mavunqo Floating AI Concierge Client Widget
 * Bilingual English/Spanish inquiry and discovery assistant
 */

(function() {
  function detectUserRole() {
    const p = window.location.pathname.toLowerCase();
    if (p.includes('dashboard') || p.includes('merchant_ops')) return 'owner';
    if (p.includes('driver')) return 'driver';
    if (p.includes('admin')) return 'admin';
    return 'customer';
  }

  function injectConciergeUI() {
    const role = detectUserRole();
    const roleTips = {
      owner: {
        title: 'Mavunqo Owner Guide',
        sub: 'Storefront, pricing & WhatsApp help',
        welcome: '👋 Need help updating prices, photos, or checking your 10% bookings? Ask me anything!',
        chips: ['How do I update prices?', 'How does 10% commission work?']
      },
      driver: {
        title: 'Mavunqo Driver Guide',
        sub: 'Distance pay & pin navigation help',
        welcome: '🛵 Need help with distance payouts or dropoff pins? Ask me here!',
        chips: ['How does distance pay work?', 'Where is the customer address?']
      },
      admin: {
        title: 'Mavunqo Admin Guide',
        sub: 'Approvals, security & payouts',
        welcome: '🛡️ Ask about security alerts, pending approvals, or SaaS plans.',
        chips: ['Show security alerts']
      },
      customer: {
        title: 'Mavunqo AI Concierge',
        sub: 'Puerto Plata · Sosúa · Cabarete Guide',
        welcome: '🌴 ¡Hola! Ask me about North Coast tours & waterfalls, bachata & cultural events, comida criolla, wellness, villas, or verified DR lawyers.',
        chips: ['Tours & waterfalls', 'Bachata & events', 'Verified lawyers', 'Massage in Puerto Plata']
      }
    }[role];

    // 1. Pill button with Dominican photo avatar
    const pill = document.createElement('div');
    pill.className = 'ai-concierge-pill';
    pill.innerHTML = `<img src="/frontend/uploads/heritage/people_catamaran.jpg" alt="Concierge" style="width:28px;height:28px;border-radius:50%;object-fit:cover;border:2px solid #f59e0b;"> <span>${role === 'customer' ? 'AI Concierge' : 'Help Guide'}</span>`;
    pill.onclick = toggleDrawer;

    // 2. Drawer container
    const drawer = document.createElement('div');
    drawer.className = 'ai-drawer';
    drawer.id = 'aiDrawer';
    const chipsHtml = (roleTips.chips || []).map(c =>
      `<button type="button" class="ai-chip-btn" onclick="document.getElementById('aiInput').value='${c}'; sendConciergeQuery();" style="background:#ffffff; border:1px solid #cbd5e1; border-radius:999px; padding:0.32rem 0.72rem; font-size:0.76rem; font-weight:750; cursor:pointer; color:#0f172a; box-shadow:0 2px 6px rgba(15,23,42,0.05);">${c}</button>`
    ).join('');

    drawer.innerHTML = `
      <div class="ai-drawer-header">
        <div style="display:flex;align-items:center;gap:0.65rem;">
          <img src="/frontend/uploads/heritage/people_bachata.jpg" alt="Mavunqo" style="width:38px;height:38px;border-radius:50%;object-fit:cover;border:2px solid #f59e0b;flex-shrink:0;">
          <div>
            <strong style="font-size: 1.02rem; text-shadow: 0 1px 3px rgba(0,0,0,0.35);">${roleTips.title}</strong>
            <div style="font-size: 0.75rem; opacity: 0.95;">${roleTips.sub}</div>
          </div>
        </div>
        <button onclick="toggleDrawer();" style="background: rgba(15,23,42,0.35); border: none; color: white; width: 30px; height: 30px; border-radius: 50%; font-size: 1.25rem; line-height: 1; cursor: pointer;">&times;</button>
      </div>

      <div class="ai-drawer-body" id="aiDrawerBody">
        <div class="ai-bubble-bot">
          ${roleTips.welcome}
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:0.4rem; margin-top:0.5rem;">${chipsHtml}</div>
      </div>

      <div class="ai-drawer-footer">
        <input type="text" id="aiInput" class="input-field" placeholder="Ask anything in English or Spanish..." onkeydown="if(event.key === 'Enter') sendConciergeQuery();" style="border-radius: var(--radius-pill); font-size: 0.88rem; padding: 0.5rem 0.9rem;">
        <button id="aiAskBtn" class="btn btn-amber btn-sm" onclick="sendConciergeQuery();" style="border-radius: var(--radius-pill); padding: 0.5rem 0.9rem;">Ask</button>
      </div>
    `;

    document.body.appendChild(pill);
    document.body.appendChild(drawer);
    updateConciergeLang();
  }

  function updateConciergeLang() {
    const lang = (localStorage.getItem('mavunqo_lang') || 'en').toLowerCase();
    const inp = document.getElementById('aiInput');
    const btn = document.getElementById('aiAskBtn');
    if (inp) {
      inp.placeholder = lang === 'es'
        ? 'Pregunta lo que necesites en español o inglés...'
        : (lang === 'fr' ? 'Posez votre question ici...' : 'Ask anything in English or Spanish...');
    }
    if (btn) {
      btn.textContent = lang === 'es' ? 'Preguntar' : (lang === 'fr' ? 'Demander' : 'Ask');
    }
  }

  window.toggleDrawer = function() {
    const d = document.getElementById('aiDrawer');
    if (d) {
      const isOpen = d.classList.toggle('open');
      document.body.classList.toggle('ai-drawer-open', isOpen);
      if (isOpen) {
        document.getElementById('aiInput')?.focus();
      }
    }
  };

  window.sendConciergeQuery = async function() {
    const input = document.getElementById('aiInput');
    const query = (input.value || '').trim();
    if (!query) return;

    const body = document.getElementById('aiDrawerBody');

    // Add user bubble
    const userMsg = document.createElement('div');
    userMsg.className = 'ai-bubble-user';
    userMsg.textContent = query;
    body.appendChild(userMsg);
    input.value = '';
    body.scrollTop = body.scrollHeight;

    // Loading indicator
    const lang = (localStorage.getItem('mavunqo_lang') || 'en').toLowerCase();
    const botLoading = document.createElement('div');
    botLoading.className = 'ai-bubble-bot';
    botLoading.textContent = lang === 'es' ? 'Pensando...' : (lang === 'fr' ? 'Réflexion...' : 'Thinking...');
    body.appendChild(botLoading);
    body.scrollTop = body.scrollHeight;

    try {
      const role = detectUserRole();
      const pathMatch = window.location.pathname.match(/^\/b\/([^\/?#]+)/i);
      const bizSlug = pathMatch ? decodeURIComponent(pathMatch[1]) : '';
      const slugParam = bizSlug ? `&slug=${encodeURIComponent(bizSlug)}` : '';
      const res = await fetch(`/api/concierge?q=${encodeURIComponent(query)}&lang=${lang}&role=${encodeURIComponent(role)}${slugParam}`);
      const data = await res.json();

      let recsHtml = '';
      if (data.recommendations && data.recommendations.length > 0) {
        recsHtml = `<div style="margin-top: 0.65rem; display: flex; flex-direction: column; gap: 0.45rem;">` +
          data.recommendations.map(r => {
            const thumb = r.logo_url || r.cover_image_url || '/frontend/uploads/heritage/cayo_arena_waterfalls.jpg';
            return `
            <a href="/b/${r.slug}" class="ai-rec-card" style="display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0.6rem; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; text-decoration: none; color: #0f172a; font-weight: 750; font-size: 0.84rem;">
              <img src="${thumb}" alt="${r.trading_name}" style="width:36px;height:36px;border-radius:8px;object-fit:cover;flex-shrink:0;">
              <span style="flex:1;">${r.trading_name}</span>
              <span style="color:#0d9488;">→</span>
            </a>`;
          }).join('') + `</div>`;
      }

      botLoading.innerHTML = `<div>${data.answer}</div>${recsHtml}`;
    } catch (e) {
      botLoading.textContent = 'Sorry, could not connect to concierge services right now.';
    }
    body.scrollTop = body.scrollHeight;
  };

  window.addEventListener('languageChanged', updateConciergeLang);
  document.addEventListener('DOMContentLoaded', injectConciergeUI);
})();
