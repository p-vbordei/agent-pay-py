"""Shared test harness: a tiny app that routes paths to a Paywall + handler."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from agent_pay.client import FetchResponse
from agent_pay.server import Paywall, PaywallResponse


def make_fetch(
    paywall: Paywall,
    handler: Callable[[str, dict[str, str]], Awaitable[PaywallResponse]],
) -> Callable[[str, dict[str, str] | None], Awaitable[FetchResponse]]:
    """Returns a fetch(url, headers) function that drives the paywall."""

    async def fetch(url: str, headers: dict[str, str] | None) -> FetchResponse:
        # The TS tests pass full URLs like http://x/report; strip to path.
        path = url
        if "://" in url:
            path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        resp = await paywall.process_request(headers or {}, handler, path=path)
        return _to_fetch_response(resp)

    return fetch


def make_raw_fetch(
    paywall: Paywall,
    handler: Callable[[str, dict[str, str]], Awaitable[PaywallResponse]],
) -> Callable[[str, dict[str, str] | None], Awaitable[PaywallResponse]]:
    async def raw(url: str, headers: dict[str, str] | None) -> PaywallResponse:
        path = url
        if "://" in url:
            path = "/" + url.split("://", 1)[1].split("/", 1)[1]
        return await paywall.process_request(headers or {}, handler, path=path)

    return raw


def _to_fetch_response(resp: PaywallResponse) -> FetchResponse:
    return FetchResponse(
        status=resp.status,
        headers=dict(resp.headers),
        body=resp.body,
        json_body=resp.json,
    )


async def echo_handler(_path: str, _headers: dict[str, str]) -> PaywallResponse:
    return PaywallResponse(status=200, json={"data": "hello"})


async def ok_handler(_path: str, _headers: dict[str, str]) -> PaywallResponse:
    return PaywallResponse(status=200, json={"ok": True})
