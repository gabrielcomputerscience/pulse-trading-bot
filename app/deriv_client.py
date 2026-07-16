"""
Deriv trading API client — rebuilt against the current API (verified live
against Deriv's own API Playground, July 2026).

Deriv now runs a REST + WebSocket "Options" API:
  - REST (https://api.derivws.com/trading/v1/options/...): account listing
    and OTP issuance for opening an authenticated WebSocket connection.
    Auth via `Deriv-App-ID` header + `Authorization: Bearer <token>`
    (either an OAuth 2.0 access_token or a Personal Access Token generated
    at developers.deriv.com/dashboard/tokens).
  - WebSocket:
      - Public, no auth: wss://api.derivws.com/trading/v1/options/ws/public
        — used for market data (ticks/history), which isn't account-specific.
      - Per-account, authenticated via a short-lived OTP embedded directly
        in the URL (obtained from the REST OTP endpoint):
        .../ws/demo?otp=... or .../ws/real?otp=...

Trading message shapes (ticks_history, balance, proposal, buy, sell,
forget) are UNCHANGED from the older "legacy" WS API this was originally
built against — verified live, request and response both match exactly.
Only the connection/auth handshake changed; a single Bearer token now
covers every account under that login (no more separate per-account
tokens), and there's no `authorize` message anymore — auth happens via the
OTP-bearing URL itself.
"""
import asyncio
import itertools
import json
from typing import AsyncIterator, Optional

import httpx
import websockets

from app.config import settings

_req_id_counter = itertools.count(1)

REST_BASE_URL = "https://api.derivws.com"
PUBLIC_WS_URL = "wss://api.derivws.com/trading/v1/options/ws/public"


class DerivAPIError(Exception):
    pass


class DerivClient:
    """One instance per connection. For account-specific work (balance,
    proposal, buy, sell) call connect(account_id=...). For public market
    data (ticks_history, tick subscriptions) call connect() with no
    account_id — no token needed at all for that case."""

    def __init__(self, api_token: str = "", app_id: Optional[str] = None):
        self.api_token = api_token
        self.app_id = app_id or settings.deriv_app_id
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._pending: dict[int, asyncio.Future] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._tick_subscribers: dict[str, list[asyncio.Queue]] = {}
        self.account_info: dict = {}

    # ---- REST (account discovery + OTP) --------------------------------

    def _rest_headers(self) -> dict:
        return {"Deriv-App-ID": self.app_id, "Authorization": f"Bearer {self.api_token}"}

    async def list_accounts(self) -> list[dict]:
        """Every account (demo + real) the token's owner has, via REST.
        Each entry: account_id, balance, currency, account_type ('demo'/
        'real'), status."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{REST_BASE_URL}/trading/v1/options/accounts",
                                     headers=self._rest_headers())
        if resp.status_code != 200:
            raise DerivAPIError(f"Failed to list accounts ({resp.status_code}): {resp.text}")
        return resp.json().get("data", [])

    async def _get_otp_ws_url(self, account_id: str) -> str:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{REST_BASE_URL}/trading/v1/options/accounts/{account_id}/otp",
                headers=self._rest_headers())
        if resp.status_code != 200:
            raise DerivAPIError(f"Failed to get a connection OTP for {account_id} "
                                 f"({resp.status_code}): {resp.text}")
        return resp.json()["data"]["url"]

    # ---- connection lifecycle -------------------------------------------------

    async def connect(self, account_id: Optional[str] = None):
        if account_id:
            accounts = await self.list_accounts()
            match = next((a for a in accounts if a["account_id"] == account_id), None)
            if not match:
                raise DerivAPIError(f"Account {account_id} not found for this token.")
            self.account_info = {
                "loginid": match["account_id"],
                "is_virtual": match.get("account_type") == "demo",
                "currency": match.get("currency", "USD"),
                "balance": match.get("balance"),
            }
            url = await self._get_otp_ws_url(account_id)
        else:
            url = PUBLIC_WS_URL

        self.ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
        self._listener_task = asyncio.create_task(self._listen())

    async def close(self):
        if self._listener_task:
            self._listener_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _listen(self):
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

    # ---- historical data (public — no auth needed) ---------------------

    async def ticks_history(self, symbol: str, count: int = 5000, style: str = "ticks") -> list[dict]:
        resp = await self._send({
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "start": 1,
            "style": style,
        })
        if style == "candles":
            return resp.get("candles", [])
        history = resp.get("history", {})
        prices = history.get("prices", [])
        times = history.get("times", [])
        return [{"epoch": t, "price": p} for t, p in zip(times, prices)]

    # ---- live streaming (public) -----------------------------------------

    async def subscribe_ticks(self, symbol: str) -> AsyncIterator[dict]:
        await self._send({"ticks": symbol, "subscribe": 1})
        queue: asyncio.Queue = asyncio.Queue()
        self._tick_subscribers.setdefault(symbol, []).append(queue)
        try:
            while True:
                tick = await queue.get()
                yield tick
        finally:
            self._tick_subscribers[symbol].remove(queue)

    # ---- trading (requires connect(account_id=...)) -----------------------

    async def proposal(self, symbol: str, contract_type: str, stake: float,
                        duration: int = 5, duration_unit: str = "t") -> dict:
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
        resp = await self._send({"buy": proposal_id, "price": price})
        return resp.get("buy", {})

    async def sell_contract(self, contract_id: int, price: float = 0) -> dict:
        resp = await self._send({"sell": contract_id, "price": price})
        return resp.get("sell", {})

    async def check_open_contract(self, contract_id: int) -> dict:
        """One-shot check on a contract's current status. Once resolved,
        the response includes is_sold=1 and a final profit figure. Same
        message shape as the pre-migration API — not yet confirmed with a
        real trade the way balance/ticks_history were, so treat results
        here with the same caution until verified live."""
        resp = await self._send({"proposal_open_contract": 1, "contract_id": contract_id})
        return resp.get("proposal_open_contract", {})

    async def balance(self) -> dict:
        resp = await self._send({"balance": 1})
        return resp.get("balance", {})
