"""
Database models. Deriv tokens are stored encrypted (Fernet, symmetric) —
never in plaintext, never logged. Passwords are bcrypt-hashed.
"""
import datetime as dt

from cryptography.fernet import Fernet
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                         String, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

_fernet = Fernet(settings.token_encryption_key) if settings.token_encryption_key else None


def encrypt_token(raw_token: str) -> str:
    if not _fernet:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY not set — refusing to store a token unencrypted.")
    return _fernet.encrypt(raw_token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    if not _fernet:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY not set — cannot decrypt.")
    return _fernet.decrypt(encrypted_token.encode()).decode()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    # Legacy manual-signup path (still usable via /docs, not shown in the UI
    # anymore now that Deriv OAuth is the primary login).
    username = Column(String, unique=True, nullable=True, index=True)
    hashed_password = Column(String, nullable=True)
    deriv_token_encrypted = Column(String, nullable=True)  # legacy single-token field

    # Deriv OAuth identity + per-account-type tokens. Deriv can hand back
    # several accounts (usually one demo + one or more real) in a single
    # OAuth approval; we keep the demo and the primary real token
    # separately so bots can be pointed at either explicitly.
    deriv_loginid = Column(String, unique=True, nullable=True, index=True)
    deriv_demo_loginid = Column(String, nullable=True)
    deriv_demo_token_encrypted = Column(String, nullable=True)
    deriv_real_loginid = Column(String, nullable=True)
    deriv_real_token_encrypted = Column(String, nullable=True)
    deriv_currency = Column(String, nullable=True)

    created_at = Column(DateTime, default=dt.datetime.utcnow)

    bots = relationship("Bot", back_populates="owner", cascade="all, delete-orphan")

    def token_for_mode(self, mode: str) -> str | None:
        """mode: 'demo' | 'real'. Falls back to the legacy single token
        field if the OAuth-specific fields aren't populated (manual-token
        users)."""
        if mode == "real" and self.deriv_real_token_encrypted:
            return self.deriv_real_token_encrypted
        if mode == "demo" and self.deriv_demo_token_encrypted:
            return self.deriv_demo_token_encrypted
        return self.deriv_token_encrypted


class Bot(Base):
    __tablename__ = "bots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    strategy = Column(String, nullable=False)  # mean_reversion | trend_following | candlestick_indicator | martingale
    asset = Column(String, nullable=False)     # e.g. R_100, 1HZ100V, BOOM1000
    stake = Column(Float, nullable=False, default=1.0)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    max_daily_loss = Column(Float, nullable=True)
    status = Column(String, default="stopped")  # stopped | demo_running | real_running | paused
    account_mode = Column(String, default="demo")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    demo_started_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="bots")
    trades = relationship("Trade", back_populates="bot", cascade="all, delete-orphan")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    bot_id = Column(Integer, ForeignKey("bots.id"), nullable=False)
    symbol = Column(String, nullable=False)
    trade_type = Column(String, nullable=False)  # CALL | PUT
    stake = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    profit_loss = Column(Float, nullable=True)
    is_demo = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=dt.datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    bot = relationship("Bot", back_populates="trades")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
