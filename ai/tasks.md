# Tasks

## T-001 Provider abstraction and config

- Add interfaces for chat and embedding providers.
- Implement adapters for OpenAI + local HTTP-compatible provider.
- Add environment-based runtime routing (`PRIMARY_LLM_PROVIDER`, `EMBEDDING_PROVIDER`).
- Add integration tests for provider selection and failure behavior.

Status: DONE

Implemented in:

- `app/services/chat_providers.py`
- `app/services/embeddings.py`
- `app/services/llm.py`
- `app/core/config.py`
- `tests/test_chat_providers.py`
- `tests/test_embeddings.py`
- `tests/test_llm.py`
- `.env.example`
- `README.md`

**Definition of done**
- `/api/v1/chat` behaves consistently for `openai` and `local` modes.
- Error mapping is documented and tested.

## T-002 Memory orchestrator (rules mode)

- Implement `MemoryOrchestrator` that emits typed `MemoryActions`.
- Add deterministic heuristics for profile fact extraction and episodic event capture.
- Persist action audit trail for debugging.
- Cover with unit tests for Russian and English examples.

Status: DONE

Implemented in:

- `app/services/memory_orchestrator.py`
- `app/models/memory.py`
- `app/api/v1/endpoints/chat.py`
- `alembic/versions/20260313_0004_add_memory_action_audit.py`
- `tests/test_memory_orchestrator.py`
- `tests/test_memory_pipeline.py`

**Definition of done**
- Deterministic outputs for identical inputs.
- Tests include at least one negative case (`SKIP` on irrelevant message).

## T-003 LLM policy mode for memory actions

- Add optional model-driven policy for ambiguous persistence decisions.
- Support confidence scores and safe fallback to rules mode.
- Add guardrails to avoid storing sensitive secrets by default.

Status: DONE

Implemented in:

- `app/services/memory_policy.py`
- `app/services/memory_actions.py`
- `app/services/memory_orchestrator.py`
- `app/core/config.py`
- `tests/test_memory_policy.py`
- `.env.example`
- `README.md`

**Definition of done**
- Policy mode is feature-flagged and can be disabled at runtime.
- Sensitive data suppression tests pass.

## T-004 Retrieval v2

- Build layered retrieval (profile + episodic + semantic top-k).
- Add token-budget packer and weighted ranking controls.
- Validate response quality via scenario tests.

Status: DONE

Implemented in:

- `app/services/memory.py`
- `app/core/config.py`
- `tests/test_memory_retrieval.py`
- `.env.example`
- `README.md`

**Definition of done**
- Deterministic ordering for tie scores.
- User isolation tests cover `user_id` boundaries.

## T-005 Operations and observability

- Add metrics: memory write rate, retrieval hit rate, context budget usage.
- Add dashboards/log fields for per-provider latency and failures.
- Document cloud/private/mixed deployment recipes.

Status: DONE

Implemented in:

- `app/services/observability.py`
- `app/services/chat_providers.py`
- `app/services/embeddings.py`
- `app/services/memory.py`
- `app/services/memory_orchestrator.py`
- `app/api/v1/metrics.py`
- `app/api/v1/router.py`
- `tests/test_metrics.py`
- `docs/deployment-recipes.md`
- `docs/runbooks/provider-outage-triage.md`
- `README.md`

**Definition of done**
- Dashboards include provider error rate and p95 latency.
- Runbook section exists for provider outage triage.

## T-006 Memory deduplication and compaction

- Add a lightweight deduplication service for semantic and episodic memory.
- Define deterministic duplicate detection rules and merge/skip behavior.
- Add a manual execution path first; keep scheduling optional for a later worker.
- Add tests for duplicate, near-duplicate, and cross-user isolation cases.

**Definition of done**
- Duplicate memories are not re-saved or are compacted deterministically according to documented rules.
- Tests cover user isolation and at least one false-positive guard case.
- Operational notes describe how to run dedup safely.

## T-007 TTL and retention policies

- Add configurable TTL/retention policies by memory scope/category.
- Ensure expired memories are excluded from retrieval and optionally cleaned up.
- Support explicit retention metadata on stored memory records.
- Add tests for expiry boundaries and retrieval behavior before/after expiration.

**Definition of done**
- Expired memories are deterministically excluded from retrieval.
- Tests cover boundary timestamps and different memory scopes.
- Retention behavior is documented in config/docs.

## T-008 Internal memory inspection and management API

- Add backend endpoints for listing, filtering, and deleting memory records by user and scope.
- Include audit-friendly metadata in responses so operators can understand why memory exists.
- Keep auth and authorization explicit; do not expose cross-user access accidentally.
- Add integration tests for auth, filtering, and deletion behavior.

**Definition of done**
- Operators can inspect memory without direct DB access.
- Delete/update actions are authenticated, authorized, and tested.
- Response contracts are documented for future frontend use.

## T-009 Retrieval evaluation harness

- Add repeatable evaluation fixtures/scenarios for retrieval usefulness.
- Record baseline metrics for ranking quality before further retrieval changes.
- Make evaluation deterministic enough for regression gating in PRs or release checks.
- Add documentation describing how to run and interpret the evaluation suite.

**Definition of done**
- Retrieval changes can be compared against a stable baseline.
- Evaluation output highlights regressions clearly enough for release decisions.
- At least one multilingual scenario is included in the harness.
