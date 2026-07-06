# Backend Architecture

> FastAPI modular monolith — streaming speech intelligence with graph-backed reasoning.

## Overview

The backend is a **single deployable FastAPI application** organized by domain modules. Async I/O handles concurrent WebSocket sessions; a dedicated inference worker thread pool (or subprocess) isolates GPU-bound speech model calls from the event loop.

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────┬─────────────┬──────────────┬──────────────────┤
│  api/       │  streaming/ │  audio/      │  speech/         │
│  HTTP+WS    │  sessions   │  VAD/denoise │  encoder+heads   │
├─────────────┼─────────────┼──────────────┼──────────────────┤
│  graph/     │  reasoning/ │  memory/     │  core/           │
│  conv graph │  agents     │  RAG+store   │  config/auth     │
└─────────────┴─────────────┴──────────────┴──────────────────┘
         │              │                    │
         ▼              ▼                    ▼
    PostgreSQL      Redis Streams         Qdrant
    (+ pgvector)    (job queue)        (embeddings)
```

## Module Responsibilities

### `core/`

| Component | Purpose |
|-----------|---------|
| `config.py` | Pydantic Settings — env-based config |
| `deps.py` | FastAPI dependencies (DB session, current user) |
| `security.py` | JWT auth, API keys for research scripts |
| `events.py` | Startup/shutdown — model warm-up, pool init |

### `api/`

REST and WebSocket entry points. Routes delegate to services; no business logic in route handlers.

| Route group | Methods | Purpose |
|-------------|---------|---------|
| `/health` | GET | Liveness + model readiness |
| `/sessions` | CRUD | Create/list/archive analysis sessions |
| `/sessions/{id}/stream` | WS | Bidirectional audio + event stream |
| `/sessions/{id}/graph` | GET | Conversation graph snapshot |
| `/sessions/{id}/analysis` | GET | Latest scores and coaching |
| `/sessions/{id}/analysis/run` | POST | Trigger reasoning pipeline |
| `/embeddings/search` | POST | Similarity search over acoustic embeddings |
| `/users/me` | GET/PATCH | Profile and preferences |

### `streaming/`

Manages real-time session lifecycle.

```python
# Conceptual flow
SessionManager
  ├── create_session(user_id, config) → Session
  ├── attach_websocket(session_id, ws) → StreamHandle
  ├── on_audio_chunk(handle, bytes) → enqueue AudioFrame
  └── on_disconnect(handle) → finalize graph, persist
```

- **WebSocket protocol:** JSON control messages + binary audio frames (PCM 16-bit mono 16 kHz).
- **Backpressure:** Drop or coalesce chunks if inference queue exceeds threshold; emit `stream.lag` event to client.
- **WebTransport (phase 2):** QUIC-based transport for the audio path — now Baseline across all major browsers (including Safari/iOS as of March 2026). Enables mixing reliable control streams with unreliable datagram delivery (audio frames can drop safely under congestion) on a single connection, without WebRTC's signaling/NAT-traversal complexity for this client-server architecture.

**Streaming failure modes:**

| Failure | Behavior |
|---------|----------|
| Client disconnects during live session | Server holds session open for 60 s; reconnect resumes from last seq |
| Server-side WS crash | SessionManager recovers state from Redis; emits `stream.recovered` on reconnect |
| Audio encoding mismatch | Server detects non-PCM / wrong sample rate → WS close `4009` with expected format |
| GPU OOM during inference | Skip non-critical heads (emotion, prosody); continue with ASR + diarization only |
| Redis stream consumer group stall | Fall back to in-memory buffer (last 30 s); emit `stream.degraded` event |

### `audio/`

CPU-only preprocessing pipeline.

| Stage | Library | Output |
|-------|---------|--------|
| Resample | TorchAudio | 16 kHz mono float32 |
| VAD | Silero VAD | speech/silence segments |
| Denoise | RNNoise | cleaned waveform |
| Chunk | custom | 20–30 ms frames with overlap metadata |
| AEC | optional WebRTC AEC | echo-cancelled stream |

Runs in asyncio executor; outputs `AudioChunk` dataclass with timestamps and VAD flags.

### `speech/`

Single encoder, multiple heads.

```
SpeechService
  ├── Encoder (one checkpoint, lazy-loaded)
  │     encode(waveform) → AcousticEmbedding [B, T, D]
  ├── ASRHead → TranscriptSegment[] (streaming)
  ├── SpeakerHead → SpeakerLabel + confidence
  ├── AcousticHeads (adapter registry)
  │     ├── emotion
  │     ├── prosody
  │     ├── stress
  │     └── fluency
  └── EventHead → AudioEvent[] (overlap, laughter, long pause)
