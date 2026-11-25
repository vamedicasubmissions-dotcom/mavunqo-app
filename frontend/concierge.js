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

    // 1. Pill button
    const pill = document.createElement('div');
    pill.className = 'ai-concierge-pill';
    pill.innerHTML = `<span>🌴</span> <span>${role === 'customer' ? 'AI Concierge' : 'Help Guide'}</span>`;
    pill.onclick = toggleDrawer;

    // 2. Drawer container
    const drawer = document.createElement('div');
    drawer.className = 'ai-drawer';
    drawer.id = 'aiDrawer';
    const chipsHtml = (roleTips.chips || []).map(c =>
      `<button type="button" onclick="document.getElementById('aiInput').value='${c}'; sendConciergeQuery();" style="background:#f1f5f9; border:1px solid #cbd5e1; border-radius:999px; padding:0.25rem 0.65rem; font-size:0.75rem; font-weight:700; cursor:pointer; color:#0f172a;">${c}</button>`
    ).join('');

    drawer.innerHTML = `
      <div class="ai-drawer-header">
        <div>
          <strong style="font-size: 1.05rem;">${roleTips.title}</strong>
          <div style="font-size: 0.75rem; opacity: 0.9;">${roleTips.sub}</div>
        </div>
        <button onclick="toggleDrawer();" style="background: none; border: none; color: white; font-size: 1.4rem; cursor: pointer;">&times;</button>
      </div>

      <div class="ai-drawer-body" id="aiDrawerBody">
        <div class="ai-bubble-bot">
          ${roleTips.welcome}
        </div>
        <div style="display:flex; flex-wrap:wrap; gap:0.4rem; margin-top:0.5rem;">${chipsHtml}</div>
      </div>

      <div class="ai-drawer-footer">
        <input type="text" id="aiInput" class="input-field" placeholder="Ask anything in English or Spanish..." onkeydown="if(event.key === 'Enter') sendConciergeQuery();" style="border-radius: var(--radius-pill); font-size: 0.88rem; padding: 0.5rem 0.9rem;">
        <button class="btn btn-amber btn-sm" onclick="sendConciergeQuery();" style="border-radius: var(--radius-pill); padding: 0.5rem 0.9rem;">Ask</button>
      </div>
    `;

    document.body.appendChild(pill);
    document.body.appendChild(drawer);
  }

  window.toggleDrawer = function() {
    const d = document.getElementById('aiDrawer');
    if (d) {
      d.classList.toggle('open');
      if (d.classList.contains('open')) {
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
    const botLoading = document.createElement('div');
    botLoading.className = 'ai-bubble-bot';
    botLoading.textContent = 'Thinking...';
    body.appendChild(botLoading);
    body.scrollTop = body.scrollHeight;

    try {
      const currentLang = localStorage.getItem('mavunqo_lang') || 'en';
      const role = detectUserRole();
      const res = await fetch(`/api/concierge?q=${encodeURIComponent(query)}&lang=${currentLang}&role=${encodeURIComponent(role)}`);
      const data = await res.json();

      let recsHtml = '';
      if (data.recommendations && data.recommendations.length > 0) {
        recsHtml = `<div style="margin-top: 0.6rem; display: flex; flex-direction: column; gap: 0.4rem;">` +
          data.recommendations.map(r => `
            <a href="/b/${r.slug}" style="display: block; padding: 0.45rem 0.65rem; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm); text-decoration: none; color: var(--teal-primary); font-weight: 750; font-size: 0.85rem;">
              → ${r.trading_name}
            </a>
          `).join('') + `</div>`;
      }

      botLoading.innerHTML = `<div>${data.answer}</div>${recsHtml}`;
    } catch (e) {
      botLoading.textContent = 'Sorry, could not connect to concierge services right now.';
    }
    body.scrollTop = body.scrollHeight;
  };

  document.addEventListener('DOMContentLoaded', injectConciergeUI);
})();
