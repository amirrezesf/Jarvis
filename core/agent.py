"""
Agent wrapper for 9Router.

Talks to a local 9Router gateway's OpenAI-compatible API.
"""

from __future__ import annotations

import logging
import requests

import config

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for agent errors."""


class AgentConnectionError(AgentError):
    """Raised when the 9Router gateway cannot be reached."""


class AgentTimeoutError(AgentError):
    """Raised when the 9Router request exceeds the configured timeout."""


class Agent:
    """Thin wrapper around a 9Router gateway's HTTP API.

    Sends chat completion requests to a local 9Router instance,
    which routes them across providers using the configured Combo.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (base_url or config.NINEROUTER_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else config.NINEROUTER_KEY
        self.model = model or config.NINEROUTER_COMBO_NAME
        self.timeout = timeout if timeout is not None else config.NINEROUTER_TIMEOUT

        self._session = requests.Session()
        if self.api_key:
            self._session.headers.update(
                {"Authorization": f"Bearer {self.api_key}"}
            )
        self._session.headers.update({"Content-Type": "application/json"})

    def ask(self, text: str) -> str:
        """Send *text* to the configured 9Router combo and return the reply.

        Raises:
            AgentConnectionError: Gateway not reachable.
            AgentTimeoutError: Request exceeded ``self.timeout``.
            AgentError: Any other API or response error.
        """
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }

        logger.debug(
            "POST %s  model=%s  chars=%d", url, self.model, len(text)
        )

        try:
            resp = self._session.post(
                url, json=payload, timeout=self.timeout
            )
        except requests.ConnectionError as exc:
            raise AgentConnectionError(
                f"Cannot reach 9Router at {self.base_url}. "
                "Is `9router` running? "
                f"({exc})"
            ) from exc
        except requests.Timeout as exc:
            raise AgentTimeoutError(
                f"9Router request timed out after {self.timeout:.0f}s."
            ) from exc

        if resp.status_code == 401:
            raise AgentError(
                "9Router rejected the API key (HTTP 401). "
                "Check NINEROUTER_KEY in config.py."
            )
        if resp.status_code != 200:
            raise AgentError(
                f"9Router returned HTTP {resp.status_code}: {resp.text[:500]}"
            )

        try:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise AgentError(
                f"Unexpected response from 9Router: {resp.text[:500]}"
            ) from exc