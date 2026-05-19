# agent-pay — v1.0 specification

**Status:** stable. Reference implementation at version 0.1.0. Requires a Lightning node (BYO via LND REST; NWC and `did:web` deferred to v0.2).

## Abstract

`agent-pay` is a reference implementation that composes [L402](https://github.com/lightninglabs/L402) (HTTP 402 + Lightning) with DID-signed invoices. It is NOT a new payment protocol. It is the glue that lets agent A charge agent B a known price per request, where the invoice is cryptographically bound to agent A's DID — solving L402's identity-binding gap.

## 1. Terminology

- **Server agent** — the agent charging for a resource.
- **Client agent** — the agent paying for access.
- **DID** — W3C Decentralized Identifier (see [`agent-id`](../agent-id/)).
- **L402** — Lightning HTTP 402 challenge/response protocol (bLIP-0026). Invoice + macaroon + preimage.
- **NWC** — Nostr Wallet Connect ([NIP-47](https://nips.nostr.com/47)).

## 2. Flow

```
Client: GET /resource
Server: 402 Payment Required
        WWW-Authenticate: L402 macaroon="<base64>", invoice="<BOLT11>"
        X-Did-Invoice: <JWS>               // binds invoice to server DID
Client: (verifies X-Did-Invoice JWS under server's DID; pays BOLT11 via NWC/LND)
Client: GET /resource
        Authorization: L402 <macaroon>:<preimage>
Server: 200 OK
        X-Payment-Receipt: <JWS>           // optional: server signs "paid, preimage X, resource Y"
```

## 3. Server-side spec

### 3.1 402 response

The `WWW-Authenticate: L402` header is per bLIP-0026. Additionally, servers MUST emit:

```
X-Did-Invoice: <compact JWS>
```

The JWS payload (JSON, JCS-canonical):

```
{
  "v": "agent-pay/0.1",
  "invoice_hash": "<sha256 of BOLT11>",
  "did": "did:key:..." | "did:web:...",
  "price_msat": <uint>,
  "resource": "<URL path>",
  "expires_at": "<RFC 3339>",
  "nonce": "<base64 16 bytes>"
}
```

Signed with Ed25519 (`alg: EdDSA`) under the server's DID. `kid` MUST match a verification method in the DID Document.

### 3.2 Success response

On valid `Authorization: L402`, the server MAY emit:

```
X-Payment-Receipt: <compact JWS>
```

Payload:

```
{
  "v": "agent-pay/0.1",
  "invoice_hash": "...",
  "preimage_hash": "<sha256 of preimage>",
  "resource": "<URL path>",
  "paid_at": "<RFC 3339>"
}
```

Also signed by the server. Receipts are convenient for audit; clients MAY require them.

## 4. Client-side spec

A conforming client MUST:

1. Verify `X-Did-Invoice` JWS before paying. Reject if DID resolution fails, signature invalid, `invoice_hash` doesn't match the BOLT11 hash, `expires_at` has passed, or `price_msat` exceeds a configured cap.
2. Pay the BOLT11 invoice via the client's wallet integration (NWC or LND REST).
3. Retry the request with `Authorization: L402 <macaroon>:<preimage>`.
4. Optionally verify `X-Payment-Receipt` on the success response.

## 5. Wallet integration

v0.1 supports:

- **NWC (Nostr Wallet Connect)** via [`@getalby/sdk`](https://github.com/getAlby/js-sdk). Client configured with an NWC connection URI.
- **LND REST** via configured `LND_URL` + macaroon + TLS cert.

LDK-node embedded wallet is NOT in v0.1. Future versions may add it.

## 6. Security considerations

- **Invoice-replay**: a BOLT11 invoice's `payment_hash` is unique; the Lightning network prevents double-spend of a preimage. The JWS `nonce` prevents the server from re-using the same signed `X-Did-Invoice` for multiple distinct invoices.
- **DID revocation**: if the server's DID rotates its key, prior `X-Did-Invoice` values are still valid for their `expires_at` window but SHOULD be superseded on new requests. v0.1 has no status-list revocation; clients SHOULD treat `expires_at` as the practical upper bound on stale-key acceptance. A status-list mechanism is deferred to v0.2.
- **Overcharging**: clients MUST enforce `price_msat` caps. The JWS prevents servers from silently raising the price after signing; clients MUST also verify the BOLT11 amount matches `price_msat`.
- **Privacy**: clients leak their paying wallet identity via the Lightning network. Use route-blinding / LN-onion if that matters. v0.1 does not implement route-blinding; users requiring payer privacy should pair `agent-pay` with an LN-onion-capable wallet.

## 7. AP2 compatibility (stretch)

A conforming implementation MAY provide an adapter that wraps the `X-Did-Invoice` + successful preimage into an AP2-style PaymentMandate, enabling interop with Google-AP2 agents that expect that shape. Spec: [AP2 PaymentMandate](https://ap2-protocol.org/specification/).

## 8. Conformance (polar regtest harness)

A conforming implementation MUST:

- (C1) Reject a 402 response with missing or invalid `X-Did-Invoice`.
- (C2) Pay a valid invoice, retry with `Authorization: L402`, receive 200 and a valid `X-Payment-Receipt`.
- (C3) Reject a replayed preimage (server-side).
- (C4) Reject an invoice whose BOLT11 hash doesn't match `X-Did-Invoice.invoice_hash`.

Test vectors and a polar scenario live in `conformance/`.

## 9. References

- [L402 bLIP-0026](https://github.com/lightninglabs/L402)
- [`aperture` reverse proxy](https://github.com/lightninglabs/aperture)
- [NIP-47 Nostr Wallet Connect](https://nips.nostr.com/47)
- [AP2 PaymentMandate](https://ap2-protocol.org/specification/)
- [`agent-id` spec](../agent-id/SPEC.md)
