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
    #admin-panel { position: fixed; right: 1rem; bottom: 1rem; z-index: 40; width: min(94vw, 30rem); max-height: 70vh; overflow: auto; border: 1px solid rgba(174,222,255,.18); border-radius: 1.2rem; padding: 1rem; color: white; background: rgba(11,27,48,.96); box-shadow: 0 24px 80px rgba(0,0,0,.4); }
    #admin-panel h3 { margin: 0 0 .8rem; }
    .admin-user { display: flex; align-items: center; justify-content: space-between; gap: .6rem; border-top: 1px solid rgba(255,255,255,.1); padding: .7rem 0; font-size: .78rem; }
    .admin-user small { display: block; color: #9db2ca; }
    .admin-plan-button { white-space: nowrap; }
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
      const { error } = await supabaseClient.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } });
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

  async function renderAdminPanel() {
    document.querySelector('#admin-panel')?.remove();
    if (!account?.is_master) return;
    const panel = document.createElement('div');
    panel.id = 'admin-panel';
    panel.innerHTML = '<h3>Panel maestro</h3><p style="color:#9db2ca;font-size:.8rem">Administrá accesos especiales.</p><div id="admin-users">Cargando usuarios...</div>';
    document.body.appendChild(panel);
    const response = await authenticatedFetch(`${apiBase}/api/v1/admin/users`);
    if (!response.ok) return;
    const users = await response.json();
    panel.querySelector('#admin-users').innerHTML = users.map((user) => `<div class="admin-user"><span>${user.email}<small>Plan actual: ${user.plan}</small></span><span><button class="admin-plan-button" data-id="${user.id}" data-plan="premium">30 días</button> <button class="admin-plan-button" data-id="${user.id}" data-plan="lifetime">Permanente</button></span></div>`).join('');
    panel.querySelectorAll('.admin-plan-button').forEach((button) => {
      button.onclick = async () => {
        await authenticatedFetch(`${apiBase}/api/v1/admin/users/${button.dataset.id}/plan`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ plan: button.dataset.plan }) });
        renderAdminPanel();
      };
    });
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
      await supabaseClient.auth.signOut();
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
