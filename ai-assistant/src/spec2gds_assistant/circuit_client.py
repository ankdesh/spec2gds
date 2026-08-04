from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import httpx


class CircuitServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"Circuit Designer request failed with status {status_code}.")
        self.status_code = status_code
        self.detail = detail


def normalize_circuit_base_url(
    value: str, allowlist: tuple[str, ...] = ()
) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Circuit Designer URL must use http or https.")
    host = parsed.hostname
    try:
        address = ipaddress.ip_address(host)
        loopback = address.is_loopback
    except ValueError:
        loopback = host.lower() == "localhost"
    path = parsed.path.rstrip("/")
    if not path.endswith("/api/circuit-designer/v1"):
        raise ValueError(
            "Circuit Designer URL must end with /api/circuit-designer/v1."
        )
    normalized = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    configured = normalized in {item.rstrip("/") for item in allowlist}
    if not configured and not (loopback and parsed.scheme == "http"):
        raise ValueError(
            "Circuit Designer URL must be loopback or configured in the service allowlist."
        )
    return normalized


class CircuitDesignerClient:
    def __init__(
        self, timeout_seconds: float = 30, allowlist: tuple[str, ...] = ()
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.allowlist = allowlist

    def normalize(self, base_url: str) -> str:
        return normalize_circuit_base_url(base_url, self.allowlist)

    async def snapshot(self, base_url: str, document_id: str) -> dict[str, Any]:
        return await self._json(
            "GET", self._document_url(base_url, document_id)
        )

    async def png(self, base_url: str, document_id: str) -> bytes:
        response = await self._request(
            "POST",
            f"{self._document_url(base_url, document_id)}/exports",
            json={"format": "png"},
            headers={"Accept": "image/png"},
        )
        return response.content

    async def svg(self, base_url: str, document_id: str) -> str:
        response = await self._request(
            "POST",
            f"{self._document_url(base_url, document_id)}/exports",
            json={"format": "svg"},
            headers={"Accept": "image/svg+xml"},
        )
        return response.text

    async def preview(
        self, base_url: str, document_id: str, batch: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._json(
            "POST",
            f"{self._document_url(base_url, document_id)}/operations/preview",
            json=batch,
        )

    async def submit_proposal(
        self, base_url: str, document_id: str, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._json(
            "POST",
            f"{self._document_url(base_url, document_id)}/proposals",
            json=proposal,
        )

    def _document_url(self, base_url: str, document_id: str) -> str:
        normalized = self.normalize(base_url)
        return f"{normalized}/documents/{quote(document_id, safe='')}"

    async def _json(
        self, method: str, url: str, **kwargs: Any
    ) -> dict[str, Any]:
        response = await self._request(method, url, **kwargs)
        value = response.json()
        if not isinstance(value, dict):
            raise CircuitServiceError(502, "Circuit Designer returned non-object JSON.")
        return value

    async def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(method, url, **kwargs)
        if response.is_error:
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text
            raise CircuitServiceError(response.status_code, detail)
        return response
