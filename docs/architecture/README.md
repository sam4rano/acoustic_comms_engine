# Acoustic Comms Engine — System Architecture

> Research-grade speech intelligence platform built for a single workstation, open-weight components, and a path to production.

## Classification

| Dimension | Choice | Rationale |
|-----------|--------|-----------|
| Stage | Research MVP → production-ready | Fast iteration on workstation; scale later |
| Team | Solo / small team | Modular monolith over microservices |
| Scale (initial) | <1K sessions | Docker Compose, no Kubernetes |
| Real-time | High | WebTransport (phase 2); WebSocket for MVP |
| Domain | Complex (speech + reasoning) | Clear layer boundaries, graph as source of truth |

### MVP Scope Boundary

| In MVP | Phase 2+ |
|--------|----------|
| Single workstation (Docker Compose) | Kubernetes / Ray Serve |
| WebSocket streaming + MediaRecorder | WebTransport for lower-latency audio delivery |
| Context assembly fusion (L6) | Cross-attention Multimodal Fusion Transformer |
| 5-agent reasoning pipeline | Summarizer, Comparative, Adaptation agents |
| Single GPU speech inference | Dedicated inference pods |
| Monolingual sessions | Cross-lingual comparison, code-switch scoring |
| Dashboard + coaching delivery | Annotation mode, side-by-side comparison |
| pgvector + Qdrant dual store | Qdrant-only after scale validation |

## Design Philosophy

1. **One encoder, many heads** — A single speech foundation model produces shared acoustic embeddings; task adapters (LoRA, linear probes, small MLPs) consume them.
2. **Embeddings as first-class artifacts** — Persist, version, and index acoustic embeddings alongside transcripts.
3. **Conversation graph over flat transcript** — Turns, speakers, emotions, tools, and memory form a queryable graph for reasoning.
4. **Explainable reasoning chain** — Retriever → Planner → Reasoner → Verifier → Scorer, not a single LLM prompt.
5. **Simplicity first** — Plain async FastAPI initially; add Ray Serve, Feast, and Kubernetes only when proven necessary.

## High-Level Architecture

```
                    Client (Browser / API)
                              │
────────────────────────────────────────────────
                    FastAPI Gateway
────────────────────────────────────────────────
                              │
                    Streaming Manager
                 (WebRTC / WebSocket)
                              │
────────────────────────────────────────────────
                   Audio Processing Layer
              VAD • Denoise • AEC • Chunking
                              │
────────────────────────────────────────────────
              Universal Speech Foundation Model
                   (single shared encoder)
                              │
                   Shared Acoustic Embedding
                              │
         ┌──────────┬───────────┬────────────┐
         │          │           │            │
    ASR Head   Speaker Head  Acoustic Heads  Events
         │          │           │            │
         └──────────┴───────────┴────────────┘
                              │
                 Conversation Graph (PostgreSQL + pgvector)
                              │
 ────────────────────────────────────────────────
               Context Assembly (Fusion Layer)
 ────────────────────────────────────────────────
                               │
               Reasoning Agent Pipeline (see agents.md)
                               │
 ────────────────────────────────────────────────
                    Communication Engine
            Dashboard • Coaching • Analytics • API

         ┌──────────────────────────────────┐
         │  Error / Degraded Paths          │
         │  ────────────────────────────    │
         │  • ASR confidence < threshold    │
         │    → abort, suggest re-record    │
         │  • Acoustic heads disabled       │
         │    → score transcript-only       │
         │  • LLM backend unreachable        │
         │    → degraded mode, skip steps   │
         │  • Single-speaker session        │
         │    → adjust dimension weights    │
         │  • Pipeline timeout              │
         │    → partial report with caveats │
         └──────────────────────────────────┘
```

## Layer Map

| Layer | Responsibility | Primary Tech |
|-------|----------------|--------------|
| L0 Client | Capture, playback, live feedback | Next.js, WebSocket (WebRTC phase 2) |
| L1 Gateway | Auth, routing, rate limits | FastAPI |
| L2 Streaming | Session lifecycle, chunk relay | WebSocket, aiortc |
| L3 Audio | VAD, denoise, chunking | Silero VAD, RNNoise, TorchAudio |
| L4 Speech FM | Shared encoder + task heads | PyTorch / ONNX Runtime |
| L5 Graph | Conversation representation | PostgreSQL, NetworkX in-memory |
| L6 Fusion | Speech + text + metadata at analysis time | Context assembly (MVP); cross-attention module (phase 2) |
| L7 Reasoning | Multi-agent pipeline | vLLM / SGLang + agents (see [agents.md](../../agents.md)) |
| L8 Memory | Short/long-term, RAG | Qdrant, PostgreSQL, Redis |
| L9 Delivery | Scores, coaching, exports | FastAPI + Next.js |

## Repository Layout

```
acoustic_comms_engine/
├── agents.md                    # Agent definitions and orchestration
├── docs/architecture/           # This documentation
├── frontend/                    # Next.js application
├── backend/
│   ├── app/
│   │   ├── api/                 # HTTP + WebSocket routes
│   │   ├── core/                # Config, deps, security
│   │   ├── streaming/           # WebRTC / session manager
│   │   ├── audio/               # VAD, denoise, chunking
│   │   ├── speech/              # Foundation model + heads
│   │   ├── fusion/              # Multimodal context assembly (phase 2: transformer)
│   │   ├── graph/               # Conversation graph builder
│   │   ├── reasoning/           # Agent orchestration
│   │   ├── memory/              # Vector + structured memory
│   │   └── models/              # SQLAlchemy / Pydantic schemas
│   ├── inference/               # Model loading, batching
│   └── tests/
├── infra/
│   ├── docker-compose.yml
│   └── prometheus/
└── scripts/
```

