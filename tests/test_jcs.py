from agent_pay.jcs import canonical_json, jcs_hash


def test_canonical_json_sorts_keys() -> None:
    a = canonical_json({"b": 1, "a": 2})
    b = canonical_json({"a": 2, "b": 1})
    assert a.decode() == '{"a":2,"b":1}'
    assert a == b


def test_jcs_hash_returns_32_byte_sha256() -> None:
    h = jcs_hash({"x": 1})
    assert len(h) == 32
