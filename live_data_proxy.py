"""
Proxy server for the Alpaca WebSocket, using websockets and asyncio. 
It listens for client connections, subscribes to Alpaca's WebSocket, and relays messages to all connected clients.
You need to install in command line: pip3 install websockets aiohttp

How it works:
Client scripts connect to ws://localhost:8765 and receive all the messages from Alpaca's WebSocket.
The proxy authenticates and subscribes to Alpaca's stream, then relays all messages to connected clients.
You can expand this to handle client-specific subscriptions or message filtering.

Note:
Make sure the .env file contains the ALPACA_DATA_KEY and ALPACA_DATA_SECRET.

To stream stock prices through the WebSocket proxy, run the proxy in a terminal and specify the symbols, for example SPY and NVDA:
    python3 live_data_proxy.py SPY NVDA

If DATA_SYMBOLS is set in the env file, symbols can be omitted on the CLI:
    python3 live_data_proxy.py --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Then you can run a streaming script in another terminal:
    python3 stream_bars_single_proxy.py SPY

To load credentials/settings from a specific env file:
    python3 live_data_proxy.py SPY NVDA --env-file /path/to/.env


"""


import asyncio
import argparse
import websockets
import os
import sys
import json
import fcntl
import errno
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

from MachineTrader.helpers.auth import AccountAuth
from MachineTrader.helpers.driver_common import rounded_print as _rounded_print
from MachineTrader.helpers.parse_args import (
    create_data_proxy_arg_parser,
    resolve_symbols_from_env,
)
from MachineTrader.helpers.file_handlers import append_bar_to_symbol_date_csv, append_proxy_error_csv
from MachineTrader.helpers.markets import Markets
from MachineTrader.helpers.live_data import (
    complete_symbol_bar_set,
    event_datetime_ny,
    minute_key_from_datetime,
    resolve_proxy_schedule_from_env,
    proxy_schedule_status,
    proxy_idle_heartbeat_key,
    format_proxy_idle_heartbeat_message,
    next_proxy_start_datetime,
)


DEFAULT_ENV_FILE = Path(__file__).resolve().parent / ".env"


def _parse_args() -> argparse.Namespace:
    parser = create_data_proxy_arg_parser(default_env_file=DEFAULT_ENV_FILE)
    return parser.parse_args()


args = _parse_args()

raw_cli_args = sys.argv[1:]
has_cli_parameters = len(raw_cli_args) > 0
env_file_path = str(args.env_file or "").strip()
env_file_exists = bool(env_file_path) and os.path.exists(env_file_path)

if not has_cli_parameters and not env_file_exists:
    print("[Alpaca Proxy] No CLI parameters provided and no env file was found.")
    print("[Alpaca Proxy] Exiting. Provide symbols on the CLI or create an env file.")
    sys.exit(1)

if env_file_path and not env_file_exists:
    print(f"[Alpaca Proxy] Env file not found: {env_file_path}")
    print("[Alpaca Proxy] Continuing without env file; relying on CLI args and process env vars.")

effective_env_file = env_file_path if env_file_exists else None
env_values = dotenv_values(effective_env_file) if effective_env_file else {}

# Resolve symbols: CLI first, then DATA_SYMBOLS from env file, then STRATEGY_SYMBOL fallback.
if args.symbols:
    symbols = list(args.symbols)
else:
    symbols = []
    if effective_env_file:
        raw_data_symbols = str(env_values.get("DATA_SYMBOLS", "") or "").strip()
        if raw_data_symbols:
            symbols = [
                s.strip().upper()
                for s in raw_data_symbols.replace(",", " ").split()
                if s.strip()
            ]
    if not symbols:
        symbols = resolve_symbols_from_env(effective_env_file)

symbols = [arg.strip().upper() for arg in symbols if str(arg or "").strip()]
if not symbols:
    print(
        "No symbols provided. Supply symbols as CLI arguments or set DATA_SYMBOLS (or STRATEGY_SYMBOL) in the env file. "
        "Example: python3 live_data_proxy.py SPY NVDA"
    )
    sys.exit(1)
print(f"Setting up proxy for: {symbols}")

force_start = bool(args.force)

auth = AccountAuth(env_file=effective_env_file)
creds = auth.resolve_data_credentials()
# Handle both 2-value and 4-value returns from resolve_data_credentials
if isinstance(creds, tuple) and len(creds) >= 2:
    API_KEY, API_SECRET = creds[0], creds[1]
