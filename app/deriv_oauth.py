"""
Deriv OAuth 2.0 — Authorization Code flow with PKCE.

This replaces an earlier implementation built against Deriv's older
implicit-style flow (oauth.deriv.com/oauth2/authorize returning acct#/token#
pairs directly), which Deriv has since retired. Current spec, per
https://developers.deriv.com/docs/intro/oauth:

  1. Generate a PKCE code_verifier + code_challenge (SHA256) and a random
     state, and hold onto the verifier until the token exchange.
  2. Redirect the user to https://auth.deriv.com/oauth2/auth with those
     values plus response_type=code, client_id, redirect_uri, scope.
  3. User logs in / consents on Deriv's own site.
  4. Deriv redirects back to redirect_uri with ?code=...&state=...
  5. Backend exchanges the code (+ original code_verifier) for an
     access_token at https://auth.deriv.com/oauth2/token.
  6. That access_token is usable as a Bearer token for both REST calls and
     as the token passed to the existing WebSocket `authorize` request —
     so the rest of this codebase (DerivClient, bot_engine, backtest) needs
     no changes, only how the token is obtained changes.

PKCE is generated and held server-side here (rather than in the browser via
sessionStorage, which is what Deriv's own docs example shows) — the
verifier never needs to leave the backend, which is simpler for this
architecture and equally secure. State is stored alongside it and used to
correlate the callback back to the right verifier.

NOTE: implemented against the documented spec pulled July 2026. If Deriv's
endpoints or parameter names change again, this is the one file to check.
"""
import base64
import hashlib
import secrets as _secrets
import time
from urllib.parse import urlencode

import httpx

from app.config import settings

AUTH_URL = "https://auth.deriv.com/oauth2/auth"
TOKEN_URL = "https://auth.deriv.com/oauth2/token"

# Short-lived server-side store for PKCE verifiers, keyed by state.
# In-memory is fine for a single backend instance; move to Redis/DB if you
# ever run more than one instance behind a load balancer.
_pending_logins: dict[str, dict] = {}
_PENDING_TTL_SECONDS = 600


def _cleanup_expired():
    now = time.time()
    expired = [k for k, v in _pending_logins.items() if now - v["created_at"] > _PENDING_TTL_SECONDS]
    for k in expired:
        _pending_logins.pop(k, None)


def _generate_pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge)."""
    code_verifier = base64.urlsafe_b64encode(_secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge_bytes = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(challenge_bytes).rstrip(b"=").decode()
    return code_verifier, code_challenge


def build_authorize_url() -> str:
    """Generates fresh PKCE + state, stores the verifier server-side keyed
    by state, and returns the URL the frontend should redirect the browser
    to."""
    _cleanup_expired()

    code_verifier, code_challenge = _generate_pkce_pair()
    state = _secrets.token_hex(16)
    _pending_logins[state] = {"code_verifier": code_verifier, "created_at": time.time()}

    params = {
        "response_type": "code",
        "client_id": settings.deriv_app_id,
        "redirect_uri": settings.deriv_redirect_uri,
        "scope": "trade account_manage",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str, state: str) -> dict:
    """Looks up the stored code_verifier by state and exchanges the
    authorization code for an access token. Raises ValueError on any
    failure (unknown state, expired, or Deriv rejecting the exchange)."""
    _cleanup_expired()
    pending = _pending_logins.pop(state, None)
    if not pending:
        raise ValueError("Login session expired or already used — try Continue with Deriv again.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "client_id": settings.deriv_app_id,
            "code": code,
            "code_verifier": pending["code_verifier"],
            "redirect_uri": settings.deriv_redirect_uri,
        })

    if resp.status_code != 200:
        raise ValueError(f"Deriv token exchange failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    if "access_token" not in data:
        raise ValueError(f"Deriv token exchange returned no access_token: {data}")
    return data
