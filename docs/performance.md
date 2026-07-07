# API Performance Tuning

## Quick Start (Dev)

```bash
# Start Docker Desktop first, then:
docker compose -f infra/docker-compose.yml up -d
```

---

## LLM Backend Options

### Fastest (No GPU needed) — Groq

Groq runs on LPU hardware — no GPU needed on your machine. Set in `.env`:

```env
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
LLM_API_KEY=gsk_your_key_here
```

Get a free key at https://console.groq.com.

### Local + GPU — SGLang or vLLM

Both need NVIDIA GPU + CUDA. SGLang's RadixAttention caches shared prefixes across the 5-agent pipeline for ~3–5x throughput vs Ollama.

```yaml
# infra/docker-compose.yml — add as service
  sglang:
    image: lmsysorg/sglang:latest
    ports:
      - "30000:30000"
    volumes:
      - ~/.cache/huggingface:/root/.cache/huggingface
    command: python -m sglang.launch_server
      --model-path Qwen/Qwen3-8B-Instruct
      --host 0.0.0.0 --port 30000
      --context-length 32768 --tp 1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

Then set `LLM_BASE_URL=http://sglang:30000/v1`.

---

## Latency Tuning

### Uvicorn Workers

```yaml
# infra/docker-compose.yml — api service
command: >
  uvicorn app.main:app
  --host 0.0.0.0 --port 8000
  --workers 4                    # match CPU cores
  --loop uvloop                  # faster event loop
  --limit-concurrency 64         # backpressure
  --backlog 2048
  --timeout-keep-alive 30
```

### Database Pool

```python
# backend/app/core/config.py
DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/acoustic_comms?pool_size=20&max_overflow=10"
```

### GPU Audio Pipeline

```python
# backend/app/main.py
encoder = SpeechEncoder(device="cuda")  # was "cpu"

# backend/app/audio/vad.py — ONNX mode for 2-3x faster VAD
model = torch.hub.load("snakers4/silero-vad", "silero_vad", onnx=True)
```

### Agent Timeouts

Tighten for faster iteration:

```env
# .env
ANALYSIS_TIMEOUT_PER_AGENT_S=30
LOG_LEVEL=WARN
```

### Benchmark

```bash
curl -w "\n%{time_total}s\n" http://localhost:8000/health
```
