"""
Supabase OAuth credential helpers for Alpaca accounts.

Data model used by this module:
1. strategies table:
    Holds strategy rows; used here only to discover unique (acctname, account)
    pairs that need credentials.
2. account_type table:
    Maps each (acctname, account) pair to db_alpaca_account.
3. alpaca_oauth_tokens table:
    Stores OAuth bearer tokens keyed by alpaca_account.

This module resolves credentials through the 3-table chain and then verifies
those credentials against Alpaca PAPER/LIVE account endpoints.
"""

import os
from pathlib import Path

import requests

HERE = Path(__file__).resolve()

# ── Supabase helpers ──────────────────────────────────────────────────────────


# Parse a local .env file into a dictionary of string key/value settings.
def _load_env() -> dict[str, str]:
    """Load key-value pairs from a local .env file into a dictionary."""
    env_path = os.path.join(
        os.path.dirname(HERE), ".env"
    )  # Full path to the local .env file.
    result: dict[str, str] = {}  # Parsed environment key-value mapping.
    if not os.path.exists(env_path):
        return result  # Early return with empty mapping when .env is missing.
    with open(env_path) as fh:  # File handle used to iterate through .env lines.
        for line in fh:  # Raw line string read from .env.
            line = (
                line.strip()
            )  # Normalized line without surrounding whitespace/newline.
            if not line or line.startswith("#"):
                continue  # Skip empty/comment lines.
            if "=" in line:
                k, _, v = line.partition(
                    "="
                )  # Parsed key, separator, and value substrings.
                result[k.strip()] = (
                    v.strip()
                )  # Store normalized key/value in output mapping.
    return result


