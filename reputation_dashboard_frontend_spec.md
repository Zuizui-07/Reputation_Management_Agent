# Reputation Management Dashboard — Frontend Specification
> Use this document as a complete prompt to build the frontend directly.

---

## Project Overview

Build a **Reputation Management Dashboard** for Auxilo Finserve (an education loan NBFC). This is an internal tool used exclusively by one superadmin to monitor, review, and approve AI-drafted replies to social media DMs coming from Facebook and Instagram.

The agent automatically classifies incoming DMs, drafts replies, and either auto-sends them (high confidence) or holds them in an inbox for superadmin approval.

---

## Tech Stack

- **Frontend**: Plain HTML + CSS + Vanilla JavaScript (no frameworks)
- **Backend**: FastAPI (Python) — connect via REST API calls using `fetch()`
- **Auth**: JWT token stored in localStorage, sent as `Authorization: Bearer <token>` header on every request
- **Fonts**: Use Google Fonts — `Syne` (headings/logo), `DM Sans` (body), `DM Mono` (code/badges/timestamps)

---

## Design System

### Color Palette (Dark Theme)
```css
:root {
  --bg: #0d0f12;                        /* Page background */
  --surface: #141619;                   /* Sidebar, cards */
  --surface2: #1c1f24;                  /* Hover states, input bg */
  --border: #26292f;                    /* All borders */

  --accent: #00e5a0;                    /* Primary green — CTAs, active states */
  --accent-dim: rgba(0,229,160,0.08);
  --accent-border: rgba(0,229,160,0.2);

  --lead: #3ecfff;                      /* Potential lead intent */
  --lead-dim: rgba(62,207,255,0.08);

  --warn: #f5a623;                      /* Support / general inquiry intent */
  --warn-dim: rgba(245,166,35,0.08);

  --danger: #ff4f6a;                    /* Sensitive / complaint intent */
  --danger-dim: rgba(255,79,106,0.08);

  --spam: #6b7280;                      /* Spam intent */
  --spam-dim: rgba(107,114,128,0.08);

  --fb-blue: #1877f2;                   /* Facebook brand color */
  --ig-pink: #e1306c;                   /* Instagram brand color */

  --text: #e8eaed;                      /* Primary text */
  --text-dim: #9ca3af;                  /* Secondary text */
  --text-muted: #6b7280;               /* Placeholder, labels */
}
```

### Typography
```css
/* Logo */
font-family: 'Syne', sans-serif;
font-weight: 800;

/* Headings */
font-family: 'Syne', sans-serif;
font-weight: 700;

/* Body */
font-family: 'DM Sans', sans-serif;
font-weight: 400;

/* Badges, timestamps, monospace values */
font-family: 'DM Mono', monospace;
font-weight: 400;
```

