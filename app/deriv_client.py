"""
Thin async wrapper around Deriv's WebSocket API (v3).

Docs: https://developers.deriv.com/docs/websockets
Every call here is a request/response or subscribe/stream pair over a single
persistent websocket connection, matched by Deriv's `req_id`.

This module is intentionally the ONLY place that talks to Deriv. The
frontend / API layer never sees a raw Deriv token — it goes user -> DB
(encrypted) -> here -> Deriv.
"""
import asyncio
import itertools
import json
from typing import AsyncIterator, Optional

import websockets

from app.config import settings

_req_id_counter = itertools.count(1)


class DerivAPIError(Exception):
    pass


class DerivClient:
    """
    One instance per active user session / bot. Not thread-safe across
    multiple concurrent bots on the same instance — spin up one per bot
    (see bot_engine.py).
    """

    def __init__(self, api_token: str, app_id: Optional[str] = None):
        self.api_token = api_token
        self.app_id = app_id or settings.deriv_app_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._tick_subscribers: dict[str, list[asyncio.Queue]] = {}
        self.account_info: dict = {}

    # ---- connection lifecycle -------------------------------------------------

    async def connect(self, authorize: bool = True):
        url = f"{settings.deriv_ws_url}?app_id={self.app_id}"
        self.ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
        self._listener_task = asyncio.create_task(self._listen())
        if authorize:
            await self.authorize()

    async def close(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _listen(self):
        """Background task: routes every incoming frame either to a pending
        request future (matched by req_id) or to a tick subscriber queue."""
        assert self.ws is not None
        async for raw in self.ws:
            msg = json.loads(raw)
            msg_type = msg.get("msg_type")

            if msg_type == "tick":
                symbol = msg["tick"]["symbol"]
                for q in self._tick_subscribers.get(symbol, []):
                    q.put_nowait(msg["tick"])
                continue

            req_id = msg.get("req_id")
            fut = self._pending.pop(req_id, None)
            if fut and not fut.done():
                if "error" in msg:
                    fut.set_exception(DerivAPIError(msg["error"].get("message", "Deriv API error")))
                else:
                    fut.set_result(msg)

    async def _send(self, payload: dict, timeout: float = 15.0) -> dict:
        assert self.ws is not None, "call connect() first"
        req_id = next(_req_id_counter)
        payload = {**payload, "req_id": req_id}
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = fut
        await self.ws.send(json.dumps(payload))
        return await asyncio.wait_for(fut, timeout=timeout)

    # ---- auth -------------------------------------------------------------

    async def authorize(self) -> dict:
        """Authorize this websocket connection using the user's API token.
        Deriv resolves whether that token maps to a demo or real account
        server-side based on which of the user's accounts the token was
        scoped to — so demo/real is determined by which token was issued,
        not by a flag we send."""
        resp = await self._send({"authorize": self.api_token})
        self.account_info = resp.get("authorize", {})
        return self.account_info

    # ---- historical data (for backtesting) ---------------------------------

    async def ticks_history(self, symbol: str, count: int = 5000, style: str = "ticks") -> list[dict]:
        """Pull real historical ticks/candles for backtesting. This is the
        actual market history — not synthetic/fabricated data."""
        resp = await self._send({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "style": style,  # "ticks" or "candles"
        })
        if style == "candles":
            return resp.get("candles", [])
        history = resp.get("history", {})
        prices = history.get("prices", [])
        times = history.get("times", [])
        return [{"epoch": t, "price": p} for t, p in zip(times, prices)]

    # ---- live streaming -----------------------------------------------------

    async def subscribe_ticks(self, symbol: str) -> AsyncIterator[dict]:
        """Subscribe once, yield forever. Multiple callers can subscribe to
        the same symbol; each gets its own queue fed by the shared listener."""
        await self._send({"ticks": symbol, "subscribe": 1})
        queue: asyncio.Queue = asyncio.Queue()
        self._tick_subscribers.setdefault(symbol, []).append(queue)
        try:
            while True:
                tick = await queue.get()
                yield tick
        finally:
            self._tick_subscribers[symbol].remove(queue)

    # ---- trading ------------------------------------------------------------

    async def proposal(self, symbol: str, contract_type: str, stake: float,
                        duration: int = 5, duration_unit: str = "t") -> dict:
        """Request a price quote for a contract before buying it.
        contract_type: 'CALL' (rise) or 'PUT' (fall) for rise/fall contracts.
        duration_unit: 't' = ticks, 's' = seconds, 'm' = minutes."""
        resp = await self._send({
            "proposal": 1,
            "amount": stake,
            "basis": "stake",
            "contract_type": contract_type,
            "currency": self.account_info.get("currency", "USD"),
            "duration": duration,
            "duration_unit": duration_unit,
            "symbol": symbol,
        })
        return resp.get("proposal", {})

    async def buy(self, proposal_id: str, price: float) -> dict:
        """Execute the trade using a proposal id from proposal(). `price` is
        the max price willing to pay (usually the proposal's ask price)."""
        resp = await self._send({"buy": proposal_id, "price": price})
        return resp.get("buy", {})

    async def sell_contract(self, contract_id: int, price: float = 0) -> dict:
        """Close/sell an open contract early if supported for that contract type."""
        resp = await self._send({"sell": contract_id, "price": price})
        return resp.get("sell", {})

    async def balance(self) -> dict:
        resp = await self._send({"balance": 1})
        return resp.get("balance", {})
