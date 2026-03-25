from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.utils.logger import setup_logger
from src.utils.telegram_notifier import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["TEST_TELEGRAM_BOT_TOKEN"] = "token"
        os.environ["TEST_TELEGRAM_CHAT_ID"] = "chat"
        self.state_path = Path("reports/test_telegram_state.json")
        if self.state_path.exists():
            self.state_path.unlink()
        self.notifier = TelegramNotifier(
            {
                "enabled": True,
                "summary_time_utc": "21:00",
                "state_path": str(self.state_path),
                "bot_token_env": "TEST_TELEGRAM_BOT_TOKEN",
                "chat_id_env": "TEST_TELEGRAM_CHAT_ID",
            },
            setup_logger("test_telegram_notifier"),
        )

    def tearDown(self) -> None:
        if self.state_path.exists():
            self.state_path.unlink()

    def test_should_send_daily_summary_once_per_day(self) -> None:
        now = datetime(2026, 3, 25, 21, 5, tzinfo=timezone.utc)
        self.assertTrue(self.notifier.should_send_daily_summary(now))
        self.notifier.mark_daily_summary_sent(now)
        self.assertFalse(self.notifier.should_send_daily_summary(now))

    def test_build_daily_summary_contains_key_fields(self) -> None:
        text = self.notifier.build_daily_summary(
            strategy_name="trend_following",
            now_utc=datetime(2026, 3, 25, 21, 5, tzinfo=timezone.utc),
            account={"balance": 10000.0, "equity": 10050.0},
            guard_payload={"status": "OK", "reasons": ["All operational guard checks passed"]},
            trades_frame=pd.DataFrame({"pnl": [10.0, -5.0]}),
        )
        self.assertIn("สรุปรายวัน XAUUSD", text)
        self.assertIn("trend_following", text)
        self.assertIn("10050.00", text)
        self.assertIn("สถานะ Guard", text)

    def test_event_cooldown_blocks_immediate_repeat(self) -> None:
        now = datetime(2026, 3, 25, 21, 5, tzinfo=timezone.utc)
        self.assertTrue(self.notifier.should_send_event("startup", now))
        self.notifier.mark_event_sent("startup", now)
        self.assertFalse(self.notifier.should_send_event("startup", now))


if __name__ == "__main__":
    unittest.main()