# Resolve OAuth credentials by walking strategies -> account_type -> alpaca_oauth_tokens.
def _load_oauth_credentials(supabase_url: str, supabase_key: str) -> list[dict]:
    """Load OAuth bearer tokens using the 3-step chain:

      1. strategies                          → unique (acctname, account) pairs
      2. account_type                        → db_alpaca_account  (case-insensitive match)
      3. alpaca_oauth_tokens                 → id, uuid     (keyed by alpaca_account = db_alpaca_account)

    Args:
        supabase_url: Base URL for the Supabase project REST API.
        supabase_key: Supabase API key used for authenticated REST requests.

    Returns a list of dicts:
        {acctname, account, acct_number, token_id, oauth_token}
    """
    sb_headers = {  # HTTP headers required by Supabase REST.
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    # ── Step 1: strategies → collect unique (acctname, account) pairs ────────
    try:
        resp = requests.get(  # HTTP response object for strategies query.
            f"{supabase_url}/rest/v1/strategies",
            headers=sb_headers,
            params={"select": "acctname,account"},
            timeout=10,
        )
        resp.raise_for_status()
        strat_rows = resp.json()  # List of rows from strategies table.
    except requests.RequestException as e:
        print(f"❌  strategies query failed: {e}")
        return []

    if not strat_rows:
        print("⚠️   No rows found in strategies table")
        return []

    # Deduplicate; skip null/empty entries
    seen: set[tuple[str, str]] = set()  # Lowercased pair keys already processed.
    pairs: list[tuple[str, str]] = []  # Unique original-case (acctname, account) pairs.
    for row in strat_rows:  # One strategies row dictionary.
        acctname = (
            row.get("acctname") or ""
        ).strip()  # Account owner name/email field.
        account = (
            row.get("account") or ""
        ).strip()  # Account slot label (for example p1/p2/p3).
        if (
            not acctname
            or not account
            or acctname.lower() == "null"
            or account.lower() == "null"
        ):
            continue
        key = (
            acctname.lower(),
            account.lower(),
        )  # Case-insensitive dedupe key for this pair.
        if key not in seen:
            seen.add(key)
            pairs.append(
                (acctname, account)
            )  # Preserve original pair for downstream queries.

    if not pairs:
        print("⚠️   No valid (acctname, account) pairs found in strategies")
        return []

    credentials: list[dict] = []  # Final credential records to return.

    for acctname, account in pairs:

        # ── Step 2: account_type → db_alpaca_account (case-insensitive) ──────────
        try:
            resp = requests.get(  # HTTP response object for account_type lookup.
                f"{supabase_url}/rest/v1/account_type",
                headers=sb_headers,
                params={
                    "acctname": f"ilike.{acctname}",
                    "account": f"ilike.{account}",
                    "select": "db_alpaca_account",
                    "limit": "1",
                },
                timeout=10,
            )
            resp.raise_for_status()
            aa_rows = (
                resp.json()
            )  # account_type rows for the current (acctname, account).
        except requests.RequestException as e:
            print(
                f"⚠️   account_type query failed for acctname={acctname} account={account}: {e}"
            )
            continue

        if not aa_rows:
            print(f"⚠️   No account_type row for acctname={acctname} account={account}")
            continue

        acct_number = (
            aa_rows[0].get("db_alpaca_account") or ""
        ).strip()  # Mapped alpaca account identifier.
        if not acct_number:
            print(f"⚠️   Empty acct_number for acctname={acctname} account={account}")
            continue

        # ── Step 3: alpaca_oauth_tokens → id + uuid (oauth_token) ────────────
        try:
            resp = requests.get(  # HTTP response object for token lookup.
                f"{supabase_url}/rest/v1/alpaca_oauth_tokens",
                headers=sb_headers,
                params={
                    "alpaca_account": f"eq.{acct_number}",
                    "select": "id,oauth_token",
                    "limit": "1",
                },
                timeout=10,
            )
            resp.raise_for_status()
            tok_rows = resp.json()  # OAuth token rows for the mapped alpaca account.
        except requests.RequestException as e:
            print(
                f"⚠️   alpaca_oauth_tokens query failed for acct_number={acct_number}: {e}"
            )
            continue

        if not tok_rows:
            print(f"⚠️   No alpaca_oauth_tokens row for alpaca_account={acct_number}")
            continue

        token_id = tok_rows[0].get("id")  # Database row id for the oauth token record.
        oauth_token = (
            tok_rows[0].get("oauth_token") or ""
        ).strip()  # Bearer token used with Alpaca API.
        if not oauth_token:
            print(
                f"⚠️   Empty oauth_token for acct_number={acct_number} (id={token_id})"
            )
            continue

        credentials.append(  # Append one resolved credential record.
            {
                "acctname": acctname,  # Human/account owner name from strategies.
                "account": account,  # Account slot (p1/p2/p3 style label).
                "acct_number": acct_number,  # Canonical Alpaca account identifier.
                "token_id": token_id,  # Internal Supabase token record identifier.
                "oauth_token": oauth_token,  # OAuth bearer token for Alpaca REST auth.
            }
        )

    return credentials


def _load_oauth_credentials_for_account(
    supabase_url: str,
    supabase_key: str,
    acctname: str,
    account: str,
) -> dict | None:
    """Load one OAuth credential record for a specific (acctname, account) pair."""
    acctname = (acctname or "").strip()
    account = (account or "").strip()
    if not supabase_url or not supabase_key or not acctname or not account:
        return None

    sb_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/account_type",
            headers=sb_headers,
            params={
                "acctname": f"ilike.{acctname}",
                "account": f"ilike.{account}",
                "select": "db_alpaca_account",
                "limit": "1",
            },
            timeout=10,
        )
        resp.raise_for_status()
        aa_rows = resp.json()
    except requests.RequestException:
        return None

    if not aa_rows:
        return None

    acct_number = (aa_rows[0].get("db_alpaca_account") or "").strip()
    if not acct_number:
        return None

    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/alpaca_oauth_tokens",
            headers=sb_headers,
            params={
                "alpaca_account": f"eq.{acct_number}",
                "select": "id,oauth_token",
                "limit": "1",
            },
            timeout=10,
        )
        resp.raise_for_status()
        tok_rows = resp.json()
    except requests.RequestException:
        return None

    if not tok_rows:
        return None

    token_id = tok_rows[0].get("id")
    oauth_token = (tok_rows[0].get("oauth_token") or "").strip()
    if not oauth_token:
        return None

    return {
        "acctname": acctname,
        "account": account,
        "acct_number": acct_number,
        "token_id": token_id,
        "oauth_token": oauth_token,
    }


def _load_oauth_trade_credentials_for_account(
    supabase_url: str,
    supabase_key: str,
    acctname: str,
    account: str,
    data_key: str,
    data_secret: str,
) -> tuple[str, str, str, str] | None:
    """Load trade OAuth credentials as (trade_key, trade_secret, data_key, data_secret)."""
    acctname = (acctname or "").strip()
    account = (account or "").strip()
    if not supabase_url or not supabase_key or not acctname or not account:
        return None

    acctname_candidates = [acctname]
    if "@" in acctname:
        acctname_candidates.append(acctname.split("@", 1)[0].strip())

    seen: set[str] = set()
    for acctname_candidate in acctname_candidates:
        candidate_l = acctname_candidate.lower()
        if not acctname_candidate or candidate_l in seen:
            continue
        seen.add(candidate_l)

        credential = _load_oauth_credentials_for_account(
            supabase_url,
            supabase_key,
            acctname_candidate,
            account,
        )
        if credential is None:
            continue

        oauth_token = str(credential.get("oauth_token", "")).strip()
        if oauth_token:
            return oauth_token, "", data_key, data_secret

    return None