else:
    API_KEY, API_SECRET = creds
print(f"[Alpaca Proxy] Data credential source: {auth.credential_source}")
ALPACA_DATA_FEED = os.getenv("ALPACA_DATA_FEED", "sip").strip().lower()
ALPACA_WS_URL = f"wss://stream.data.alpaca.markets/v2/{ALPACA_DATA_FEED}"
PROXY_HOST = "localhost"
PROXY_PORT = 8765
DATA_DIR_NAME = str(env_values.get("DATA_DIR_NAME", "") or "").strip() or "data"
DATA_DIR_PATH = Path(DATA_DIR_NAME).expanduser()
DATA_DIR_PATH.mkdir(parents=True, exist_ok=True)

clients = set()
HEARTBEAT_INTERVAL = float(os.getenv("ALPACA_PROXY_HEARTBEAT_INTERVAL", "60"))
STALE_WEBSOCKET_SECONDS = float(
    os.getenv("ALPACA_PROXY_STALE_WEBSOCKET_SECONDS", str(max(90.0, HEARTBEAT_INTERVAL * 1.5)))
)
FORCE_RECONNECT_COOLDOWN_SECONDS = float(
    os.getenv("ALPACA_PROXY_FORCE_RECONNECT_COOLDOWN_SECONDS", str(max(120.0, STALE_WEBSOCKET_SECONDS)))
)
UPSTREAM_CONNECT_TIMEOUT_SECONDS = float(os.getenv("ALPACA_PROXY_UPSTREAM_CONNECT_TIMEOUT_SECONDS", "15"))
LOCK_FILE_PATH = os.getenv("ALPACA_PROXY_LOCK_FILE", "/tmp/live_data_proxy.lock")
proxy_lock_file = None
latest_prices = {}
latest_price_updated_at = {}
latest_bars = {}
pending_bar_minute_key = None
pending_bars_by_symbol = {}
last_ws_message_at = None
current_upstream_ws = None
relay_task_handle = None
last_forced_reconnect_at = None
force_reconnect_lock = None
last_idle_heartbeat_key = None
last_schedule_should_run = None
NY_TZ = ZoneInfo("America/New_York")
PROXY_ERROR_DIR = str(env_values.get("LOG_DIR_NAME", "") or os.getenv("LOG_DIR_NAME", "") or "/Users/jerzy/Develop/trading/logs").strip()
PROXY_START_TIME, PROXY_END_TIME = resolve_proxy_schedule_from_env(env_values)
markets = Markets()


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


def _log_proxy_error(message: str) -> None:
    append_proxy_error_csv(message, PROXY_ERROR_DIR, timezone=NY_TZ)


def _optional_float_setting(name: str, default: float | None) -> float | None:
    raw_value = str(env_values.get(name, os.getenv(name, "")) or "").strip()
    if not raw_value:
        return default

    lowered = raw_value.lower()
    if lowered in {"none", "off", "false", "disable", "disabled"}:
        return None

    try:
        parsed = float(raw_value)
    except ValueError:
        return default

    if parsed <= 0.0:
        return None
    return parsed


def _emit_idle_heartbeat_once(now_ny: datetime, schedule_reason: str) -> None:
    global last_idle_heartbeat_key

    resume_at = next_proxy_start_datetime(
        now_ny,
        markets,
        PROXY_START_TIME,
        PROXY_END_TIME,
        timezone=NY_TZ,
    )
    idle_key = proxy_idle_heartbeat_key(now_ny, schedule_reason, PROXY_START_TIME, PROXY_END_TIME)
    if idle_key == last_idle_heartbeat_key:
        return
    last_idle_heartbeat_key = idle_key
    if ":after_end:" in idle_key:
        print("\n=================================================================")
    print(
        format_proxy_idle_heartbeat_message(
            now_ny,
            schedule_reason,
            PROXY_START_TIME,
            PROXY_END_TIME,
            resume_at,
        )
    )


def _clear_idle_heartbeat_state() -> None:
    global last_idle_heartbeat_key
    last_idle_heartbeat_key = None


