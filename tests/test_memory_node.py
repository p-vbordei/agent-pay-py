import pytest

from agent_pay.lightning import InvoiceCreateRequest
from agent_pay.memory_node import MemoryLedger, MemoryNode


async def test_two_memory_nodes_share_ledger_and_route_payment() -> None:
    ledger = MemoryLedger()
    alice = MemoryNode(ledger=ledger, name="alice")
    bob = MemoryNode(ledger=ledger, name="bob")

    inv = await alice.create_invoice(InvoiceCreateRequest(amount_msat=1000, memo="tea"))
    assert inv.bolt11.startswith("lnbcrt")
    assert len(inv.payment_hash) == 64

    before = await alice.lookup_invoice(inv.payment_hash)
    assert before.settled is False

    pay = await bob.pay_invoice(inv.bolt11)
    assert len(pay.preimage) == 32

    after = await alice.lookup_invoice(inv.payment_hash)
    assert after.settled is True
    assert after.preimage == pay.preimage


async def test_pay_invoice_rejects_unknown_bolt11() -> None:
    ledger = MemoryLedger()
    node = MemoryNode(ledger=ledger, name="solo")
    with pytest.raises(ValueError):
        await node.pay_invoice("lnbcrt0unknown")
