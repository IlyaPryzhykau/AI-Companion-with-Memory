# Decisions

## ADR-001: Introduce model-provider abstraction for chat + embeddings

- **Status:** accepted
- **Context:** Product must support both external key-based models and local models without changing API flows.
- **Decision:** Use a provider abstraction for chat and embedding generation with runtime selection via config.
- **Consequences:**
  - Easier provider switching and fallback.
  - Slightly more adapter code and integration testing needs.
  - Explicit provider error contract is required across modes.

## ADR-002: Add agentic memory orchestrator with safe default rules mode

- **Status:** accepted
- **Context:** Current memory handling is hard to control when relying on a single general model behavior.
- **Decision:** Create an explicit memory-orchestration layer producing typed memory actions. Default mode is deterministic rules; LLM policy is opt-in.
- **Consequences:**
  - Better observability and debugging of memory writes.
  - Lower risk of over-saving irrelevant content.
  - Requires schema for memory actions and audit fields.

## ADR-003: Separate memory into profile, episodic, and semantic scopes

- **Status:** accepted
- **Context:** Different memory lifecycles need different retention and retrieval behavior.
- **Decision:** Keep three memory scopes with shared metadata (`confidence`, `importance`, `ttl`, `privacy_tag`, `policy_mode`).
- **Consequences:**
  - Improved control over recall quality and storage growth.
  - Additional retrieval logic and migration complexity.

## ADR-004: Explicit bounded fallback provider policy

- **Status:** accepted
- **Context:** Strict fail-fast surfaced outages quickly, but several production scenarios require limited resilience without hiding incidents.
- **Decision:** Allow only explicit, bounded fallback paths for selected failure classes. Hidden or arbitrary cross-provider retries within a request remain disallowed.
- **Consequences:**
  - Provider failures remain visible via logs/metrics and deterministic error mapping.
  - Runtime behavior is more resilient for known failure modes while staying predictable.
  - Fallback paths must stay documented and test-covered to avoid policy drift.

## ADR-005: Kubernetes-ready deployment with modular monolith backend

- **Status:** accepted
- **Context:** The product is expected to grow to include backend, frontend, background jobs, and optional local model-serving. We want to learn and adopt Kubernetes, but splitting the backend into multiple services right now would add delivery and coordination overhead.
- **Decision:** Keep the codebase in a single repository and keep the backend as a modular monolith for now. Prepare deployment boundaries so API, future frontend, background jobs, Redis, and optional local model-serving can run as separate Kubernetes workloads/pods.
- **Consequences:**
  - Easier iteration on backend-first product work and shared contracts.
  - Kubernetes learning path remains available through runtime separation.
  - Internal module boundaries must stay explicit so future extraction remains possible if justified later.
