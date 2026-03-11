"""Shared vector payload validation helpers."""

import math


def validate_embedding_vector(values: list[float | int], expected_dimensions: int) -> list[float]:
    """Validate and normalize embedding values for DB and similarity operations."""

    if len(values) != expected_dimensions:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dimensions}, got {len(values)}."
        )

    try:
        normalized = [float(value) for value in values]
    except (TypeError, ValueError) as exc:
        raise ValueError("Embedding contains non-convertible numeric values.") from exc

    if not all(math.isfinite(value) for value in normalized):
        raise ValueError("Embedding vector contains non-finite values.")

    return normalized
