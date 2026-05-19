# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-05-19

Initial Python port of [`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay).
Passes the same `C1`–`C4` conformance vectors as the TS reference.

### Added

- `Paywall` — framework-agnostic L402 challenge/response middleware
  (`process_request(headers, inner)`).
- L402 token (HMAC SHA-256 `{payload}.{hmac}`) — `issue_token` / `verify_token`.
- BOLT11 parse + encode via the lnbits `bolt11` package (with `payment_secret`).
- DID-bound JWS envelopes for invoices and receipts (Ed25519 + RFC 8785 JCS).
- `did:key` Ed25519 (multicodec `0xed01`) helpers.
- `MemoryNode` — in-process mock LND for tests and offline demos, backed by a
  shared `MemoryLedger`.
- `LndRest` — optional real LND adapter (skipped unless
  `AGENT_PAY_INTEGRATION=1`).
- `ReplayCache` — preimage replay protection keyed by `payment_hash`.
- `fetch_with_l402` client wrapper — resolves `did:key`, verifies JWS, enforces
  `max_price_msat` and `expires_at`, pays via a `LightningNode`, retries,
  optionally verifies the receipt.
- Conformance vectors `c1-missing-did-invoice`, `c1-invalid-jws`, `c2-roundtrip`,
  `c3-replayed-preimage`, `c4-bolt11-hash-mismatch` (`tests/test_conformance.py`).
- End-to-end test (`tests/test_e2e.py`) running the full round-trip against
  `MemoryNode`.
- Runnable demo at `examples/quickstart.py`.

[0.1.0]: https://github.com/p-vbordei/agent-pay-py/releases/tag/v0.1.0
