# Frontend Architecture

> Next.js 15 application — live session capture, conversation visualization, and coaching delivery.

## Design Goals

| Goal | Approach |
|------|----------|
| Simple but not bare | shadcn/ui components, consistent spacing, purposeful empty states |
| Real-time first | WebSocket-driven live transcript and acoustic feedback |
| Explainable | Show agent reasoning trace and graph visualization |
| Research-friendly | Export embeddings, graphs, and reports as JSON/CSV |
| Accessible | WCAG 2.1 AA for dashboard and live session UI |

## Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | Next.js 16 (App Router) | SSR for dashboard, client components for streaming |
| Language | TypeScript | Shared types with backend OpenAPI client |
| Styling | Tailwind CSS 4 | Utility-first, fast iteration |
| Components | shadcn/ui + Radix | Accessible, composable, not generic-looking |
| State (server) | TanStack Query | Cache sessions, analysis, user data |
| State (live) | Zustand | WebSocket stream buffer, UI chrome |
| Charts | Recharts | Score trends, radar charts for communication dimensions |
| Graph viz | React Flow (`@xyflow/react`) | Conversation graph explorer |
| Audio | Web Audio API + MediaRecorder | Capture; WebTransport in phase 2 |
| API client | openapi-fetch (generated) | Type-safe REST |
| Real-time | native WebSocket wrapper | Binary + JSON multiplex |

## Application Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout, providers, fonts
│   ├── page.tsx                # Marketing / landing (minimal)
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   └── (dashboard)/
│       ├── layout.tsx          # Sidebar + header shell
│       ├── page.tsx            # Session list + quick stats
│       ├── sessions/
│       │   ├── new/page.tsx    # Session setup (language, heads)
│       │   └── [id]/
│       │       ├── page.tsx    # Live session OR replay
│       │       ├── analysis/page.tsx
│       │       └── graph/page.tsx
│       ├── coaching/page.tsx   # Aggregated coaching history
│       ├── search/page.tsx     # Embedding + transcript search
│       └── settings/page.tsx
├── components/
│   ├── ui/                     # shadcn primitives + Skeleton, Sonner (toast)
│   ├── session/
│   │   ├── LiveCapture.tsx     # Mic controls, level meter, VAD indicator
│   │   ├── TranscriptPanel.tsx # Rolling partial + final turns
│   │   ├── AcousticStrip.tsx   # Emotion/prosody chips per turn
│   │   ├── SessionTimer.tsx
│   │   └── DisconnectOverlay.tsx  # Reconnection banner + retry
│   ├── analysis/
│   │   ├── ScoreCard.tsx       # Communication dimension scores
│   │   ├── CoachingCards.tsx   # Actionable suggestions
│   │   ├── AgentTrace.tsx      # Step-by-step reasoning visibility
│   │   └── RadarChart.tsx
│   ├── graph/
│   │   ├── ConversationGraph.tsx
│   │   └── TurnDetail.tsx
│   └── layout/
│       ├── Sidebar.tsx
│       ├── Header.tsx
│       └── EmptyState.tsx
├── hooks/
│   ├── useSessionStream.ts     # WebSocket lifecycle + reconnect
│   ├── useAudioCapture.ts      # Mic permissions, encoding, tab visibility
│   └── useAnalysis.ts
├── lib/
│   ├── api.ts                  # Generated + configured client
│   ├── ws-protocol.ts          # Event types (mirror backend)
│   ├── audio-encoder.ts        # PCM 16kHz mono encoding (AudioWorklet)
│   ├── reconnect.ts            # Exponential backoff, seq tracking
│   └── i18n.ts                 # Locale config, RTL detection
├── stores/
│   └── session-store.ts        # Live stream state
├── types/
│   └── index.ts                # Re-export from OpenAPI + WS events
├── messages/                   # i18n strings (next-intl)
│   ├── en.json
│   └── yo.json                 # Yoruba UI chrome
└── proxy.ts                    # Auth guard, locale redirect (Next 16; was middleware.ts in 15)
```

## Page Map

```
/                          Landing — product summary, sign in
/login, /register          Auth forms