## Key Architectural Decisions

### ADR-001: Modular Monolith (FastAPI)

**Decision:** Single FastAPI application with domain modules, not microservices.

**Rationale:** Solo/small team, workstation deployment, shared GPU memory for speech model.

**Revisit when:** Team > 8, or inference latency requires dedicated GPU workers.

### ADR-002: Single Speech Encoder

**Decision:** One primary foundation model (evaluate Granite Speech, Parakeet TDT, Canary, Qwen Audio); expose latent representations to all downstream heads.

**Rationale:** Avoid loading five encoders on limited GPU memory; aligns with 2026 research direction.

**Revisit when:** A single open model clearly wins on all target languages and tasks.

### ADR-003: Embeddings as Persistent Assets

**Decision:** Store acoustic embeddings in PostgreSQL (metadata) + Qdrant (similarity search), versioned per encoder checkpoint.

**Rationale:** Enables transfer learning, retrieval-over-speech, and re-running heads without re-encoding.

### ADR-004: Conversation Graph as Source of Truth

**Decision:** Build and query a graph (Speaker → Turn → Embedding → Emotion → Context → Action) rather than storing flat transcripts alone.

**Rationale:** Powers explainable reasoning, coaching timelines, and multimodal fusion.

### ADR-005: Agent-Based Reasoning Pipeline

**Decision:** Five specialized agents (Retriever, Planner, Reasoner, Verifier, Scorer) orchestrated sequentially with structured I/O.

**Rationale:** Explainability, testability, and independent iteration on each step.

See [agents.md](../../agents.md) for full agent specifications.

## Data Flow (End-to-End)

```text
Audio Stream
     │
     ▼
Audio Processing (VAD, denoise, 16kHz chunks)
     │
     ▼
Speech Foundation Model → cached embeddings
     │
     ├── ASR (streaming, timestamps, confidence)
     ├── Speaker (diarization alignment)
     ├── Acoustic heads (emotion, prosody, stress, fluency)
     └── Audio events (laughter, overlap, silence)
     │
     ▼
Conversation Graph (persist turns + link embeddings)
     │
     ▼
Multimodal Fusion (speech embeddings + transcript + metadata)
     │
     ▼
Reasoning Pipeline (agents.md)
     │
     ▼
Communication Scores • Coaching • Analytics • API responses
```

## Infrastructure (Workstation → Production)

| Concern | Local (Docker Compose) | Production path |
|---------|------------------------|-----------------|
| API | FastAPI on `:8000` | Same + reverse proxy |
| Frontend | Next.js on `:3000` | Vercel or static + CDN |
| DB | PostgreSQL 16 + pgvector | Managed Postgres |
| Vector | Qdrant | Qdrant Cloud or self-hosted |
| Cache / bus | Redis Streams | Redis / NATS |
| Object storage | MinIO | S3-compatible |
| Inference | Local GPU (PyTorch) | Dedicated inference pod |
| LLM | Ollama local (:11434) | vLLM / SGLang |
| Monitoring | Prometheus + Grafana | Same |

## Observability

Core metrics exposed by all services:

| Service | Metric | Type |
|---------|--------|------|
| API | `http_requests_total`, `http_request_duration_seconds` | Counter, Histogram |
| Streaming | `ws_connections_active`, `ws_frames_dropped` | Gauge, Counter |
| Speech | `inference_latency_ms`, `asr_confidence_distribution` | Histogram |
| Agents | `agent_step_duration_ms`, `agent_error_count` | Histogram, Counter |
| Graph | `graph_turns_per_session`, `graph_build_duration_ms` | Histogram |
| Memory | `retrieval_hit_rate`, `qdrant_latency_ms` | Gauge, Histogram |

Alerts for production deploy:
- `ws_connections_active == 0` for > 5 min on active node → restart streaming
- `inference_latency_ms.p99 > 2000` → GPU bottleneck, scale or batch
- `agent_error_count > 5/hour` → check LLM backend health
- `qdrant_latency_ms.p50 > 100` → check vector store, disk I/O

## Related Documents

- [Backend Architecture](./backend.md)
- [Frontend Architecture](./frontend.md)
- [Agent Pipeline](../../agents.md)

## Validation Checklist

- [x] Requirements understood (workstation, open-weight, low-resource languages, research-grade)
- [x] Constraints identified (single GPU, no K8s initially)
- [x] Simpler alternatives considered (monolith over microservices)
- [x] ADRs documented for significant decisions
- [x] Scale path defined without premature complexity
- [ ] Model evaluation complete — Granite Speech vs Parakeet vs Canary vs Qwen Audio
- [ ] End-to-end latency budget validated (< 500 ms ASR partial, < 2 s turn final)
- [ ] GPU memory budget validated (encoder + LLM runtime co-resident on single GPU)
- [ ] pgvector performance at target session volume (< 1K sessions)
- [ ] Agent pipeline outputs verified against human-annotated ground truth
- [ ] Low-resource language performance benchmarked (Yoruba demo target)
