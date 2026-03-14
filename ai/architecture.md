# Architecture

## Goal

Enable a hybrid memory architecture where the assistant can:

- run with an external LLM provider by API key,
- run with a local model provider,
- use the same `/api/v1/chat` contract in both modes,
- and apply an explicit memory policy layer that decides what to persist.

## Non-goals (phase 1)

- No autonomous tool-use planner in response generation.
- No automatic long-term summarization jobs yet.
- No cross-user shared memory.

## Current status

Phase 1 is complete:

- provider abstraction and runtime routing are in place;
- memory orchestration supports deterministic rules and optional LLM policy mode;
- retrieval v2 is live with token-budgeted layered context assembly;
- observability and deployment/runbook documentation are in place.

## Proposed target architecture

### 1) Provider abstraction layer

Introduce a unified provider interface for all model calls:

- `chat.generate(...)`
- `embeddings.embed(...)`
- `memory_policy.classify(...)` (optional lightweight model for routing decisions)

Provider implementations:

- `OpenAIProvider` (external, key-based)
- `LocalProvider` (Ollama/vLLM/llama.cpp-compatible HTTP adapter)

Routing config:

- `PRIMARY_LLM_PROVIDER` = `openai|local`
- `EMBEDDING_PROVIDER` = `openai|local`
- optional `MEMORY_POLICY_PROVIDER` = `openai|local|rules`

Operational requirements:

- Provider selection is hot-configurable via environment variables.
- Chat flow must return deterministic error mapping (`provider_unavailable`, `invalid_provider_config`).
- Fallback policy: if configured provider fails hard, request fails fast (no hidden cross-provider retries in phase 1).

### 2) Agentic memory orchestrator (policy layer)

Add a dedicated memory-orchestration component between user message intake and persistence:

- input: user turn + recent context + current user profile/memory summary
- output: structured `MemoryActions[]`

Example actions:

- `UPSERT_PROFILE_FACT` (long-lived user facts)
- `ADD_EPISODIC_MEMORY` (important session events)
- `ADD_SEMANTIC_MEMORY` (vectorized knowledge snippets)
- `SKIP` (no persistence)

Policy modes:

1. `rules` (deterministic, cheap default)
2. `llm_policy` (agent model decides actions)
3. `hybrid` (rules first, model resolves ambiguous cases)

Guardrails:

- `sensitive` detector blocks raw secrets from persistence by default.
- Low-confidence actions are dropped or converted to `SKIP`.
- Every decision is auditable (policy mode + confidence + reason).

### 3) Memory storage model

Use 3 explicit memory scopes:

- **Profile memory** (stable facts, preferences, constraints)
- **Episodic memory** (conversation events with timestamps)
- **Semantic/vector memory** (retrieval chunks + embeddings)

Each memory record should include:

- `source_turn_id`
- `confidence`
- `importance`
- `ttl` (optional)
- `privacy_tag` (`normal|sensitive`)
- `policy_mode` (`rules|llm_policy|hybrid`)

### 4) Retrieval pipeline

At response time, build memory context with layered retrieval:

1. Profile facts (small deterministic budget)
2. Recent episodic events
3. Top-k semantic matches (vector search)
4. Optional reranker stage (if available)

Then enforce a strict token budget before final generation.

Quality constraints:

- Retrieval should be user-scoped only (strict `user_id` isolation).
- Ranking must be deterministic for equal scores (stable tie-breaker by timestamp/id).
- Context builder must expose contribution counters for observability.

### 5) Local + external operation model

Support two production modes with identical API behavior:

- **Cloud mode**: external LLM + external embeddings
- **Private mode**: local LLM + local embeddings

And one mixed mode:

- external LLM + local embeddings (or vice versa) for cost/privacy balancing.

### 6) Deployment topology direction

Near-term deployment target:

- keep one repository for backend, future frontend, and infrastructure assets;
- keep backend as a modular monolith while the product surface is still evolving;
- package runtime components so they can be deployed independently on Kubernetes.

Target Kubernetes workload split:

- `api` deployment for FastAPI backend;
- `frontend` deployment when UI work starts;
- `worker` or `cron` deployment for background memory maintenance jobs;
- `redis` deployment/service for cache/queue support;
- PostgreSQL as either managed infrastructure or a stateful workload;
- optional `model-serving` deployment for local LLM/embedding providers.

Rationale:

- preserves fast iteration in one codebase;
- supports operational isolation by runtime role;
- avoids premature backend microservice fragmentation.

## Rollout plan (incremental)

### Phase A — Provider abstraction foundation

- Introduce interfaces/adapters and runtime config.
- Add contract tests for both provider modes.
- Exit criteria: same API schema and status mapping across `openai` and `local`.

### Phase B — Rules-based memory orchestrator

- Implement typed actions + audit trail.
- Add deterministic extraction heuristics.
- Exit criteria: predictable writes and passing RU/EN memory extraction tests.

### Phase C — LLM policy mode

- Add optional classifier model path with fallback to rules.
- Add sensitive-data suppression checks.
- Exit criteria: no regression in precision versus rules baseline on evaluation set.

### Phase D — Retrieval v2 and tuning

- Add layered retrieval + context budget packer + telemetry.
- Tune relevance/importance/recency weights.
- Exit criteria: improved retrieval usefulness metrics and stable latency.

### Phase E — Memory lifecycle management

- Add deduplication for semantic and episodic memory noise reduction.
- Introduce TTL and retention policies by memory scope/category.
- Add maintenance execution model (manual job first, scheduled worker later).
- Exit criteria: duplicate memory rate drops measurably and expired memory is excluded deterministically.

### Phase F — Internal memory management APIs

- Add internal/admin APIs to inspect, filter, and delete memory by user and scope.
- Preserve auditability for manual interventions.
- Keep contracts backend-first so future UI can build on stable endpoints.
- Exit criteria: operators can inspect and manage stored memory without direct DB access.

### Phase G — Retrieval evaluation and tuning harness

- Add repeatable evaluation scenarios for retrieval usefulness and regression detection.
- Establish baseline metrics before adding rerankers or more advanced ranking models.
- Exit criteria: retrieval changes can be gated on explicit evaluation evidence.

## Risks and mitigations

- **Risk:** model-driven policy over-saves noisy memories.
  - **Mitigation:** default `rules` mode, confidence threshold, offline evaluation gate.
- **Risk:** local embedding quality degrades retrieval.
  - **Mitigation:** provider-specific scoring calibration and minimum quality checks.
- **Risk:** privacy leakage via raw storage.
  - **Mitigation:** sensitive detector + explicit `privacy_tag` + retention/TTL policies.
- **Risk:** backend gets split into too many services too early.
  - **Mitigation:** keep modular monolith boundaries in code, separate workloads only at deployment/runtime level first.
