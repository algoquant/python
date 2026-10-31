"""Strategy bundle helper for sandbox master driver.

This module defines reusable strategy bundles so master_driver can load
multiple strategy callbacks with a single bundle name.
"""

from __future__ import annotations

BUNDLES = {
    "core": [
        "strat_bollinger_bars:bollinger_signal",
        "strat_bollinger_bars_ema:bollinger_ema_signal",
        "strat_tanaka:call_back",
    ],
    "bollinger": [
        "strat_bollinger_bars:bollinger_signal",
        "strat_bollinger_bars_ema:bollinger_ema_signal",
    ],
    "tanaka": [
        "strat_tanaka:call_back",
    ],
    "momentum": [
        "MachineTrader.strat_cross:call_back",
        "MachineTrader.strat_ratchet:call_back",
        "MachineTrader.strat_trend:call_back",
        "MachineTrader.strat_trendpreopen:call_back",
        "MachineTrader.strat_trendfromopen:call_back",
    ],
    "momentum_trend": [
        "MachineTrader.strat_trend:call_back",
        "MachineTrader.strat_trendpreopen:call_back",
        "MachineTrader.strat_trendfromopen:call_back",
    ],
    "trendfromopen": [
        "MachineTrader.strat_trendfromopen:call_back",
    ],
    "all": [
        "strat_bollinger_bars:bollinger_signal",
        "strat_bollinger_bars_ema:bollinger_ema_signal",
        "strat_tanaka:call_back",
        "MachineTrader.strat_trendfromopen:call_back",
    ],
}


def get_bundle_specs(bundle_names: list[str]) -> list[str]:
    """Return deduplicated strategy specs for one or more bundle names."""
    specs: list[str] = []

    for name in bundle_names:
        bundle_key = str(name or "").strip().lower()
        if not bundle_key:
            continue
        if bundle_key not in BUNDLES:
            available = ", ".join(sorted(BUNDLES.keys()))
            raise ValueError(f"Unknown strategy bundle '{bundle_key}'. Available bundles: {available}")

        for spec in BUNDLES[bundle_key]:
            if spec not in specs:
                specs.append(spec)

    return specs
