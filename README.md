# Gold Trading Bot

โปรเจกต์นี้คือบอทเทรดทองคำ `XAUUSD` สำหรับ `MetaTrader 5` ที่พัฒนาด้วย Python โดยโฟกัสที่แนวทาง `trend_following` เป็นหลัก และออกแบบให้สามารถรันแบบอัตโนมัติได้ต่อเนื่อง พร้อมระบบควบคุมความเสี่ยง, guard conditions, runtime heartbeat, และสรุปรายวันผ่าน Telegram

สถานะปัจจุบันของโปรเจกต์:

- เปิดใช้งานจริงเฉพาะ `trend_following`
- `scalping_smc` และ `linear_grid` ถูกปิดไว้เป็น research-only
- รองรับ `.env`
- รองรับ MT5 reconnect อัตโนมัติ
- รองรับ Telegram daily summary และ alert
- รองรับ guard สำหรับหยุดเปิดไม้ใหม่เมื่อ performance แย่ลง

## ภาพรวมกลยุทธ์

กลยุทธ์ที่ใช้งานอยู่คือ `trend_following` โดยใช้แนวคิด:

- `EMA 34 / EMA 150`
- `RSI 14`
- `ATR 14`
- `ATR SL Multiplier = 1.2`
- `Take Profit RR = 2.0`

ค่าชุดนี้มาจากการจูนบนข้อมูลจริงย้อนหลัง และผ่านการเช็กแบบ out-of-sample แล้วดีกว่าค่า baseline เดิม

## โครงสร้างโปรเจกต์

```text
gold_trading_bot/
├── config/
│   └── config.yaml
├── data/
├── logs/
├── reports/
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
├── .env
├── FORWARD_TEST_CHECKLIST.md
├── main.py
├── requirements.txt
└── README.md
```

## ติดตั้ง

ติดตั้ง dependencies:

```bash
pip install -r requirements.txt
```

## การตั้งค่า `.env`

สร้างไฟล์ [\.env](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/.env) ที่ root ของโปรเจกต์:

```env
MT5_LOGIN=your_mt5_login
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_mt5_server
MT5_PATH=C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe

TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

คำอธิบาย:

- `MT5_*` ใช้สำหรับเชื่อมต่อบัญชี MT5
- `TELEGRAM_*` ใช้ส่งสรุปรายวันและแจ้งเตือน

หมายเหตุ:

- โปรแกรมจะโหลด `.env` อัตโนมัติ
- ถ้าไม่มีค่า Telegram บอทยังรันได้ แต่จะไม่ส่งข้อความ

## การตั้งค่า `config.yaml`

ไฟล์หลักอยู่ที่ [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml)

หัวข้อสำคัญ:

- `risk.allow_live_trading`
  - ถ้าเป็น `false` จะไม่ยอมเข้าโหมด live
- `strategies.*.enabled`
  - ตอนนี้เปิดแค่ `trend_following`
- `operational_guards`
  - ตั้งเงื่อนไขหยุดเปิดไม้ใหม่
- `notifications.telegram`
  - ตั้งเวลาส่ง daily summary และเปิด/ปิด alerts
- `runtime`
  - ตั้ง path ของ heartbeat file

## วิธีรัน

### 1. รัน backtest

```bash
python main.py --mode=backtest --symbol=XAUUSD --strategy=trend_following
```

ถ้าจะระบุไฟล์ CSV เอง:

```bash
python main.py --mode=backtest --symbol=XAUUSD --strategy=trend_following --csv=data/xauusd_h1.csv
```

### 2. รัน live

ก่อนรัน live ต้องเปิด `risk.allow_live_trading=true` ใน [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml)

จากนั้นรัน:

```bash
python main.py --mode=live --symbol=XAUUSD --strategy=trend_following
```

### 3. รันผ่าน PowerShell launcher

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_live_bot.ps1 -Symbol XAUUSD -Strategy trend_following
```

## การตั้งให้เปิดอัตโนมัติบน Windows