def _load_alpaca_keys_for_account(
    supabase_url: str,
    supabase_key: str,
    acctname: str,
    account: str,
) -> dict | None:
    """Load one Alpaca key/secret credential record for a specific (acctname, account) pair."""
    acctname = (acctname or "").strip()
    account = (account or "").strip().lower()
    if not supabase_url or not supabase_key or not acctname or not account:
        return None

    if account not in {"p1", "p2", "p3"}:
        return None

    key_col = f"apikey{account}"
    secret_col = f"apisecret{account}"

    sb_headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    acctname_candidates = [acctname]
    if "@" in acctname:
        acctname_candidates.append(acctname.split("@", 1)[0].strip())

    seen: set[str] = set()
    for acctname_candidate in acctname_candidates:
        candidate_l = acctname_candidate.lower()
        if not acctname_candidate or candidate_l in seen:
            continue
        seen.add(candidate_l)

        try:
            resp = requests.get(
                f"{supabase_url}/rest/v1/alpaca",
                headers=sb_headers,
                params={
                    "acctname": f"ilike.{acctname_candidate}",
                    "select": f"acctname,{key_col},{secret_col},dataapikey,apiDataKey,datakey,datasecret,apiDataSecret,data_secret",
                    "limit": "1",
                },
                timeout=10,
            )
            resp.raise_for_status()
            rows = resp.json()
        except requests.RequestException:
            return None

        if not rows:
            continue

        row = rows[0]
        trade_key = (row.get(key_col) or "").strip()
        trade_secret = (row.get(secret_col) or "").strip()
        if not trade_key or not trade_secret:
            continue

        data_key = (
            (row.get("dataapikey") or row.get("apiDataKey") or row.get("datakey") or "").strip()
        )
        data_secret = (
            (row.get("datasecret") or row.get("apiDataSecret") or row.get("data_secret") or "").strip()
        )
        if not data_key or not data_secret:
            data_key = trade_key
            data_secret = trade_secret

        return {
            "acctname": row.get("acctname") or acctname_candidate,
            "account": account,
            "trade_key": trade_key,
            "trade_secret": trade_secret,
            "data_key": data_key,
            "data_secret": data_secret,
        }

    return None


def _load_alpaca_key_credentials_for_account(
    supabase_url: str,
    supabase_key: str,
    acctname: str,
    account: str,
) -> tuple[str, str, str, str] | None:
    """Load trade/data key credentials as (trade_key, trade_secret, data_key, data_secret)."""
    credential = _load_alpaca_keys_for_account(
        supabase_url,
        supabase_key,
        acctname,
        account,
    )
    if credential is None:
        return None

    trade_key = str(credential.get("trade_key", "")).strip()
    trade_secret = str(credential.get("trade_secret", "")).strip()
    data_key = str(credential.get("data_key", "")).strip()
    data_secret = str(credential.get("data_secret", "")).strip()

    if not trade_key or not trade_secret:
        return None
    if not data_key or not data_secret:
        data_key = trade_key
        data_secret = trade_secret

    return trade_key, trade_secret, data_key, data_secret


# Validate each resolved OAuth token against Alpaca PAPER/LIVE account endpoints.
def _test_credentials(credentials: list[dict]) -> None:
    """
    Verify each OAuth token by hitting Alpaca /v2/account endpoints.

    Args:
        credentials: List of credential dictionaries returned by
            _load_oauth_credentials.
    """
    PAPER_BASE = "https://paper-api.alpaca.markets"  # Alpaca paper trading base URL.
    LIVE_BASE = "https://api.alpaca.markets"  # Alpaca live trading base URL.

    print(f"\n{'='*60}")
    print(f"  Credential test — {len(credentials)} account(s)")
    print(f"{'='*60}")

    for cred in credentials:  # One credential record to validate.
        acct = cred["acct_number"]  # Canonical Alpaca account number for display.
        token = cred["oauth_token"]  # OAuth bearer token used for authentication.
        label = f"{cred['acctname']} / {cred['account']} ({acct})"  # Human-readable account label.

        # Try paper first, then live
        for base_url, env_label in ((PAPER_BASE, "PAPER"), (LIVE_BASE, "LIVE")):
            try:
                r = requests.get(  # HTTP response for the current environment check.
                    f"{base_url}/v2/account",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "content-type": "application/json",
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()  # Parsed account payload from Alpaca.
                    equity = data.get("equity", "?")  # Current account equity value.
                    status = data.get("status", "?")  # Account status string.
                    print(
                        f"  ✅  {label}  [{env_label}]  equity={equity}  status={status}"
                    )
                    break
                elif r.status_code == 401:
                    continue  # try next environment
                else:
                    print(f"  ⚠️   {label}  [{env_label}]  HTTP {r.status_code}")
                    break
            except requests.RequestException as e:
                print(f"  ❌  {label}  [{env_label}]  {e}")
                break
        else:
            print(f"  ❌  {label}  — token rejected by both PAPER and LIVE endpoints")

    print(f"{'='*60}\n")