def _clear_stale_market_data() -> None:
    global last_ws_message_at, pending_bar_minute_key, pending_bars_by_symbol

    last_ws_message_at = None
    pending_bar_minute_key = None
    pending_bars_by_symbol = {}
    latest_prices.clear()
    latest_price_updated_at.clear()
    latest_bars.clear()


def _complete_minute_bars(minute_key: tuple[int, int, int, int, int]) -> list[dict]:
    return complete_symbol_bar_set(
        pending_bars_by_symbol,
        latest_bars,
        symbols,
        minute_key,
        timezone=NY_TZ,
    )


def _append_completed_bars_to_csv(events: list[dict]) -> None:
    for event in events:
        append_bar_to_symbol_date_csv(
            event,
            DATA_DIR_PATH,
            fallback_tz=NY_TZ,
            date_format="%Y%m%d",
        )


def _flush_pending_completed_minute() -> str | None:
    global pending_bar_minute_key, pending_bars_by_symbol
    if pending_bar_minute_key is None:
        return None

    completed = _complete_minute_bars(pending_bar_minute_key)
    if not completed:
        pending_bar_minute_key = None
        pending_bar_minute_time = None
        pending_bars_by_symbol = {}
        return None

    # Always clear pending state even on failure so one bad bar can't wedge the pipeline forever.
    try:
        _append_completed_bars_to_csv(completed)
        payload = json.dumps(completed, default=str)
    except Exception as exc:
        print(f"[Alpaca Proxy] Failed to flush completed minute bars: {exc}")
        payload = None
    finally:
        pending_bar_minute_key = None
        pending_bars_by_symbol = {}
    return payload


def _record_bar_event(event: dict) -> list[str]:
    global pending_bar_minute_key, pending_bars_by_symbol

    symbol = str(event.get("S", "") or "").strip().upper()
    if not symbol or symbol not in symbols:
        return []

    bar_time_ny = event_datetime_ny(event, wall_time_ny=datetime.now(NY_TZ), timezone=NY_TZ)
    minute_key = minute_key_from_datetime(bar_time_ny, timezone=NY_TZ)
    payloads: list[str] = []

    if pending_bar_minute_key is not None and minute_key != pending_bar_minute_key:
        payload = _flush_pending_completed_minute()
        if payload is not None:
            payloads.append(payload)

    if pending_bar_minute_key is None:
        pending_bar_minute_key = minute_key
        pending_bars_by_symbol = {}

    event = dict(event)
    event["S"] = symbol
    pending_bars_by_symbol[symbol] = event
    latest_bars[symbol] = event

    close_price = event.get("c")
    if close_price is not None:
        latest_prices[symbol] = float(close_price)
        latest_price_updated_at[symbol] = datetime.now(NY_TZ)

    if set(pending_bars_by_symbol) >= set(symbols):
        payload = _flush_pending_completed_minute()
        if payload is not None:
            payloads.append(payload)

    return payloads


def _record_bar_events_from_message(msg: str) -> list[str]:
    parsed = json.loads(msg)
    events = parsed if isinstance(parsed, list) else [parsed]
    payloads: list[str] = []
    for event in events:
        if isinstance(event, dict) and event.get("T") == "b":
            payloads.extend(_record_bar_event(event))
    return payloads


def _broadcast_completed_payloads(payloads: list[str]) -> None:
    for payload in payloads:
        websockets.broadcast(clients, payload)


def _flush_and_broadcast_pending_completed_minute() -> None:
    payload = _flush_pending_completed_minute()
    if payload is not None:
        websockets.broadcast(clients, payload)


# --------- Define the Alpaca WebSocket proxy server --------

async def websocket_handler(websocket, path=None):
    clients.add(websocket)
    try:
        # Downstream clients are receive-only for this proxy.
        # Wait until they disconnect instead of reading messages.
        await websocket.wait_closed()
    except websockets.ConnectionClosedOK:
        pass
    except websockets.ConnectionClosedError as exc:
        # Common disconnect path (for example, client timeout/termination).
        print(f"[Alpaca Proxy] Downstream client disconnected: {exc}")
    except asyncio.TimeoutError:
        print("[Alpaca Proxy] Downstream close timed out; disconnecting client.")
    finally:
        clients.discard(websocket)


# --------- Define the Alpaca WebSocket proxy server startup function --------

