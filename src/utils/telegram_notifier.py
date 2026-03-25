from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


class TelegramNotifier:
    def __init__(self, config: dict[str, Any], logger: Any) -> None:
        self.config = config
        self.logger = logger

    def is_enabled(self) -> bool:
        if not self.config.get("enabled", False):
            return False
        return bool(self._bot_token() and self._chat_id())

    def _bot_token(self) -> str | None:
        return os.getenv(self.config.get("bot_token_env", "TELEGRAM_BOT_TOKEN"))

    def _chat_id(self) -> str | None:
        return os.getenv(self.config.get("chat_id_env", "TELEGRAM_CHAT_ID"))

    def _state_path(self) -> Path:
        return Path(self.config.get("state_path", "reports/telegram_state.json"))

    def load_state(self) -> dict[str, Any]:
        path = self._state_path()
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_state(self, state: dict[str, Any]) -> None:
        path = self._state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def should_send_daily_summary(self, now_utc: datetime) -> bool:
        if not self.is_enabled():
            return False
        target = self.config.get("summary_time_utc", "21:00")
        hour, minute = map(int, target.split(":"))
        if (now_utc.hour, now_utc.minute) < (hour, minute):
            return False
        state = self.load_state()
        return state.get("last_daily_summary_date") != now_utc.date().isoformat()

    def mark_daily_summary_sent(self, now_utc: datetime) -> None:
        state = self.load_state()
        state["last_daily_summary_date"] = now_utc.date().isoformat()
        self.save_state(state)

    def should_send_event(self, event_key: str, now_utc: datetime) -> bool:
        if not self.is_enabled():
            return False
        state = self.load_state()
        last_sent = state.get(f"event_{event_key}_sent_at")
        if not last_sent:
            return True
        last_dt = datetime.fromisoformat(last_sent)
        cooldown = timedelta(minutes=int(self.config.get("event_cooldown_minutes", 30)))
        return now_utc >= last_dt + cooldown

    def mark_event_sent(self, event_key: str, now_utc: datetime) -> None:
        state = self.load_state()
        state[f"event_{event_key}_sent_at"] = now_utc.isoformat()
        self.save_state(state)

    def send_message(self, text: str) -> bool:
        if not self.is_enabled():
            self.logger.info("Telegram notifier disabled or missing credentials.")
            return False
        url = f"https://api.telegram.org/bot{self._bot_token()}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": self._chat_id(),
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        response.raise_for_status()
        return True

    def build_daily_summary(
        self,
        strategy_name: str,
        now_utc: datetime,
        account: dict[str, Any],
        guard_payload: dict[str, Any] | None,
        trades_frame: Any,
    ) -> str:
        total_trades = int(len(trades_frame)) if trades_frame is not None else 0
        day_profit = float(trades_frame["pnl"].sum()) if trades_frame is not None and not trades_frame.empty else 0.0
        win_rate = float((trades_frame["pnl"] > 0).mean() * 100) if trades_frame is not None and not trades_frame.empty else 0.0
        guard_status = guard_payload.get("status", "UNKNOWN") if guard_payload else "UNKNOWN"
        reasons = ", ".join(guard_payload.get("reasons", [])) if guard_payload else "No guard payload"
        return (
            f"*XAUUSD Daily Summary*\n"
            f"- Date UTC: `{now_utc.date().isoformat()}`\n"
            f"- Strategy: `{strategy_name}`\n"
            f"- Balance: `{account['balance']:.2f}`\n"
            f"- Equity: `{account['equity']:.2f}`\n"
            f"- Closed trades today: `{total_trades}`\n"
            f"- Day PnL: `{day_profit:.2f}`\n"
            f"- Day win rate: `{win_rate:.2f}%`\n"
            f"- Guard status: `{guard_status}`\n"
            f"- Guard note: {reasons}"
        )

    def build_event_message(self, event_name: str, now_utc: datetime, details: str) -> str:
        return (
            f"*Bot {event_name}*\n"
            f"- Time UTC: `{now_utc.isoformat()}`\n"
            f"- Details: {details}"
        )
