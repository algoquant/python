from __future__ import annotations

import asyncio
import errno
import inspect
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import websockets

from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.args import FALLBACK_CONFIRMATION_PROXY_URL, resolve_confirmation_proxy_url


DEFAULT_CONFIRMATION_PROXY_URL = resolve_confirmation_proxy_url()


def _optional_float_env(name: str, default: float | None) -> float | None:
    raw_value = str(os.getenv(name, "")).strip()
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


def parse_confirmation_proxy_url(url: str | None) -> tuple[str, int, str]:
    raw_url = str(url or DEFAULT_CONFIRMATION_PROXY_URL).strip() or DEFAULT_CONFIRMATION_PROXY_URL
    parsed = urlparse(raw_url)
    host = str(parsed.hostname or "127.0.0.1").strip() or "127.0.0.1"
    port = int(parsed.port or 8766)
    path = str(parsed.path or "").strip() or "/"
    return host, port, path


def normalize_trade_update_event(event_data: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}

    if isinstance(event_data, dict):
        payload = dict(event_data)
    else:
        for method_name in ("model_dump", "dict"):
            method = getattr(event_data, method_name, None)
            if not callable(method):
                continue
            try:
                candidate = method()
            except TypeError:
                try:
                    candidate = method(mode="python")
                except Exception:
                    candidate = None
            except Exception:
                candidate = None
            if isinstance(candidate, dict):
                payload = dict(candidate)
                break

    order_payload = payload.get("order") if isinstance(payload.get("order"), dict) else {}
    normalized = dict(order_payload)
    normalized["event"] = str(payload.get("event", normalized.get("event", "")) or "").strip()
    normalized["event_id"] = str(payload.get("event_id", "") or "").strip()
    normalized["execution_id"] = str(payload.get("execution_id", "") or "").strip()
    normalized["timestamp"] = payload.get("timestamp", normalized.get("timestamp"))
    normalized["position_qty"] = payload.get("position_qty", normalized.get("position_qty"))
    normalized["event_qty"] = payload.get("qty", None)
    normalized["event_price"] = payload.get("price", None)

    status_text = str(normalized.get("status", "") or "").strip()
    if not status_text:
        normalized["status"] = str(payload.get("event", "") or "").strip()

    if "id" not in normalized:
        normalized_order_id = (
            payload.get("id")
            or payload.get("order_id")
            or payload.get("client_order_id")
        )
        if normalized_order_id is not None:
            normalized["id"] = normalized_order_id

    return normalized