```

**Embedding cache:** After encode, persist embedding to Qdrant + reference in PostgreSQL before running heads. Heads can be re-run independently.

**GPU concurrency model:**

```python
# Single process per GPU; asyncio.Lock serializes encode calls
class SpeechService:
    _encode_lock: asyncio.Lock = asyncio.Lock()

    async def encode(self, waveform: Tensor) -> AcousticEmbedding:
        async with self._encode_lock:
            return await run_in_executor(self._gpu_pool, self._encoder.forward, waveform)
```

- One inference at a time per GPU — avoids OOM from concurrent encoder calls
- LLM runtime (vLLM or SGLang) runs in separate process; encoder gets priority on shared GPU
- If encoder + LLM co-resident on single GPU, encoder gets scheduling priority; LLM runtime uses remaining VRAM (e.g., `--gpu-memory-utilization=0.4`)
- Heads (ASR, emotion, etc.) run sequentially on cached embedding — lock is released after encode

**Model registry (`inference/registry.py`):**

```yaml
encoder:
  name: granite-speech  # swappable via config; evaluate against canary, qwen-audio for target languages
  checkpoint: /models/<encoder-checkpoint>
  device: cuda:0
heads:
  asr:
    # Throughput-optimized default — swap to canary-qwen for accuracy-critical paths
    type: parakeet-tdt-streaming
    # Parakeet-TDT-0.6B-v3: 25 European languages with auto-detection.
    # Does NOT cover Yorùbá or most African languages — non-covered
    # languages need a separate fine-tune, adapter, or different backbone.
    # Alternatives per deployment target:
    #   - Edge / CPU: Nemotron Speech Streaming (NVIDIA)
    #   - Accuracy > throughput: Canary-Qwen-2.5B (Conformer + Qwen decoder, tops HF Open ASR Leaderboard on English WER)
  emotion:
    type: linear_probe
    adapter: adapters/emotion_v1.pt
```

### `graph/`

Builds and queries the conversation graph.

**Node types:** `Session`, `Speaker`, `Turn`, `Embedding`, `Emotion`, `Prosody`, `Event`, `Action`, `ToolCall`, `MemoryRef`

**Edge types:** `SPOKE`, `FOLLOWS`, `EXPRESSES`, `REFERENCES`, `TRIGGERED`, `RETRIEVED`

```python
class GraphBuilder:
    def add_turn(self, session_id, speaker_id, transcript, embedding_id, ...) -> TurnNode
    def link_emotion(self, turn_id, emotion_label, confidence) -> EmotionNode
    def snapshot(self, session_id) -> ConversationGraph  # serializable for agents
```

Stored primarily in PostgreSQL (relational + JSONB for flexible attributes). In-memory NetworkX graph rebuilt per reasoning run for traversal.

### `reasoning/`

Orchestrates the agent pipeline defined in [agents.md](../../agents.md). See that document for the full orchestrator code, dependency injection, agent timeouts, idempotency guards, and kill-recovery strategy.

Key components:
- `ReasoningOrchestrator` — runs the 5-agent pipeline (Retriever → Planner → Reasoner → Verifier → Scorer)
- `LLMClient` — thin wrapper over LLM runtime API (compatible with Ollama, vLLM, and SGLang; defined in [agents.md](../../agents.md))
- Each agent is a class with typed Pydantic input/output schemas
- Agent traces persisted to `analysis_reports.agent_trace` (JSONB column)

**LLM runtime choice:** The agent pipeline re-sends significant overlapping context (system prompt, retrieved evidence, session state) at every stage. For local single-user research, **Ollama** (`localhost:11434`) is the default — simple, no separate server process management. For production or multi-user deployments, both vLLM and SGLang expose an OpenAI-compatible API, so `LLMClient` works with either by swapping `LLM_BASE_URL`. SGLang's RadixAttention (prefix caching) gives a throughput edge over vLLM for this pipeline's shared-prefix pattern.

### `memory/`

| Store | Content | TTL |
|-------|---------|-----|
| Redis | Session state, streaming buffers | Session duration |
| PostgreSQL | Users, sessions, graph nodes, reports | Persistent |
| Qdrant | Acoustic + text embeddings | Persistent, versioned |
| MinIO | Raw audio recordings (opt-in) | Configurable retention |

**Retrieval:** Hybrid search — graph traversal for structural context, Qdrant for semantic/acoustic similarity, PostgreSQL full-text for transcript keyword match.

## API Design Conventions

- **Versioning:** `/api/v1/...`
- **Auth:** Bearer JWT; WebSocket auth via query token or first message
- **Errors:** RFC 7807 Problem Details
- **Pagination:** cursor-based for session lists
- **Idempotency:** `Idempotency-Key` header on analysis trigger

### WebSocket Event Schema

```json
// Client → Server
{ "type": "audio", "seq": 42, "timestamp_ms": 1280 }
// binary frame follows

