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
- Treat test coverage as a delivery requirement, not an optional follow-up.

### Required Coverage by Change Type

| Change Type | Required Tests | Notes |
| --- | --- | --- |
| Pure refactor (no behavior change) | Existing affected tests must pass | Explain why no new tests are needed in PR |
| Business logic change | Unit tests for new branches + edge cases | Include at least one negative/failure case |
| API endpoint change | Integration tests for request/response + auth/error paths | Cover contract compatibility expectations |
| DB schema/migration change | Migration test/check + integration test on changed flow | Document rollback validation approach |
| Retrieval/ranking/scoring logic | Deterministic tests for ranking order and tie behavior | Avoid flaky assertions and random inputs |
| Bug fix | Regression test reproducing old failure | Regression test should fail before fix |
| Config/feature-flag behavior | Tests for both enabled and disabled modes | If one mode is unavailable, state why |

### Test Quality Bar

- Tests for changed areas must pass locally before opening PR.
- New logic must include at least one edge-case assertion.
- If behavior depends on ordering/ranking, assert explicit order.
- If behavior is user-scoped, include isolation tests by `user_id`.
- If no test is added for a behavior change, PR must include a concrete justification.

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