class ConfirmationStreamOwner:
    def __init__(
        self,
        *,
        env_file: str | None = None,
        listen_url: str | None = None,
        ping_interval: float | None = None,
        ping_timeout: float | None = None,
        close_timeout: float = 20.0,
    ):
        self.env_file = env_file
        self.listen_url = resolve_confirmation_proxy_url(env_file=env_file, explicit_url=listen_url)
        self.ping_interval = _optional_float_env(
            "CONFIRMATION_FANOUT_PING_INTERVAL",
            ping_interval,
        )
        self.ping_timeout = _optional_float_env(
            "CONFIRMATION_FANOUT_PING_TIMEOUT",
            ping_timeout,
        )
        close_timeout_value = _optional_float_env("CONFIRMATION_FANOUT_CLOSE_TIMEOUT", close_timeout)
        self.close_timeout = float(close_timeout if close_timeout_value is None else close_timeout_value)
        self.idle_shutdown_seconds = _optional_float_env(
            "CONFIRMATION_OWNER_IDLE_SHUTDOWN_SECONDS",
            24.0 * 3600.0,
        )
        self.alpaca_api = AlpacAPI()
        self._clients: set[Any] = set()
        self._last_confirm_at = time.monotonic()

    async def _handle_driver_client(self, websocket):
        self._clients.add(websocket)
        try:
            await websocket.send(json.dumps({"type": "hello", "channel": "trade_updates"}, ensure_ascii=True))
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)

    async def _broadcast_payload(self, payload: dict[str, Any]):
        if not self._clients:
            return

        message = json.dumps(payload, default=str, ensure_ascii=True)
        stale_clients: list[Any] = []
        for websocket in tuple(self._clients):
            try:
                await websocket.send(message)
            except Exception:
                stale_clients.append(websocket)

        for websocket in stale_clients:
            self._clients.discard(websocket)

    async def _handle_trade_update(self, event_data):
        self._last_confirm_at = time.monotonic()
        payload = normalize_trade_update_event(event_data)
        if not payload:
            return
        await self._broadcast_payload(payload)

    async def _idle_shutdown_watchdog(self):
        idle_limit = self.idle_shutdown_seconds
        if idle_limit is None:
            return

        check_interval = min(idle_limit, 60.0)
        while True:
            await asyncio.sleep(check_interval)
            idle_seconds = time.monotonic() - self._last_confirm_at
            if idle_seconds >= idle_limit:
                print(
                    "🛑 ",
                    f"No confirmations received in {idle_seconds / 3600.0:.1f}h; shutting down idle confirmation stream owner.",
                )
                return

    async def run(self):
        host, port, path = parse_confirmation_proxy_url(self.listen_url)
        bind_url = f"ws://{host}:{port}{path if path != '/' else ''}"

        # Bind before touching Alpaca so an already-running owner is a no-op, not a crash.
        try:
            server = await websockets.serve(
                self._handle_driver_client,
                host,
                port,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=self.close_timeout,
            )
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                print(
                    "ℹ️ ",
                    f"Confirmation stream owner already running on {bind_url}; not starting a duplicate.",
                )
                return
            raise

        self.alpaca_api.create_trade_clients(env_file=self.env_file)
        confirm_stream = self.alpaca_api.get_confirm_stream()
        confirm_stream.subscribe_trade_updates(self._handle_trade_update)

        print("✅ ", f"Confirmation stream owner listening on {bind_url}")
        self._last_confirm_at = time.monotonic()

        async with server:
            stream_task = asyncio.ensure_future(confirm_stream._run_forever())
            idle_task = asyncio.ensure_future(self._idle_shutdown_watchdog())
            done, pending = await asyncio.wait({stream_task, idle_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in pending:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise exc

    async def close(self):
        await self.alpaca_api.cleanup_websocket()


async def consume_confirmation_fanout(
    url: str,
    on_payload: Callable[[dict[str, Any]], Awaitable[None] | None],
    *,
    reconnect_delay: float = 5.0,
    open_timeout: float = 10.0,
    close_timeout: float = 20.0,
    ping_interval: float | None = None,
    ping_timeout: float | None = None,
    print_fn=print,
    env_file: str | None = None,
    respawn_after_failures: int = 3,
    respawn_cooldown: float = 30.0,
):
    ws_ping_interval = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_PING_INTERVAL", ping_interval)
    ws_ping_timeout = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_PING_TIMEOUT", ping_timeout)
    ws_close_timeout = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_CLOSE_TIMEOUT", close_timeout)
    resolved_close_timeout = float(close_timeout if ws_close_timeout is None else ws_close_timeout)

    consecutive_failures = 0
    last_respawn_at: float | None = None

    while True:
        try:
            async with websockets.connect(
                url,
                open_timeout=float(open_timeout),
                close_timeout=resolved_close_timeout,
                ping_interval=ws_ping_interval,
                ping_timeout=ws_ping_timeout,
            ) as websocket:
                print_fn("🔌 ", f"Connected to confirmation fanout {url}")
                consecutive_failures = 0
                async for message in websocket:
                    payload = json.loads(message)
                    if isinstance(payload, dict) and str(payload.get("type", "")).strip().lower() == "hello":
                        continue
                    result = on_payload(payload)
                    if inspect.isawaitable(result):
                        await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            consecutive_failures += 1
            print_fn("🔄 ", f"Confirmation fanout error: {exc}. Reconnecting in {float(reconnect_delay):.1f}s...")

            # The shared owner can idle-shutdown mid-run; re-spawn it if reconnects keep failing.
            if env_file is not None and consecutive_failures >= max(1, int(respawn_after_failures)):
                now = time.monotonic()
                if last_respawn_at is None or (now - last_respawn_at) >= max(1.0, float(respawn_cooldown)):
                    last_respawn_at = now
                    try:
                        owner_process = spawn_confirmation_owner_process(env_file=env_file, listen_url=url)
                        print_fn(
                            "🚀 ",
                            f"Confirmation owner unreachable after {consecutive_failures} attempts; "
                            f"re-spawned pid={owner_process.pid} for {url}",
                        )
                    except Exception as spawn_exc:
                        print_fn("❌ ", f"Failed to re-spawn confirmation owner for {url}: {spawn_exc}")

            await asyncio.sleep(max(0.5, float(reconnect_delay)))


async def verify_confirmation_fanout(
    url: str,
    *,
    open_timeout: float = 5.0,
    read_timeout: float = 5.0,
    close_timeout: float = 20.0,
    ping_interval: float | None = None,
    ping_timeout: float | None = None,
) -> None:
    ws_ping_interval = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_PING_INTERVAL", ping_interval)
    ws_ping_timeout = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_PING_TIMEOUT", ping_timeout)
    ws_close_timeout = _optional_float_env("CONFIRMATION_FANOUT_CLIENT_CLOSE_TIMEOUT", close_timeout)
    resolved_close_timeout = float(close_timeout if ws_close_timeout is None else ws_close_timeout)

    async with websockets.connect(
        url,
        open_timeout=float(open_timeout),
        close_timeout=resolved_close_timeout,
        ping_interval=ws_ping_interval,
        ping_timeout=ws_ping_timeout,
    ) as websocket:
        message = await asyncio.wait_for(websocket.recv(), timeout=float(read_timeout))
        payload = json.loads(message)
        if not isinstance(payload, dict):
            raise RuntimeError(f"Confirmation owner at {url} sent a non-dict hello payload")

        payload_type = str(payload.get("type", "") or "").strip().lower()
        channel = str(payload.get("channel", "") or "").strip().lower()
        if payload_type != "hello" or channel != "trade_updates":
            raise RuntimeError(
                f"Confirmation owner at {url} responded with unexpected hello payload: {payload}"
            )


def build_confirmation_owner_command(*, env_file: str | None = None, listen_url: str | None = None) -> list[str]:
    command = [sys.executable, "-m", "MachineTrader.confirm_stream_owner"]

    env_path = str(env_file or "").strip()
    if env_path:
        command.extend(["--env-file", env_path])

    listen_text = str(listen_url or "").strip()
    if listen_text:
        command.extend(["--listen-url", listen_text])

    return command


def spawn_confirmation_owner_process(
    *,
    env_file: str | None = None,
    listen_url: str | None = None,
) -> subprocess.Popen:
    repo_root = Path(__file__).resolve().parents[2]
    command = build_confirmation_owner_command(env_file=env_file, listen_url=listen_url)
    return subprocess.Popen(
        command,
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env=os.environ.copy(),
    )