# Memory Phase 2 Runbook

## Scope

This runbook covers deployment and rollback for memory phase 2 changes:

- DB migration for memory tables
- Structured memory upsert in chat flow
- Vector memory write in chat flow
- Memory context injection into assistant reply generation

## Related Change

| Item | Value |
| --- | --- |
| Migration | `alembic/versions/20260310_0002_add_memory_tables.py` |
| Affected endpoint | `POST /api/v1/chat` |
| Main validation test | `tests/test_memory_pipeline.py` |

## Pre-deploy Checklist

- Confirm current app version is healthy (`GET /api/v1/health`).
- Confirm database backups/snapshots policy is active.
- Verify migration runner has DB permissions.
- Ensure rollback path for application artifact is available.

## Rollout Steps

1. Deploy application artifact containing phase 2 code.
2. Run migrations:

```bash
alembic upgrade head
```

3. Validate schema revision is current:

```bash
alembic current
```

4. Run smoke tests:

```bash
pytest tests/test_memory_pipeline.py
pytest tests/test_chat.py
```

5. Execute API smoke:
- Create/login user
- Send `POST /api/v1/chat` message
- Verify response is `200` and messages are saved

## Rollback Steps

1. Roll back application artifact to the previous stable version.
2. If required by incident policy, downgrade one migration step:

```bash
alembic downgrade -1
```

3. Re-run health and chat smoke checks.
4. Monitor error rates and logs until stabilized.

## Observability

Track during and after rollout:

- Chat endpoint error rate
- Authentication failures on chat endpoint
- DB errors on memory writes
- Request latency changes on `POST /api/v1/chat`

## Notes

- Backfill is not required for this phase.
- This phase adds persistence paths; retrieval quality tuning is a next phase concern.
