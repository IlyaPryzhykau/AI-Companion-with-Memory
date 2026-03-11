"""Memory service error-handling tests."""

from app.services import memory as memory_service


class _FailingVectorStore:
    """Test double that raises on semantic store writes."""

    def store(self, **kwargs) -> None:
        raise ValueError("simulated store failure")


def test_store_vector_memory_does_not_raise_on_backend_error(db_session) -> None:
    """Vector storage errors should be logged and not crash chat pipeline calls."""

    original_factory = memory_service.get_vector_store
    try:
        memory_service.get_vector_store = lambda: _FailingVectorStore()  # type: ignore[assignment]
        memory_service.store_vector_memory(
            db=db_session,
            user_id=1,
            text="hello",
            importance=0.5,
        )
    finally:
        memory_service.get_vector_store = original_factory  # type: ignore[assignment]
