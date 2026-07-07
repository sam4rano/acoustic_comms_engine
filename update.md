# Acoustic Comms Engine — Progress Report

**Date:** July 7, 2026  
**Branch:** `main` (2 commits, ~1350 lines changed across 29 files + 7 new files)

---

## Project Summary

The Acoustic Comms Engine is a speech communication analysis platform. A user records audio through a browser, the backend transcribes it via Groq Whisper, then runs a multi-agent reasoning pipeline (Planner → Reasoner → Verifier → Scorer) through a Groq-hosted LLM to produce quantified communication scores and actionable coaching recommendations.

---

## What Has Been Done

### Backend

- **Auth layer** — Simplified to no-auth mode for open-ended development. `get_current_user()` returns a dev user ID with no credential checks. Auth can be added later without changing endpoint signatures.

- **Database** — Removed Alembic migration system in favor of auto-creating tables on startup (`create_all`). Cleaner for early-stage iteration where schema is fluid. Can reintroduce Alembic when the schema stabilizes.

- **5-Agent Reasoning Pipeline** — Wired the full Planner → Reasoner → Verifier → Scorer chain through Groq's LLM API. Previously the analysis endpoint used a single monolithic Groq prompt; now each agent runs independently with typed inputs/outputs:
  - **Planner** — Selects communication dimensions and creates an analysis plan
  - **Reasoner** — Drafts evidence-linked claims from the transcript (LLM-backed, falls back to rule-based `GraphAnalyzer` if Groq is down)
  - **Verifier** — Validates claims against the conversation graph, flags hallucinations
  - **Scorer** — Computes dimension scores, generates coaching recommendations from templates

- **Transcription + Pipeline service** — Separated concerns into two services:
  - `GroqService` — Handles Whisper transcription
  - `PipelineService` — Coordinates the 5-agent reasoning pipeline, builds a minimal `ConversationGraph` from a single transcript, runs all agents

- **Graceful degradation** — The analysis endpoint no longer returns HTTP 502 on transcription failure. Instead it returns `status: "degraded"` with algorithmic fallback scores and coaching. The system works with or without a configured Groq API key.

- **Streaming sessions** — `StreamSessionManager` now supports optional Redis-backed persistence. Session metadata is serialised to Redis on create/update/remove and can be restored after a process restart. Falls back cleanly to in-memory-only when Redis is unavailable.

- **Postgres port** — Unified to standard `5432` across docker-compose, config defaults, and bootstrap script.

### Frontend

- **Analysis persistence** — Analysis results are cached in `localStorage` with LRU eviction. Survives tab close, page navigation, and backend restarts. Created `lib/analysis-cache.ts`.

- **Session routing** — Sessions list now detects cached analysis and links directly to the analysis page (shows an "Analyzed" badge). Session detail page auto-redirects to analysis when cached data exists.

- **Analysis page** — Handles all response states (`complete`, `degraded`, `pending`, `no_speech`) gracefully. Coaching section has an empty-state fallback message. All back-navigation links point to the sessions list.

- **Recording page** — Caches analysis response before redirecting. Handles `no_speech` responses without redirecting to a broken analysis page.

### Infrastructure

- **Environment** — `.env.example` removed from git tracking and added to `.gitignore`. Safe template with placeholder API key committed locally for bootstrap. Exposed Groq API key rotated.
- **`backend/cache/`** — Added to `.gitignore` (contains compiled Silero VAD model binary).
- **Bootstrap script** — Removed Alembic step; `create_all` handles table creation on API startup.

---

## Issues Resolved

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | Exposed Groq API key in `.env.example` | Committed to git history | Removed from tracking, gitignored, key rotated |
| 2 | Auth bypassed but cluttered | `HTTPBearer` + `decode_token` with silent fallback | Simplified to single `return DEV_USER_ID` |
| 3 | Alembic + `create_all` conflict | Two migration strategies competing | Removed Alembic, kept `create_all` |
| 4 | Postgres port mismatch | Compose used 5434, config defaulted to 5432 | Unified to 5432 |
| 5 | 5-agent pipeline bypassed | `analyze()` used a single monolithic Groq prompt | Created `PipelineService` running the full agent chain |
| 6 | Analysis lost on navigation | In-memory backend store only | Added `localStorage` caching on client |
| 7 | Session list showed 0 turns, linked to recorder | Turns not persisted; no analysis-awareness | Links to analysis when cached; removed misleading turn count |
| 8 | Coaching section empty | LLM Planner returned dimension names ("Pace") that didn't match `COACHING_TEMPLATES` keys ("pacing") | Added `_DIMENSION_ALIASES` normalisation mapper |
| 9 | Page crash on incomplete report data | Analysis page accessed `.dimensions.map()` on `{status: "pending"}` response | Added `status !== "complete" && status !== "degraded"` guard |
| 10 | Transcription failure killed entire analysis | 502 error on Groq Whisper failure | Degraded report with fallback coaching instead of hard error |
| 11 | Redundant VAD null check | Double `if cls._model is None` | Removed dead inner check |
| 12 | Streaming init warning suppressed | Exception swallowed silently | Now logs actual exception message |

---

## Architecture Overview (Current Data Flow)

```
Browser Mic → PCM audio → POST /sessions/{id}/analysis/analyze
                               │
                    ┌──────────┴──────────┐
                    │   GroqService       │
                    │   (Whisper)         │
                    │   transcript text   │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │  PipelineService    │
                    │  ┌───────────────┐  │
                    │  │   Planner     │  │  ← Groq LLM
                    │  │   Reasoner    │  │  ← Groq LLM
                    │  │   Verifier    │  │  ← rules-only
                    │  │   Scorer      │  │  ← templates
                    │  └───────────────┘  │
                    │  AnalysisReport     │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │  Frontend           │
                    │  localStorage cache │
                    │  /sessions/{id}/    │
                    │       analysis      │
                    │  Scores + Coaching  │
                    └─────────────────────┘
```

---

## Current Work in Progress

1. **Coaching section rendering verification** — Ensuring the coaching cards render correctly end-to-end. The alias mapper fix was just applied to resolve the dimension name mismatch between the LLM Planner output and the Scorer templates.

2. **Groq API key setup** — The system will produce degraded (algorithmic) reports without a valid Groq key. Full LLM-powered analysis requires `LLM_API_KEY` in `.env`. Documenting this for the team.

---

## Key Files (Quick Reference)

| File | Role |
|------|------|
| `backend/app/services/pipeline_service.py` | 5-agent pipeline coordinator |
| `backend/app/services/groq_service.py` | Whisper transcription + fallback analysis |
| `backend/app/reasoning/agents/scorer.py` | Dimension scoring + coaching generation |
| `backend/app/api/v1/analysis.py` | POST `/analyze` and GET analysis endpoints |
| `backend/app/streaming/manager.py` | WebSocket session manager with Redis backing |
| `frontend/lib/analysis-cache.ts` | localStorage persistence utility |
| `frontend/app/(dashboard)/sessions/[id]/analysis/page.tsx` | Analysis dashboard UI |
| `frontend/app/(dashboard)/sessions/[id]/page.tsx` | Recording page UI |
| `frontend/app/(dashboard)/sessions/page.tsx` | Sessions list UI |
