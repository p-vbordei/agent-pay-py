# Architecture

## Goal

Port [`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay) to idiomatic Python while staying wire-compatible at the JWS + L402-token layers. The same `C1`–`C4` conformance vectors that pass against the TypeScript reference pass here.

## Module map

| TS source | Python module | Role |
| --- | --- | --- |
| `src/envelope.ts` | `agent_pay.envelope` | Build + verify `InvoiceEnvelope` and `ReceiptEnvelope`. |
| `src/bolt11.ts` | `agent_pay.bolt11` | Parse + encode BOLT11 invoices. |
| `src/lightning.ts` | `agent_pay.lightning` | `LightningNode` protocol + data types. |
| `src/replay.ts` | `agent_pay.replay` | `ReplayCache` keyed by `payment_hash`. |
| `src/lnd-rest.ts` | `agent_pay.lnd_rest` | Real LND adapter (gated). |
| `src/memory-node.ts` | `agent_pay.memory_node` | In-process mock LND for tests + demos. |
| `src/token.ts` | `agent_pay.token` | L402 bearer token (HMAC SHA-256). |
| `src/jws.ts` | `agent_pay.jws` | Compact JWS (EdDSA). |
| `src/jcs.ts` | `agent_pay.jcs` | RFC 8785 JSON Canonicalization Scheme. |
| `src/keys.ts` | `agent_pay.keys` | Ed25519 + `did:key` (multicodec `0xed01`). |
| `src/client.ts` | `agent_pay.client` | `fetch_with_l402` — JWS verify, price/expiry check, pay, retry. |
| `src/server.ts` | `agent_pay.server` | `Paywall.process_request` middleware. |

The Python port exposes a framework-agnostic `Paywall` class that any HTTP server (FastAPI, Starlette, AIOHTTP) can wrap in a one-line adapter. The TS reference is Hono-specific.

## Dependency choices

- **`bolt11`** (PyPI, by lnbits) — battle-tested BOLT11 codec.
- **`cryptography`** — Ed25519 + HMAC + SHA-256 from a single vetted dep.
- **`jcs`** — RFC 8785 canonicalisation.
- **`base58`**, **`httpx`** — DID multibase + the optional LND adapter.

No `pymacaroons`. The L402 token we issue is the simple `{base64url(payload)}.{base64url(hmac)}` form the TS reference uses — opaque to the client, validated only by us. A real macaroon implementation is wire-compatible but out of v0.1 scope (same as the TS reference).

## BOLT11 wire-format caveat

BOLT11 invoices with **identical contents** can produce **different signed strings** across libraries. The signature covers the bech32-decoded tagged fields; ordering rules in the spec allow legitimate variations, and library-side defaults (timestamp truncation, optional tags, signature recovery flag) differ. Concretely:

- The TS reference uses the npm `bolt11` package.
- This port uses the PyPI `bolt11` (lnbits) package.

Each port **round-trips its own invoices** (`parse(encode(x)) == x`) and the JWS envelope binds `bolt11_hash = sha256(bolt11_bytes)`, so a tampered invoice fails C4. But you should not expect `python_encode(parse(ts_bolt11)) == ts_bolt11`.

What **does** match byte-for-byte across ports:

- The JCS-canonical JWS header and payload bytes.
- The `Token` payload + HMAC.
- The DID resolution rules (`did:key` + multicodec `0xed01`).

That is what the conformance vectors lock down.

## `payment_secret` tag

Modern BOLT11 (BOLT-11 amendment, ~2020) requires the `payment_secret` ("s") tag for MPP and to defeat probing attacks. Both ports emit it; both reject invoices without it on the receive path.

## Integration tests

Real-LND tests sit alongside unit tests but are gated behind `AGENT_PAY_INTEGRATION=1`. They drive a `polar`-style regtest network from `docker-compose.polar.yml` (mirrors the TS reference). The default `uv run pytest` does **not** require Docker.

## Testing strategy

- **`tests/test_bolt11.py`** — round-trip equality for a generated invoice.
- **`tests/test_jcs.py`** — JCS canonical bytes match a golden vector.
- **`tests/test_jws.py`** — sign + verify; tamper detection.
- **`tests/test_keys.py`** — `did:key` round-trip; multicodec correctness.
- **`tests/test_token.py`** — issue + verify; expiry; tampered HMAC.
- **`tests/test_replay.py`** — second presentation of the same preimage rejected.
- **`tests/test_envelope.py`** — invoice + receipt envelopes against fixtures.
- **`tests/test_memory_node.py`** — `MemoryNode` invoice lifecycle + ledger book-keeping.
- **`tests/test_conformance.py`** — drives every `vectors/c{1..4}-*.json`.
- **`tests/test_e2e.py`** — `Paywall` + `MemoryNode` full round-trip; receipt verified.

A green `uv run pytest` is 37 tests in <200 ms.
