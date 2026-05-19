"""LND REST adapter (BYO node)."""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from .lightning import (
    Invoice,
    InvoiceCreateRequest,
    InvoiceLookup,
    PaymentResult,
)


def _b64_from_hex(hex_str: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_str)).decode("ascii")


def _hex_from_b64(b64_str: str) -> str:
    return base64.b64decode(b64_str).hex()


@dataclass
class LndRestConfig:
    url: str
    macaroon_hex: str
    verify_tls: bool = True


class LndRestNode:
    def __init__(self, cfg: LndRestConfig, *, client: httpx.AsyncClient | None = None) -> None:
        self._cfg = cfg
        self._client = client

    async def _req(
        self, method: str, path: str, *, json: dict | None = None
    ) -> httpx.Response:
        headers = {
            "grpc-metadata-macaroon": self._cfg.macaroon_hex,
            "content-type": "application/json",
        }
        url = f"{self._cfg.url}{path}"
        if self._client is not None:
            return await self._client.request(method, url, headers=headers, json=json)
        async with httpx.AsyncClient(verify=self._cfg.verify_tls) as c:
            return await c.request(method, url, headers=headers, json=json)

    async def create_invoice(self, req: InvoiceCreateRequest) -> Invoice:
        body = {
            "value_msat": str(req.amount_msat),
            "memo": req.memo or "",
            "expiry": str(req.expiry_seconds or 300),
        }
        res = await self._req("POST", "/v1/invoices", json=body)
        if res.status_code >= 400:
            raise RuntimeError(f"LND createInvoice {res.status_code}: {res.text}")
        data = res.json()
        return Invoice(
            bolt11=data["payment_request"],
            payment_hash=_hex_from_b64(data["r_hash"]),
        )

    async def lookup_invoice(self, payment_hash: str) -> InvoiceLookup:
        b64 = _b64_from_hex(payment_hash)
        # encodeURIComponent equivalent: httpx will url-encode path params if we pass them,
        # but here we replicate the TS exactly (manual encode of the base64 string).
        from urllib.parse import quote

        res = await self._req("GET", f"/v1/invoice/{quote(b64, safe='')}")
        if res.status_code >= 400:
            raise RuntimeError(f"LND lookupInvoice {res.status_code}: {res.text}")
        data = res.json()
        preimage_b64 = data.get("r_preimage")
        return InvoiceLookup(
            settled=bool(data.get("settled")),
            amount_msat=int(data.get("value_msat", "0")),
            preimage=base64.b64decode(preimage_b64) if preimage_b64 else None,
        )

    async def pay_invoice(self, bolt11: str) -> PaymentResult:
        res = await self._req(
            "POST",
            "/v1/channels/transactions",
            json={"payment_request": bolt11},
        )
        if res.status_code >= 400:
            raise RuntimeError(f"LND payInvoice {res.status_code}: {res.text}")
        data = res.json()
        if data.get("payment_error"):
            raise RuntimeError(f"LND payment_error: {data['payment_error']}")
        return PaymentResult(
            preimage=base64.b64decode(data["payment_preimage"]),
            fee_msat=int((data.get("payment_route") or {}).get("total_fees_msat", "0")),
        )
