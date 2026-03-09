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

## Backend Quick Start

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
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

## Development Rules

Project-wide engineering rules are documented in [CONTRIBUTING.md](CONTRIBUTING.md).
