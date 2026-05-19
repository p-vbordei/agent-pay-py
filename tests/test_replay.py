from agent_pay.replay import ReplayCache


def test_replay_cache_marks_and_detects() -> None:
    cache = ReplayCache(max_entries=100)
    assert cache.is_used("hash1") is False
    cache.mark_used("hash1", 10**18)
    assert cache.is_used("hash1") is True


def test_replay_cache_evicts_expired_on_access() -> None:
    now_value = {"v": 1000}
    cache = ReplayCache(max_entries=100, now=lambda: now_value["v"])
    cache.mark_used("h", 2000)
    assert cache.is_used("h") is True
    now_value["v"] = 3000
    assert cache.is_used("h") is False


def test_replay_cache_evicts_oldest_when_over_max() -> None:
    cache = ReplayCache(max_entries=2)
    cache.mark_used("a", 10**18)
    cache.mark_used("b", 10**18)
    cache.mark_used("c", 10**18)
    assert cache.is_used("a") is False
    assert cache.is_used("b") is True
    assert cache.is_used("c") is True