async def relay_alpaca_stream():
    global last_ws_message_at, current_upstream_ws

    if not API_KEY or not API_SECRET:
        print("[Alpaca Proxy] Missing API credentials.")
        print("[Alpaca Proxy] Set one of: API_KEY or APCA_API_KEY_ID")
        print("[Alpaca Proxy] Set one of: API_SECRET or APCA_API_SECRET_KEY")
        _log_proxy_error("Missing API credentials")
        return

    reconnect_delay = 5  # seconds
    while True:
        now_ny = datetime.now(NY_TZ)
        should_run_now, schedule_reason = proxy_schedule_status(
            now_ny,
            markets,
            PROXY_START_TIME,
            PROXY_END_TIME,
        )
        if not should_run_now:
            _emit_idle_heartbeat_once(now_ny, schedule_reason)
            resume_at = next_proxy_start_datetime(
                now_ny,
                markets,
                PROXY_START_TIME,
                PROXY_END_TIME,
                timezone=NY_TZ,
            )
            sleep_seconds = min(
                max(5.0, (resume_at - now_ny).total_seconds()),
                max(5.0, HEARTBEAT_INTERVAL),
            )
            await asyncio.sleep(sleep_seconds)
            continue

        _clear_idle_heartbeat_state()

        try:
            # Bound the handshake itself: after sleep/wake or network changes it can hang forever with no exception.
            alpaca_ws_cm = await asyncio.wait_for(websockets.connect(ALPACA_WS_URL), timeout=UPSTREAM_CONNECT_TIMEOUT_SECONDS)
            async with alpaca_ws_cm as alpaca_ws:
                current_upstream_ws = alpaca_ws
                try:
                    # The server sends an unsolicited "connected" banner before any auth reply.
                    connected_resp = await asyncio.wait_for(alpaca_ws.recv(), timeout=10)
                    last_ws_message_at = datetime.now(NY_TZ)
                    print(f"[Alpaca Proxy] Connect response: {connected_resp}")

                    # Authenticate
                    auth_msg = {
                        "action": "auth",
                        "key": API_KEY,
                        "secret": API_SECRET
                    }
                    await alpaca_ws.send(json.dumps(auth_msg))

                    auth_resp = await asyncio.wait_for(alpaca_ws.recv(), timeout=10)
                    last_ws_message_at = datetime.now(NY_TZ)
                    print(f"[Alpaca Proxy] Auth response: {auth_resp}")
                    parsed_auth = json.loads(auth_resp)
                    if isinstance(parsed_auth, list) and parsed_auth:
                        first = parsed_auth[0]
                        if first.get("T") == "error" and first.get("code") == 402:
                            print("[Alpaca Proxy] Authentication failed (402). Check key/secret and account permissions.")
                            return

                    # Subscribe to bar data only; the proxy relays bars to downstream consumers.
                    sub_msg = {
                        "action": "subscribe",
                        "bars": symbols
                    }
                    await alpaca_ws.send(json.dumps(sub_msg))

                    sub_resp = await asyncio.wait_for(alpaca_ws.recv(), timeout=10)
                    last_ws_message_at = datetime.now(NY_TZ)
                    print(f"[Alpaca Proxy] Subscription response: {sub_resp}")
                    parsed_sub = json.loads(sub_resp)
                    if isinstance(parsed_sub, list) and parsed_sub:
                        first = parsed_sub[0]
                        if first.get("T") == "error" and first.get("code") == 402:
                            print("[Alpaca Proxy] Subscription failed with 402 auth error. Verify credentials and selected feed.")
                            return
                        if first.get("T") == "error" and first.get("code") == 406:
                            print("[Alpaca Proxy] Subscription failed with 406 connection limit exceeded. Reduce symbols or close other Alpaca data connections.")
                            return
                        if first.get("T") == "subscription":
                            subscribed_bars = set(first.get("bars", []) or [])
                            missing_bars = sorted(set(symbols) - subscribed_bars)
                            if missing_bars:
                                print(
                                    "[Alpaca Proxy] WARNING: Alpaca did not confirm bar subscription for "
                                    f"{missing_bars}. These symbols will never receive price bars."
                                )
                                _log_proxy_error(f"Bar subscription not confirmed for symbols: {missing_bars}")

                    while True:
                        now_ny = datetime.now(NY_TZ)
                        should_run_now, schedule_reason = proxy_schedule_status(
                            now_ny,
                            markets,
                            PROXY_START_TIME,
                            PROXY_END_TIME,
                        )
                        if not should_run_now:
                            _flush_and_broadcast_pending_completed_minute()
                            _emit_idle_heartbeat_once(now_ny, schedule_reason)
                            break

                        try:
                            msg = await asyncio.wait_for(alpaca_ws.recv(), timeout=STALE_WEBSOCKET_SECONDS)
                        except asyncio.TimeoutError:
                            last_seen_text = (
                                last_ws_message_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                                if last_ws_message_at is not None
                                else "never"
                            )
                            print(
                                "[Alpaca Proxy] ERROR: No new websocket data arrived within "
                                f"{STALE_WEBSOCKET_SECONDS:.2f} seconds. "
                                f"Last message at {last_seen_text}. Resetting websocket connection."
                            )
                            _log_proxy_error(
                                "No new websocket data arrived within "
                                f"{STALE_WEBSOCKET_SECONDS:.2f} seconds; last message at {last_seen_text}."
                            )
                            _flush_and_broadcast_pending_completed_minute()
                            break

                        last_ws_message_at = datetime.now(NY_TZ)

                        # Build complete per-minute frames before relaying to clients.
                        try:
                            completed_payloads = _record_bar_events_from_message(msg)
                        except Exception as exc:
                            print(f"[Alpaca Proxy] Skipping malformed bar payload: {exc}")
                            continue

                        _broadcast_completed_payloads(completed_payloads)
                except asyncio.TimeoutError:
                    _flush_and_broadcast_pending_completed_minute()
                    print(f"[Alpaca Proxy] Timed out waiting for auth/subscription response. Reconnecting in {reconnect_delay} seconds...")
                    _log_proxy_error("Timed out waiting for auth/subscription response")
                    await asyncio.sleep(reconnect_delay)
                except websockets.ConnectionClosed as e:
                    _flush_and_broadcast_pending_completed_minute()
                    print(f"[Alpaca Proxy] Connection closed: {e}. Reconnecting in {reconnect_delay} seconds...")
                    _log_proxy_error(f"Connection closed: {e}")
                    await asyncio.sleep(reconnect_delay)
                except Exception as e:
                    _flush_and_broadcast_pending_completed_minute()
                    print(f"[Alpaca Proxy] Error in Alpaca stream: {e}. Reconnecting in {reconnect_delay} seconds...")
                    _log_proxy_error(f"Error in Alpaca stream: {e}")
                    await asyncio.sleep(reconnect_delay)
                finally:
                    current_upstream_ws = None
        except (OSError, websockets.InvalidURI, websockets.InvalidHandshake) as e:
            print(f"[Alpaca Proxy] Connection error: {e}. Retrying in {reconnect_delay} seconds...")
            _log_proxy_error(f"Connection error: {e}")
            await asyncio.sleep(reconnect_delay)

        except asyncio.TimeoutError:
            print(f"[Alpaca Proxy] Upstream connect timed out after {UPSTREAM_CONNECT_TIMEOUT_SECONDS:.2f}s. Retrying in {reconnect_delay} seconds...")
            _log_proxy_error(f"Upstream connect timed out after {UPSTREAM_CONNECT_TIMEOUT_SECONDS:.2f}s")
            await asyncio.sleep(reconnect_delay)

        except KeyboardInterrupt:
            print("[Alpaca Proxy] Relay stopped by user.")
            break


