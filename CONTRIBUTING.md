# Contributing

Thanks for the interest. This is a port of
[`@p-vbordei/agent-pay`](https://github.com/p-vbordei/agent-pay); the TS
reference is the source of truth for wire format and conformance vectors.

## Dev loop

```bash
git clone https://github.com/p-vbordei/agent-pay-py
cd agent-pay-py
uv sync --extra dev
uv run pytest            # 37 tests, ~200 ms
uv run ruff check src tests
uv run mypy src
```

## Running the demo

```bash
uv run python examples/quickstart.py
```

Spins a `Paywall` + two `MemoryNode` wallets in-process and walks the full
402 → pay → retry → 200 round-trip. No Docker, no real Lightning node.

## Real-LND integration tests

The default test suite uses the in-memory `MemoryNode` and never hits the
network. Tests that drive a real LND node over REST are gated behind the
`AGENT_PAY_INTEGRATION` env var (mirrors the TS reference's behavior).

```bash
docker compose -f docker-compose.polar.yml up -d   # polar regtest network
export LND_ALICE_URL=https://localhost:8081
export LND_ALICE_MACAROON_HEX=...
AGENT_PAY_INTEGRATION=1 uv run pytest -k lnd_rest
```

See [docs/architecture.md](./docs/architecture.md) for the rationale.

## What to PR

- Bug fixes against `vectors/c{1..4}-*.json` (always with a failing test
  first).
- Tightenings to the `Paywall` middleware that keep
  `tests/test_conformance.py` and `tests/test_e2e.py` green.
- New `LightningNode` adapters (NWC, LDK-node, CLN, …) — keep them as
  separate modules and default-off.

Please **don't** change the wire format in this port without a corresponding
change to the TS reference. Out-of-scope items live in
[SPEC.md §Deferred](./SPEC.md).

## Commit + PR style

- Conventional-ish (`fix:`, `feat:`, `docs:`) but not strict.
- Small, focused PRs.
- New behavior comes with a test.

## License

By contributing you agree your work is licensed under Apache-2.0 (see
[LICENSE](./LICENSE)).
