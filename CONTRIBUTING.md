# Contributing Guide

This document defines coding standards for this repository and for AI coding agents.

## Language Policy

- Write all code comments in English.
- Write all docstrings in English.
- Write commit messages in English.
- Keep user-facing product copy consistent with feature requirements.

## Code Style

- Follow PEP 8 for Python code.
- Use type hints for all public functions and methods.
- Prefer clear, explicit names over short abbreviations.
- Keep functions focused and small; split complex logic into helpers.
- Avoid dead code and commented-out blocks.

## Docstrings

- Add docstrings to all modules, classes, and public functions.
- Use concise, practical descriptions.
- Document parameters, return values, and raised exceptions when non-trivial.
- Keep docstrings aligned with actual behavior; update them during refactors.

## Comments

- Comment the "why", not the obvious "what".
- Add comments for non-trivial business rules, edge cases, and tradeoffs.
- Remove stale comments in the same change where behavior changes.

## Error Handling and Logging

- Fail with explicit, actionable errors.
- Do not silently swallow exceptions.
- Log meaningful context without leaking secrets or personal data.

## Testing

- Add or update tests for all behavior changes.
- Cover success paths and important failure paths.
- Keep tests deterministic and isolated.

## API and Data Contracts

- Validate all external input.
- Keep request/response schemas explicit and versionable.
- For DB changes, include migrations and rollback-safe planning.

## Security and Privacy

- Never commit secrets, tokens, or private keys.
- Minimize stored personal data and follow least-privilege principles.
- Redact sensitive values in logs and error outputs.

## Pull Request Checklist

- Code follows this guide.
- Comments/docstrings are in English.
- Tests pass locally for changed areas.
- Documentation is updated when behavior or contracts change.
- No unrelated refactors in the same PR.

## AI Agent Rules

- Respect existing architecture and naming conventions.
- Make minimal, targeted changes.
- Explain assumptions in PR descriptions.
- If requirements are unclear, document open questions before large edits.
