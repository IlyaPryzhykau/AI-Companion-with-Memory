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

**Definition of done**
- Policy mode is feature-flagged and can be disabled at runtime.
- Sensitive data suppression tests pass.

## T-004 Retrieval v2

- Build layered retrieval (profile + episodic + semantic top-k).
- Add token-budget packer and weighted ranking controls.
- Validate response quality via scenario tests.

**Definition of done**
- Deterministic ordering for tie scores.
- User isolation tests cover `user_id` boundaries.

## T-005 Operations and observability

- Add metrics: memory write rate, retrieval hit rate, context budget usage.
- Add dashboards/log fields for per-provider latency and failures.
- Document cloud/private/mixed deployment recipes.

**Definition of done**
- Dashboards include provider error rate and p95 latency.
- Runbook section exists for provider outage triage.
