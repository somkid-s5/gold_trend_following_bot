import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk.risk_manager import RiskManager

class TestCorrelationGuard(unittest.TestCase):
    def setUp(self):
        # Mock config
        self.config = {
            "max_total_drawdown_pct": 95.0,
            "max_daily_loss_pct": 10.0,
            "max_spread_points": 500
        }
        self.symbols_config = {
            "XAUUSDm": {"point": 0.01},
            "GBPUSDm": {"point": 0.00001},
            "EURUSDm": {"point": 0.00001}
        }
        self.rm = RiskManager(self.config, self.symbols_config)

    def test_correlation_limit(self):
        # Scenario: 2 USD-sensitive positions are already open
        open_positions = [
            {"symbol": "XAUUSDm", "ticket": 123},
            {"symbol": "GBPUSDm", "ticket": 456}
        ]
        
        # Try to open another USD-sensitive pair (EURUSDm)
        decision = self.rm.check_correlation("EURUSDm", open_positions)
        
        print(f"\n[Test] Checking EURUSDm with XAU & GBP open: {decision.allowed} - {decision.reason}")
        self.assertFalse(decision.allowed)
        self.assertIn("Correlation Limit", decision.reason)

    def test_uncorrelated_allowed(self):
        # Scenario: 1 USD-sensitive position is open
        open_positions = [{"symbol": "XAUUSDm", "ticket": 123}]
        
        # Opening another one should be allowed (limit is 2)
        decision = self.rm.check_correlation("EURUSDm", open_positions)
        print(f"[Test] Checking EURUSDm with only XAU open: {decision.allowed}")
        self.assertTrue(decision.allowed)

if __name__ == "__main__":
    unittest.main()
