/**
 * ================================================
 *   Knowledge Base — Frontend JavaScript
 * ================================================
 */

// ── Configuration ──
// const API = window.API_BASE || 'http://localhost:8000';
const POLL_INTERVAL = 5000; // 5s polling for processing status

// ── State ──
let documents = [];
let pollTimer = null;

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();
    loadStats();
    setupDropZone();
    setupUrlScan();
    setupSearch();
    setupFilters();
});


// ══════════════════════════════════════════════
//  DOCUMENT LOADING
// ══════════════════════════════════════════════

async function loadDocuments() {
    try {
        const token = localStorage.getItem('auth_token');
        const statusFilter = document.getElementById('filterStatus').value;
        const typeFilter = document.getElementById('filterType').value;

        let endpoint = `/api/knowledge/documents?`;
        if (statusFilter) endpoint += `status=${statusFilter}&`;
        if (typeFilter) endpoint += `doc_type=${typeFilter}&`;

        const data = await apiFetch(endpoint);
        if (!data) return;
        documents = data;
        renderDocuments();

        // Check if any documents are still processing
        const hasProcessing = documents.some(d => d.status === 'processing' || d.status === 'pending');
        if (hasProcessing) {
            startPolling();
        } else {
            stopPolling();
        }
    } catch (err) {
        console.error('Failed to load documents:', err);
        showToast('Failed to load documents', 'error');
    }
}

async function loadStats() {
    try {
        const stats = await apiFetch('/api/knowledge/stats');
        if (!stats) return;

        document.getElementById('statDocs').textContent =
            Object.values(stats.documents || {}).reduce((a, b) => a + b, 0);
        document.getElementById('statChunks').textContent = stats.total_chunks_in_db || 0;
        document.getElementById('statVectors').textContent = stats.vector_store?.total_vectors || 0;
    } catch (err) {
        console.error('Failed to load stats:', err);
    }
}


// ══════════════════════════════════════════════
//  RENDER DOCUMENTS TABLE
// ══════════════════════════════════════════════

function renderDocuments() {
    const tbody = document.getElementById('docsTableBody');

    if (documents.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty-cell">
            No documents uploaded yet. Upload a PDF or scan a website to get started.
        </td></tr>`;
        return;
    }

    tbody.innerHTML = documents.map(doc => {
        const typeIcon = doc.doc_type === 'pdf' ? '📄' : '🌐';
        const typeBadge = `<span class="type-badge type-badge--${doc.doc_type}">${typeIcon} ${doc.doc_type.toUpperCase()}</span>`;

        const statusBadge = `<span class="status-badge status-badge--${doc.status}">${getStatusIcon(doc.status)} ${doc.status}</span>`;

        const name = doc.doc_type === 'url'
            ? `<a href="${doc.filename}" target="_blank" class="doc-name" title="${doc.filename}">${doc.filename}</a>`
            : `<span class="doc-name" title="${doc.filename}">${doc.filename}</span>`;

        const uploadedDate = new Date(doc.uploaded_at).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });

        return `<tr>
            <td>${typeBadge}</td>
            <td>${name}</td>
            <td>${statusBadge}${doc.error_message ? `<br><small style="color:var(--danger);font-size:11px;">${doc.error_message.substring(0, 80)}...</small>` : ''}</td>
            <td style="font-family:var(--font-mono);color:var(--accent);">${doc.total_chunks}</td>
            <td style="font-size:12px;color:var(--text-dim);">${uploadedDate}</td>
            <td>
                <div class="doc-actions">
                    <button class="btn--icon" onclick="viewChunks(${doc.id})" title="View Chunks" ${doc.status !== 'ready' ? 'disabled' : ''}>👁</button>
                    <button class="btn--icon" onclick="reindexDoc(${doc.id})" title="Re-index">🔄</button>
                    <button class="btn--icon" onclick="deleteDoc(${doc.id}, '${doc.filename.replace(/'/g, "\\'")}' )" title="Delete" style="color:var(--danger);">🗑</button>
                </div>
            </td>
        </tr>`;
    }).join('');
}

function getStatusIcon(status) {
    switch (status) {
        case 'pending': return '⏳';
        case 'processing': return '⚙️';
        case 'ready': return '✅';
        case 'failed': return '❌';
        default: return '';
    }
}


// ══════════════════════════════════════════════
//  PDF UPLOAD (DRAG & DROP)
// ══════════════════════════════════════════════

function setupDropZone() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');

    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drop-zone--active');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drop-zone--active');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drop-zone--active');
        const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.pdf'));
        if (files.length > 0) {
            uploadFiles(files);
        } else {
            showToast('Please drop PDF files only', 'error');
        }
    });

    fileInput.addEventListener('change', () => {
        const files = Array.from(fileInput.files);
        if (files.length > 0) uploadFiles(files);
        fileInput.value = '';
    });
}

async function uploadFiles(files) {
    const progressEl = document.getElementById('uploadProgress');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    progressEl.style.display = 'block';

    let completed = 0;

    for (const file of files) {
        try {
            progressText.textContent = `Uploading ${file.name}... (${completed + 1}/${files.length})`;
            progressFill.style.width = `${((completed) / files.length) * 100}%`;

            const formData = new FormData();
            formData.append('file', file);

            const res = await fetch(`${API_BASE}/api/knowledge/upload-pdf`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` },
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || `HTTP ${res.status}`);
            }

            completed++;
            progressFill.style.width = `${(completed / files.length) * 100}%`;
            showToast(`✅ ${file.name} uploaded successfully`, 'success');
        } catch (err) {
            console.error(`Upload failed for ${file.name}:`, err);
            showToast(`❌ Failed to upload ${file.name}: ${err.message}`, 'error');
            completed++;
        }
    }

    progressText.textContent = `${completed} file(s) uploaded! Processing...`;
    setTimeout(() => { progressEl.style.display = 'none'; }, 3000);

    loadDocuments();
    loadStats();
}


