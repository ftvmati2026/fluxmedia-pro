(() => {
  const apiBase = window.location.origin;
  const whatsappUrl = 'https://wa.me/5492612404479?text=Quiero%20suscribirme%20al%20plan%20pago%20mensual%20por%20el%20servicio%20de%20transcripci%C3%B3n.';
  const originalFetch = window.fetch.bind(window);
  let supabaseClient;
  let session;
  let account;

  const style = document.createElement('style');
  style.textContent = `
    #auth-shell { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; padding: 1.25rem; background: rgba(3,10,22,.9); backdrop-filter: blur(18px); }
    .auth-card { width: min(100%, 30rem); border: 1px solid rgba(174,222,255,.18); border-radius: 1.5rem; padding: 2rem; background: rgba(11,27,48,.96); box-shadow: 0 24px 80px rgba(0,0,0,.4); }
    .auth-card h2 { margin: 0; color: white; font: 700 1.7rem "Space Grotesk", sans-serif; }
    .auth-card p { color: #a9bad0; font-size: .9rem; line-height: 1.5; }
    .auth-card input { width: 100%; margin-top: .35rem; border: 1px solid rgba(174,222,255,.2); border-radius: .75rem; padding: .8rem .9rem; color: white; background: rgba(255,255,255,.07); outline: none; }
    .auth-card input:focus { border-color: #65e7f5; }
    .auth-label { display: block; margin-top: 1rem; color: #dcecff; font-size: .82rem; font-weight: 600; }
    .auth-button { width: 100%; margin-top: 1rem; border: 0; border-radius: .75rem; padding: .8rem 1rem; color: #06101d; background: #65e7f5; font-weight: 800; cursor: pointer; }
    .auth-button.secondary { color: white; background: rgba(255,255,255,.1); }
    .auth-button.google { color: white; background: #273d5d; }
    .auth-error { min-height: 1.25rem; margin-top: .8rem; color: #ff9eae !important; }
    .account-bar { position: fixed; right: 1rem; top: 1rem; z-index: 40; display: flex; align-items: center; gap: .7rem; border: 1px solid rgba(174,222,255,.18); border-radius: 999px; padding: .45rem .55rem .45rem .9rem; color: #dcecff; background: rgba(7,17,31,.85); backdrop-filter: blur(12px); font-size: .75rem; }
    .account-bar button, .admin-plan-button { border: 0; border-radius: 999px; padding: .45rem .7rem; color: #06101d; background: #65e7f5; font-size: .72rem; font-weight: 800; cursor: pointer; }
    .account-bar .logout { color: white; background: rgba(255,255,255,.12); }
    .upgrade-card { position: fixed; left: 50%; top: 50%; z-index: 60; width: min(92vw, 29rem); transform: translate(-50%,-50%); border: 1px solid rgba(101,231,245,.35); border-radius: 1.5rem; padding: 1.6rem; color: white; background: #0b1b30; box-shadow: 0 25px 90px rgba(0,0,0,.55); }
    .upgrade-card a { display: inline-block; margin-top: 1rem; border-radius: .75rem; padding: .75rem 1rem; color: #06101d; background: #65e7f5; font-weight: 800; text-decoration: none; }
    .upgrade-card button { float: right; border: 0; color: #aac0d8; background: transparent; font-size: 1.2rem; cursor: pointer; }
    #admin-panel { position: fixed; right: 1rem; bottom: 1rem; z-index: 40; width: min(94vw, 32rem); border: 1px solid rgba(174,222,255,.2); border-radius: 1.2rem; color: white; background: rgba(11,27,48,.96); backdrop-filter: blur(16px); box-shadow: 0 24px 80px rgba(0,0,0,.5); transition: all .25s ease; overflow: hidden; }
    #admin-panel.collapsed { width: auto; border-radius: 999px; box-shadow: 0 8px 24px rgba(0,0,0,.35); }
    .admin-header { display: flex; align-items: center; justify-content: space-between; gap: .8rem; padding: .65rem 1rem; cursor: pointer; user-select: none; background: rgba(255,255,255,.04); }
    .admin-header:hover { background: rgba(255,255,255,.07); }
    .admin-header h3 { margin: 0; font-size: .88rem; font-weight: 700; color: #65e7f5; display: flex; align-items: center; gap: .45rem; white-space: nowrap; }
    .admin-header .admin-toggle-icon { font-size: .75rem; color: #a9bad0; transition: transform .2s ease; }
    .admin-body { padding: .8rem 1rem 1rem; max-height: 65vh; overflow-y: auto; }
    #admin-panel.collapsed .admin-body { display: none; }
    .admin-user { display: flex; align-items: center; justify-content: space-between; gap: .8rem; border-top: 1px solid rgba(255,255,255,.08); padding: .75rem 0; font-size: .8rem; }
    .admin-user-info { display: flex; flex-direction: column; gap: .2rem; min-width: 0; }
    .admin-user-email { font-weight: 600; color: #f1f5f9; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .plan-badge { display: inline-flex; align-items: center; gap: .25rem; font-size: .7rem; font-weight: 700; padding: .18rem .55rem; border-radius: 999px; width: fit-content; }
    .plan-badge.lifetime { background: rgba(52,211,153,.18); color: #34d399; border: 1px solid rgba(52,211,153,.45); }
    .plan-badge.premium { background: rgba(101,231,245,.18); color: #65e7f5; border: 1px solid rgba(101,231,245,.45); }
    .plan-badge.free { background: rgba(148,163,184,.14); color: #94a3b8; border: 1px solid rgba(148,163,184,.25); }
    .admin-actions { display: flex; align-items: center; gap: .35rem; flex-shrink: 0; }
    .admin-plan-button { border: 1px solid transparent; border-radius: 999px; padding: .35rem .7rem; font-size: .72rem; font-weight: 800; cursor: pointer; transition: all .15s ease; white-space: nowrap; }
    .admin-plan-button.inactive { background: rgba(255,255,255,.08); color: #a9bad0; border-color: rgba(255,255,255,.14); }
    .admin-plan-button.inactive:hover { background: rgba(255,255,255,.18); color: white; transform: translateY(-1px); }
    .admin-plan-button.btn-lifetime.active { background: #10b981; color: #022c22; border-color: #34d399; box-shadow: 0 0 12px rgba(16,185,129,.45); }
    .admin-plan-button.btn-premium.active { background: #06b6d4; color: #082f49; border-color: #65e7f5; box-shadow: 0 0 12px rgba(6,182,212,.45); }
    .admin-plan-button.btn-free { background: transparent; color: #64748b; font-size: .68rem; padding: .25rem .45rem; }
    .admin-plan-button.btn-free:hover { color: #f87171; background: rgba(239,68,68,.12); }
    @media (max-width: 640px) { .account-bar { left: 1rem; right: 1rem; justify-content: space-between; } }
  `;
  document.head.appendChild(style);

  function setMainVisible(visible) {
    document.querySelector('main')?.style.setProperty('visibility', visible ? 'visible' : 'hidden');
  }

  function createAuthShell() {
    const shell = document.createElement('div');
    shell.id = 'auth-shell';
    shell.innerHTML = `<div class="auth-card">
      <h2>Entrá a FluxMedia Pro</h2>
      <p>Registrate con una cuenta Gmail para comenzar. Tenés una prueba gratuita de cada servicio.</p>
      <button class="auth-button google" id="google-login">Continuar con Google</button>
      <div style="margin:1rem 0;text-align:center;color:#7288a2;font-size:.8rem">o usá tu Gmail</div>
      <form id="email-login-form">
        <label class="auth-label">Email Gmail<input id="auth-email" type="email" autocomplete="email" placeholder="tuusuario@gmail.com" required /></label>
        <label class="auth-label">Contraseña<input id="auth-password" type="password" autocomplete="current-password" placeholder="Mínimo 6 caracteres" required /></label>
        <button class="auth-button" type="submit">Iniciar sesión</button>
      </form>
      <button class="auth-button secondary" id="create-account">Crear cuenta nueva</button>
      <p class="auth-error" id="auth-error"></p>
    </div>`;
    document.body.appendChild(shell);
    shell.querySelector('#google-login').onclick = async () => {
      const { error } = await supabaseClient.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: `${window.location.origin}/app` } });
      if (error) showAuthError(error.message);
    };
    shell.querySelector('#email-login-form').onsubmit = async (event) => {
      event.preventDefault();
      const email = shell.querySelector('#auth-email').value.trim().toLowerCase();
      if (!isGmail(email)) return showAuthError('Solo se permiten cuentas Gmail.');
      const { error } = await supabaseClient.auth.signInWithPassword({ email, password: shell.querySelector('#auth-password').value });
      if (error) showAuthError(error.message);
    };
    shell.querySelector('#create-account').onclick = async () => {
      const email = shell.querySelector('#auth-email').value.trim().toLowerCase();
      const password = shell.querySelector('#auth-password').value;
      if (!isGmail(email)) return showAuthError('Escribí una dirección @gmail.com válida.');
      if (password.length < 6) return showAuthError('La contraseña debe tener al menos 6 caracteres.');
      const { error } = await supabaseClient.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } });
      if (error) return showAuthError(error.message);
      showAuthError('Revisá tu Gmail y confirmá la cuenta para poder entrar.');
    };
  }

  function showAuthError(message) { const node = document.querySelector('#auth-error'); if (node) node.textContent = message; }
  function isGmail(email) { return email.endsWith('@gmail.com') || email.endsWith('@googlemail.com'); }
  function showUpgrade() {
    if (document.querySelector('.upgrade-card')) return;
    const modal = document.createElement('div');
    modal.className = 'upgrade-card';
    modal.innerHTML = `<button aria-label="Cerrar">x</button><h3>Prueba gratuita utilizada</h3><p>Para seguir usando este servicio, suscribite al plan mensual de <strong>$10.000</strong>.</p><a href="${whatsappUrl}" target="_blank" rel="noreferrer">💬 Suscribirme por WhatsApp</a>`;
    modal.querySelector('button').onclick = () => modal.remove();
    document.body.appendChild(modal);
  }

  async function authenticatedFetch(input, init = {}) {
    const currentSession = session || (await supabaseClient?.auth.getSession())?.data?.session;
    const headers = new Headers(init.headers || {});
    if (currentSession?.access_token) headers.set('Authorization', `Bearer ${currentSession.access_token}`);
    const response = await originalFetch(input, { ...init, headers });
    if (response.status === 402) showUpgrade();
    return response;
  }

  function renderAccountBar() {
    document.querySelector('.account-bar')?.remove();
    const bar = document.createElement('div');
    bar.className = 'account-bar';
    const days = account?.premium_until ? ` · vence ${new Date(account.premium_until).toLocaleDateString('es-AR')}` : '';
    bar.innerHTML = `<span>${account.plan_label}${days}</span><button class="logout">Salir</button>`;
    bar.querySelector('.logout').onclick = () => supabaseClient.auth.signOut();
    document.body.appendChild(bar);
  }

  let adminPanelOpen = false;

  async function renderAdminPanel() {
    if (!account?.is_master) {
      document.querySelector('#admin-panel')?.remove();
      return;
    }
    let panel = document.querySelector('#admin-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'admin-panel';
      if (!adminPanelOpen) panel.classList.add('collapsed');
      document.body.appendChild(panel);
    }
    panel.innerHTML = `
      <div class="admin-header">
        <h3>⚙️ Panel Administrador</h3>
        <span class="admin-toggle-icon">${adminPanelOpen ? '▼' : '▲'}</span>
      </div>
      <div class="admin-body">
        <p style="color:#9db2ca;font-size:.8rem;margin:0 0 .8rem">Administrá accesos y planes de usuarios.</p>
        <div id="admin-users">Cargando usuarios...</div>
      </div>
    `;

    panel.querySelector('.admin-header').onclick = () => {
      adminPanelOpen = !adminPanelOpen;
      panel.classList.toggle('collapsed', !adminPanelOpen);
      const icon = panel.querySelector('.admin-toggle-icon');
      if (icon) icon.textContent = adminPanelOpen ? '▼' : '▲';
    };

    const response = await authenticatedFetch(`${apiBase}/api/v1/admin/users`);
    if (!response.ok) {
      const container = panel.querySelector('#admin-users');
      if (container) container.innerHTML = '<p style="color:#ff9eae;font-size:.8rem">No se pudieron cargar los usuarios.</p>';
      return;
    }
    const users = await response.json();
    const container = panel.querySelector('#admin-users');
    if (container) {
      container.innerHTML = users.map((user) => {
        const isLifetime = user.plan === 'lifetime';
        const isPremium = user.plan === 'premium';
        let badgeHtml = '';
        if (isLifetime) {
          badgeHtml = '<span class="plan-badge lifetime">🌟 Permanente (Sin límite)</span>';
        } else if (isPremium) {
          const exp = user.premium_until ? ` · vence ${new Date(user.premium_until).toLocaleDateString('es-AR')}` : '';
          badgeHtml = `<span class="plan-badge premium">💎 30 días${exp}</span>`;
        } else {
          badgeHtml = '<span class="plan-badge free">⚪ Gratuito (1 prueba)</span>';
        }

        return `
          <div class="admin-user">
            <div class="admin-user-info">
              <span class="admin-user-email" title="${user.email}">${user.email}</span>
              ${badgeHtml}
            </div>
            <div class="admin-actions">
              <button class="admin-plan-button btn-premium ${isPremium ? 'active' : 'inactive'}" data-id="${user.id}" data-plan="premium">
                ${isPremium ? '✓ 30 días' : '30 días'}
              </button>
              <button class="admin-plan-button btn-lifetime ${isLifetime ? 'active' : 'inactive'}" data-id="${user.id}" data-plan="lifetime">
                ${isLifetime ? '✓ Permanente' : 'Permanente'}
              </button>
              ${!isLifetime && !isPremium ? '' : `
                <button class="admin-plan-button btn-free" data-id="${user.id}" data-plan="free" title="Pasar a cuenta gratuita">
                  ✕ Quitar
                </button>
              `}
            </div>
          </div>
        `;
      }).join('');

      container.querySelectorAll('.admin-plan-button').forEach((button) => {
        button.onclick = async (e) => {
          e.stopPropagation();
          button.disabled = true;
          button.textContent = '...';
          await authenticatedFetch(`${apiBase}/api/v1/admin/users/${button.dataset.id}/plan`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan: button.dataset.plan })
          });
          renderAdminPanel();
        };
      });
    }
  }

  async function onSessionChanged(nextSession) {
    session = nextSession;
    if (!session) {
      setMainVisible(false);
      document.querySelector('.account-bar')?.remove();
      document.querySelector('#admin-panel')?.remove();
      if (!document.querySelector('#auth-shell')) createAuthShell();
      return;
    }
    const response = await authenticatedFetch(`${apiBase}/api/v1/account`);
    if (!response.ok) {
      const errData = await response.json().catch(() => ({ detail: 'Error al consultar la cuenta.' }));
      await supabaseClient.auth.signOut();
      if (!document.querySelector('#auth-shell')) createAuthShell();
      showAuthError(errData.detail || 'Error al autenticar con el servidor.');
      return;
    }
    account = await response.json();
    document.querySelector('#auth-shell')?.remove();
    setMainVisible(true);
    renderAccountBar();
    renderAdminPanel();
  }

  async function init() {
    const config = await originalFetch(`${apiBase}/api/v1/auth/config`).then((response) => response.json()).catch(() => ({ enabled: false }));
    if (!config.enabled || !config.supabase_anon_key) return;
    supabaseClient = window.supabase.createClient(config.supabase_url, config.supabase_anon_key);
    window.fetch = authenticatedFetch;
    window.addEventListener('flux:upgrade', showUpgrade);
    supabaseClient.auth.onAuthStateChange((_event, nextSession) => onSessionChanged(nextSession));
    const { data } = await supabaseClient.auth.getSession();
    await onSessionChanged(data.session);
  }

  init();
})();
