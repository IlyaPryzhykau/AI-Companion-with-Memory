# Provider Outage Triage

## Purpose

Operational guide for diagnosing and mitigating chat/embedding provider outages.

## Signals to Monitor

- Provider error rate (`provider.*.error_rate`) above normal baseline.
- Provider p95 latency (`provider.*.p95_latency_ms`) sudden increase.
- Fallback activity increase:
  - chat fallback to `local`
  - embedding fallback to deterministic local hash

## Immediate Actions

1. Identify affected provider path:
   - chat: `chat:openai` / `chat:local_http`
   - embedding: `embedding:openai` / `embedding:local_http`
2. Validate credentials and base URL configuration:
   - `OPENAI_API_KEY`
   - `LOCAL_LLM_BASE_URL`
   - `LOCAL_LLM_API_KEY`
3. Switch to safe mode when needed:
   - `PRIMARY_LLM_PROVIDER=local`
   - `EMBEDDING_PROVIDER=local`
4. Restart API service and verify `/api/v1/health` and `/api/v1/metrics`.

## Verification Checklist

- Error rate falls below alert threshold.
- p95 latency returns to expected range.
- `/api/v1/chat` returns successful responses.
- Retrieval hit rate remains stable.

## Postmortem Notes

- Record outage window and blast radius.
- Capture root cause (provider, auth, network, config, quota).
- Add preventive action item (alerting threshold, retry strategy, capacity tuning).
