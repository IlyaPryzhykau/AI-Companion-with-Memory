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
- LLM/Embeddings providers: OpenAI + local fallback providers
- Containerization: Docker Compose

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

- Structured memory table: key/value user facts (for example `name`, `goal`, `location`).
- Semantic memory table: text + embedding payload.
- Retrieval includes multilingual extraction/tokenization support for:
  - English (`en`)
  - Russian (`ru`)
  - Czech (`cs`)

## Planned Architecture Evolution

- Introduce provider abstraction for chat + embeddings with config-based runtime switching (`openai|local`) and explicit provider error mapping.
- Add agentic memory orchestrator that emits typed memory actions with a default rules mode and auditable decisions.
- Evolve memory model into profile + episodic + semantic scopes with shared metadata (`confidence`, `importance`, `ttl`, `privacy_tag`).
- Keep deployment parity across cloud, private-local, and mixed provider modes, while using fail-fast provider behavior in phase 1.

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
