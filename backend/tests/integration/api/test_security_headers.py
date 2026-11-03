"""Tests for the security headers on all responses."""

import httpx
import pytest

EXPECTED = {
    "content-security-policy": (
        "default-src 'self'; img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
    ),
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
}


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/api/health", "/api/no-such-route"])
async def test_security_headers_on_api_responses(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path)

    for name, value in EXPECTED.items():
        assert response.headers[name] == value
