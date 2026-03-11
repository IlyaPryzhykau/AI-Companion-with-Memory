# Agent Workflow Rules

These rules are mandatory for coding agents working in this repository.

## Push Confirmation

- Before any `git push`, the agent must ask for user confirmation.
- The agent must not push automatically after edits, tests, or commits.

## PR Communication

- After each meaningful fix batch, the agent must post a PR comment summarizing:
- what was fixed,
- which files were changed,
- what tests were run and their result.

## Review Handling

- When addressing AI/peer review findings, the agent must prioritize only the latest review comment unless the user asks otherwise.
- The agent should avoid repeating already resolved findings and must reference current code state.

## Documentation Discipline

- Documentation is mandatory and must be maintained continuously (`README.md`, relevant docs in repo, and runbooks/changelogs where applicable).
- The agent must keep docs up to date for behavior, API, configuration, migrations, backfills, and rollout/rollback operational steps.
- If implementation changes user-facing or operational behavior, docs updates are required in the same change set.
- If docs are intentionally unchanged, the agent must explicitly justify that in the PR comment.

## Testing Discipline

- Every behavior change must be covered by automated tests in the same branch before merge.
- The agent must add or update tests for happy-path and relevant edge/failure-path scenarios.
- For bug fixes, tests must protect against regression (repro-before/fix-after when feasible).
- Before proposing push/merge, the agent must run the relevant test suite and report concrete results in the PR comment.
