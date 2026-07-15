"""
Centralized settings. Everything sensitive comes from the environment —
nothing here is ever hardcoded, and nothing here should ever be logged.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deriv_app_id: str = "1089"
    # The WebSocket trading API (ws.derivws.com) still expects the older
    # numeric "legacy" app_id in its connection URL — this is DIFFERENT
    # from the OAuth client_id used for the auth.deriv.com PKCE flow below.
    # Deriv's own docs: "app_id: Your legacy app ID... include this only
    # if you also maintain a legacy API app." The shared default (1089)
    # works for the WS connection regardless of which OAuth client_id your
    # own app was issued.
    deriv_legacy_app_id: str = "1089"
    deriv_api_token: str = ""
    deriv_account_mode: str = "demo"  # "demo" | "real"
    deriv_ws_url: str = "wss://ws.derivws.com/websockets/v3"
    deriv_oauth_url: str = "https://oauth.deriv.com/oauth2/authorize"
    # Must exactly match a Redirect URI registered for this app at
    # https://developers.deriv.com — Deriv rejects the OAuth flow otherwise.
    # Deriv does not allow localhost redirect URLs, so this needs to be a
    # real HTTPS URL even during early testing (see README "Deployment").
    deriv_redirect_uri: str = "https://your-frontend-domain.example/oauth/callback"

    # Comma-separated list of frontend origins allowed to call this API.
    # Set this in your host's env vars — no code edit needed per deploy.
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    database_url: str = "sqlite:///./pulse.db"
    secret_key: str = "changeme"
    token_encryption_key: str = ""

    # Safety rails — deliberately hardcoded, not env-overridable, so a bot
    # can't accidentally skip the forced demo period via config.
    forced_demo_hours: int = 24
    martingale_max_doublings: int = 4
    martingale_absolute_stake_cap: float = 500.0


settings = Settings()
