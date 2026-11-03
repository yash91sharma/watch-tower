"""Security headers on all responses.

A pure ASGI middleware, so that streams (SSE, log download) stay streams.
Radix UI adds <style> elements, so the CSP allows inline styles.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

CSP = (
    b"default-src 'self'; img-src 'self' data:; "
    b"style-src 'self' 'unsafe-inline'; frame-ancestors 'none'"
)
SECURITY_HEADERS = [
    (b"content-security-policy", CSP),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"same-origin"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *SECURITY_HEADERS]
            await send(message)

        await self.app(scope, receive, send_with_headers)