### Intent Color Mapping
| Intent Label | Color Variable | Use for |
|---|---|---|
| `potential_lead` | `--lead` (#3ecfff) | Border, badge bg |
| `customer_support` | `--warn` (#f5a623) | Border, badge bg |
| `general_inquiry` | `--warn` (#f5a623) | Border, badge bg |
| `sensitive_complaint` | `--danger` (#ff4f6a) | Border, badge bg |
| `partnership_inquiry` | `--lead` (#3ecfff) | Border, badge bg |
| `spam` | `--spam` (#6b7280) | Border, badge bg |

### Platform Badge Colors
- Facebook → `--fb-blue` (#1877f2) with `f` icon or text "FB"
- Instagram → `--ig-pink` (#e1306c) with `ig` icon or text "IG"

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────┐
│                         TOPBAR                              │
├──────────┬──────────────────────────────────────────────────┤
│          │                                                  │
│ SIDEBAR  │              MAIN CONTENT AREA                  │
│ (220px)  │         (changes based on active nav)           │
│          │                                                  │
└──────────┴──────────────────────────────────────────────────┘
```

The layout is fixed height (100vh), no page scroll. Internal panels scroll independently.

---

## Page 1: Login Page (`/login`)

Single centered card on a dark background.

### Elements:
- Logo: "AUXILO" in Syne 800, color `--accent`, with subtitle "Reputation Manager" in DM Mono below
- Heading: "Welcome back" in Syne 700, white
- Subtext: "Sign in to your admin dashboard" in DM Sans, `--text-muted`
- Email input field (full width, dark bg `--surface2`, border `--border`, focus border `--accent`)
- Password input field (same style, with show/hide toggle)
- "Sign In" button — full width, bg `--accent`, text black, Syne font, bold. On hover: slight brightness increase
- On error: show inline error message in `--danger` color below the button

### Behavior:
- `POST /api/auth/login` with `{ email, password }`
- On success: store JWT in localStorage as `auth_token`, redirect to `/inbox`
- On failure: show "Invalid credentials" error

---

## Sidebar (Persistent across all pages)

### Top Section — Logo
```
REPUTATION MGR          ← Syne 800, --accent color
AUXILO FINSERVE         ← DM Mono, --text-muted, uppercase, tiny
```

### Navigation Items
```
📥  Inbox              ← with badge showing pending count (green badge)
📤  Auto-sent Log      ← no badge
```

### Bottom Section — Admin Info
Small chip at the bottom showing:
```
[A]  superadmin@auxilo.com
     Super Admin
```
With a logout icon/button on hover.

### Active State
Active nav item gets: `background: --accent-dim`, `color: --accent`, `border: 1px solid --accent-border`, left side accent bar (3px wide, `--accent` color).

---

## Page 2: Inbox (`/inbox`) — PRIMARY PAGE

This is the most important screen. Two-panel layout.

### Left Panel — Message List (320px wide, full height, scrollable)

**Header:**
```
Inbox                           Filter ▾
12 pending approval
```
- Title in Syne 700
- Count in DM Mono, `--text-muted`
- Filter dropdown: All Platforms | Facebook | Instagram | All Intents | Lead | Support | Sensitive

**Each Message Card:**
```
┌─────────────────────────────────────────────┐
│ [FB] Rahul Sharma              2 mins ago   │
│ potential_lead badge                         │
│ "Hi, I want to apply for education loan..." │
│ (truncated to 2 lines)                      │
└─────────────────────────────────────────────┘
```
- Platform badge (colored pill): `FB` in `--fb-blue` or `IG` in `--ig-pink`
- Sender name in DM Sans 500
- Timestamp in DM Mono, `--text-muted`, right-aligned
- Intent badge: small pill with intent label, colored per intent mapping above
- Message preview: 2-line truncate, `--text-dim`
- Left border: 3px solid, colored by intent
- Active/selected card: `background: --surface2`, left border becomes intent color full opacity
- Unread indicator: small dot on the left before platform badge
- Cards sorted by newest first

**Loading state:** Skeleton shimmer cards (3-4 cards with animated gradient)

**Empty state:** Centered illustration-free message: "✓ All caught up" in Syne, subtext "No messages pending approval" in `--text-muted`

---

### Right Panel — Message Detail (flex: 1, scrollable)

When a message card is selected, this panel shows full detail.

**Header Bar (sticky at top of right panel):**
```
Rahul Sharma                    [← Back (mobile only)]
facebook.com/profile/...   •  received 2 mins ago
```

**Section 1 — Message Metadata Strip**
Horizontal strip with 3 pills:
```
[📘 Facebook]   [🟢 Potential Lead  87%]   [⏱ 2 min ago]
```
- Platform pill: colored by platform
- Intent + confidence pill: colored by intent, shows confidence % in DM Mono
- Time pill: neutral color

**Section 2 — Original Message**
```
ORIGINAL MESSAGE
┌──────────────────────────────────────────────────────┐
│ Hi, I want to apply for an education loan for my MS  │
│ in Canada from University of Toronto. Can you please │
│ help me understand the process and what documents    │
│ I will need?                                         │
└──────────────────────────────────────────────────────┘
```
- Label "ORIGINAL MESSAGE" in DM Mono, `--text-muted`, uppercase, small
- Message in a card with `background: --surface2`, `border: 1px solid --border`, rounded corners, padding 16px
- Full message text, no truncation

**Section 3 — AI Drafted Reply**
```
AI DRAFTED REPLY                           ✦ regenerate
┌──────────────────────────────────────────────────────┐
│ Hi Rahul! Thank you for reaching out to Auxilo       │
│ Finserve. We'd be happy to help you with your        │ 
│ education loan for MS in Canada. 🎓                  │
│                                                      │
│ Here's what you'll need to get started:              │
│ • Admission letter from the university               │
│ • KYC documents (Aadhaar, PAN)                       │
│ • Last 2 years ITR or Form 16                        │
│                                                      │
│ You can start your application at auxilo.com or      │
│ our team can call you back. Would you prefer a       │
│ callback?                                            │
└──────────────────────────────────────────────────────┘
                                           ✏️ Edit reply
```
- Label "AI DRAFTED REPLY" in DM Mono, `--text-muted`, with `✦ regenerate` link on the right (calls API to regenerate draft)
- Reply in an editable `<textarea>` styled to look like a card (same style as original message card)
- By default `readonly`. Clicking "✏️ Edit reply" makes it editable — border changes to `--accent`, cursor becomes text
- Character count shown bottom-right of textarea in DM Mono, `--text-muted`

**Section 4 — Action Buttons (sticky at bottom of right panel)**
```
┌────────────────────┐  ┌──────────────────────────────┐
│   ✗  Reject        │  │   ✓  Approve & Send          │
└────────────────────┘  └──────────────────────────────┘
```
- Reject: `background: --danger-dim`, `border: 1px solid --danger`, `color: --danger`, hover fills with `--danger`
- Approve & Send: `background: --accent`, `color: #000`, Syne font bold, hover brightens. This is the PRIMARY CTA — make it visually dominant
- Both buttons: rounded, padding 12px 24px, font-size 14px

**After Approve click:**
- Button shows loading spinner briefly
- Success: green checkmark animation, card disappears from left panel list, right panel shows next message or empty state
- Failure: show error toast bottom-right

**After Reject click:**
- Show a small inline reason dropdown (optional): "Not relevant", "Wrong tone", "Needs human reply", "Other"
- Then confirm button — card disappears from list

---

## Page 3: Auto-sent Log (`/auto-sent`)

Full-width table/list of all messages the agent auto-sent without human approval.

### Header
```
Auto-sent Log
Messages sent automatically by the agent (confidence ≥ 85%)
```

### Filter Bar
```
[All Platforms ▾]  [All Intents ▾]  [Date range ▾]       🔍 Search
```

### Table / Card List

Each row/card shows:
```
┌──────────────────────────────────────────────────────────────┐
│ [FB]  Priya Mehta          potential_lead   91%   5 Jan, 2:30pm │
│                                                              │
│ MSG:  "What is the interest rate for abroad education loan?" │
│ SENT: "Hi Priya! Interest rates at Auxilo start from 10.5%  │
│        p.a. for education loans. The exact rate depends..."  │
└──────────────────────────────────────────────────────────────┘
```
- Collapsed by default showing just the header row
- Click to expand and see full original message + full sent reply
- No approve/reject buttons — these are already sent, view only
- "MSG" label in DM Mono green, "SENT" label in DM Mono blue
- Confidence shown in DM Mono with color (green if ≥85%, yellow if 70-84%)

### Pagination
Simple prev/next at the bottom, showing "Showing 1–20 of 143 messages"

---

## Global Components

### Toast Notifications (bottom-right)
```
┌──────────────────────────────┐
│ ✓  Reply sent successfully   │  ← green, auto-dismiss 3s
└──────────────────────────────┘

┌──────────────────────────────┐
│ ✗  Failed to send reply      │  ← red, stays until dismissed
└──────────────────────────────┘
```
Slide in from bottom-right with CSS animation.

### Loading States
- Page load: full skeleton (not spinner) — show ghost versions of the actual layout
- Button actions: replace button text with a small inline spinner (CSS only)
- API calls: subtle top-of-page progress bar (thin, `--accent` colored, like YouTube's red bar)

### Empty States
- Inbox empty: `✓ All caught up — No messages pending approval`
- Auto-sent log empty: `No auto-sent messages yet`
Both centered vertically in their panels, text in Syne, subtext in `--text-muted`

---

## API Endpoints to Connect

```javascript
// Auth
POST   /api/auth/login              → { token, user }

// Inbox
GET    /api/messages/pending        → [{ id, platform, sender_name, sender_id, content, intent, confidence, received_at, drafted_reply }]
POST   /api/messages/{id}/approve   → { success, sent_at }
POST   /api/messages/{id}/reject    → { success }
POST   /api/messages/{id}/regenerate → { drafted_reply }

// Auto-sent log
GET    /api/messages/auto-sent      → [{ id, platform, sender_name, content, intent, confidence, sent_reply, sent_at }]
```

All requests include header: `Authorization: Bearer <token>`

On 401 response → clear localStorage → redirect to `/login`

---

## Responsive Behavior

This is a desktop-first internal tool. No need for full mobile support. However:
- Below 768px: hide left panel, show only message list. Clicking a card shows detail panel full-screen with a back button.
- Below 480px: simplify metadata strip to stacked layout.

---

## File Structure

```
frontend/
├── index.html          ← redirect to /inbox or /login based on auth
├── login.html          ← login page
├── inbox.html          ← inbox page (default after login)
├── autosent.html       ← auto-sent log page
├── css/
│   ├── variables.css   ← all CSS variables (design tokens)
│   ├── base.css        ← reset, typography, global styles
│   ├── sidebar.css     ← sidebar + topbar styles
│   ├── inbox.css       ← inbox two-panel layout
│   └── autosent.css    ← auto-sent log styles
└── js/
    ├── auth.js         ← login, logout, token management
    ├── api.js          ← all fetch() calls wrapped as functions
    ├── inbox.js        ← inbox page logic
    └── autosent.js     ← auto-sent log logic
```

---

## Key Interactions Summary

| Action | Trigger | API Call | UI Result |
|---|---|---|---|
| Load inbox | Page load | GET /messages/pending | Render message list |
| Select message | Click card | none | Show detail in right panel |
| Approve reply | Click "Approve & Send" | POST /messages/{id}/approve | Remove card, show next |
| Reject message | Click "Reject" + confirm | POST /messages/{id}/reject | Remove card, show next |
| Edit reply | Click "✏️ Edit reply" | none (local edit) | Textarea becomes editable |
| Regenerate draft | Click "✦ regenerate" | POST /messages/{id}/regenerate | Replace textarea content |
| Filter messages | Change filter dropdown | GET /messages/pending?platform=facebook | Re-render list |
| View auto-sent | Click nav item | GET /messages/auto-sent | Render log list |
| Expand log row | Click row | none | Expand to show full message |
| Logout | Click logout | none | Clear token, redirect login |

---

## Prompt to Use for Development

Copy and paste this entire document to your developer or AI coding tool with this instruction at the top:

> "Build this Reputation Management Dashboard exactly as specified in this document. Use plain HTML, CSS, and Vanilla JavaScript — no frameworks. Create all files in the structure defined. Connect to the FastAPI backend at `http://localhost:8000`. Use the design system, color palette, typography, and component specs exactly as described. Make it production-quality, pixel-perfect, and fully functional."
