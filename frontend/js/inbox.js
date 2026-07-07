/* ============================================
   INBOX — Page logic
   ============================================ */

(function initInbox() {
    // Only run on inbox page
    if (!document.getElementById('messageList')) return;

    /* ── State ── */
    let messages = [];
    let selectedId = null;

    /* ── DOM refs ── */
    const messageList = document.getElementById('messageList');
    const skeletonCards = document.getElementById('skeletonCards');
    const messageCount = document.getElementById('messageCount');
    const pendingBadge = document.getElementById('pendingBadge');
    const filterPlatform = document.getElementById('filterPlatform');
    const filterIntent = document.getElementById('filterIntent');
    const detailPanel = document.getElementById('messageDetailPanel');
    const detailEmpty = document.getElementById('detailEmpty');
    const detailContent = document.getElementById('detailContent');
    const detailName = document.getElementById('detailName');
    const detailPlatformLink = document.getElementById('detailPlatformLink');
    const detailTimeAgo = document.getElementById('detailTimeAgo');
    const metadataStrip = document.getElementById('metadataStrip');
    const originalMessage = document.getElementById('originalMessage');
    const replyTextarea = document.getElementById('replyTextarea');
    const charCount = document.getElementById('charCount');
    const editReplyBtn = document.getElementById('editReplyBtn');
    const regenerateBtn = document.getElementById('regenerateBtn');
    const approveBtn = document.getElementById('approveBtn');
    const rejectBtn = document.getElementById('rejectBtn');
    const rejectReason = document.getElementById('rejectReason');
    const rejectReasonSelect = document.getElementById('rejectReasonSelect');
    const confirmRejectBtn = document.getElementById('confirmRejectBtn');
    const cancelRejectBtn = document.getElementById('cancelRejectBtn');
    const detailBackBtn = document.getElementById('detailBackBtn');

    /* ── Animation delay cap ── */
    const MAX_ANIM_DELAY = 0.5; // seconds — cards beyond this render instantly
    const ANIM_STEP = 0.04; // seconds per card

    /* ══════════════════════════════════════════
       HELPERS
       ══════════════════════════════════════════ */

    function timeAgo(dateStr) {
        const date = new Date(dateStr.endsWith('z') || dateStr.includes('+')
            ? dateStr
            : dateStr + 'Z');
        const now = new Date();
        const diff = Math.floor((now - date) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
        if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
        if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
        return date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
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

    function intentPillClass(intent) {
        const map = {
            potential_lead: 'meta-pill--lead',
            customer_support: 'meta-pill--support',
            general_inquiry: 'meta-pill--general',
            sensitive_complaint: 'meta-pill--sensitive',
            partnership_inquiry: 'meta-pill--partnership',
            spam: 'meta-pill--spam',
        };
        return map[intent] || '';
    }

    function platformBadge(platform) {
        const span = document.createElement('span');
        span.className = 'badge';
        if (platform === 'facebook') {
            span.classList.add('badge--fb');
            span.textContent = 'FB';
        } else if (platform === 'instagram') {
            span.classList.add('badge--ig');
            span.textContent = 'IG';
        }else if(platform == 'google_reviews'){
            span.classList.add('badge--google');
            span.textContent = 'G';
        } else {
            span.textContent = platform || 'Unknown';
        }
        return span.outerHTML;
    }

    function platformIcon(platform) {
        if (platform === 'facebook') return '📘';
        if (platform === 'instagram') return '📸';
        if (platform === 'google_reviews') return '⭐';
        return '💬';
    }

    function platformPillClass(platform) {
        if (platform === 'facebook') return 'meta-pill--fb';
        if (platform === 'instagram') return 'meta-pill--ig';
        if (platform === 'google-reviews') return 'meta-pill--google';
        return '';
    }

    function getPlatformProfileUrl(platform, senderId) {
        if (platform === 'instagram') return `https://instagram.com/${senderId}`;
        return `https://facebook.com/${senderId}`;
    }

    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str || '';
        return div.innerHTML;
    }

    /* ══════════════════════════════════════════
       RENDER MESSAGE LIST (optimized with DocumentFragment)
       ══════════════════════════════════════════ */

    function renderMessageList() {
        // Remove skeleton
        if (skeletonCards) skeletonCards.style.display = 'none';

        // Clear existing cards (keep skeleton hidden)
        const existingCards = messageList.querySelectorAll('.message-card');
        existingCards.forEach(c => c.remove());

        // Empty state check
        const existingEmpty = messageList.querySelector('.empty-state');
        if (existingEmpty) existingEmpty.remove();

        if (messages.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.innerHTML = `
        <div class="empty-state__icon">✓</div>
        <div class="empty-state__title">All caught up</div>
        <div class="empty-state__sub">No messages pending approval</div>
      `;
            messageList.appendChild(empty);
            messageCount.textContent = '0 pending approval';
            updateBadge(0);
            return;
        }

        messageCount.textContent = `${messages.length} pending approval`;
        updateBadge(messages.length);

        // ── Batch DOM insertion with DocumentFragment ──
        const fragment = document.createDocumentFragment();

        messages.forEach((msg, index) => {
            const card = document.createElement('div');
            card.className = `message-card fade-in${msg.intent === 'spam' ? ' spam-card' : ''}`;
            card.dataset.intent = msg.intent;
            card.dataset.id = msg.id;
            if (msg.id === selectedId) card.classList.add('active');

            // Cap animation delay to avoid long waits on large lists
            const delay = Math.min(index * ANIM_STEP, MAX_ANIM_DELAY);
            card.style.animationDelay = `${delay}s`;

            card.innerHTML = `
        <div class="message-card__header">
          ${platformBadge(msg.platform)}
          <span class="message-card__sender">${escapeHtml(msg.sender_name || 'Unknown Sender')}</span>
          <span class="message-card__time">${timeAgo(msg.received_at)}</span>
        </div>
        <div class="message-card__badges">
          <span class="badge ${intentBadgeClass(msg.intent)}">${intentLabel(msg.intent)}</span>
            ${msg.intent === 'spam' ? '<span class="spam-warning">⚠️ ABUSIVE</span>' : ''}
        </div>
        <div class="message-card__preview">${escapeHtml(msg.content)}</div>
      `;

            card.addEventListener('click', () => selectMessage(msg));
            fragment.appendChild(card);
        });

        // Single DOM insertion
        messageList.appendChild(fragment);
    }

    function updateBadge(count) {
        if (pendingBadge) {
            if (count > 0) {
                pendingBadge.textContent = count;
                pendingBadge.style.display = 'inline-block';
            } else {
                pendingBadge.style.display = 'none';
            }
        }
    }

    /* ══════════════════════════════════════════
       SELECT MESSAGE — DETAIL PANEL
       ══════════════════════════════════════════ */

    function selectMessage(msg) {
        selectedId = msg.id;

        // Update list active state
        messageList.querySelectorAll('.message-card').forEach(c => {
            c.classList.toggle('active', c.dataset.id == msg.id);
        });

        // Show detail panel
        detailEmpty.style.display = 'none';
        detailContent.style.display = 'flex';

        // Mobile: open detail panel
        detailPanel.classList.add('open');

        // Header — use fallback for null sender_name
        detailName.textContent = msg.sender_name || 'Unknown Sender';
        const platformLables = { facebook: 'Facebook', instagram: 'Instagram', google_reviews: 'Google Reviews'}
        detailPlatformLink.textContent = platformLables[msg.platform] || msg.platform;
        detailTimeAgo.textContent = `received ${timeAgo(msg.received_at)}`;

        // Metadata strip
        const confPercent = Math.round((msg.confidence || 0) * 100);
        metadataStrip.innerHTML = `
      <div class="meta-pill ${platformPillClass(msg.platform)}">
        <span class="meta-pill__icon">${platformIcon(msg.platform)}</span>
        ${{ facebook: 'Facebook', instagram: 'Instagram', google_reviews: 'Google Reviews' }[msg.platform] || msg.platform}
      </div>
      <div class="meta-pill ${intentPillClass(msg.intent)}">
        <span>🟢</span>
        ${intentLabel(msg.intent)}
        <span class="meta-pill__confidence">${confPercent}%</span>
      </div>
      <div class="meta-pill">
        <span class="meta-pill__icon">⏱</span>
        ${timeAgo(msg.received_at)}
      </div>
    `;

        // Original message
        originalMessage.textContent = msg.content;

        // Reply textarea
        replyTextarea.value = msg.drafted_reply || '';
        replyTextarea.readOnly = true;
        updateCharCount();

        // Reset edit state
        editReplyBtn.innerHTML = '✏️ Edit reply';

        // Hide reject reason
        rejectReason.classList.remove('visible');

        // Reset button states
        approveBtn.classList.remove('loading');
        rejectBtn.classList.remove('loading');
        // Hide approve + edit buttons for spam messages
        const isSpam = msg.intent === 'spam';
        approveBtn.style.display = isSpam ? 'none' : 'flex';
        editReplyBtn.style.display = isSpam ? 'none' : 'flex';
        regenerateBtn.style.display = isSpam ? 'none' : 'flex';
        replyTextarea.style.display = isSpam ? 'none' : 'block';
        charCount.style.display = isSpam ? 'none' : 'block';

        // Show profile link for spam — use correct platform URL
        const existingProfileLink = detailContent.querySelector('.spam-profile-link');
        if (existingProfileLink) existingProfileLink.remove();
        if (isSpam) {
            const profileLink = document.createElement('a');
            profileLink.className = 'spam-profile-link';
            profileLink.href = getPlatformProfileUrl(msg.platform, msg.sender_id);
            profileLink.target = '_blank';
            profileLink.innerHTML = '👤 View Sender Profile for Legal Action';
            rejectBtn.parentNode.insertBefore(profileLink, rejectBtn);
        }
        confirmRejectBtn.classList.remove('loading');
    }

    function updateCharCount() {
        charCount.textContent = `${replyTextarea.value.length} characters`;
    }

    /* ══════════════════════════════════════════
       ACTIONS
       ══════════════════════════════════════════ */

    // Edit reply toggle
    editReplyBtn.addEventListener('click', () => {
        const isEditing = !replyTextarea.readOnly;
        replyTextarea.readOnly = isEditing;
        editReplyBtn.innerHTML = isEditing ? '✏️ Edit reply' : '✓ Done editing';
        if (!isEditing) {
            replyTextarea.focus();
        }
    });

    // Update char count on input
    replyTextarea.addEventListener('input', updateCharCount);

    // Regenerate draft
    regenerateBtn.addEventListener('click', async () => {
        if (!selectedId) return;
        regenerateBtn.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px;display:inline-block;"></span> regenerating…';

        try {
            const data = await regenerateDraft(selectedId);
            replyTextarea.value = data.drafted_reply;
            updateCharCount();
            showToast('Draft regenerated');

            // Update local state
            const msg = messages.find(m => m.id === selectedId);
            if (msg) msg.drafted_reply = data.drafted_reply;
        } catch (error) {
            showToast('Failed to regenerate draft', 'error');
        }

        regenerateBtn.innerHTML = '<span>✦</span> regenerate';
    });

    // Approve
    approveBtn.addEventListener('click', async () => {
        if (!selectedId) return;
        approveBtn.classList.add('loading');

        try {
            // Check if reply was edited
            const msg = messages.find(m => m.id === selectedId);
            const currentReply = replyTextarea.value;
            const originalDraft = msg ? msg.drafted_reply : '';
            const editedReply = (currentReply !== originalDraft) ? currentReply : null;

            await approveMessage(selectedId, editedReply);
            showToast('Reply sent successfully');
            removeMessageById(selectedId);
        } catch (error) {
            showToast(error.message || 'Failed to send reply', 'error');
            approveBtn.classList.remove('loading');
        }
    });

    // Reject — step 1: show reason dropdown
    rejectBtn.addEventListener('click', () => {
        rejectReason.classList.add('visible');
        rejectReasonSelect.value = '';
    });

    // Cancel reject
    cancelRejectBtn.addEventListener('click', () => {
        rejectReason.classList.remove('visible');
    });

    // Confirm reject
    confirmRejectBtn.addEventListener('click', async () => {
        if (!selectedId) return;
        confirmRejectBtn.classList.add('loading');

        try {
            await rejectMessage(selectedId, rejectReasonSelect.value);
            showToast('Message rejected');
            removeMessageById(selectedId);
        } catch (error) {
            showToast('Failed to reject message', 'error');
            confirmRejectBtn.classList.remove('loading');
        }
    });

    // Back button (mobile)
    detailBackBtn.addEventListener('click', () => {
        detailPanel.classList.remove('open');
        selectedId = null;
        detailEmpty.style.display = 'flex';
        detailContent.style.display = 'none';
    });

    /* ── Remove message & show next ── */
    function removeMessageById(id) {
        messages = messages.filter(m => m.id !== id);
        selectedId = null;

        // Re-render list first, then select next message
        renderMessageList();

        if (messages.length > 0) {
            selectMessage(messages[0]);
        } else {
            detailEmpty.style.display = 'flex';
            detailContent.style.display = 'none';
        }
    }

    /* ══════════════════════════════════════════
       FILTERS
       ══════════════════════════════════════════ */

    filterPlatform.addEventListener('change', loadMessages);
    filterIntent.addEventListener('change', loadMessages);

    /* ══════════════════════════════════════════
       LOAD MESSAGES (with retry button on error)
       ══════════════════════════════════════════ */

    async function loadMessages() {
        const filters = {
            platform: filterPlatform.value,
            intent: filterIntent.value,
        };

        try {
            const data = await getPendingMessages(filters);
            if (!data) return; // null means 401 → redirecting to login
            messages = Array.isArray(data) ? data : (data.messages || []);
            renderMessageList();

            // Auto-select first
            if (messages.length > 0 && !selectedId) {
                selectMessage(messages[0]);
            }
        } catch (error) {
            if (skeletonCards) skeletonCards.style.display = 'none';
            console.error('Failed to load messages:', error);

            // Show empty state with error + retry button
            const existingEmpty = messageList.querySelector('.empty-state');
            if (existingEmpty) existingEmpty.remove();

            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.innerHTML = `
        <div class="empty-state__icon">⚠️</div>
        <div class="empty-state__title">Unable to load messages</div>
        <div class="empty-state__sub">Check your connection and try again</div>
        <button class="btn btn--primary btn--small" style="margin-top:12px;" id="retryLoadBtn">🔄 Retry</button>
      `;
            messageList.appendChild(empty);
            messageCount.textContent = 'Connection error';

            // Attach retry handler
            const retryBtn = document.getElementById('retryLoadBtn');
            if (retryBtn) {
                retryBtn.addEventListener('click', () => {
                    empty.remove();
                    if (skeletonCards) skeletonCards.style.display = '';
                    loadMessages();
                });
            }
        }
    }

    // Initial load
    loadMessages();

})();
