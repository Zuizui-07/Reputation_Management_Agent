/* ============================================
   API LAYER — All fetch() wrappers
   ============================================ */

// Configurable API base — change this for production deployment
const API_BASE = window.__API_BASE__ || 'http://localhost:8000';

/* ── Retry Configuration ── */
const MAX_RETRIES = 3;
const RETRY_DELAYS = [0, 1000, 2000]; // exponential backoff: 0s, 1s, 2s
const REQUEST_TIMEOUT = 30000; // 30 seconds — generous for slower machines

/**
 * Core fetch wrapper with auth header, progress bar, retry, and 401 handling.
 */
async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem('auth_token');

  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    window.location.replace('login.html');
    return null;
  }

  // Show progress bar
  showProgressBar();

  let lastError;

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    // Wait before retry (0ms on first attempt)
    if (attempt > 0) {
      console.log(`API retry attempt ${attempt + 1}/${MAX_RETRIES} for ${endpoint}`);
      await new Promise(r => setTimeout(r, RETRY_DELAYS[attempt] || 2000));
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

      const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      // Handle 401 — unauthorized (don't retry)
      if (response.status === 401) {
        hideProgressBar();
        localStorage.removeItem('auth_token');
        window.location.replace('login.html');
        return null;
      }

      // Don't retry client errors (4xx)
      if (response.status >= 400 && response.status < 500) {
        hideProgressBar();
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Request failed (${response.status})`);
      }

      // Retry server errors (5xx)
      if (!response.ok) {
        lastError = new Error(`Server error (${response.status})`);
        continue; // retry
      }

      hideProgressBar();
      return await response.json();
    } catch (error) {
      lastError = error;
      if (error.name === 'AbortError') {
        lastError = new Error('Request timed out — backend may be busy');
        continue; // retry on timeout
      }
      // Network errors (fetch failed) — retry
      if (error instanceof TypeError && error.message.includes('fetch')) {
        continue;
      }
      // Non-retryable errors — break immediately
      hideProgressBar();
      throw error;
    }
  }

  // All retries exhausted
  hideProgressBar();
  throw lastError || new Error('Request failed after retries');
}

/**
 * Lightweight backend health check — used to detect unreachable backend early.
 * Returns true if backend is reachable, false otherwise.
 */
async function checkBackendHealth() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    const response = await fetch(`${API_BASE}/health`, { signal: controller.signal });
    clearTimeout(timeoutId);
    return response.ok;
  } catch {
    return false;
  }
}

/* ── Progress Bar ── */
function showProgressBar() {
  const bar = document.getElementById('progressBar');
  if (bar) {
    bar.classList.remove('active');
    void bar.offsetWidth; // force reflow
    bar.classList.add('active');
  }
}

function hideProgressBar() {
  const bar = document.getElementById('progressBar');
  if (bar) {
    setTimeout(() => bar.classList.remove('active'), 400);
  }
}

/* ── Toast Notifications ── */
function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast--${type}`;

  const icon = document.createElement('span');
  icon.className = 'toast-icon';
  icon.textContent = type === 'success' ? '✓' : '✗';

  const text = document.createElement('span');
  text.textContent = message;

  toast.appendChild(icon);
  toast.appendChild(text);

  container.appendChild(toast);

  // Auto-dismiss success (3s), errors stay
  if (type === 'success') {
    setTimeout(() => removeToast(toast), 3000);
  } else {
    // Add close on click for errors
    toast.style.cursor = 'pointer';
    toast.addEventListener('click', () => removeToast(toast));
  }
}

function removeToast(toast) {
  toast.classList.add('removing');
  setTimeout(() => toast.remove(), 300);
}

/* ══════════════════════════════════════════
   API FUNCTIONS
   ══════════════════════════════════════════ */

/** Login */
async function apiLogin(email, password) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid credentials');
  }

  return await response.json();
}

/** Get pending messages (inbox) */
async function getPendingMessages(filters = {}) {
  const params = new URLSearchParams();
  if (filters.platform) params.set('platform', filters.platform);
  if (filters.intent) params.set('intent', filters.intent);

  const query = params.toString();
  return await apiFetch(`/api/messages/pending${query ? '?' + query : ''}`);
}

/** Approve a message (optionally with an edited reply) */
async function approveMessage(messageId, editedReply = null) {
  const body = {};
  if (editedReply) body.edited_reply = editedReply;
  return await apiFetch(`/api/messages/${messageId}/approve`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** Reject a message */
async function rejectMessage(messageId, reason = '') {
  return await apiFetch(`/api/messages/${messageId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

/** Regenerate draft for a message */
async function regenerateDraft(messageId) {
  return await apiFetch(`/api/messages/${messageId}/regenerate`, {
    method: 'POST',
  });
}

/** Get auto-sent messages */
async function getAutoSentMessages(filters = {}) {
  const params = new URLSearchParams();
  if (filters.platform) params.set('platform', filters.platform);
  if (filters.intent) params.set('intent', filters.intent);
  if (filters.search) params.set('search', filters.search);
  if (filters.page) params.set('page', filters.page);
  if (filters.limit) params.set('limit', filters.limit);

  const query = params.toString();
  return await apiFetch(`/api/messages/auto-sent${query ? '?' + query : ''}`);
}

/* ══════════════════════════════════════════
   USER MANAGEMENT API FUNCTIONS
   ══════════════════════════════════════════ */

/** Get all users (superadmin only) */
async function getUsers() {
  return await apiFetch('/api/users/');
}

/** Create a new user (superadmin only) */
async function createUser(email, password, role = 'admin') {
  return await apiFetch('/api/users/', {
    method: 'POST',
    body: JSON.stringify({ email, password, role }),
  });
}

/** Delete a user by ID (superadmin only) */
async function deleteUser(userId) {
  return await apiFetch(`/api/users/${userId}`, {
    method: 'DELETE',
  });
}

/* ══════════════════════════════════════════
   ACTIVITY LOG API FUNCTIONS
   ══════════════════════════════════════════ */

/** Get paginated activity logs (superadmin only) */
async function getActivityLogs(filters = {}) {
  const params = new URLSearchParams();
  if (filters.user) params.set('user', filters.user);
  if (filters.action) params.set('action', filters.action);
  if (filters.page) params.set('page', filters.page);
  if (filters.limit) params.set('limit', filters.limit);

  const query = params.toString();
  return await apiFetch(`/api/activity/${query ? '?' + query : ''}`);
}

/** Get distinct action types for filter dropdown */
async function getActivityActions() {
  return await apiFetch('/api/activity/actions');
}

/** Get distinct user emails for filter dropdown */
async function getActivityUsers() {
  return await apiFetch('/api/activity/users');
}