async def force_reset_upstream(reason: str, *, bypass_cooldown: bool = False):
    global last_forced_reconnect_at, relay_task_handle

    if force_reconnect_lock is None:
        return

    async with force_reconnect_lock:
        now_ny = datetime.now(NY_TZ)
        relay_is_dead = relay_task_handle is None or relay_task_handle.done()
        if not bypass_cooldown and not relay_is_dead and last_forced_reconnect_at is not None:
            since_last = (now_ny - last_forced_reconnect_at).total_seconds()
            if since_last < FORCE_RECONNECT_COOLDOWN_SECONDS:
                print(
                    "[Alpaca Proxy] Reconnect skipped due to cooldown. "
                    f"reason={reason} elapsed={since_last:.2f}s cooldown={FORCE_RECONNECT_COOLDOWN_SECONDS:.2f}s"
                )
                return

        last_forced_reconnect_at = now_ny
        print(f"[Alpaca Proxy] Forcing upstream reset. reason={reason}")

        ws = current_upstream_ws
        if ws is not None:
            try:
                await asyncio.wait_for(ws.close(code=1012, reason="stale_data_watchdog"), timeout=5.0)
            except Exception as exc:
                print(f"[Alpaca Proxy] Upstream close error during forced reset: {exc}")

        # Closing the socket may not unblock a relay task wedged in a hung connect(); cancel and restart unconditionally.
        if relay_task_handle is not None and not relay_task_handle.done():
            relay_task_handle.cancel()
            try:
                await relay_task_handle
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                print(f"[Alpaca Proxy] Relay task ended with error during forced cancel: {exc}")
        elif relay_task_handle is not None:
            try:
                relay_task_handle.result()
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                print(f"[Alpaca Proxy] Relay task ended with error: {exc}")

        relay_task_handle = asyncio.create_task(relay_alpaca_stream())
        print("[Alpaca Proxy] Relay task restarted by watchdog.")


