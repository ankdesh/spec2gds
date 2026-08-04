"""HTTP client for the local Spec Editor assistant contract."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx


class SpecServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: object) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def normalize_spec_base_url(base_url: str, allowlist: tuple[str, ...]) -> str:
    normalized = base_url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Spec service must be an allowlisted HTTP(S) origin.")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise ValueError("Spec service URL must contain only scheme, host, and port.")
    configured = {value.rstrip("/") for value in allowlist}
    if normalized not in configured:
        raise ValueError("Spec service origin is not in SPEC_SERVICE_ALLOWLIST.")
    return normalized


class SpecEditorClient:
    def __init__(self, timeout_seconds: float, allowlist: tuple[str, ...]) -> None:
        self.timeout_seconds = timeout_seconds
        self.allowlist = allowlist

    def normalize(self, base_url: str) -> str:
        return normalize_spec_base_url(base_url, self.allowlist)

    async def context(
        self,
        base_url: str,
        document_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"{self.normalize(base_url)}/assistant/context",
            params={
                "document_id": document_id,
                "entity_kind": entity_kind,
                "entity_id": entity_id,
            },
        )

    async def preview(self, base_url: str, proposal: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{self.normalize(base_url)}/assistant/proposals/preview",
            json=proposal,
        )

    async def apply(self, base_url: str, proposal: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"{self.normalize(base_url)}/assistant/proposals/apply",
            json=proposal,
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise SpecServiceError(503, f"Spec service request failed: {exc}") from exc
        if response.is_error:
            try:
                payload = response.json()
                detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
            except ValueError:
                detail = response.text
            raise SpecServiceError(response.status_code, detail)
        value = response.json()
        if not isinstance(value, dict):
            raise SpecServiceError(502, "Spec service returned a non-object response.")
        return value