// ══════════════════════════════════════════════
//  URL SCANNING
// ══════════════════════════════════════════════

function setupUrlScan() {
    const btn = document.getElementById('scanUrlBtn');
    const input = document.getElementById('urlInput');

    btn.addEventListener('click', () => scanUrl());
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') scanUrl();
    });
}

async function scanUrl() {
    const input = document.getElementById('urlInput');
    const btn = document.getElementById('scanUrlBtn');
    const url = input.value.trim();

    if (!url) {
        showToast('Please enter a URL', 'error');
        return;
    }

    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        showToast('URL must start with http:// or https://', 'error');
        return;
    }

    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const maxDepth = parseInt(document.getElementById('maxDepth').value);
        const maxPages = parseInt(document.getElementById('maxPages').value);

        const data = await apiFetch('/api/knowledge/add-url', {
            method: 'POST',
            body: JSON.stringify({ url, max_depth: maxDepth, max_pages: maxPages }),
        });
        if (!data) return;

        showToast(`🌐 Website scan started for ${url}`, 'success');
        input.value = '';
        loadDocuments();
        loadStats();
    } catch (err) {
        console.error('URL scan failed:', err);
        showToast(`❌ ${err.message}`, 'error');
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}


// ══════════════════════════════════════════════
//  SEARCH
// ══════════════════════════════════════════════

function setupSearch() {
    const btn = document.getElementById('searchBtn');
    const input = document.getElementById('searchInput');

    btn.addEventListener('click', () => searchKnowledge());
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') searchKnowledge();
    });
}

