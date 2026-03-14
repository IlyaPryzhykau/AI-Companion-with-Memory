# Deployment Recipes

## Cloud Mode (Managed LLM API)

Use external hosted providers (for example OpenAI).

Recommended settings:

```text
PRIMARY_LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=...
```

Characteristics:

- Fastest to launch
- Simplest operations
- External dependency risk

## Private Mode (Self-hosted local_http)

Use internal OpenAI-compatible endpoint for chat and embeddings.

Recommended settings:

```text
PRIMARY_LLM_PROVIDER=local_http
EMBEDDING_PROVIDER=local_http
LOCAL_LLM_BASE_URL=https://<internal-endpoint>/v1
LOCAL_LLM_API_KEY=...
```

Characteristics:

- Better data control
- Higher infra ownership
- Requires latency/capacity tuning

## Mixed Mode

Split providers by use case.

Example:

```text
PRIMARY_LLM_PROVIDER=openai
EMBEDDING_PROVIDER=local_http
```

Characteristics:

- Balanced cost/latency/control
- More complex observability and incident triage

## Observability Baseline

Monitor on all modes:

- provider error rate
- provider p95 latency
- retrieval hit rate
- context budget utilization

Use endpoint:

```text
GET /api/v1/metrics
```
