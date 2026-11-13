/**
 * Mavunqo Floating AI Concierge Client Widget
 * Bilingual English/Spanish inquiry and discovery assistant
 */

(function() {
  function injectConciergeUI() {
    // 1. Pill button
    const pill = document.createElement('div');
    pill.className = 'ai-concierge-pill';
    pill.innerHTML = `<span>🌴</span> <span>AI Concierge</span>`;
    pill.onclick = toggleDrawer;

    // 2. Drawer container
    const drawer = document.createElement('div');
    drawer.className = 'ai-drawer';
    drawer.id = 'aiDrawer';
    drawer.innerHTML = `
      <div class="ai-drawer-header">
        <div>
          <strong style="font-size: 1.05rem;">Mavunqo AI Concierge</strong>
          <div style="font-size: 0.75rem; opacity: 0.9;">Sosúa & Puerto Plata Local Guide</div>
        </div>
        <button onclick="toggleDrawer();" style="background: none; border: none; color: white; font-size: 1.4rem; cursor: pointer;">&times;</button>
      </div>

      <div class="ai-drawer-body" id="aiDrawerBody">
        <div class="ai-bubble-bot">
          👋 ¡Hola! I am your bilingual North Coast Concierge. Ask me about local restaurants, City Lights boutique rooms, auto repair, or beach services in Sosúa!
        </div>
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
      const res = await fetch(`/api/concierge?q=${encodeURIComponent(query)}&lang=${currentLang}`);
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
