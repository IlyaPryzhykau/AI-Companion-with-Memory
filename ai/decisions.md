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

## ADR-004: Fail-fast provider policy in phase 1

- **Status:** accepted
- **Context:** Silent cross-provider fallback can hide outages and produce inconsistent behavior.
- **Decision:** In phase 1, do not auto-fallback between providers within a single request.
- **Consequences:**
  - Operational issues are visible immediately.
  - Requires clear error mapping and dashboarding for provider incidents.
