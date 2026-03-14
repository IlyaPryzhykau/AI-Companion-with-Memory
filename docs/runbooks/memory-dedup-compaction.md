# Memory Deduplication and Compaction Runbook

## Scope

This runbook covers manual execution of memory deduplication for `vector_memory` rows:

- exact duplicate removal (same normalized text, same user);
- near-duplicate compaction (high lexical overlap, same user);
- deterministic winner selection (`importance` -> `created_at` -> `id`).

Cross-user deduplication is explicitly disallowed.

## Safety Rules

- Start with dry-run mode and inspect the summary output.
- Run for a single user first if this is the first execution in an environment.
- Keep a DB backup/snapshot before `--apply` runs in production.
- Run during low-traffic windows if large datasets are expected.

## Commands

Dry-run for all users:

```bash
python scripts/run_memory_compaction.py
```

Dry-run for one user:

```bash
python scripts/run_memory_compaction.py --user-id 42
```

Apply compaction for one user:

```bash
python scripts/run_memory_compaction.py --user-id 42 --apply
```

Apply compaction for all users:

```bash
python scripts/run_memory_compaction.py --apply
```

## Output Interpretation

The command prints:

- `users`: number of scanned users
- `rows`: scanned `vector_memory` rows
- `deleted`: total rows planned/removed
- `exact_deleted`: removed as exact duplicates
- `near_deleted`: removed as near-duplicates

## Rollback Guidance

- If compaction result is unexpected, stop further runs.
- Restore database from snapshot/backup according to environment policy.
- Re-run in dry-run with a stricter threshold before applying again.

