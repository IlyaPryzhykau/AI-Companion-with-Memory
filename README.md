# Project: AI Companion with Memory

## Overview

AI Companion is a multi-user AI assistant with long-term memory, available through:

- Web interface
- Telegram bot
- (future) voice interface

The assistant can:

- hold conversations
- remember user information
- retrieve relevant memory from past interactions
- create reminders
- help users practice English
- maintain long-term interaction context

The system is built as **AI backend + memory engine + integrations**.

The main goal is to build a **personal AI assistant that evolves with each user over time**.

## Core Features

### 1) Chat Interface

Users can talk to the assistant via:

- Web chat
- Telegram bot

Message pipeline:

```text
User message
↓
Save message
↓
Memory retrieval
↓
Prompt assembly
↓
LLM
↓
Response
```

### 2) Long-term Memory

The assistant includes long-term memory.

#### Structured memory

User facts:

```text
name
profession
location
goals
preferences
```

Stored in PostgreSQL.

#### Semantic memory

Conversation fragments stored as embeddings.

Example:

```text
User felt nervous before interview
```

Stored in a Vector DB.

Used for:

```text
semantic recall
context enrichment
```

#### Conversation summaries

Older conversations are summarized to reduce prompt context size.

### 3) Reminder System

The assistant can create reminders.

Example:

```text
Remind me tomorrow at 10 to call recruiter
```

Flow:

1. Extract intent
2. Create reminder
3. Deliver notification

Notification channels:

- Telegram
- Web notification
- Email (future)

### 4) Telegram Integration

Users can link their Telegram account.

This enables:

- direct messaging with the assistant
- reminder delivery
- continuous engagement

### 5) Multi-user Architecture

The system supports many users.

Each user has:

```text
own chats
own memory
own reminders
own assistant context
```

All user-scoped data is tied to:

```text
user_id
```

### 6) English Practice Mode (future feature)

The assistant can run as an **AI English companion**.

Capabilities:

- English conversation practice
- grammar correction
- learning through dialogue
- vocabulary card generation from chats

## System Architecture

### High-level Architecture

```text
                Web UI
                   |
                   |
Telegram Bot ------ API Gateway
                   |
                FastAPI
                   |
         ------------------------
         |          |           |
       Memory      Tools       LLM
         |          |           |
   Vector DB   Reminders     Model API
   PostgreSQL
```

## Backend Components

### API Server

FastAPI backend responsible for:

- authentication
- chat API
- memory retrieval
- LLM orchestration
- Telegram integration

### Memory Engine

Responsible for:

- memory extraction
- memory storage
- semantic search

Components:

```text
memory extractor
vector search
memory ranking
memory consolidation
```

### Tool System

Assistant tools:

```text
create_reminder
get_reminders
save_memory
search_memory
```

### Scheduler

Background processing for:

```text
reminder dispatch
memory consolidation
summary generation
```

## Database Design

### users

```text
id
email
password_hash
created_at
language_level
```

### chats

```text
id
user_id
assistant_id
created_at
```

### messages

```text
id
chat_id
role
content
created_at
```

### reminders

```text
id
user_id
text
remind_at
status
created_at
```

### user_memory

```text
id
user_id
key
value
importance
updated_at
```

### vector_memory

```text
id
user_id
text
embedding
importance
created_at
```

## Vector Database

Used for semantic search.

Per record:

```text
embedding
text
user_id
importance
```

Search logic:

```text
vector search
+ user_id filter
+ importance ranking
```

## LLM Pipeline

Every request runs through:

```text
1 receive message
2 save message
3 retrieve relevant memories
4 build prompt
5 call LLM
6 detect tool usage
7 execute tool if needed
8 return response
```

## Memory Processing Pipeline

After each message:

```text
message
↓
memory extraction
↓
fact detection
↓
semantic chunk creation
↓
embedding generation
↓
store in vector DB
```

## Memory Phase 2 (Current Implementation)

This project now includes baseline memory persistence in the chat flow:

- Structured memory upsert from detected user facts
- Vector memory record creation for user messages
- Memory context assembly before assistant reply generation

Structured fact extraction and lexical retrieval tokenization are currently
language-aware for:

- English (`en`)
- Russian (`ru`)
- Czech (`cs`)

Database migration introduced in phase 2:

```text
alembic/versions/20260310_0002_add_memory_tables.py
```

Operational rollout and rollback instructions:

```text
docs/runbooks/memory-phase2.md
```

## Technology Stack

### Backend

```text
Python
FastAPI
PostgreSQL
Redis
```

### Vector Search

```text
pgvector
or
Qdrant
```

### AI

```text
OpenAI
OpenRouter
Anthropic
```

### Integrations

```text
Telegram Bot API
```

