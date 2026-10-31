import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from MachineTrader.strat_ladder import StrategyState


class LadderFillReferenceTests(unittest.TestCase):
    def test_bands_use_last_fill_even_when_queue_is_empty_or_different(self):
        for queue in ([], [-500.0]):
            for signed_fill in (-100.0, 100.0):
                for price, expected in ((97.0, 3.0), (100.0, 0.0), (103.0, -3.0)):
                    with self.subTest(queue=queue, signed_fill=signed_fill, price=price):
                        state = StrategyState("SPY")
                        state.calculate_indicators = Mock(return_value=True)
                        state.indicators.update(price=price, volatility=1.0, ema=100.0)
                        context = SimpleNamespace(
                            last_fill_prices={"SPY": signed_fill},
                            positions={"SPY": {"qty": 0.0, "position_queue_prices": queue}},
                            minute_bars={"SPY": {"h": 200.0, "l": 1.0, "c": price}},
                            strategy_params={"quantity_by_symbol": {"SPY": 3}, "risk_premium": 2.0, "price_premium": 0.0},
                            trading_state=SimpleNamespace(add_strategy_amount=Mock()),
                        )
                        self.assertEqual(expected, state.calculate_target(context))
                        self.assertEqual(100.0, state.indicators["reference_price"])
                        self.assertNotIn("price_skew", state.indicators)

    def test_missing_fill_reference_uses_current_price_without_skew_entry(self):
        state = StrategyState("SPY")
        state.calculate_indicators = Mock(return_value=True)
        state.indicators.update(price=100.0, volatility=1.0, ema=100.0)
        context = SimpleNamespace(
            last_fill_prices={"SPY": None}, positions={},
            minute_bars={"SPY": {"h": 101.0, "l": 90.0, "c": 100.0}},
            strategy_params={"price_premium": 0.0},
            trading_state=SimpleNamespace(add_strategy_amount=Mock()),
        )
        self.assertEqual(0.0, state.calculate_target(context))
        self.assertEqual(100.0, state.indicators["reference_price"])