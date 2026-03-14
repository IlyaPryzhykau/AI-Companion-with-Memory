"""In-process observability counters and latency statistics."""

from collections import defaultdict, deque
from threading import Lock

_LOCK = Lock()
_COUNTERS: dict[str, float] = defaultdict(float)
_LATENCY_MS: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=2000))


def _latency_key(provider_kind: str, provider_name: str) -> str:
    return f"{provider_kind}:{provider_name}"


def record_provider_call(provider_kind: str, provider_name: str, latency_ms: float, success: bool) -> None:
    """Record provider call latency and success/failure counters."""

    status = "success" if success else "failure"
    latency = max(0.0, float(latency_ms))
    key = _latency_key(provider_kind, provider_name)
    with _LOCK:
        _COUNTERS[f"provider_calls_total:{provider_kind}:{provider_name}:{status}"] += 1.0
        _LATENCY_MS[key].append(latency)


def record_memory_action(action_type: str) -> None:
    """Record memory action count."""

    with _LOCK:
        _COUNTERS[f"memory_actions_total:{action_type}"] += 1.0


def record_retrieval(
    selected_count: int,
    char_budget: int,
    chars_used: int,
    token_budget: int,
    tokens_used: int,
) -> None:
    """Record retrieval hit/miss and context budget usage."""

    with _LOCK:
        _COUNTERS["retrieval_requests_total"] += 1.0
        if selected_count > 0:
            _COUNTERS["retrieval_hits_total"] += 1.0
        else:
            _COUNTERS["retrieval_misses_total"] += 1.0
        _COUNTERS["context_chars_used_total"] += max(0.0, float(chars_used))
        _COUNTERS["context_chars_budget_total"] += max(1.0, float(char_budget))
        _COUNTERS["context_tokens_used_total"] += max(0.0, float(tokens_used))
        _COUNTERS["context_tokens_budget_total"] += max(1.0, float(token_budget))


def get_metrics_snapshot() -> dict[str, object]:
    """Return aggregated metrics snapshot for operational visibility."""

    with _LOCK:
        counters = dict(_COUNTERS)
        latencies = {key: list(values) for key, values in _LATENCY_MS.items()}

    retrieval_requests = int(counters.get("retrieval_requests_total", 0.0))
    retrieval_hits = int(counters.get("retrieval_hits_total", 0.0))

    provider_stats: dict[str, dict[str, float]] = {}
    for key, samples in latencies.items():
        provider_kind, provider_name = key.split(":", maxsplit=1)
        success = counters.get(f"provider_calls_total:{provider_kind}:{provider_name}:success", 0.0)
        failure = counters.get(f"provider_calls_total:{provider_kind}:{provider_name}:failure", 0.0)
        total = success + failure
        sorted_samples = sorted(samples)
        if sorted_samples:
            index = max(0, int(round(0.95 * (len(sorted_samples) - 1))))
            p95_ms = sorted_samples[index]
        else:
            p95_ms = 0.0
        provider_stats[key] = {
            "calls_total": float(total),
            "errors_total": float(failure),
            "error_rate": (float(failure) / float(total)) if total else 0.0,
            "p95_latency_ms": float(p95_ms),
        }

    context_chars_budget = counters.get("context_chars_budget_total", 0.0)
    context_tokens_budget = counters.get("context_tokens_budget_total", 0.0)

    return {
        "memory_write_rate_total": {
            "upsert_facts": int(counters.get("memory_actions_total:UPSERT_FACTS", 0.0)),
            "store_episodic": int(counters.get("memory_actions_total:STORE_EPISODIC", 0.0)),
            "skip": int(counters.get("memory_actions_total:SKIP", 0.0)),
        },
        "retrieval": {
            "requests_total": retrieval_requests,
            "hits_total": retrieval_hits,
            "hit_rate": (float(retrieval_hits) / float(retrieval_requests)) if retrieval_requests else 0.0,
        },
        "context_budget_usage": {
            "chars_utilization": (
                float(counters.get("context_chars_used_total", 0.0)) / float(context_chars_budget)
                if context_chars_budget
                else 0.0
            ),
            "tokens_utilization": (
                float(counters.get("context_tokens_used_total", 0.0)) / float(context_tokens_budget)
                if context_tokens_budget
                else 0.0
            ),
        },
        "provider": provider_stats,
    }


def reset_metrics() -> None:
    """Reset metrics state (used by tests)."""

    with _LOCK:
        _COUNTERS.clear()
        _LATENCY_MS.clear()