### Frontend

```text
Next.js
React
```

## Development Roadmap

### Phase 1: Core Backend

Goal: build the base AI chat backend.

Features:

```text
user auth
chat endpoint
LLM integration
message storage
basic prompt system
```

### Phase 2: Memory System

Add memory support.

Features:

```text
vector DB
memory extraction
semantic search
prompt memory injection
```

### Phase 3: Telegram Bot

Add Telegram interface.

Features:

```text
telegram bot
user linking
message routing
notifications
```

### Phase 4: Reminder System

Add reminders.

Features:

```text
reminder creation
scheduler
reminder notifications
```

### Phase 5: Memory Optimization

Add:

```text
memory consolidation
importance scoring
memory cleanup
conversation summarization
```

### Phase 6: English Mode

Add English learning mode.

Features:

```text
grammar correction
conversation practice
vocabulary cards
```

### Phase 7: Voice Interface

Add:

```text
speech to text
text to speech
voice conversation
```

## Future Features

```text
calendar integration
email assistant
task management
mobile app
avatar interface
video conversation
```

## Project Goals

Build an AI system that:

```text
remembers user context
communicates naturally
integrates into daily life
works across platforms
improves over time
```

The project should be:

```text
scalable
multi-user
modular
extensible
```

## Success Criteria

The system is successful when:

```text
users return regularly
assistant remembers context
reminders work reliably
multi-platform communication works
```

## Next Step

Start implementation with:

```text
FastAPI project skeleton
auth system
chat endpoint
LLM integration
```

## Local Configuration

Use `.env.example` as the baseline local configuration.

Default PostgreSQL port for this project is:

```text
5440
```

Vector retrieval backend can be configured with:

```text
ASSISTANT_PROVIDER=local|openai
OPENAI_CHAT_MODEL=gpt-4o-mini
OPENAI_CHAT_TIMEOUT_SECONDS=15
VECTOR_BACKEND=json|pgvector
VECTOR_EMBEDDING_DIMENSIONS=64
EMBEDDING_PROVIDER=local|openai
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_TIMEOUT_SECONDS=10
```

Current implementation supports `VECTOR_EMBEDDING_DIMENSIONS=64` only.
If `EMBEDDING_PROVIDER=openai` is configured without a valid `OPENAI_API_KEY`,
the service falls back to local deterministic embeddings to keep retrieval available.
If `ASSISTANT_PROVIDER=openai` is configured without a valid `OPENAI_API_KEY`
or the model call fails, the service falls back to local echo-style behavior.

Memory retrieval policy is configurable via environment variables:

```text
MEMORY_RETRIEVAL_TOP_K=6
MEMORY_RETRIEVAL_CANDIDATE_MULTIPLIER=3
MEMORY_CONTEXT_MAX_CHARS=800
MEMORY_WEIGHT_RELEVANCE=0.65
MEMORY_WEIGHT_IMPORTANCE=0.25
MEMORY_WEIGHT_RECENCY=0.10
```

Retrieval ranking score is computed as:

```text
score = (relevance * MEMORY_WEIGHT_RELEVANCE)
      + (importance * MEMORY_WEIGHT_IMPORTANCE)
      + (recency * MEMORY_WEIGHT_RECENCY)
```

Weights are normalized at runtime, and memory context is trimmed to `MEMORY_CONTEXT_MAX_CHARS`.

## Backend Quick Start

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Docker Quick Start

```bash
copy .env.example .env
docker compose up --build
```

Security note:
- `.env` is local-only and must never be committed.
- Keep `OPENAI_API_KEY` empty in `.env` when possible; inject it at runtime for Docker.
- Keep `OPENAI_API_KEY` only in local/private environment storage.
- For production, use platform secrets management (for example: CI/CD secrets, Docker/Kubernetes secrets, Vault).
- Avoid passing API keys inline in command history. Prefer shell/session env export or secrets managers.

Migration note:
- If pgvector extension is unavailable, migration `20260311_0003` will fail by default.
- To explicitly allow degraded JSON fallback mode, set `ALLOW_PGVECTOR_JSON_FALLBACK=true` before migration.

Services:

```text
API: http://localhost:8000
PostgreSQL: localhost:5440
Redis: localhost:6379
```

Stop services:

```bash
docker compose down
```

Health check endpoint:

```text
GET /api/v1/health
```

Auth endpoints:

```text
POST /api/v1/auth/signup
POST /api/v1/auth/login
GET /api/v1/auth/me
```

Chat endpoint:

```text
POST /api/v1/chat
```

Run tests:

```bash
pytest
```

Run focused memory tests:

```bash
pytest tests/test_memory_pipeline.py
```

## Development Rules

Project-wide engineering rules are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
