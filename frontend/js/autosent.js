/* ============================================
   AUTO-SENT LOG — Page logic
   ============================================ */

(function initAutoSent() {
    // Only run on autosent page
    if (!document.getElementById('logScroll')) return;

    /* ── State ── */
    let allMessages = [];
    let filteredMessages = [];
    let currentPage = 1;
    let totalPages = 1;
    let totalMessages = 0;
    const perPage = 20;

    /* ── Animation delay cap ── */
    const MAX_ANIM_DELAY = 0.5; // seconds
    const ANIM_STEP = 0.03; // seconds per card

    /* ── DOM refs ── */
    const logScroll = document.getElementById('logScroll');
    const skeletonCards = document.getElementById('skeletonCards');
    const emptyState = document.getElementById('emptyState');
    const filterPlatform = document.getElementById('filterPlatform');
    const filterIntent = document.getElementById('filterIntent');
    const searchInput = document.getElementById('searchInput');
    const pagination = document.getElementById('pagination');
    const paginationInfo = document.getElementById('paginationInfo');
    const prevPageBtn = document.getElementById('prevPageBtn');
    const nextPageBtn = document.getElementById('nextPageBtn');

    /* ══════════════════════════════════════════
       HELPERS
       ══════════════════════════════════════════ */

    function formatDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-IN', {
            day: 'numeric',
            month: 'short',
        }) + ', ' + date.toLocaleTimeString('en-IN', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
        });
    }

    function intentLabel(intent) {
        const map = {
            potential_lead: 'Potential Lead',
            customer_support: 'Customer Support',
            general_inquiry: 'General Inquiry',
            sensitive_complaint: 'Sensitive Complaint',
            partnership_inquiry: 'Partnership Inquiry',
            spam: 'Spam',
        };
        return map[intent] || intent;
    }

    function intentBadgeClass(intent) {
        const map = {
            potential_lead: 'badge--lead',
            customer_support: 'badge--support',
            general_inquiry: 'badge--general',
            sensitive_complaint: 'badge--sensitive',
            partnership_inquiry: 'badge--partnership',
            spam: 'badge--spam',
        };
        return map[intent] || '';
    }

    function platformBadge(platform) {
        if (platform === 'facebook') return '<span class="badge badge--fb">FB</span>';
        if (platform === 'instagram') return '<span class="badge badge--ig">IG</span>';
        const span = document.createElement('span');
        span.className = 'badge';
        span.textContent = platform || 'Unknown';
        return span.outerHTML;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    /* ══════════════════════════════════════════
       RENDER (optimized with DocumentFragment)
       ══════════════════════════════════════════ */

    function renderLogCards() {
        // Hide skeleton
        if (skeletonCards) skeletonCards.style.display = 'none';

        // Remove existing cards
        logScroll.querySelectorAll('.log-card').forEach(c => c.remove());

        if (allMessages.length === 0) {
            emptyState.style.display = 'flex';
            pagination.style.display = 'none';
            return;
        }

        emptyState.style.display = 'none';

        // ── Batch DOM insertion with DocumentFragment ──
        const fragment = document.createDocumentFragment();

        allMessages.forEach((msg, index) => {
            const confPercent = Math.round((msg.confidence || 0) * 100);
            const confClass = confPercent >= 85 ? 'log-card__confidence--high' : 'log-card__confidence--med';

            const card = document.createElement('div');
            card.className = 'log-card fade-in';

            // Cap animation delay to avoid long waits on large lists
            const delay = Math.min(index * ANIM_STEP, MAX_ANIM_DELAY);
            card.style.animationDelay = `${delay}s`;

            card.innerHTML = `
        <div class="log-card__header">
          ${platformBadge(msg.platform)}
          <span class="log-card__sender">${escapeHtml(msg.sender_name)}</span>
          <div class="log-card__badges">
            <span class="badge ${intentBadgeClass(msg.intent)}">${intentLabel(msg.intent)}</span>
            <span class="log-card__confidence ${confClass}">${confPercent}%</span>
          </div>
          <span class="log-card__time">${formatDate(msg.sent_at)}</span>
          <span class="log-card__chevron">▼</span>
        </div>
        <div class="log-card__body">
          <div class="log-card__section">
            <div class="log-card__label log-card__label--msg">MSG</div>
            <div class="log-card__text">${escapeHtml(msg.content)}</div>
          </div>
          <div class="log-card__section">
            <div class="log-card__label log-card__label--sent">SENT</div>
            <div class="log-card__text">${escapeHtml(msg.sent_reply)}</div>
          </div>
        </div>
      `;

            // Toggle expand
            const header = card.querySelector('.log-card__header');
            header.addEventListener('click', () => {
                card.classList.toggle('expanded');
            });

            fragment.appendChild(card);
        });

        // Single DOM insertion
        logScroll.appendChild(fragment);

        // Update pagination
        updatePagination();
    }

    function updatePagination() {
        if (totalMessages > perPage) {
            pagination.style.display = 'flex';
            const start = (currentPage - 1) * perPage + 1;
            const end = Math.min(currentPage * perPage, totalMessages);
            paginationInfo.textContent = `Showing ${start}–${end} of ${totalMessages} messages`;
            prevPageBtn.disabled = currentPage <= 1;
            nextPageBtn.disabled = currentPage >= totalPages;
        } else {
            pagination.style.display = 'none';
        }
    }

    /* ══════════════════════════════════════════
       EVENTS
       ══════════════════════════════════════════ */

    filterPlatform.addEventListener('change', () => { currentPage = 1; loadAutoSent(); });
    filterIntent.addEventListener('change', () => { currentPage = 1; loadAutoSent(); });

    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            currentPage = 1;
            loadAutoSent();
        }, 300);
    });

    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            loadAutoSent();
            logScroll.scrollTop = 0;
        }
    });

    nextPageBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadAutoSent();
            logScroll.scrollTop = 0;
        }
    });

    /* ══════════════════════════════════════════
       LOAD DATA — uses server-side pagination and filtering
       ══════════════════════════════════════════ */

    async function loadAutoSent() {
        try {
            // Send all filter params to the server for proper pagination
            const filters = {
                platform: filterPlatform.value || undefined,
                intent: filterIntent.value || undefined,
                search: searchInput.value.trim() || undefined,
                page: currentPage,
                limit: perPage,
            };

            const data = await getAutoSentMessages(filters);

            // Handle paginated server response
            if (data && typeof data === 'object' && !Array.isArray(data)) {
                allMessages = data.messages || [];
                totalMessages = data.total || allMessages.length;
                totalPages = data.total_pages || Math.ceil(totalMessages / perPage);
            } else {
                // Fallback for array response
                allMessages = Array.isArray(data) ? data : [];
                totalMessages = allMessages.length;
                totalPages = 1;
            }

            renderLogCards();
        } catch (error) {
            if (skeletonCards) skeletonCards.style.display = 'none';
            console.error('Failed to load auto-sent messages:', error);

            emptyState.style.display = 'flex';
            emptyState.querySelector('.empty-state__title').textContent = 'Unable to load messages';
            emptyState.querySelector('.empty-state__sub').textContent = 'Check your connection and try again';
            emptyState.querySelector('.empty-state__icon').textContent = '⚠️';

            // Add retry button if not already present
            let retryBtn = emptyState.querySelector('#retryAutoSentBtn');
            if (!retryBtn) {
                retryBtn = document.createElement('button');
                retryBtn.id = 'retryAutoSentBtn';
                retryBtn.className = 'btn btn--primary btn--small';
                retryBtn.style.marginTop = '12px';
                retryBtn.textContent = '🔄 Retry';
                retryBtn.addEventListener('click', () => {
                    emptyState.style.display = 'none';
                    if (skeletonCards) skeletonCards.style.display = '';
                    loadAutoSent();
                });
                emptyState.appendChild(retryBtn);
            }
        }
    }

    // Initial load
    loadAutoSent();

})();
