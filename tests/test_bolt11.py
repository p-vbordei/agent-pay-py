import os
import time

import bolt11 as _bolt11
import pytest
from bolt11 import Bolt11, MilliSatoshi
from bolt11.models.tags import Tag, TagChar, Tags

from agent_pay.bolt11 import parse_invoice

_SIGNING_KEY_HEX = "e126f68f7eafcc8b74f54d269fe206be715000f94dac067d1c04a8ca3b2db734"


def _make_invoice(amount_msat: int, payment_hash: str) -> str:
    inv = Bolt11(
        currency="bcrt",
        date=int(time.time()),
        amount_msat=MilliSatoshi(amount_msat),
        tags=Tags(
            [
                Tag(TagChar.payment_hash, payment_hash),
                Tag(TagChar.description, "test"),
                Tag(TagChar.expire_time, 300),
                Tag(TagChar.payment_secret, os.urandom(32).hex()),
            ]
        ),
    )
    return _bolt11.encode(inv, _SIGNING_KEY_HEX)


def test_parse_invoice_extracts_amount_and_payment_hash() -> None:
    ph = "b" * 64
    inv = _make_invoice(10_000, ph)
    parsed = parse_invoice(inv)
    assert parsed.amount_msat == 10_000
    assert parsed.payment_hash == ph


def test_parse_invoice_throws_on_non_bolt11_input() -> None:
    with pytest.raises(Exception):  # noqa: B017
        parse_invoice("not a bolt11")
