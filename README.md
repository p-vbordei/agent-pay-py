# agent-pay (Python)

[![CI](https://github.com/p-vbordei/agent-pay-py/actions/workflows/ci.yml/badge.svg)](https://github.com/p-vbordei/agent-pay-py/actions/workflows/ci.yml)
[![Spec](https://img.shields.io/badge/spec-v0.1-blue)](./SPEC.md)
[![License](https://img.shields.io/badge/license-Apache%202.0-green)](./LICENSE)

> **Idiomatic Python port of [`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay).** L402 + DID-signed invoices for agent-to-agent Lightning payments. Wire-compatible with the TS reference; ships an in-memory mock LND so tests and demos run without a real node.

## What's in the box

- `Paywall.process_request(headers, inner)` — L402 challenge/response middleware, framework-agnostic.
- `Token` — L402 macaroon-style bearer token (HMAC SHA-256 `{payload}.{hmac}`).
- `BOLT11` — parse + encode Lightning invoices (with the modern `payment_secret` tag).
- `JWS` — DID-bound envelope (Ed25519 + JCS-canonical headers/payloads).
- `MemoryNode` — mock LND for tests and offline demos (shared `MemoryLedger` between server and client wallets).
- `LndRest` — real LND adapter (optional, skipped in tests unless `AGENT_PAY_INTEGRATION=1`).
- `ReplayCache` — preimage-based replay protection keyed by `payment_hash`.

## Install

```bash
pip install agent-pay
```

## Quickstart

```python
import asyncio
from agent_pay import MemoryLedger, MemoryNode, did_key_from_public_key, generate_key_pair
from agent_pay.client import FetchResponse, fetch_with_l402
from agent_pay.server import Paywall, PaywallOptions, PaywallResponse

async def main() -> None:
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server_node = MemoryNode(ledger=ledger, name="server")
    client_node = MemoryNode(ledger=ledger, name="client")

    paywall = Paywall(PaywallOptions(
        server_did=did, server_private_key=kp.private_key,
        price_msat=1000, resource="/report",
        lightning=server_node, token_secret=b"thirty-two-byte-test-secret-pad!",
    ))

    async def handler(_p, _h):
        return PaywallResponse(status=200, json={"insight": "agents charging agents works."})

    async def fetch(url, headers):
        path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        r = await paywall.process_request(headers or {}, handler, path=path)
        return FetchResponse(status=r.status, headers=dict(r.headers), json_body=r.json)

    res = await fetch_with_l402("http://x/report", wallet=client_node,
                                 max_price_msat=5000, expected_did=did, fetch=fetch)
    print(res.status, res.json_body)

asyncio.run(main())
```

Run the full demo:

```bash
uv run python examples/quickstart.py
```

```
server DID: did:key:z6Mk…
status:  200
payload: {'insight': 'agents charging agents works.'}
receipt: eyJhbGciOiJFZERTQSIsImtpZCI6ImRpZDprZXk6ejZNa…
```

## How it relates

| Language | Package | Source of truth |
| --- | --- | --- |
| TypeScript | [`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay) | reference |
| Python | `agent-pay` (this) | port |
| Rust | [`agent-pay-rs`](https://github.com/p-vbordei/agent-pay-rs) | port |

## Conformance

This port passes the same `C1`–`C4` clauses as the TS reference and adds a full e2e round-trip:

- **C1-missing** — client rejects 402 missing `X-Did-Invoice`.
- **C1-bad-sig** — client rejects 402 with a tampered `X-Did-Invoice` JWS.
- **C2** — happy-path: valid invoice paid → 200 with verified `X-Payment-Receipt`.
- **C3** — server rejects a replayed preimage with 401.
- **C4** — client rejects when `invoice_hash` mismatches BOLT11.
- **e2e** — `Paywall` + `MemoryNode` round-trip end to end (`tests/test_e2e.py`).

```bash
uv run pytest -v
```

Vectors live in [`vectors/`](./vectors) and are byte-identical to the TS suite's `conformance/vectors/` for the JWS + token layers. BOLT11 wire bytes differ across libraries even with identical contents — see [`docs/architecture.md`](./docs/architecture.md#bolt11-wire-format-caveat) for why.

## Architecture

See [docs/architecture.md](./docs/architecture.md).

## Development

```bash
git clone https://github.com/p-vbordei/agent-pay-py
cd agent-pay-py
uv sync --extra dev
uv run pytest
uv run ruff check src tests
```

## License

Apache-2.0 — see [LICENSE](./LICENSE).