{ "type": "config", "language": "yo", "heads": ["asr", "emotion"] }

// Server → Client
{ "type": "transcript.partial", "text": "...", "start_ms": 1200, "confidence": 0.91 }
{ "type": "transcript.final", "turn_id": "...", "speaker": "A", "text": "..." }
{ "type": "acoustic", "head": "emotion", "label": "neutral", "confidence": 0.82 }
{ "type": "analysis.ready", "report_id": "..." }
```

## Database Schema (Core Tables)

```sql
-- Simplified; full migrations in backend/migrations/
-- All identifiers lowercase_snake_case per Postgres best practice
-- Targets PostgreSQL 18+ for native uuidv7() support

create extension if not exists vector;

-- ── Users & auth ───────────────────────────────────────────────────

create table users (
    id uuid primary key default uuidv7(),
    email text not null unique,
    display_name text,
    settings jsonb not null default '{}',
    created_at timestamptz not null default now()
);

-- ── Sessions ───────────────────────────────────────────────────────

create table sessions (
    id uuid primary key default uuidv7(),
    user_id uuid not null references users(id) on delete cascade,
    status text not null default 'created'
        check (status in ('created', 'live', 'processing', 'ready', 'archived', 'aborted')),
    language text not null default 'en',
    config jsonb not null default '{}',
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz not null default now()
);
create index sessions_user_id_idx on sessions (user_id);
create index sessions_status_idx on sessions (status);

-- ── Speakers ───────────────────────────────────────────────────────

create table speakers (
    id uuid primary key default uuidv7(),
    session_id uuid not null references sessions(id) on delete cascade,
    label text not null,
    embedding_id uuid
);
create index speakers_session_id_idx on speakers (session_id);

-- ── Turns ──────────────────────────────────────────────────────────

create table turns (
    id uuid primary key default uuidv7(),
    session_id uuid not null references sessions(id) on delete cascade,
    speaker_id uuid not null references speakers(id) on delete cascade,
    text text not null,
    start_ms int not null,
    end_ms int not null,
    confidence float not null check (confidence between 0 and 1),
    turn_index int not null
);
create index turns_session_id_idx on turns (session_id);
create index turns_speaker_id_idx on turns (speaker_id);
create index turns_session_index_idx on turns (session_id, turn_index);

-- ── Embeddings ─────────────────────────────────────────────────────

create table embeddings (
    id uuid primary key default uuidv7(),
    session_id uuid not null references sessions(id) on delete cascade,
    turn_id uuid not null references turns(id) on delete cascade,
    encoder_version text not null,
    vector vector(1024),               -- pgvector column; dim depends on encoder
    vector_id uuid not null,            -- Qdrant point ID
    dims int not null,
    created_at timestamptz not null default now()
);
create index embeddings_session_id_idx on embeddings (session_id);
create index embeddings_turn_id_idx on embeddings (turn_id);
create index embeddings_vector_idx on embeddings
    using hnsw (vector vector_cosine_ops);

-- ── Acoustic Labels ────────────────────────────────────────────────

create table acoustic_labels (
    id uuid primary key default uuidv7(),
    turn_id uuid not null references turns(id) on delete cascade,
    head text not null
        check (head in ('emotion', 'prosody', 'stress', 'fluency')),
    label text not null,
    confidence float not null check (confidence between 0 and 1),
    metadata jsonb
);
create index acoustic_labels_turn_id_idx on acoustic_labels (turn_id);
create index acoustic_labels_head_idx on acoustic_labels (head);

-- ── Audio Events ───────────────────────────────────────────────────

create table audio_events (
    id uuid primary key default uuidv7(),
    session_id uuid not null references sessions(id) on delete cascade,
    turn_id uuid references turns(id) on delete set null,
    event_type text not null
        check (event_type in ('laughter', 'overlap', 'long_pause', 'filler', 'cough', 'silence')),
    start_ms int not null,
    end_ms int not null,
    confidence float not null default 1.0
);
create index audio_events_session_id_idx on audio_events (session_id);
create index audio_events_turn_id_idx on audio_events (turn_id);
create index audio_events_type_idx on audio_events (event_type);