def pid_is_running(pid_text):
    try:
        pid = int(pid_text)
    except (TypeError, ValueError):
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as error:
        if error.errno == errno.ESRCH:
            return False
        return True
    return True


def acquire_proxy_lock(force=False):
    global proxy_lock_file

    proxy_lock_file = open(LOCK_FILE_PATH, "w")
    try:
        fcntl.flock(proxy_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        existing_pid = "unknown"
        try:
            with open(LOCK_FILE_PATH, "r") as lock_reader:
                existing_pid = lock_reader.read().strip() or "unknown"
        except OSError:
            pass
        if force and not pid_is_running(existing_pid):
            print(f"[Alpaca Proxy] Stale lock detected for PID {existing_pid}. Breaking lock at {LOCK_FILE_PATH} and continuing.")
            proxy_lock_file.close()
            try:
                os.unlink(LOCK_FILE_PATH)
            except FileNotFoundError:
                pass
            proxy_lock_file = open(LOCK_FILE_PATH, "w")
            fcntl.flock(proxy_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            print(f"[Alpaca Proxy] Another proxy/data stream is already running (lock file: {LOCK_FILE_PATH}).")
            print(f"[Alpaca Proxy] Active process PID: {existing_pid}")
            print("[Alpaca Proxy] Stop the existing process before starting a new one.")
            if force:
                print("[Alpaca Proxy] --force can only break a stale lock; it cannot override an active process.")
            sys.exit(1)
    proxy_lock_file.seek(0)
    proxy_lock_file.truncate()
    proxy_lock_file.write(str(os.getpid()))
    proxy_lock_file.flush()


async def proxy_heartbeat_loop():
    global last_schedule_should_run

    script_name = os.path.basename(__file__)
    params_text = (
        f"symbols={symbols}, feed={ALPACA_DATA_FEED}, proxy={PROXY_HOST}:{PROXY_PORT}, "
        f"heartbeat_interval={HEARTBEAT_INTERVAL}, force={force_start}, env_file={args.env_file}"
    )

    while True:
        await asyncio.sleep(HEARTBEAT_INTERVAL)
        now_ny = datetime.now(NY_TZ)
        should_run_now, schedule_reason = proxy_schedule_status(
            now_ny,
            markets,
            PROXY_START_TIME,
            PROXY_END_TIME,
        )

        if not should_run_now:
            last_schedule_should_run = False
            _emit_idle_heartbeat_once(now_ny, schedule_reason)
            continue

        schedule_just_resumed = last_schedule_should_run is False
        last_schedule_should_run = True
        _clear_idle_heartbeat_state()

        if schedule_just_resumed:
            print("[Alpaca Proxy] Active schedule resumed; resetting upstream connection and stale market data.")
            _clear_stale_market_data()
            await force_reset_upstream("schedule_resumed", bypass_cooldown=True)
            continue

        if relay_task_handle is None or relay_task_handle.done():
            print("[Alpaca Proxy] ERROR: Relay task is not running; restarting it immediately.")
            await force_reset_upstream("relay_task_not_running", bypass_cooldown=True)
            continue

        prices = []
        for symbol in symbols:
            if symbol in latest_prices:
                prices.append(f"{symbol}={latest_prices[symbol]}")
            else:
                prices.append(f"{symbol}=n/a")
        prices_text = ", ".join(prices)
        print(
            f"💓 [Alpaca Proxy Heartbeat] time={now_ny.strftime('%Y-%m-%d %H:%M:%S %Z')} "
            f"| script={script_name} | {params_text} | prices={prices_text}"
        )

        if last_ws_message_at is None:
            print("[Alpaca Proxy] WARNING: No websocket messages received yet.")
        else:
            stale_seconds = max(0.0, (now_ny - last_ws_message_at).total_seconds())
            if stale_seconds > STALE_WEBSOCKET_SECONDS:
                print(
                    "[Alpaca Proxy] ERROR: Websocket data is stale. "
                    f"age_seconds={stale_seconds:.2f} threshold_seconds={STALE_WEBSOCKET_SECONDS:.2f}"
                )
                await force_reset_upstream(
                    reason=(
                        "websocket_stale "
                        f"age={stale_seconds:.2f}s threshold={STALE_WEBSOCKET_SECONDS:.2f}s"
                    )
                )

        stale_price_symbols: list[str] = []
        for symbol in symbols:
            last_symbol_update = latest_price_updated_at.get(symbol)
            if last_symbol_update is None:
                stale_price_symbols.append(symbol)
                continue
            symbol_age = max(0.0, (now_ny - last_symbol_update).total_seconds())
            if symbol_age > STALE_WEBSOCKET_SECONDS:
                stale_price_symbols.append(symbol)

        all_prices_stale = bool(symbols) and len(stale_price_symbols) == len(symbols)
        if all_prices_stale:
            print(
                "[Alpaca Proxy] ERROR: All symbol prices are stale. "
                f"symbols={stale_price_symbols} threshold_seconds={STALE_WEBSOCKET_SECONDS:.2f}"
            )
            await force_reset_upstream(
                reason=(
                    "all_symbol_prices_stale "
                    f"count={len(stale_price_symbols)} threshold={STALE_WEBSOCKET_SECONDS:.2f}s"
                )
            )


# --------- Add main entry point to start the proxy server and relay ---------

async def main():
    global relay_task_handle, force_reconnect_lock

    acquire_proxy_lock(force_start)
    force_reconnect_lock = asyncio.Lock()
    downstream_ping_interval = _optional_float_setting("ALPACA_PROXY_DOWNSTREAM_PING_INTERVAL_SECONDS", None)
    downstream_ping_timeout = _optional_float_setting("ALPACA_PROXY_DOWNSTREAM_PING_TIMEOUT_SECONDS", None)
    downstream_close_timeout = _optional_float_setting("ALPACA_PROXY_DOWNSTREAM_CLOSE_TIMEOUT_SECONDS", 10.0)
    # Start proxy server for clients
    server = await websockets.serve(
        websocket_handler,
        PROXY_HOST,
        PROXY_PORT,
        ping_interval=downstream_ping_interval,
        ping_timeout=downstream_ping_timeout,
        close_timeout=float(10.0 if downstream_close_timeout is None else downstream_close_timeout),
    )
    print(f"[Alpaca Proxy] Listening on ws://{PROXY_HOST}:{PROXY_PORT}")
    print(f"[Alpaca Proxy] Upstream feed: {ALPACA_DATA_FEED} ({ALPACA_WS_URL})")
    print(
        "[Alpaca Proxy] Schedule "
        f"STRATEGY_START_TIME={PROXY_START_TIME.strftime('%H:%M')} "
        f"STRATEGY_END_TIME={PROXY_END_TIME.strftime('%H:%M')} "
        "(America/New_York); weekends/holidays suspended"
    )
    # Start Alpaca stream relay in a background task
    heartbeat_task = asyncio.create_task(proxy_heartbeat_loop())
    relay_task_handle = asyncio.create_task(relay_alpaca_stream())
    try:
        await server.wait_closed()
    finally:
        print("[Alpaca Proxy] Shutting down...")
        heartbeat_task.cancel()
        relay_task_handle.cancel()
        server.close()
        results = await asyncio.gather(
            heartbeat_task, relay_task_handle, server.wait_closed(), return_exceptions=True
        )
        for result in results:
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                print(f"[Alpaca Proxy] Cleanup: task ended with error: {result}")

if __name__ == "__main__":
    try:
        print("Press Ctrl-C to stop the proxy server... \n")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Alpaca Proxy] Server stopped by user")