/dashboard                 Session list, recent scores, "New Session" CTA
/dashboard/sessions/new    Language picker, head toggles, device test
/dashboard/sessions/[id]   Live capture (active) or replay (ended)
/dashboard/sessions/[id]/analysis   Scores, coaching, agent trace
/dashboard/sessions/[id]/graph      Interactive conversation graph
/dashboard/coaching        Cross-session coaching timeline
/dashboard/search         Hybrid search (transcript + acoustic similarity)
/dashboard/settings       Profile, retention, export preferences
```

## Live Session UX

Primary layout for `/dashboard/sessions/[id]`:

```
┌──────────────────────────────────────────────────────────────────┐
│  Header: Session title • Language badge • Timer • End Session    │
├────────────────────────────┬─────────────────────────────────────┤
│                            │                                     │
│   Transcript Panel         │   Acoustic Strip                    │
│   (speaker-colored turns)  │   (emotion • prosody • stress)      │
│                            │                                     │
│                            │   ─────────────────────────────     │
│                            │                                     │
│                            │   Live Scores (mini radar)          │
│                            │                                     │
├────────────────────────────┴─────────────────────────────────────┤
│  Capture Bar: [Mic] [Level meter] [VAD dot] [Connection status] │
└──────────────────────────────────────────────────────────────────┘
```

**States:**

- `connecting` — spinner, device permission prompt
- `live` — streaming transcript, acoustic chips update per turn
- `reconnecting` — DisconnectOverlay banner with elapsed time and retry button; transcript retained
- `processing` — session ended, analysis pipeline running (progress from WS)
- `ready` — link to full analysis and graph views
- `error` — reconnect offer, clear error message
- `degraded` — server reported fallback mode (e.g., emotion head disabled); indicator in header

**Loading skeletons:** Every async view uses `Skeleton` components:
- Session list: card-shaped placeholders with shimmer animation
- Analysis: ScoreCard skeletons (gray bars) + AgentTrace step placeholders
- Graph: node/edge wireframe before layout stabilizes
- Transcript: gray text blocks mimicking turn height distribution

## Component Design Notes

### LiveCapture

- Requests `getUserMedia({ audio: true })`
- Encodes to PCM 16-bit mono 16 kHz via `AudioWorklet` (low latency)
- Sends binary frames over WebSocket with sequence numbers
- Visual level meter from AnalyserNode
- VAD indicator reflects server-side `acoustic` events

### DisconnectOverlay

- Appears after 3 s without server heartbeat (server sends `ping` every 5 s)
- Shows connection status icon, elapsed disconnected time, retry button
- On reconnect: replays missed events from server-supplied backlog (deduplicated by `seq`)
- If reconnect fails after 5 min window → session auto-ends; offers re-record

### iOS Safari Considerations

| Quirk | Mitigation |
|-------|------------|
| `getUserMedia` requires HTTPS (localhost exempt) | Dev on `localhost:3000`; production behind reverse proxy with valid TLS |
| AudioContext suspended until user gesture | `resume()` called on first mic button tap |
| `AudioWorklet` limited to 128-sample buffer | PCM encoder handles any quantum size; no quality loss. Under WebTransport (phase 2), datagram-based delivery removes the chunk alignment concerns present with WebSocket framing. |
| Page unload kills WS immediately | `beforeunload` handler sends `disconnect` control frame; backend holds session 60 s |
| Background tabs may throttle timers | `requestAnimationFrame`-driven meter pauses gracefully; no audio data loss |

### Tab Visibility

```typescript
// useAudioCapture — respond to visibility changes
useEffect(() => {
    const handle = () => {
        if (document.hidden) {
            // Continue capturing (no pause) but mute AnalyserNode → zero meter
            analyser.disconnect();
        } else {
            analyser.connect(ctx.destination);
        }
    };
    document.addEventListener('visibilitychange', handle);
    return () => document.removeEventListener('visibilitychange', handle);
}, []);
```
- Audio capture **never stops** when tab is hidden (uninterrupted recording)
- UI-only components (level meter, VAD dot) pause rendering when hidden
- On tab re-focus: re-attach visualizers, re-sync missed transcript turns via WS backlog

### i18n & Low-Resource Language Support

- `next-intl` for UI chrome (not transcript content — content language is session-language)
- Default locale: `en`; additional: `yo` (Yoruba), `ha` (Hausa), `fr` (French)
- RTL support via CSS logical properties (`start`/`end` instead of `left`/`right`); `dir="rtl"` on `<html>` for Arabic-script languages (phase 2)
- Noto Sans and Noto Sans Mono extended font stack for broad Unicode coverage
- Language-specific date/time/score formatting via `Intl` APIs

### TranscriptPanel

- Partial transcripts rendered in muted style at bottom
- Final turns committed with speaker color (A/B/C palette)
- Click turn → highlight corresponding graph node
- Supports low-resource language fonts (Noto Sans extended)

### AgentTrace

- Collapsible timeline: Retriever → Planner → Reasoner → Verifier → Scorer
- Each step shows inputs summary, output JSON (pretty), duration
- Builds trust for research users; critical for debugging

### ConversationGraph

- React Flow (`@xyflow/react` v12+) nodes: Speaker, Turn, Emotion, Event
- Auto-layout via dagre
- **v12 API notes:** node dimensions live under `node.measured` (not directly on node); `node.parentNode` renamed to `node.parentId` — both affect dagre layout code
- Side panel for selected turn metadata + embedding version
- Export PNG / JSON

## Data Flow (Client)

```
User mic
    │
    ▼
