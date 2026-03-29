![Gold Trading Bot](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/logo.png)

# Gold Trading Bot

โปรเจกต์นี้เป็นบอทเทรดทองคำ `XAUUSD` สำหรับ `MetaTrader 5` ที่พัฒนาด้วย Python โดยเวอร์ชันสุดท้ายของโปรเจกต์ถูกสรุปให้เหลือเฉพาะกลยุทธ์ `trend_following` เท่านั้น เพื่อให้ดูแลง่าย ใช้งานจริงง่าย และพร้อม push ขึ้น Git

## ภาพรวม

- กลยุทธ์ที่ใช้งานจริง: `trend_following`
- ตลาดหลัก: `XAUUSD`
- timeframe: `H1`
- รองรับ live, backtest, Telegram alerts, runtime heartbeat และ operational guards
- ใช้ `.env` สำหรับ MT5 และ Telegram

## กลยุทธ์ที่ใช้

พารามิเตอร์ปัจจุบัน:

- `EMA 34 / EMA 150`
- `RSI 14`
- `ATR 14`
- `ATR SL Multiplier = 1.2`
- `Take Profit RR = 2.0`

พฤติกรรมของบอท:

- รอแท่งใหม่ก่อนคำนวณสัญญาณ
- เปิดได้สูงสุด 1 position
- ตั้ง `SL/TP` ตั้งแต่เข้า order
- ใช้ `breakeven` และ `trailing stop`
- หยุดเปิดไม้ใหม่เมื่อเจอข่าวแรง, spread สูง, drawdown เกิน limit หรือ guard สั่ง `PAUSE`

## ผลทดสอบย้อนหลัง

- 12 เดือน: กำไร `+1386.88`, เทรด `165` ไม้, win rate `55.76%`, max DD `3.85%`
- out-of-sample 12 เดือน: `+630.08`, Sharpe `0.59`, win rate `58.62%`
- 5 ปี: กำไร `+3127.17`, เทรด `886` ไม้, win rate `52.37%`, max DD `9.45%`

โปรเจกต์นี้ยังไม่การันตีกำไร แต่ `trend_following` เป็น strategy ที่ให้ผลดีที่สุดและเสถียรที่สุดในงานวิจัยทั้งหมดของโปรเจกต์

## โครงสร้างโปรเจกต์

```text
gold_trading_bot/
├── config/
│   └── config.yaml
├── data/
│   ├── news_events.json
│   └── xauusd_h1.csv
├── scripts/
│   ├── register_live_bot_task.ps1
│   ├── run_forward_test_report.py
│   ├── run_mt5_backtests.py
│   ├── run_operational_guard_check.py
│   ├── run_trend_grid_search.py
│   ├── run_trend_oos_analysis.py
│   └── start_live_bot.ps1
├── src/
│   ├── broker/
│   ├── core/
│   ├── data/
│   ├── risk/
│   ├── strategies/
│   └── utils/
├── tests/
├── FORWARD_TEST_CHECKLIST.md
├── RUNBOOK_TH.md
├── main.py
├── requirements.txt
└── README.md
```

## ติดตั้ง

```bash
pip install -r requirements.txt
```

## ตั้งค่า `.env`

สร้างไฟล์ [\.env](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/.env)

```env
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
MT5_PATH=C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

## ตั้งค่า `config.yaml`

ไฟล์หลักอยู่ที่ [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml)

ค่าที่ควรเช็กก่อนใช้งาน:

- `risk.allow_live_trading`
- `risk.risk_per_trade_pct`
- `news_filter`
- `operational_guards`
- `notifications.telegram`

## วิธีรัน

### Backtest

```bash
python main.py --mode=backtest --symbol=XAUUSD --strategy=trend_following
```

หรือระบุ CSV เอง:

```bash
python main.py --mode=backtest --symbol=XAUUSD --strategy=trend_following --csv=data/xauusd_h1.csv
```

### Live

```bash
python main.py --mode=live --symbol=XAUUSD --strategy=trend_following
```

### PowerShell launcher

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_live_bot.ps1 -Symbol XAUUSD -Strategy trend_following
```

### เปิดอัตโนมัติหลัง logon

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_live_bot_task.ps1 -TaskName GoldTradingBot -Symbol XAUUSD -Strategy trend_following
```

## สคริปต์วิเคราะห์ที่ยังเก็บไว้

backtest จาก MT5:

```bash
python scripts/run_mt5_backtests.py --symbol XAUUSD --days 365 --strategies trend_following
```

out-of-sample:

```bash
python scripts/run_trend_oos_analysis.py --symbol XAUUSD --days 365 --split-ratio 0.7
```

grid search:

```bash
python scripts/run_trend_grid_search.py --symbol XAUUSD --days 365 --split-ratio 0.7 --fast-emas 34,50 --slow-emas 150,200 --buy-levels 35,40 --sell-levels 60,65 --atr-multipliers 1.2,1.5 --rr-values 1.5,2.0 --top 8
```

forward test report:

```bash
python scripts/run_forward_test_report.py --trades-csv=reports/trend_following_365d_trades.csv --strategy=trend_following
```

operational guard check:

```bash
python scripts/run_operational_guard_check.py --trades-csv=reports/trend_following_365d_trades.csv
```

## Telegram และการติดตามสถานะ

ถ้าตั้งค่า Telegram แล้ว บอทจะส่ง:

- daily summary
- guard alert
- startup alert
- error alert
- shutdown alert

ไฟล์ที่ใช้ดูสถานะ:

- [runtime_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/runtime_status.json)
- [guard_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/guard_status.json)
- [gold_trading_bot.log](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/logs/gold_trading_bot.log)

## ตรวจสอบคุณภาพ

```bash
python -m unittest discover -s tests
```

## เอกสารเพิ่มเติม

- [FORWARD_TEST_CHECKLIST.md](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/FORWARD_TEST_CHECKLIST.md)
- [RUNBOOK_TH.md](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/RUNBOOK_TH.md)

## หมายเหตุ

โปรเจกต์นี้ถูก clean ให้เหลือเฉพาะ `trend_following` อย่างตั้งใจ เพื่อให้เป็น final project ที่เรียบง่าย พร้อมใช้งาน และพร้อม push ขึ้น Git โดยไม่มี strategy research ที่ไม่ได้ใช้งานจริงปะปนอยู่
