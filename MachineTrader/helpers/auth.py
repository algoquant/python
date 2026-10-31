"""Credential bootstrap utilities for AlpacaSDK scripts."""

import os

from dotenv import load_dotenv

try:
    from supabase_fun import (
        _load_alpaca_key_credentials_for_account,
        _load_oauth_trade_credentials_for_account,
    )
except ModuleNotFoundError:
    def _load_alpaca_key_credentials_for_account(*_args, **_kwargs):
        return None

    def _load_oauth_trade_credentials_for_account(*_args, **_kwargs):
        return None


class AccountAuth:
    """Load local env values and resolve Alpaca credentials with Supabase fallback."""

    def __init__(self, env_file=None):
        self.env_file = env_file
        self.credential_source = None
        self.refresh()

    def refresh(self):
        """Reload env values into instance attributes."""
        if self.env_file:
            load_dotenv(self.env_file)
        else:
            load_dotenv()

        self.acctname = (os.getenv("ACCTNAME") or "").strip()
        self.account = (os.getenv("ACCOUNT") or "").strip()
        self.supabase_url = os.getenv("SUPABASE_URL", "")
        self.supabase_key = os.getenv("SUPABASE_KEY", "")
        self.trade_key = (os.getenv("ALPACA_TRADE_KEY") or "").strip()
        self.trade_secret = (os.getenv("ALPACA_TRADE_SECRET") or "").strip()
        self.data_key = (os.getenv("DATA_KEY") or os.getenv("ALPACA_DATA_KEY") or "").strip()
        self.data_secret = (os.getenv("DATA_SECRET") or os.getenv("ALPACA_DATA_SECRET") or "").strip()
        return self

    def _set_env(self, trade_key, trade_secret, data_key, data_secret):
        os.environ["ALPACA_TRADE_KEY"] = trade_key or ""
        os.environ["ALPACA_TRADE_SECRET"] = trade_secret or ""
        os.environ["DATA_KEY"] = data_key or ""
        os.environ["DATA_SECRET"] = data_secret or ""

    def resolve_data_credentials(self):
        """Resolve data keys from .env, with trade-key or Supabase fallback when needed."""
        self.refresh()

        data_key = self.data_key
        data_secret = self.data_secret
        trade_key = self.trade_key
        trade_secret = self.trade_secret

        if not data_key or not data_secret:
            if trade_key and trade_secret:
                data_key = trade_key
                data_secret = trade_secret
                self.credential_source = "local .env"
            elif self.supabase_url and self.supabase_key and self.acctname and self.account:
                creds = _load_alpaca_key_credentials_for_account(
                    self.supabase_url,
                    self.supabase_key,
                    self.acctname,
                    self.account,
                )
                if creds is not None:
                    trade_key, trade_secret, data_key, data_secret = creds
                    self.credential_source = "Supabase fallback"
                else:
                    self.credential_source = "local .env"
            else:
                self.credential_source = "local .env"

        self._set_env(trade_key, trade_secret, data_key, data_secret)
        self.data_key = data_key
        self.data_secret = data_secret
        if trade_key:
            self.trade_key = trade_key
        if trade_secret:
            self.trade_secret = trade_secret
        return data_key, data_secret

    def resolve_trade_credentials(self):
        """Resolve trade OAuth credentials, falling back to Supabase when needed."""
        self.refresh()

        trade_key = self.trade_key
        trade_secret = self.trade_secret
        data_key = self.data_key
        data_secret = self.data_secret

        if not (trade_key and trade_secret):
            creds = _load_oauth_trade_credentials_for_account(
                self.supabase_url,
                self.supabase_key,
                self.acctname,
                self.account,
                data_key,
                data_secret,
            )
            if creds is not None:
                trade_key, trade_secret, data_key, data_secret = creds
                self.credential_source = "Supabase fallback"
            else:
                self.credential_source = "local .env"
        else:
            self.credential_source = "local .env"

        self._set_env(trade_key, trade_secret, data_key, data_secret)

        if not trade_key:
            raise ValueError(
                "Missing trading credentials: .env ALPACA_TRADE_KEY/ALPACA_TRADE_SECRET not set and Supabase lookup failed. "
                "Ensure .env defines ACCTNAME and ACCOUNT (plus SUPABASE_URL and SUPABASE_KEY). "
                f"Current acctname={self.acctname or '<empty>'} account={self.account or '<empty>'}"
            )

        self.trade_key = trade_key
        self.trade_secret = trade_secret
        self.data_key = data_key
        self.data_secret = data_secret
        return trade_key, trade_secret, data_key, data_secret

    def resolve_alpaca_credentials(self):
        """Resolve Alpaca key/secret credentials for trading + data access."""
        self.refresh()

        trade_key = self.trade_key
        trade_secret = self.trade_secret
        data_key = self.data_key
        data_secret = self.data_secret

        if trade_key and trade_secret:
            if not data_key or not data_secret:
                data_key = trade_key
                data_secret = trade_secret
            self.credential_source = "local .env"
            self._set_env(trade_key, trade_secret, data_key, data_secret)
            self.trade_key = trade_key
            self.trade_secret = trade_secret
            self.data_key = data_key
            self.data_secret = data_secret
            return trade_key, trade_secret, data_key, data_secret

        if not self.supabase_url or not self.supabase_key or not self.acctname or not self.account:
            self.credential_source = "local .env"
            return None

        creds = _load_alpaca_key_credentials_for_account(
            self.supabase_url,
            self.supabase_key,
            self.acctname,
            self.account,
        )
        if creds is None:
            self.credential_source = "Supabase fallback"
            return None

        trade_key, trade_secret, data_key, data_secret = creds
        self.credential_source = "Supabase fallback"
        self._set_env(trade_key, trade_secret, data_key, data_secret)
        self.trade_key = trade_key
        self.trade_secret = trade_secret
        self.data_key = data_key
        self.data_secret = data_secret
        return trade_key, trade_secret, data_key, data_secret
