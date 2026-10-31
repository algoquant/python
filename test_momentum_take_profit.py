from MachineTrader.master_momentum import MasterMomentumDriver


def test_take_profit_hint_is_computed_from_queue_and_unrealized_pnl():
    driver = MasterMomentumDriver.__new__(MasterMomentumDriver)
    driver.required_symbols = {"AAPL"}
    driver.strategy_params = {
        "take_profit_threshold": 5.0,
        "take_profit_factor": 1.0,
    }
    driver.latest_execution_hints = {}

    merged_local_queue = {"AAPL": [-10.0, -10.0]}
    positions_snapshot = {
        "AAPL": {
            "qty": 2.0,
            "unrealized_pnls": [22.0, 18.0],
        }
    }
    unrealized_by_symbol = {"AAPL": 40.0}

    delta, hint = driver._compute_take_profit_delta(
        "AAPL",
        merged_local_queue=merged_local_queue,
        positions_snapshot=positions_snapshot,
        unrealized_by_symbol=unrealized_by_symbol,
    )

    assert delta == -2.0
    assert hint["take_profit_triggered"] is True
    assert hint["take_profit_reason"] == "aggregate"


def test_volatility_spacing_gate_consecutive_sell_orders():
    driver = MasterMomentumDriver.__new__(MasterMomentumDriver)
    driver.required_symbols = {"SPY"}
    driver.strategy_params = {}
    driver.last_fill_prices = {"SPY": 741.0}  # Last fill was SELL at +741.0
    driver.latest_symbol_prices = {}
    driver.latest_execution_hints = {
        "SPY": {"volatility_gap": 1.5}
    }

    class MockContext:
        minute_bars = {"SPY": {"c": 742.0}}

    trade_plan = {"SPY": -1.0}
    driver._apply_volatility_spacing_gate("SPY", trade_plan, {}, context=MockContext())
    assert trade_plan["SPY"] == 0.0  # 742.0 <= 742.5, blocked

    MockContext.minute_bars = {"SPY": {"c": 743.0}}
    trade_plan = {"SPY": -1.0}
    driver._apply_volatility_spacing_gate("SPY", trade_plan, {}, context=MockContext())
    assert trade_plan["SPY"] == -1.0  # 743.0 > 742.5, allowed


def test_volatility_spacing_gate_consecutive_buy_orders():
    driver = MasterMomentumDriver.__new__(MasterMomentumDriver)
    driver.required_symbols = {"SPY"}
    driver.strategy_params = {}
    driver.last_fill_prices = {"SPY": -741.0}  # Last fill was BUY at -741.0
    driver.latest_symbol_prices = {}
    driver.latest_execution_hints = {
        "SPY": {"volatility_gap": 1.5}
    }

    class MockContext:
        minute_bars = {"SPY": {"c": 740.0}}

    trade_plan = {"SPY": 1.0}
    driver._apply_volatility_spacing_gate("SPY", trade_plan, {}, context=MockContext())
    assert trade_plan["SPY"] == 0.0  # 740.0 >= 739.5, blocked

    MockContext.minute_bars = {"SPY": {"c": 739.0}}
    trade_plan = {"SPY": 1.0}
    driver._apply_volatility_spacing_gate("SPY", trade_plan, {}, context=MockContext())
    assert trade_plan["SPY"] == 1.0  # 739.0 < 739.5, allowed


def test_strat_momentum_ratchet_trading_rules():
    from MachineTrader.strat_momentum_ratchet import MomentumState

    state = MomentumState(symbol="SPY")
    state.indicators["price"] = 100.0
    state.indicators["ema"] = 100.0
    state.indicators["volatility"] = 1.0

    class MockTradingState:
        def __init__(self):
            self.amounts = []
        def add_strategy_amount(self, symbol, delta, metadata=None):
            self.amounts.append((symbol, delta, metadata))

    class MockStrategyContext:
        def __init__(self, zscore, qty, risk_premium, current_pos, reverse=False):
            self.strategy_params = {
                "strategy_symbols": ["SPY"],
                "quantity_by_symbol": {"SPY": qty},
                "risk_premium": risk_premium,
                "strategy_reverse": reverse,
            }
            self.positions = {"SPY": {"qty": current_pos}}
            self.minute_key = (2026, 9, 16, 9, 30)
            self.trading_state = MockTradingState()

    # 1. User example: strategy_sign = -1 (reverse=True), zscore = -1.5, quantity = 3, risk_premium = 2
    # notional = trunc((-1) * (-1.5) * 3 / 2) = 2
    state.indicators["zscore"] = -1.5
    ctx1 = MockStrategyContext(zscore=-1.5, qty=3.0, risk_premium=2.0, current_pos=0.0, reverse=True)
    delta1 = state.calculate_target(ctx1)
    assert delta1 == 2.0
    assert state.indicators["notional"] == 2.0
    assert state.indicators["target"] == 2.0

    # 2. Positive notional with higher value: notional = 3, previous target = 2 -> target = max(3, 2) = 3
    state.indicators["zscore"] = -2.0  # notional = trunc((-1) * (-2.0) * 3 / 2) = 3
    ctx2 = MockStrategyContext(zscore=-2.0, qty=3.0, risk_premium=2.0, current_pos=2.0, reverse=True)
    delta2 = state.calculate_target(ctx2)
    assert delta2 == 1.0  # 3 - 2 = 1
    assert state.indicators["target"] == 3.0

    # 3. Pullback with positive notional: notional = 1, previous target = 3 -> target = max(1, 3) = 3
    state.indicators["zscore"] = -0.7  # notional = trunc((-1) * (-0.7) * 3 / 2) = 1
    ctx3 = MockStrategyContext(zscore=-0.7, qty=3.0, risk_premium=2.0, current_pos=3.0, reverse=True)
    delta3 = state.calculate_target(ctx3)
    assert delta3 == 0.0  # target stays 3, current pos 3 -> delta 0
    assert state.indicators["target"] == 3.0

    # 4. Sign switch: notional becomes -1 (was positive 1) -> target = -1
    state.indicators["zscore"] = 0.7  # notional = trunc((-1) * (0.7) * 3 / 2) = -1
    ctx4 = MockStrategyContext(zscore=0.7, qty=3.0, risk_premium=2.0, current_pos=3.0, reverse=True)
    delta4 = state.calculate_target(ctx4)
    assert delta4 == -4.0  # target -1 - position 3 = -4 (liquidates +3 and opens -1)
    assert state.indicators["target"] == -1.0

    # 5. Negative notional with more negative value: notional = -3, previous target = -1 -> target = min(-3, -1) = -3
    state.indicators["zscore"] = 2.0  # notional = trunc((-1) * (2.0) * 3 / 2) = -3
    ctx5 = MockStrategyContext(zscore=2.0, qty=3.0, risk_premium=2.0, current_pos=-1.0, reverse=True)
    delta5 = state.calculate_target(ctx5)
    assert delta5 == -2.0  # target -3 - position -1 = -2
    assert state.indicators["target"] == -3.0

    # 6. Negative notional pullback: notional = -2, previous target = -3 -> target = min(-2, -3) = -3
    state.indicators["zscore"] = 1.5  # notional = trunc((-1) * (1.5) * 3 / 2) = -2
    ctx6 = MockStrategyContext(zscore=1.5, qty=3.0, risk_premium=2.0, current_pos=-3.0, reverse=True)
    delta6 = state.calculate_target(ctx6)
    assert delta6 == 0.0  # target stays -3, position -3 -> delta 0
    assert state.indicators["target"] == -3.0