สามารถลงทะเบียน Task Scheduler ได้ด้วย:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\register_live_bot_task.ps1 -TaskName GoldTradingBot -Symbol XAUUSD -Strategy trend_following
```

พฤติกรรม:

- เริ่มบอทเมื่อ logon
- ใช้ launcher script ในการเปิด
- เหมาะกับการรันทิ้งไว้บนเครื่อง Windows

## Telegram ที่บอทส่งให้อัตโนมัติ

ถ้าตั้งค่า `TELEGRAM_BOT_TOKEN` และ `TELEGRAM_CHAT_ID` แล้ว บอทจะส่ง:

- daily summary วันละครั้ง
- guard alert เมื่อระบบเข้าสถานะ `PAUSE`
- startup alert
- error alert
- shutdown alert

ตั้งค่าเพิ่มเติมใน [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml):

- `notifications.telegram.summary_time_utc`
- `notifications.telegram.send_guard_alerts`
- `notifications.telegram.send_startup_alerts`
- `notifications.telegram.send_error_alerts`
- `notifications.telegram.send_shutdown_alerts`

## Guard และการหยุดเปิดไม้ใหม่อัตโนมัติ

ระบบ guard จะประเมินจากผลการเทรดย้อนหลังของ strategy แล้วเขียนผลไปที่:

- [guard_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/guard_status.json)

ถ้าสถานะเป็น `PAUSE` บอทจะ:

- หยุดเปิดออเดอร์ใหม่
- ยังคงทำงานต่อ
- ยังคงเขียน heartbeat
- สามารถส่ง Telegram alert ได้

เงื่อนไข guard ปัจจุบัน:

- `evaluation_window: 100`
- `minimum_trades: 20`
- `max_consecutive_losses: 6`
- `max_drawdown_pct: 5.0`
- `min_win_rate_pct: 45.0`

## ไฟล์สำคัญที่ใช้ติดตามสถานะ

ถ้าคุณอยากเช็กสถานะบอทแบบเร็วๆ ให้ดู 3 จุดนี้:

- [runtime_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/runtime_status.json)
- [guard_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/guard_status.json)
- [gold_trading_bot.log](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/logs/gold_trading_bot.log)

คำอธิบาย:

- `runtime_status.json` บอกว่าบอทตอนนี้ `running`, `paused`, หรือ `halted`
- `guard_status.json` บอกผลการประเมิน performance ล่าสุด
- `log` ใช้ตรวจสอบข้อผิดพลาดและเหตุการณ์ทั้งหมด

## สคริปต์วิจัยและวิเคราะห์

### 1. ดึงข้อมูลจาก MT5 แล้ว backtest หลายวัน

```bash
python scripts/run_mt5_backtests.py --symbol XAUUSD --days 365 --strategies trend_following
```

### 2. วิเคราะห์แบบ in-sample / out-of-sample

```bash
python scripts/run_trend_oos_analysis.py --symbol XAUUSD --days 365 --split-ratio 0.7
```

### 3. จูน parameter ของ trend strategy

```bash
python scripts/run_trend_grid_search.py --symbol XAUUSD --days 365 --split-ratio 0.7 --fast-emas 34,50 --slow-emas 150,200 --buy-levels 35,40 --sell-levels 60,65 --atr-multipliers 1.2,1.5 --rr-values 1.5,2.0 --top 8
```

### 4. สร้าง forward test report จาก trade history

```bash
python scripts/run_forward_test_report.py --trades-csv=reports/trend_following_365d_trades.csv --strategy=trend_following
```

### 5. ประเมิน operational guard จากไฟล์ trades

```bash
python scripts/run_operational_guard_check.py --trades-csv=reports/trend_following_365d_trades.csv
```

## วิธีใช้งานจริงแบบแนะนำ

ลำดับที่แนะนำ:

1. ตั้งค่า `.env`
2. เช็ก [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml)
3. เปิด `risk.allow_live_trading=true`
4. ทดสอบ Telegram ให้ส่งได้
5. รันผ่าน `start_live_bot.ps1`
6. ถ้าต้องการให้เปิดเองตอน logon ให้ลงทะเบียน Task Scheduler
7. ติดตามสถานะจากมือถือผ่าน MT5 app และ Telegram

## คำเตือน

- บอทนี้มีระบบป้องกันความเสี่ยง แต่ไม่สามารถรับประกันกำไรได้
- MT5, broker execution, spread, slippage, symbol suffix และ quality ของข้อมูลย้อนหลัง มีผลต่อผลลัพธ์จริง
- ควรทดลองบน Demo หรือขนาด lot เล็กก่อน
- ถึงแม้ระบบจะรันอัตโนมัติได้มากขึ้น แต่ควรเช็ก log/Telegram เป็นระยะ

## เช็กคุณภาพโค้ด

รัน test:

```bash
python -m unittest discover -s tests
```

## เอกสารเสริม

- [FORWARD_TEST_CHECKLIST.md](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/FORWARD_TEST_CHECKLIST.md)

เอกสารนี้ใช้สำหรับเช็ก readiness ก่อนขยับจาก Demo ไป Live
