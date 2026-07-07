/* ============================================
   USERS PAGE — Page logic
   ============================================ */

(function initUsers() {
    // Only run on users page
    if (!document.getElementById('usersTable')) return;

    // ── State ──
    let users = [];
    let pendingDeleteId = null;

    // ── DOM refs ──
    const tableBody = document.getElementById('usersTableBody');
    const userCount = document.getElementById('userCount');
    const addUserBtn = document.getElementById('addUserBtn');
    const addUserModal = document.getElementById('addUserModal');
    const deleteConfirmModal = document.getElementById('deleteConfirmModal');

    // Add modal controls
    const modalCloseBtn = document.getElementById('modalCloseBtn');
    const modalCancelBtn = document.getElementById('modalCancelBtn');
    const modalSubmitBtn = document.getElementById('modalSubmitBtn');
    const newUserEmail = document.getElementById('newUserEmail');
    const newUserPassword = document.getElementById('newUserPassword');
    const newUserRole = document.getElementById('newUserRole');
    const formError = document.getElementById('formError');

    // Delete modal controls
    const deleteCloseBtn = document.getElementById('deleteCloseBtn');
    const deleteCancelBtn = document.getElementById('deleteCancelBtn');
    const deleteConfirmBtn = document.getElementById('deleteConfirmBtn');
    const deleteUserEmail = document.getElementById('deleteUserEmail');

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

    // ── Load users ──
    async function loadUsers() {
        try {
            users = await getUsers();
            renderTable();
        } catch (err) {
            showToast('Failed to load users: ' + err.message, 'error');
        }
    }

    // ── Render table ──
    function renderTable() {
        userCount.textContent = `${users.length} user${users.length !== 1 ? 's' : ''}`;

        if (users.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="4">
                        <div class="users-empty">
                            <div class="users-empty__icon">👤</div>
                            <div class="users-empty__text">No users found</div>
                        </div>
                    </td>
                </tr>`;
            return;
        }

        // Get current user email from JWT
        let currentEmail = '';
        try {
            const token = localStorage.getItem('auth_token');
            if (token) {
                const payload = JSON.parse(atob(token.split('.')[1]));
                currentEmail = payload.sub || '';
            }
        } catch (e) { /* ignore */ }

        tableBody.innerHTML = users.map(user => {
            const isSelf = user.email === currentEmail;
            const roleClass = user.role === 'superadmin' ? 'user-role-badge--superadmin' : 'user-role-badge--admin';
            const roleLabel = user.role === 'superadmin' ? '🛡 Superadmin' : '👤 Admin';
            const createdDate = new Date(user.created_at).toLocaleDateString('en-IN', {
                day: '2-digit', month: 'short', year: 'numeric'
            });

            return `
                <tr class="fade-in">
                    <td class="user-email">${escapeHtml(user.email)}</td>
                    <td><span class="user-role-badge ${roleClass}">${roleLabel}</span></td>
                    <td class="user-date">${createdDate}</td>
                    <td class="user-actions">
                        <button class="btn--delete-user"
                                data-id="${user.id}"
                                data-email="${escapeHtml(user.email)}"
                                ${isSelf ? 'disabled title="Cannot delete yourself"' : ''}>
                            🗑 Delete
                        </button>
                    </td>
                </tr>`;
        }).join('');

        // Attach delete handlers
        tableBody.querySelectorAll('.btn--delete-user:not([disabled])').forEach(btn => {
            btn.addEventListener('click', () => {
                pendingDeleteId = parseInt(btn.dataset.id);
                deleteUserEmail.textContent = btn.dataset.email;
                deleteConfirmModal.classList.add('active');
            });
        });
    }

    // ── Add User Modal ──
    addUserBtn.addEventListener('click', () => {
        formError.textContent = '';
        newUserEmail.value = '';
        newUserPassword.value = '';
        newUserRole.value = 'admin';
        addUserModal.classList.add('active');
        setTimeout(() => newUserEmail.focus(), 100);
    });

    function closeAddModal() {
        addUserModal.classList.remove('active');
    }
    modalCloseBtn.addEventListener('click', closeAddModal);
    modalCancelBtn.addEventListener('click', closeAddModal);
    addUserModal.addEventListener('click', (e) => {
        if (e.target === addUserModal) closeAddModal();
    });

    // ── Submit new user ──
    modalSubmitBtn.addEventListener('click', async () => {
        const email = newUserEmail.value.trim();
        const password = newUserPassword.value;
        const role = newUserRole.value;

        // Validate
        formError.textContent = '';
        if (!email) { formError.textContent = 'Email is required'; return; }
        if (!email.includes('@')) { formError.textContent = 'Enter a valid email'; return; }
        if (!password || password.length < 6) {
            formError.textContent = 'Password must be at least 6 characters';
            return;
        }

        modalSubmitBtn.classList.add('loading');
        try {
            await createUser(email, password, role);
            closeAddModal();
            showToast(`User ${email} created successfully`);
            await loadUsers();
        } catch (err) {
            formError.textContent = err.message;
        } finally {
            modalSubmitBtn.classList.remove('loading');
        }
    });

    // Press Enter to submit
    [newUserEmail, newUserPassword].forEach(el => {
        el.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') modalSubmitBtn.click();
        });
    });

    // ── Delete Confirm Modal ──
    function closeDeleteModal() {
        deleteConfirmModal.classList.remove('active');
        pendingDeleteId = null;
    }
    deleteCloseBtn.addEventListener('click', closeDeleteModal);
    deleteCancelBtn.addEventListener('click', closeDeleteModal);
    deleteConfirmModal.addEventListener('click', (e) => {
        if (e.target === deleteConfirmModal) closeDeleteModal();
    });

    deleteConfirmBtn.addEventListener('click', async () => {
        if (!pendingDeleteId) return;

        deleteConfirmBtn.classList.add('loading');
        try {
            await deleteUser(pendingDeleteId);
            closeDeleteModal();
            showToast('User deleted successfully');
            await loadUsers();
        } catch (err) {
            showToast('Failed to delete: ' + err.message, 'error');
        } finally {
            deleteConfirmBtn.classList.remove('loading');
        }
    });

    // ── Escape key closes modals ──
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAddModal();
            closeDeleteModal();
        }
    });

    // ── Helpers ──
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ── Init ──
    loadUsers();
})();
