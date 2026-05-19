# agent-pay (Python)

> L402 (HTTP 402 + Lightning) with DID-signed invoices for agent-to-agent payments.
> Python port of [`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay).

[![CI](https://github.com/p-vbordei/agent-pay-py/actions/workflows/ci.yml/badge.svg)](https://github.com/p-vbordei/agent-pay-py/actions/workflows/ci.yml)
[![Spec v1.0](https://img.shields.io/badge/spec-v1.0-blue)](./SPEC.md)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](./LICENSE)

Same SPEC, same conformance vectors as the TypeScript reference. The same C1-missing, C1-bad-sig, C2, C3, C4 scenarios pass here.

## Install

```bash
pip install agent-pay
```

## Quickstart

```python
import asyncio
from agent_pay import (
    Paywall, PaywallOptions, PaywallResponse,
    MemoryLedger, MemoryNode,
    generate_key_pair, did_key_from_public_key,
)
from agent_pay.client import fetch_with_l402, FetchResponse

async def main():
    kp = generate_key_pair()
    did = did_key_from_public_key(kp.public_key)
    ledger = MemoryLedger()
    server = MemoryNode(ledger=ledger, name="server")
    client = MemoryNode(ledger=ledger, name="client")

    paywall = Paywall(PaywallOptions(
        server_did=did,
        server_private_key=kp.private_key,
        price_msat=1000,
        resource="/report",
        lightning=server,
        token_secret=b"thirty-two-byte-test-secret-pad!",
    ))

    async def handler(_path, _headers):
        return PaywallResponse(status=200, json={"insight": "paid content"})

    async def fetch(url, headers):
        resp = await paywall.process_request(headers or {}, handler)
        return FetchResponse(status=resp.status, headers=dict(resp.headers),
                             json_body=resp.json)

    res = await fetch_with_l402(
        "http://x/report",
        wallet=client,
        max_price_msat=5000,
        expected_did=did,
        fetch=fetch,
    )
    print(res.json_body)
    print(res.header("x-payment-receipt")[:64], "...")

asyncio.run(main())
```

## Conformance

Run the full test suite:

```bash
uv sync --extra dev
uv run pytest -v
```

The conformance vectors (`vectors/c1-*.json`, `c2-*.json`, `c3-*.json`, `c4-*.json`) are byte-identical to the TS reference's `conformance/vectors/`.

## Implementation parity

The Python port mirrors the TS module layout 1:1:

| TS file | Python module |
| --- | --- |
| `src/bolt11.ts` | `agent_pay.bolt11` |
| `src/client.ts` | `agent_pay.client` |
| `src/envelope.ts` | `agent_pay.envelope` |
| `src/jcs.ts` | `agent_pay.jcs` |
| `src/jws.ts` | `agent_pay.jws` |
| `src/keys.ts` | `agent_pay.keys` |
| `src/lightning.ts` | `agent_pay.lightning` |
| `src/lnd-rest.ts` | `agent_pay.lnd_rest` |
| `src/memory-node.ts` | `agent_pay.memory_node` |
| `src/replay.ts` | `agent_pay.replay` |
| `src/server.ts` | `agent_pay.server` |
| `src/token.ts` | `agent_pay.token` |

Server side: the Python port exposes a framework-agnostic `Paywall` class with `process_request(headers, inner_handler)`. The TS reference uses Hono middleware; an HTTP framework adapter (e.g. FastAPI) is a one-line wrapper around `process_request`.

## License

Apache 2.0 - see [LICENSE](./LICENSE).
