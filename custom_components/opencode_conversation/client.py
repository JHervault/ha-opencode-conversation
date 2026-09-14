"""Small authenticated client for the OpenCode Server HTTP API."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp


class OpenCodeError(Exception):
    """Base error raised while communicating with OpenCode."""


class OpenCodeAuthenticationError(OpenCodeError):
    """OpenCode rejected the configured credentials."""


class OpenCodeConnectionError(OpenCodeError):
    """OpenCode could not be contacted or sent an invalid response."""


def normalize_url(url: str) -> str:
    """Return the server root without a trailing slash or path ambiguity."""
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must be an absolute HTTP(S) URL")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


def extract_text_parts(payload: Any) -> str:
    """Extract text only from an OpenCode message result.

    The server has returned both a message object and arrays of messages across
    versions.  Never stringify tools, metadata, or unknown part types into the
    spoken response.
    """
    messages: Iterable[Any]
    if isinstance(payload, list):
        messages = payload
    elif isinstance(payload, dict) and isinstance(payload.get("messages"), list):
        messages = payload["messages"]
    else:
        messages = [payload]

    text: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            value = part.get("text")
            if isinstance(value, str) and value.strip():
                text.append(value.strip())
    return "\n".join(text)


class OpenCodeClient:
    """Use Home Assistant's shared aiohttp session to call OpenCode."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str,
        password: str,
        timeout: int,
    ) -> None:
        self._session = session
        self._url = normalize_url(url)
        self._auth = aiohttp.BasicAuth(username, password)
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._url}{path}",
                auth=self._auth,
                timeout=self._timeout,
                **kwargs,
            ) as response:
                if response.status in {401, 403}:
                    raise OpenCodeAuthenticationError("OpenCode authentication failed")
                if response.status >= 400:
                    raise OpenCodeConnectionError(
                        f"OpenCode returned HTTP {response.status}"
                    )
                try:
                    return await response.json(content_type=None)
                except (aiohttp.ContentTypeError, ValueError) as err:
                    raise OpenCodeConnectionError(
                        "OpenCode returned invalid JSON"
                    ) from err
        except OpenCodeAuthenticationError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OpenCodeConnectionError("Unable to reach OpenCode") from err

    async def health(self) -> Any:
        """Check that the server is alive and credentials are accepted."""
        return await self._request("GET", "/global/health")

    async def agents(self) -> list[dict[str, Any]]:
        """List available OpenCode agents."""
        payload = await self._request("GET", "/agent")
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [item for item in payload["data"] if isinstance(item, dict)]
        raise OpenCodeConnectionError("OpenCode returned an invalid agent list")

    async def validate(self, agent: str) -> None:
        """Validate connectivity, authentication, and the selected agent."""
        await self.health()
        agent_ids = {item.get("name") or item.get("id") for item in await self.agents()}
        if agent not in agent_ids:
            raise OpenCodeConnectionError("Configured OpenCode agent was not found")

    async def create_session(self) -> str:
        """Create an OpenCode session and return its identifier."""
        payload = await self._request("POST", "/session", json={})
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str):
            raise OpenCodeConnectionError("OpenCode returned an invalid session")
        return payload["id"]

    async def send_message(self, session_id: str, agent: str, text: str) -> str:
        """Send a text prompt and return only textual response parts."""
        payload = await self._request(
            "POST",
            f"/session/{session_id}/message",
            json={"agent": agent, "parts": [{"type": "text", "text": text}]},
        )
        return extract_text_parts(payload)
