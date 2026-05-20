"""Fixture: an intentionally failing test for the pytest provider smoke test."""


def test_fails() -> None:
    assert 1 + 1 == 3