useAudioCapture → PCM chunks
    │
    ▼
useSessionStream (WebSocket)
    │
    ├──► session-store (partials, turns, acoustic labels)
    │
    └──► TanStack Query invalidation on analysis.ready

Dashboard pages
    │
    ▼
TanStack Query ← REST API (/sessions, /analysis, /graph)
```

## Authentication

- JWT stored in httpOnly cookie (set by backend via BFF route or direct login response)
- Next.js `proxy.ts` (replaces `middleware.ts` in Next 16) protects `(dashboard)/*`
- WebSocket connects with token in query string or first auth message
- Refresh handled silently via `/api/auth/refresh` route handler
- **Security:** Pin to current Next.js 16 patch — 16.2 disclosed SSRF via WebSocket upgrades and proxy bypass via segment-prefetch routes, both relevant to this app's WebSocket-heavy / proxy-gated auth model

## Theming

```css
/* Semantic tokens — not bare gray boxes */
--background: warm neutral (zinc-50 / zinc-950)
--primary: deep teal (communication / clarity association)
--accent: amber (coaching highlights)
--speaker-a: blue-500
--speaker-b: violet-500
--speaker-c: emerald-500
```

- Light mode default; dark mode via `next-themes`
- Cards with subtle border and shadow — not flat white slabs
- Typography: **Geist Sans** (UI), **Geist Mono** (transcript timestamps, agent trace)

## Responsive Behavior

| Breakpoint | Layout |
|------------|--------|
| Desktop (≥1024px) | Side-by-side transcript + acoustic panel |
| Tablet | Stacked panels, capture bar fixed bottom |
| Mobile | Transcript primary; acoustic in bottom sheet |

Live session on mobile is supported but marketed as desktop-first for research capture quality.

## Performance

- Virtualize long transcripts (`@tanstack/react-virtual`)
- Debounce graph layout updates during live session
- Code-split React Flow and Recharts (dynamic import)
- Service worker optional for offline replay of cached sessions (phase 2)

## OpenAPI Integration

```bash
# Generate client from backend schema
pnpm run generate:api
# → lib/api.generated.ts
```

Shared event types in `lib/ws-protocol.ts` manually maintained until backend publishes JSON Schema for WS events.

## Error & Empty States

Every list view uses `EmptyState` with icon, title, description, and primary action — never a blank page.

| Context | Message tone |
|---------|--------------|
| No sessions | "Start your first analysis session" + CTA |
| Analysis pending | Progress animation + estimated wait |
| Search no results | Suggest broader query or check language filter |
| Mic denied | Step-by-step browser permission instructions |

## Accessibility

- Live regions for new transcript turns (`aria-live="polite"`)
- Keyboard navigable graph nodes
- Color not sole indicator for emotion labels (icon + text)
- Focus trap in session end confirmation dialog

## Build & Deploy

```bash
pnpm dev          # localhost:3000, proxies API to :8000 (Turbopack — stable in Next 16)
pnpm build        # static + server components
pnpm start
```

Environment:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/api/v1
```

Production: deploy to Vercel or serve static export behind same domain as API (CORS simplification).

## Phase 2 Enhancements (Not MVP)

- **WebTransport for audio path** — QUIC-based, Baseline across all major browsers (Chrome, Firefox, Edge, Safari/iOS) as of March 2026. Enables mixing reliable control streams with unreliable datagrams (audio frames — safe to drop under congestion) on one connection, without WebRTC's signaling/ICE/NAT-traversal overhead that a client-server (not peer-to-peer) architecture doesn't need. WebRTC is only the right call if the roadmap adds true P2P features (e.g., multi-party live coaching).
- Side-by-side session comparison view
- Annotation mode for ground-truth labeling (active learning)
- Extended i18n: Arabic-script languages (Hausa via Arabic script), RTL layout support
- Offline session replay via Service Worker cache
- PWA install for mobile research capture
