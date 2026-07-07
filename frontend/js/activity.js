/* ============================================
   ACTIVITY LOGS PAGE — Page logic
   ============================================ */

(function initActivity() {
    // Only run on activity page
    if (!document.getElementById('activityTableBody')) return;

    // ── State ──
    let currentPage = 1;
    let totalPages = 1;
    const LIMIT = 25;

    // ── DOM refs ──
    const tableBody = document.getElementById('activityTableBody');
    const logCount = document.getElementById('logCount');
    const pagination = document.getElementById('pagination');
    const filterUser = document.getElementById('filterUser');
    const filterAction = document.getElementById('filterAction');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');

    // ── Check role — only superadmin can access ──
    function checkAccess() {
        const token = localStorage.getItem('auth_token');
        if (!token) return false;
        try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            if (payload.role !== 'superadmin') {
                window.location.replace('inbox.html');
                return false;
            }
            return true;
        } catch (e) {
            return false;
        }
    }

    if (!checkAccess()) return;

    // ── Action display config ──
    const ACTION_CONFIG = {
        login: { label: '🔑 Login', css: 'action-badge--login' },
        approve_message: { label: '✓ Approved', css: 'action-badge--approve_message' },
        reject_message: { label: '✗ Rejected', css: 'action-badge--reject_message' },
        regenerate_draft: { label: '↻ Regenerate', css: 'action-badge--regenerate_draft' },
        create_user: { label: '＋ Created User', css: 'action-badge--create_user' },
        delete_user: { label: '🗑 Deleted User', css: 'action-badge--delete_user' },
    };

    // ── Load filter options ──
    async function loadFilters() {
        try {
            const [users, actions] = await Promise.all([
                getActivityUsers(),
                getActivityActions(),
            ]);

            users.forEach(email => {
                const opt = document.createElement('option');
                opt.value = email;
                opt.textContent = email;
                filterUser.appendChild(opt);
            });

            actions.forEach(action => {
                const opt = document.createElement('option');
                opt.value = action;
                const config = ACTION_CONFIG[action];
                opt.textContent = config ? config.label.replace(/[^\w\s]/g, '').trim() : action;
                filterAction.appendChild(opt);
            });
        } catch (e) {
            /* filters are optional */
        }
    }

    // ── Load logs ──
    async function loadLogs() {
        try {
            const filters = {};
            if (filterUser.value) filters.user = filterUser.value;
            if (filterAction.value) filters.action = filterAction.value;
            filters.page = currentPage;
            filters.limit = LIMIT;

            const data = await getActivityLogs(filters);
            totalPages = data.pages;
            renderTable(data.logs, data.total);
            renderPagination();
        } catch (err) {
            showToast('Failed to load activity logs: ' + err.message, 'error');
        }
    }

    // ── Render table ──
    function renderTable(logs, total) {
        logCount.textContent = `${total} activit${total !== 1 ? 'ies' : 'y'}`;

        if (logs.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4">
                        <div class="activity-empty">
                            <div class="activity-empty__icon">📋</div>
                            <div class="activity-empty__text">No activity logs found</div>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        tableBody.innerHTML = logs.map(log => {
            const config = ACTION_CONFIG[log.action] || { label: log.action, css: '' };
            const time = formatTime(log.performed_at);

            return `
                <tr class="fade-in">
                    <td class="activity-user">${escapeHtml(log.user_email)}</td>
                    <td><span class="action-badge ${config.css}">${config.label}</span></td>
                    <td class="activity-details" title="${escapeHtml(log.details || '')}">${escapeHtml(log.details || '—')}</td>
                    <td class="activity-time">${time}</td>
                </tr>`;
        }).join('');
    }

    // ── Render pagination ──
    function renderPagination() {
        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = `<button class="page-btn" ${currentPage <= 1 ? 'disabled' : ''} data-page="${currentPage - 1}">‹ Prev</button>`;

        // Show page numbers
        const maxVisible = 5;
        let start = Math.max(1, currentPage - Math.floor(maxVisible / 2));
        let end = Math.min(totalPages, start + maxVisible - 1);
        if (end - start < maxVisible - 1) start = Math.max(1, end - maxVisible + 1);

        if (start > 1) html += `<button class="page-btn" data-page="1">1</button><span class="page-info">…</span>`;

        for (let i = start; i <= end; i++) {
            html += `<button class="page-btn ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        if (end < totalPages) html += `<span class="page-info">…</span><button class="page-btn" data-page="${totalPages}">${totalPages}</button>`;

        html += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} data-page="${currentPage + 1}">Next ›</button>`;

        pagination.innerHTML = html;

        // Attach click handlers
        pagination.querySelectorAll('.page-btn:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                currentPage = parseInt(btn.dataset.page);
                loadLogs();
            });
        });
    }

    // ── Filter change ──
    filterUser.addEventListener('change', () => { currentPage = 1; loadLogs(); });
    filterAction.addEventListener('change', () => { currentPage = 1; loadLogs(); });
    clearFiltersBtn.addEventListener('click', () => {
        filterUser.value = '';
        filterAction.value = '';
        currentPage = 1;
        loadLogs();
    });

    // ── Helpers ──
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatTime(isoString) {
        const d = new Date(isoString);
        const now = new Date();
        const diffMs = now - d;
        const diffMins = Math.floor(diffMs / 60000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
        if (diffMins < 2880) return 'yesterday';

        return d.toLocaleDateString('en-IN', {
            day: '2-digit', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit', hour12: false,
        });
    }

    // ── Init ──
    loadFilters();
    loadLogs();
})();
