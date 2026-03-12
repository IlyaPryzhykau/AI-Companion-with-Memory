# AI Agent Workflow

This repository uses role-based AI agent workflows.

## Analyst Agent

Responsibilities:

- Discuss system architecture
- Document design decisions
- Maintain project documentation
- Generate development tasks

Main files used:

- `ai/architecture.md`
- `ai/decisions.md`
- `ai/backlog.md`
- `ai/tasks.md`

## Developer Agent

Responsibilities:

- Implement tasks from `ai/tasks.md`
- Write production code
- Write tests
- Prepare pull requests

Developer agent must follow rules defined in:

- `CONTRIBUTING.md`

## Reviewer Agent

Responsibilities:

- Review pull requests
- Detect bugs
- Suggest improvements
- Verify tests and architecture compliance