-- ── Analysis Reports ───────────────────────────────────────────────

create table analysis_reports (
    id uuid primary key default uuidv7(),
    session_id uuid not null references sessions(id) on delete cascade,
    status text not null default 'in_progress'
        check (status in ('in_progress', 'completed', 'degraded', 'aborted')),
    scores jsonb,
    coaching jsonb,
    agent_trace jsonb,
    degraded boolean not null default false,
    degradation_reason text,
    created_at timestamptz not null default now(),
    completed_at timestamptz
);
create index analysis_reports_session_id_idx on analysis_reports (session_id);
create index analysis_reports_status_idx on analysis_reports (status);

-- ── Memory Documents (user RAG) ────────────────────────────────────

create table memory_documents (
    id uuid primary key default uuidv7(),
    user_id uuid not null references users(id) on delete cascade,
    title text not null,
    content text not null,
    embedding_id uuid,
    created_at timestamptz not null default now()
);
create index memory_documents_user_id_idx on memory_documents (user_id);
```

**Schema design notes:**
- UUIDv7 (`uuidv7()`) for time-ordered primary keys — native in PostgreSQL 18+ (no extension needed). On PG16/17 deployments, fall back to `create extension if not exists pg_uuidv7;` and `default uuid_generate_v7()`.
- **Security note:** UUIDv7 embeds a millisecond-resolution timestamp, so IDs exposed in URLs or API responses leak creation-time signals (sign-up timing, session volume). Prefer opaque session slugs or short-lived share tokens in public-facing routes where this matters.
- Every foreign key column has an explicit index (Postgres does not auto-index FK columns)
- `check` constraints enforce value ranges and enums at the database level
- HNSW index on the `embeddings` table for local similarity search — preferred over IVFFlat for continuously-growing tables (IVFFlat's k-means clustering is fixed at index build time and degrades as distribution drifts)
- `turn_index` and composite index `(session_id, turn_index)` for efficient timeline ordering queries

## Async & Concurrency Model

| Workload | Model |
|----------|-------|
| HTTP/WS I/O | asyncio (uvicorn) |
| Audio preprocessing | `run_in_executor` (CPU pool) |
| Speech inference | Dedicated queue + single GPU lock |
| LLM agents | Async HTTP to LLM runtime (Ollama, vLLM, or SGLang); parallel where independent |
| Graph writes | Async SQLAlchemy 2.0 |

**Job queue:** Redis Streams for post-session analysis (`analysis.run` jobs). Streaming path stays in-process for latency.

## Connection Pooling

```yaml
# docker-compose — pgbouncer sidecar
postgres:
  image: pgvector/pgvector:pg18
pgbouncer:
  image: edoburu/pgbouncer
  environment:
    DB_HOST: postgres
    DB_PORT: 5432
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 50
    DEFAULT_POOL_SIZE: 15
```
- FastAPI uses asyncpg via SQLAlchemy 2.0 — pooled through pgbouncer in `transaction` mode
- `MAX_CLIENT_CONN` tuned for concurrent sessions; graph writes use explicit transaction blocks
- Redis connections pooled via `redis[hiredis]` connection pool with `max_connections=100`

## Rate Limiting

| Endpoint | Limit | Window | Rationale |
|----------|-------|--------|-----------|
| `/embeddings/search` | 30 req | 60 s | Vector search is expensive; per-user |
| `/sessions/{id}/analysis/run` | 5 req | 60 s | LLM inference cost; global |
| `/sessions` POST (create) | 20 req | 60 s | Per-user; prevents abuse |
| WebSocket connections | 5 concurrent | — | Per-user; browser tab limit |
| API keys (research) | 100 req | 60 s | Per-key; generous for export scripts |

Implemented via Redis sliding window; fastapi-limiter or custom middleware.

## Authentication & JWT

| Concern | Implementation |
|---------|----------------|
| Token type | JWT (HS256), short-lived access (15 min) + refresh (7 days) |
| Storage | httpOnly secure cookie (`__Host-session`); WebSocket via query token on connect |
| Refresh flow | Silent refresh: `POST /api/v1/auth/refresh` reads cookie, returns fresh access JWT in response body (not cookie — client sets it manually) |
| Token revocation | Refresh token blacklist in Redis (`blacklist:refresh:<jti>`), TTL = expiry |
| WebSocket auth | JWT in `?token=` query param on connect; validated on `websocket.accept` |
| API keys | Generated per-user via `POST /users/me/api-keys`; read-only scope; stored as SHA-256 hash in `user_api_keys` table |

**JWT refresh flow:**
```
Client (httpOnly cookie sent automatically)
    │
    ▼
