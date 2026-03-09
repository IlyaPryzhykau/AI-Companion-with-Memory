# Project: AI Companion with Memory

## Overview

AI Companion — это многопользовательский AI-ассистент с долговременной памятью, доступный через:

- Web интерфейс
- Telegram бот
- (в будущем) голосовой интерфейс

Ассистент умеет:

- вести диалог
- запоминать информацию о пользователе
- извлекать релевантную память из прошлых разговоров
- создавать напоминания
- помогать пользователю учить английский
- сохранять долгосрочный контекст взаимодействия

Система построена как **AI backend + memory engine + integrations**.

Основная цель проекта — создать **персонального AI-ассистента, который развивается вместе с пользователем**.

## Core Features

### 1) Chat Interface

Пользователь может общаться с ассистентом через:

- Web chat
- Telegram bot

Каждое сообщение проходит через pipeline:

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

Ассистент обладает долговременной памятью.

#### Structured memory

Факты о пользователе:

```text
name
profession
location
goals
preferences
```

Хранится в PostgreSQL.

#### Semantic memory

Фрагменты диалогов, сохраненные как embeddings.

Пример:

```text
User felt nervous before interview
```

Хранится в Vector DB.

Используется для:

```text
semantic recall
context enrichment
```

#### Conversation summaries

Старые диалоги суммаризируются для уменьшения контекста.

### 3) Reminder System

Ассистент может создавать напоминания.

Пример:

```text
Remind me tomorrow at 10 to call recruiter
```

Система:

1. извлекает намерение
2. создает reminder
3. отправляет уведомление пользователю

Напоминания могут приходить через:

- Telegram
- Web notification
- Email (future)

### 4) Telegram Integration

Пользователь может связать Telegram аккаунт.

Это позволяет:

- писать ассистенту напрямую
- получать напоминания
- поддерживать постоянный контакт

### 5) Multi-user Architecture

Система поддерживает множество пользователей.

Каждый пользователь имеет:

```text
own chats
own memory
own reminders
own assistant context
```

Все данные привязаны к:

```text
user_id
```

### 6) English Practice Mode (future feature)

Ассистент может работать как **AI English companion**.

Функции:

- диалог на английском
- исправление ошибок
- обучение через разговор
- генерация карточек из диалогов

## System Architecture

### High Level Architecture

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

FastAPI backend.

Отвечает за:

- authentication
- chat API
- memory retrieval
- LLM orchestration
- Telegram integration

### Memory Engine

Отвечает за:

- извлечение памяти
- сохранение памяти
- semantic search

Компоненты:

```text
memory extractor
vector search
memory ranking
memory consolidation
```

### Tool System

Ассистент может вызывать инструменты:

```text
create_reminder
get_reminders
save_memory
search_memory
```

### Scheduler

Фоновый процесс для:

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

Используется для semantic search.

Каждая запись:

```text
embedding
text
user_id
importance
```

Поиск выполняется:

```text
vector search
+ user_id filter
+ importance ranking
```

## LLM Pipeline

Каждый запрос проходит через:

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

После каждого сообщения:

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

### Phase 1 — Core Backend

Цель: создать базовый AI чат.

Features:

```text
user auth
chat endpoint
LLM integration
message storage
basic prompt system
```

### Phase 2 — Memory System

Добавить память.

Features:

```text
vector DB
memory extraction
semantic search
prompt memory injection
```

### Phase 3 — Telegram Bot

Добавить Telegram интерфейс.

Features:

```text
telegram bot
user linking
message routing
notifications
```

### Phase 4 — Reminder System

Добавить напоминания.

Features:

```text
reminder creation
scheduler
reminder notifications
```

### Phase 5 — Memory Optimization

Добавить:

```text
memory consolidation
importance scoring
memory cleanup
conversation summarization
```

### Phase 6 — English Mode

Добавить режим обучения английскому.

Features:

```text
grammar correction
conversation practice
vocabulary cards
```

### Phase 7 — Voice Interface

Добавить:

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

Создать AI систему, которая:

```text
remembers user context
communicates naturally
integrates into daily life
works across platforms
improves over time
```

Проект должен быть:

```text
scalable
multi-user
modular
extensible
```

## Success Criteria

Система считается успешной если:

```text
users return regularly
assistant remembers context
reminders work reliably
multi-platform communication works
```

## Next Step

Начать реализацию с:

```text
FastAPI project skeleton
auth system
chat endpoint
LLM integration
```
