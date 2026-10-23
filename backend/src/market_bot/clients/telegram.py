import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("market_bot.clients.telegram")


class AsyncTelegramClient:
    """Asynchronous HTTP client for the official Telegram Bot API."""

    def __init__(self, bot_token: str, base_url: str = "https://api.telegram.org"):
        self.bot_token = bot_token.strip()
        self.base_url = f"{base_url}/bot{self.bot_token}"
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(45.0, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def get_me(self) -> Dict[str, Any]:
        """Verify bot token and get bot details."""
        client = await self._get_client()
        try:
            resp = await client.get(f"{self.base_url}/getMe")
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram getMe request failed: {e}")
            return {"ok": False, "description": str(e)}

    async def get_updates(
        self,
        offset: Optional[int] = None,
        timeout: int = 15,
        allowed_updates: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Long-polling method to retrieve updates from Telegram.
        """
        client = await self._get_client()
        params: Dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        if allowed_updates:
            params["allowed_updates"] = allowed_updates

        try:
            resp = await client.get(f"{self.base_url}/getUpdates", params=params, timeout=timeout + 10)
            return resp.json()
        except httpx.TimeoutException:
            # Normal long-polling timeout (idle window elapsed)
            return {"ok": True, "result": []}
        except Exception as e:
            logger.error(f"Telegram getUpdates request failed: {e}")
            return {"ok": False, "description": str(e)}

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a message to a chat."""
        client = await self._get_client()
        payload: Dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id

        try:
            resp = await client.post(f"{self.base_url}/sendMessage", json=payload)
            return resp.json()
        except Exception as e:
            logger.error(f"Telegram sendMessage request failed: {e}")
            return {"ok": False, "description": str(e)}
