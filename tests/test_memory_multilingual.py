"""Multilingual memory extraction and retrieval tokenization tests."""

from app.services.memory import _relevance_score, _tokenize, extract_structured_facts


def test_extract_structured_name_in_russian() -> None:
    """Extractor should capture Russian name facts."""

    facts = extract_structured_facts("Привет, меня зовут Илья.")
    assert ("name", "Илья", 0.9) in facts


def test_extract_structured_name_in_czech() -> None:
    """Extractor should capture Czech name facts."""

    facts = extract_structured_facts("Ahoj, jmenuji se Václav.")
    assert ("name", "Václav", 0.9) in facts


def test_russian_short_form_name_pattern_does_not_capture_profession_phrase() -> None:
    """Short-form Russian name extraction should not treat verbs as names."""

    facts = extract_structured_facts("Я работаю тестировщиком.")
    assert not any(key == "name" and value.lower() == "работаю" for key, value, _ in facts)


def test_unicode_tokenize_handles_cyrillic_and_czech() -> None:
    """Tokenizer should preserve non-Latin words for retrieval relevance."""

    ru_tokens = _tokenize("Как меня зовут?")
    cs_tokens = _tokenize("Jak se jmenuji?")

    assert "зовут" in ru_tokens
    assert "jmenuji" in cs_tokens


def test_relevance_score_supports_russian_and_czech_queries() -> None:
    """Lexical relevance should work for Cyrillic and Czech words."""

    ru_score = _relevance_score("моя цель проект", "цель: сделать проект")
    cs_score = _relevance_score("můj cíl projekt", "cíl: dokončit projekt")

    assert ru_score > 0.0
    assert cs_score > 0.0