async function searchKnowledge() {
    const input = document.getElementById('searchInput');
    const resultsDiv = document.getElementById('searchResults');
    const query = input.value.trim();

    if (!query) return;

    try {
        const results = await apiFetch(`/api/knowledge/search?q=${encodeURIComponent(query)}&top_k=5`);
        if (!results) return;

        resultsDiv.style.display = 'flex';

        if (results.length === 0) {
            resultsDiv.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding:var(--space-xl);">
                No relevant results found. Upload more documents to improve coverage.
            </div>`;
            return;
        }

        resultsDiv.innerHTML = results.map(r => `
            <div class="search-result-card">
                <div class="search-result__header">
                    <span class="search-result__source">${r.document_name}</span>
                    <span class="search-result__score">${(r.similarity_score * 100).toFixed(1)}% match</span>
                </div>
                <div class="search-result__content">${escapeHtml(r.chunk_content)}</div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Search failed:', err);
        showToast('Search failed', 'error');
    }
}


// ══════════════════════════════════════════════
//  DOCUMENT ACTIONS
// ══════════════════════════════════════════════

async function viewChunks(docId) {
    const modal = document.getElementById('chunkModal');
    const modalBody = document.getElementById('modalBody');
    const modalTitle = document.getElementById('modalTitle');

    modalBody.innerHTML = '<div style="text-align:center;color:var(--text-muted);">Loading chunks...</div>';
    modal.style.display = 'flex';

    try {
        const doc = await apiFetch(`/api/knowledge/documents/${docId}`);
        if (!doc) return;

        modalTitle.textContent = `Chunks — ${doc.filename}`;

        if (!doc.chunks || doc.chunks.length === 0) {
            modalBody.innerHTML = '<div style="text-align:center;color:var(--text-muted);">No chunks found.</div>';
            return;
        }

        modalBody.innerHTML = doc.chunks.map(chunk => `
            <div class="chunk-card">
                <div class="chunk-card__header">
                    <span class="chunk-card__index">Chunk #${chunk.chunk_index + 1}</span>
                    <span class="chunk-card__meta">${chunk.content.length} chars</span>
                </div>
                <div class="chunk-card__content">${escapeHtml(chunk.content)}</div>
            </div>
        `).join('');
    } catch (err) {
        console.error('Failed to load chunks:', err);
        modalBody.innerHTML = '<div style="color:var(--danger);">Failed to load chunks.</div>';
    }

    // Close handlers
    document.getElementById('modalClose').onclick = () => modal.style.display = 'none';
    modal.onclick = (e) => { if (e.target === modal) modal.style.display = 'none'; };
}

async function reindexDoc(docId) {
    if (!confirm('Re-process this document? This will regenerate all chunks and embeddings.')) return;

    try {
        const data = await apiFetch(`/api/knowledge/documents/${docId}/reindex`, { method: 'POST' });
        if (!data) return;
        showToast('🔄 Document re-indexing started', 'success');
        loadDocuments();
        loadStats();
    } catch (err) {
        console.error('Re-index failed:', err);
        showToast('Re-index failed', 'error');
    }
}

async function deleteDoc(docId, filename) {
    if (!confirm(`Delete "${filename}" and all its indexed data? This cannot be undone.`)) return;

    try {
        const data = await apiFetch(`/api/knowledge/documents/${docId}`, { method: 'DELETE' });
        if (!data) return;

        showToast(`🗑 Document deleted`, 'success');
        loadDocuments();
        loadStats();
    } catch (err) {
        console.error('Delete failed:', err);
        showToast('Delete failed', 'error');
    }
}


// ══════════════════════════════════════════════
//  FILTERS
// ══════════════════════════════════════════════

function setupFilters() {
    document.getElementById('filterStatus').addEventListener('change', loadDocuments);
    document.getElementById('filterType').addEventListener('change', loadDocuments);
}


// ══════════════════════════════════════════════
//  POLLING (for processing documents)
// ══════════════════════════════════════════════

function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(() => {
        loadDocuments();
        loadStats();
    }, POLL_INTERVAL);
}

function stopPolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}


// ══════════════════════════════════════════════
//  UTILITIES
// ══════════════════════════════════════════════

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => toast.classList.add('toast--visible'), 10);
    setTimeout(() => {
        toast.classList.remove('toast--visible');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ── Scroll to Top ──
const scrollTopBtn = document.getElementById('scrollTopBtn');
const mainContent = document.querySelector('.main-content');

const scrollTarget = mainContent || window;

scrollTarget.addEventListener('scroll', () => {
    const scrollY = mainContent ? mainContent.scrollTop : window.scrollY;
    scrollTopBtn.classList.toggle('visible', scrollY > 300);
});

scrollTopBtn.addEventListener('click', () => {
    if (mainContent) {
        mainContent.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
});
