# LLM Gateway

A production-grade API gateway for Large Language Models with semantic caching and a multi-layer guardrails pipeline. Built to reduce LLM API costs and enforce safety policies before requests reach the model.


---

## The Problem

Every LLM API call costs money and takes 1–3 seconds. When multiple users ask semantically identical questions — "what is BFS", "explain breadth first search", "how does level order traversal work" — exact-match caching misses all of them. Additionally, production LLM applications need safety layers to prevent prompt injection, PII leakage, and off-topic abuse.

This gateway sits between your application and the LLM, solving both problems.

---

## Architecture

```
Incoming Request
       │
       ▼
┌─────────────────────┐
│   Input Guardrails  │
│                     │
│  1. Injection Check │ ──── BLOCK (400) ──► "Prompt injection detected"
│  2. PII Scrubbing   │ ──── scrub & continue
│  3. Domain Policy   │ ──── BLOCK (400) ──► "Off-topic request"
└────────┬────────────┘
         │ passed
         ▼
┌─────────────────────┐
│   L1 Exact Cache    │ ──── HIT ──► return in ~1ms
│   (Redis hash)      │
└────────┬────────────┘
         │ miss
         ▼
┌─────────────────────┐
│  L2 Semantic Cache  │ ──── HIT ──► return in ~10ms
│  (Redis Vector KNN) │
└────────┬────────────┘
         │ miss
         ▼
┌─────────────────────┐
│     LLM Call        │
│  (Groq / OpenAI)    │ ──── ~800–1500ms
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Output Guardrails  │
│  PII scrub on resp  │
└────────┬────────────┘
         │
         ▼
   Cache Store + Return
```

---

## Features

### Semantic Caching (L1 + L2)

- **L1 Exact Cache** — MD5 hash lookup in Redis. Same query twice returns in ~1ms with zero compute.
- **L2 Semantic Cache** — Converts queries to 384-dimensional embeddings using `sentence-transformers/all-MiniLM-L6-v2`. Uses Redis Stack's `FT.SEARCH` with KNN vector similarity to find semantically equivalent past queries. Configurable cosine similarity threshold (default: 0.85).

On a DSA Q&A workload, typical cache hit rates of 60–70% are observed after warmup, directly reducing LLM API costs by the same proportion.

### Guardrails Pipeline

Three-layer input validation ordered by computational cost (cheapest first):

**Layer 1 — Prompt Injection Detection (custom, ~0ms)**
Pattern-based detector covering 5 attack categories: instruction override, role hijacking, system prompt extraction, jailbreak attempts, and delimiter injection. Written from scratch using compiled regex — no external model, no latency overhead.

**Layer 2 — PII Detection & Scrubbing (~20ms)**
Microsoft Presidio-powered detection and anonymization for 8 entity types: email, phone, credit card, IBAN, IP address, person name, location, and crypto addresses. PII is replaced with labeled tokens (`<EMAIL>`, `<PHONE>`) before the query reaches the LLM — ensuring no user data is sent to third-party APIs.

**Layer 3 — Domain Policy Validator (custom, ~30ms)**
Semantic topic enforcement built on the same embedding infrastructure as the cache. Encodes allowed DSA topics as reference embeddings at startup, then computes cosine similarity between the incoming query and each topic. Blocks requests that fall below the similarity threshold. Unlike keyword filters, this understands that "reverse a linked list" is on-topic even without exact keyword matches.

Output guardrails scrub PII from LLM responses before returning to the caller.

### Provider Abstraction

Strategy pattern over LLM providers. All providers implement a common `BaseLLMProvider` interface — swap between Groq, OpenAI, and Anthropic via a single `provider` field in the request body. Adding a new provider requires one file.

### Observability

`GET /metrics` returns a live summary:
- Cache hit rate (%)
- Exact vs semantic cache breakdown
- Blocked request counts by category
- Total tokens consumed
- Average end-to-end latency

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Framework | FastAPI + Uvicorn (async) |
| Cache Storage | Redis Stack (RedisSearch + vector index) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| PII Detection | Microsoft Presidio |
| LLM Providers | Groq (Llama 3.1), OpenAI |

---

## Project Structure

```
llm-gateway/
├── app/
│   ├── api/
│   │   └── routes.py          # FastAPI endpoints
│   ├── cache/
│   │   └── semantic_cache.py  # L1 + L2 cache logic
│   ├── core/
│   │   ├── config.py          # pydantic-settings config
│   │   └── metrics.py         # in-memory metrics store
│   ├── guardrails/
│   │   ├── pii_detector.py    # Presidio PII scrubber
│   │   ├── injection_detector.py  # custom regex injection guard
│   │   ├── domain_policy.py   # custom semantic topic validator
│   │   └── pipeline.py        # unified guardrails pipeline
│   ├── providers/
│   │   ├── base.py            # abstract provider interface
│   │   ├── groq_provider.py   # Groq implementation
│   │   └── factory.py        # provider registry
│   └── main.py
├── main.py                    # entrypoint
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Docker + Docker Compose
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Setup

**1. Clone the repo**
```bash
git clone https://github.com/gupta-vinay123/llm-gateway.git
cd llm-gateway
```

**2. Create virtual environment**
```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment**
```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

**5. Start Redis Stack**
```bash
docker-compose up -d
```

**6. Run the server**
```bash
python main.py
```

Server runs at `http://localhost:8000`. API docs at `http://localhost:8000/docs`.
