"""
Unit tests for InstrumentSpec model.
"""

import unittest

from capital_management.models.instrument import InstrumentSpec


class TestInstrumentSpec(unittest.TestCase):

    def test_equity_default_instrument_spec(self):
        inst = InstrumentSpec.create_default("AAPL", "EQUITY")
        self.assertEqual(inst.asset_class, "EQUITY")
        self.assertEqual(inst.contract_size, 1.0)
        self.assertEqual(inst.quantity_increment, 1.0)
        self.assertEqual(inst.min_quantity, 1.0)

        risk_per_unit = inst.calculate_monetary_risk_per_unit(entry_price=150.0, stop_price=145.0)
        self.assertEqual(risk_per_unit, 5.0)  # 5.0 * 1.0 * 1.0

    def test_forex_default_instrument_spec(self):
        inst = InstrumentSpec.create_default("EURUSD", "FOREX")
        self.assertEqual(inst.asset_class, "FOREX")
        self.assertEqual(inst.contract_size, 100000.0)
        self.assertEqual(inst.pip_size, 0.0001)
        self.assertEqual(inst.quantity_increment, 0.01)

        # 30 pips stop distance, $10 per pip per lot
        risk_per_lot = inst.calculate_monetary_risk_per_unit(entry_price=1.0850, stop_price=1.0820, pip_value_per_lot=10.0)
        self.assertAlmostEqual(risk_per_lot, 300.0, places=4)  # (0.0030 / 0.0001) * 10.0 = 30 * 10 = 300

    def test_jpy_forex_instrument_spec(self):
        inst = InstrumentSpec.create_default("USDJPY", "FOREX")
        self.assertEqual(inst.pip_size, 0.01)
        self.assertEqual(inst.price_increment, 0.001)


if __name__ == "__main__":
    unittest.main()
