"""
Deriv OAuth2 login flow.

Flow:
  1. Frontend sends the user's browser to the URL from build_authorize_url().
  2. User logs in on Deriv's own site and approves your app.
  3. Deriv redirects the browser back to DERIV_REDIRECT_URI with query
     params describing every account the user approved access to, e.g.:
       ?acct1=CR900000&token1=a1-xxxx&cur1=USD
        &acct2=VRTC900000&token2=a1-yyyy&cur2=USD
     (One pair per account; count varies by user — could be just a demo,
     could be several real accounts across currencies.)
  4. Frontend hands that raw query string to POST /auth/deriv/callback,
     which is what parse_callback_accounts() below is for.

NOTE: this is implemented against Deriv's documented OAuth2 contract. If
Deriv has changed parameter names since, parse_callback_accounts() is the
one place to adjust — it's deliberately tolerant (regex over acct/token/cur
prefixes) rather than hardcoding an exact account count.
"""
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode

from app.config import settings


@dataclass
class DerivAccount:
    loginid: str
    token: str
    currency: str

    @property
    def is_demo(self) -> bool:
        # Deriv's demo/virtual accounts use these loginid prefixes.
        return self.loginid.upper().startswith(("VRTC", "VRW"))


def build_authorize_url() -> str:
    params = {
        "app_id": settings.deriv_app_id,
        "l": "en",
        "redirect_uri": settings.deriv_redirect_uri,
    }
    return f"{settings.deriv_oauth_url}?{urlencode(params)}"


def parse_callback_accounts(query_string: str) -> list[DerivAccount]:
    """query_string is everything after the '?' in the callback URL, e.g.
    'acct1=CR900000&token1=a1-xxxx&cur1=USD&acct2=VRTC900000&token2=...'."""
    params = parse_qs(query_string.lstrip("?"))
    flat = {k: v[0] for k, v in params.items() if v}

    indices = sorted({
        int(m.group(1))
        for key in flat
        if (m := re.match(r"^acct(\d+)$", key))
    })

    accounts = []
    for i in indices:
        loginid = flat.get(f"acct{i}")
        token = flat.get(f"token{i}")
        currency = flat.get(f"cur{i}", "USD")
        if loginid and token:
            accounts.append(DerivAccount(loginid=loginid, token=token, currency=currency))
    return accounts


def pick_primary_accounts(accounts: list[DerivAccount]) -> tuple[DerivAccount | None, DerivAccount | None]:
    """Returns (demo_account, real_account) — first of each kind found."""
    demo = next((a for a in accounts if a.is_demo), None)
    real = next((a for a in accounts if not a.is_demo), None)
    return demo, real
