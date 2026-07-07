/* ============================================
   AUTH — Login, logout, token management
   ============================================ */

/* ── Token helpers ── */
function getToken() {
    return localStorage.getItem('auth_token');
}

function setToken(token) {
    localStorage.setItem('auth_token', token);
}

function clearToken() {
    localStorage.removeItem('auth_token');
}

function isAuthenticated() {
    return !!getToken();
}

/** Redirect to login if not authenticated */
function requireAuth() {
    if (!isAuthenticated()) {
        window.location.replace('login.html');
    }
}

/** Logout and redirect */
function logout() {
    clearToken();
    window.location.replace('login.html');
}

/* ── Login Page Logic ── */
(function initAuth() {
    // If on login page
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        // If already logged in, redirect away
        if (isAuthenticated()) {
            window.location.replace('inbox.html');
            return;
        }

        const emailInput = document.getElementById('email');
        const passwordInput = document.getElementById('password');
        const loginBtn = document.getElementById('loginBtn');
        const loginError = document.getElementById('loginError');
        const passwordToggle = document.getElementById('passwordToggle');

        // Password visibility toggle
        if (passwordToggle) {
            passwordToggle.addEventListener('click', () => {
                const isPassword = passwordInput.type === 'password';
                passwordInput.type = isPassword ? 'text' : 'password';
                passwordToggle.textContent = isPassword ? '🙈' : '👁';
            });
        }

        // Form submit
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            if (!email || !password) return;

            // Show loading
            loginBtn.classList.add('loading');
            loginError.classList.remove('visible');

            try {
                const data = await apiLogin(email, password);
                setToken(data.access_token);
                window.location.replace('inbox.html');
            } catch (error) {
                loginError.textContent = error.message || 'Invalid credentials';
                loginError.classList.add('visible');
                loginBtn.classList.remove('loading');

                // Shake the card
                const card = document.querySelector('.login-card');
                card.style.animation = 'none';
                void card.offsetWidth;
                card.style.animation = 'shake 0.4s ease';
            }
        });

        // Add shake animation via JS
        const style = document.createElement('style');
        style.textContent = `
      @keyframes shake {
        0%, 100% { transform: translateX(0); }
        20% { transform: translateX(-8px); }
        40% { transform: translateX(8px); }
        60% { transform: translateX(-6px); }
        80% { transform: translateX(4px); }
      }
    `;
        document.head.appendChild(style);
    }

    // Logout button (present on inbox/autosent pages)
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
    }

    // Require auth on non-login pages
    if (!loginForm && !window.location.pathname.includes('login')) {
        requireAuth();

        // Populate admin email + role from JWT token
        const adminEmailEl = document.getElementById('adminEmail');
        const adminRoleEl = document.getElementById('adminRole');
        const navUsersEl = document.getElementById('navUsers');
        const navActivityEl = document.getElementById('navActivity');

        try {
            const token = getToken();
            if (token) {
                const payloadBase64 = token.split('.')[1];
                const payload = JSON.parse(atob(payloadBase64));

                // Set email
                if (adminEmailEl) {
                    adminEmailEl.textContent = payload.sub || 'Admin';
                }

                // Set role display
                const role = payload.role || 'admin';
                if (adminRoleEl) {
                    adminRoleEl.textContent = role === 'superadmin' ? 'Super Admin' : 'Admin';
                }

                // Show/hide superadmin-only nav items
                const isSuperadmin = role === 'superadmin';
                if (navUsersEl) {
                    navUsersEl.style.display = isSuperadmin ? '' : 'none';
                }
                if (navActivityEl) {
                    navActivityEl.style.display = isSuperadmin ? '' : 'none';
                }
            }
        } catch (e) {
            if (adminEmailEl) adminEmailEl.textContent = 'Admin';
        }
    }

    // Mobile sidebar toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            if (sidebarOverlay) sidebarOverlay.classList.toggle('visible');
        });

        if (sidebarOverlay) {
            sidebarOverlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('visible');
            });
        }
    }
})();
