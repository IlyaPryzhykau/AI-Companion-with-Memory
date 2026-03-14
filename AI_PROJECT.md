# AI Project Context

This file provides project context for AI agents and must stay current.

## Purpose

- Give AI agents a reliable high-level map of the project.
- Reduce incorrect assumptions during coding and review.
- Keep architecture and workflow constraints explicit.

## Update Policy

- Update this file whenever architecture, core runtime flows, or key stack decisions change.
- If a PR changes those areas, the PR must include corresponding updates in this file.

## Current Stack

- Backend: Python + FastAPI
- ORM/DB access: SQLAlchemy (current application flow is sync sessions)
- Database: PostgreSQL
- Cache/queue support: Redis
- Migrations: Alembic
- Vector support: pgvector when available, JSON fallback mode by explicit migration opt-in
- LLM/Embeddings providers: OpenAI + local HTTP-compatible providers
- Containerization: Docker Compose
- Deployment direction: Kubernetes-ready multi-service deployment with separate pods per runtime component

## Core Runtime Flow (Chat)

1. Authenticate user.
2. Accept user message via `/api/v1/chat`.
3. Persist user message.
4. Extract structured memory facts.
5. Store semantic/vector memory.
6. Retrieve ranked memory context (top-k, weighted relevance/importance/recency, budgeted context).
7. Build assistant response using configured provider and recent chat history.
8. Persist assistant message and return response.

## Memory System (Current)

- Provider abstraction supports runtime switching for chat and embeddings (`openai|local|local_http`) with explicit error mapping.
- Memory orchestration supports `rules` and optional `llm_policy` modes with auditable memory actions.
- Memory scopes are split into:
  - Profile memory for durable user facts
  - Episodic memory for conversation events
  - Semantic memory for retrieval chunks and embeddings
- Retrieval uses layered memory composition with weighted ranking and token-budget packing.
- Observability exposes memory/retrieval/provider metrics and provider outage runbooks.
- Retrieval includes multilingual extraction/tokenization support for:
  - English (`en`)
  - Russian (`ru`)
  - Czech (`cs`)

## Current Architecture Status

- Phase 1 is complete:
  - provider abstraction and runtime routing are implemented;
  - memory orchestration and policy modes are implemented;
  - retrieval v2 and observability are implemented.

## Behavior Alignment Note

- Current code path is **not strict fail-fast** for all provider scenarios.
- Chat and embedding layers include explicit safe fallback behavior in several failure paths.
- ADR/doc alignment for `fail-fast vs fallback` is pending explicit decision:
  - option A: change code to strict fail-fast;
  - option B: update architecture/ADR docs to match fallback-first operational behavior.

## Next Backend Milestone

- Focus on memory lifecycle quality rather than UI-first expansion.
- Reduce long-term memory noise with deduplication and retention policies.
- Add internal/admin-grade memory inspection and management APIs before user-facing frontend controls.
- Build retrieval evaluation workflows to measure quality regressions before adding rerankers or more advanced policies.

## Deployment Direction

- Keep the product in a single repository.
- Continue backend development as a modular monolith for now.
- Prepare runtime boundaries so the system can be deployed as separate Kubernetes workloads later:
  - backend API pod
  - frontend pod when UI work starts
  - PostgreSQL
  - Redis
  - optional worker/cron pod for memory maintenance jobs
  - optional local model-serving pod
- Avoid early microservice fragmentation inside the backend until operational needs justify it.

## Agent Workflow

- Role definitions are in `AGENTS.md`.
- Coding, testing, and PR rules are in `CONTRIBUTING.md`.
- Task planning artifacts live in:
  - `ai/architecture.md`
  - `ai/decisions.md`
  - `ai/backlog.md`
  - `ai/tasks.md`

## Delivery Policy

- PR-only workflow: no direct pushes to `main`.
- Every behavior change requires tests.
- Documentation must be updated in the same change set when behavior/architecture changes.