POST /api/v1/auth/refresh  (cookie: __Host-session = refresh_token)
    │
    ▼
Server validates refresh token, checks blacklist
    │
    ▼
200 { access_token: "eyJ...", expires_in: 900 }
    │
    ▼
Client stores in memory (not localStorage) → attaches to API calls via Authorization header
```

## WebSocket Lifecycle & Reconnection

```python
# Server-side session state machine
SessionStatus = Literal["connecting", "live", "reconnecting", "disconnected", "ended"]

# Client reconnect strategy:
# - Exponential backoff: 1s, 2s, 4s, 8s, 16s (max 30s between attempts)
# - Max retry window: 5 minutes total
# - On reconnect: send { type: "reconnect", session_id, last_seq }
# - Server replays missed events from Redis stream backlog (last 60 s)
# - Client deduplicates by seq number
```

**WS error codes sent to client:**

| Code | Meaning | Client action |
|------|---------|---------------|
| `4001` | Invalid token | Redirect to login |
| `4002` | Session not found | Navigate to dashboard |
| `4003` | Session already ended | Switch to replay mode |
| `4008` | Rate limited | Wait, exponential backoff |
| `4100` | GPU inference queue full | Drop non-critical audio frames; show lag indicator |
| `4101` | Model not loaded yet | Show warm-up progress, retry in 5 s |

## Configuration

```env
# .env.example
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://localhost:6379
QDRANT_URL=http://localhost:6333
MINIO_ENDPOINT=localhost:9000
SPEECH_ENCODER=<encoder-name>          # e.g. granite-speech — swappable per evaluation
SPEECH_ENCODER_PATH=/models/<encoder-checkpoint>
LLM_BASE_URL=http://localhost:11434/v1  # Ollama (local/research); swap to vLLM/SGLang for production
LLM_MODEL=<model-name>              # e.g. qwen3-14b-instruct — model selection configures at deploy time
JWT_SECRET=...
CORS_ORIGINS=http://localhost:3000
```

## Testing Strategy

| Layer | Approach |
|-------|----------|
| API | pytest + httpx AsyncClient |
| Audio | Fixture WAV files, golden chunk outputs |
| Speech | Mock encoder returning fixed embeddings |
| Agents | Snapshot tests on agent I/O schemas |
| Integration | docker-compose test profile |

## Deployment (Docker Compose)

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    deploy:
      resources:
        reservations:
          devices: [{ capabilities: [gpu] }]
  postgres:
    image: pgvector/pgvector:pg18
  redis:
    image: redis:7
  qdrant:
    image: qdrant/qdrant
  minio:
    image: minio/minio
  vllm:
    image: vllm/vllm-openai       # or lmsysorg/sglang:latest for prefix-caching workloads
    # optional — for local research, Ollama on :11434 is the default; vLLM/SGLang activate by swapping LLM_BASE_URL
```

Bind to `0.0.0.0:$PORT` for Render compatibility.

## Security

- JWT with short expiry + refresh tokens (see Auth section above)
- Session audio never logged by default; `sessions.audio_persist` opt-in flag
- API keys scoped to read-only for research export scripts; stored as SHA-256 hash
- Rate limiting on `/embeddings/search` and analysis triggers
- CORS restricted to frontend origin
- WebSocket token in query string — acceptable for local/dev; upgrade to `Sec-WebSocket-Protocol` auth in production. If WebTransport (phase 2) replaces the audio path, session auth moves to the WebTransport handshake's serverCertificateHashes or a token in the initial reliable stream, eliminating the query-string exposure entirely.
- Audio chunks never cached to disk in plaintext; ephemeral `/dev/shm` buffer for VAD windows
- Reasoner/Verifier LLM prompts sanitized — no user PII passed in context (speaker labels only)
- Health endpoint (`/health`) exposed; readiness (`/health/ready`) gated on model warm-up

## Extension Points

1. **New acoustic head:** Register adapter in `speech/heads/`, no encoder change
2. **New language:** Swap ASR head or fine-tune adapter; encoder may stay shared
3. **New agent step:** Insert into orchestrator with typed contract
4. **Scale inference:** Extract `speech/` into Ray Serve deployment; API unchanged
