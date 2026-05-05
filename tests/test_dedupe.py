import pytest

from listener.dedupe import LRUDeduper


def test_add_returns_true_for_new_key() -> None:
    d = LRUDeduper(capacity=10)
    assert d.add("a") is True
    assert d.add("b") is True


def test_add_returns_false_for_duplicate() -> None:
    d = LRUDeduper(capacity=10)
    assert d.add("a") is True
    assert d.add("a") is False


def test_capacity_evicts_oldest() -> None:
    d = LRUDeduper(capacity=3)
    for k in ("a", "b", "c"):
        assert d.add(k) is True
    assert d.add("d") is True
    assert "a" not in d
    assert "b" in d
    assert "c" in d
    assert "d" in d


def test_recent_access_prevents_eviction() -> None:
    d = LRUDeduper(capacity=3)
    d.add("a")
    d.add("b")
    d.add("c")
    assert d.add("a") is False
    d.add("e")
    assert "a" in d
    assert "b" not in d


def test_invalid_capacity() -> None:
    with pytest.raises(ValueError):
        LRUDeduper(capacity=0)


def test_clear() -> None:
    d = LRUDeduper(capacity=10)
    d.add("a")
    d.add("b")
    assert len(d) == 2
    d.clear()
    assert len(d) == 0
    assert "a" not in d
