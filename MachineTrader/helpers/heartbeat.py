"""Shared heartbeat helpers for long-running strategy and proxy loops."""

import asyncio


def _resolve_arg(value):
    """Evaluate dynamic heartbeat arguments when callables are provided."""
    if callable(value):
        return value()
    return value


def format_function_call(function_name, **kwargs):
    """Render a simple function-call string like name(arg=value, ...)."""
    rendered_args = ", ".join(f"{key}={value}" for key, value in kwargs.items())
    return f"{function_name}({rendered_args})"


async def heartbeat(function_name, interval, **kwargs):
    """Print a function-call style heartbeat message at a fixed interval."""
    while True:
        resolved_kwargs = {key: _resolve_arg(value) for key, value in kwargs.items()}
        call_kwargs = {"interval": interval, **resolved_kwargs}
        print(format_function_call(function_name, **call_kwargs))
        await asyncio.sleep(interval)


def start_heartbeat_task(function_name, interval, **kwargs):
    """Start a heartbeat coroutine as an asyncio background task."""
    return asyncio.create_task(heartbeat(function_name, interval, **kwargs))
