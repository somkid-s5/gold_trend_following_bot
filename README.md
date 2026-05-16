# ⚡ TITAN Berserker v3.0 — Institutional Gold Trading Bot

ระบบเทรดทองคำอัตโนมัติ (Algorithmic Trading) ที่ใช้กลยุทธ์ **Institutional Trend Following** พร้อมระบบ Risk Management ระดับมืออาชีพ

## 🎯 กลยุทธ์หลัก (Strategy)
- **Tokyo Range Breakout**: วิเคราะห์ช่วง Asian Session (00:00-08:00 UTC) แล้วเข้าเทรด Breakout ในช่วง London-NY Overlap (12:00-18:00 UTC)
- **Triple Filter**: กรอง Signal ด้วย EMA 200 (Trend), RSI 14 (Momentum), ADX 14 (Trend Strength) — เข้าเฉพาะ trade คุณภาพสูง
- **Smart Exit**: ขยับ SL มา Breakeven ที่ RR 0.5, ปิดกำไร 50% ที่ RR 2.0, TP เต็มที่ RR 3.0
- **Protective Risk**: ลด risk อัตโนมัติหลังแพ้ (2% → 1.5% → 1%), boost เล็กน้อยหลังชนะ 3+ ครั้ง (max 1.3x)

## 📊 ผลการทดสอบ (Backtest Results)
| Period | Balance | Trades | Win Rate | Max DD | ROI |
|--------|---------|--------|----------|--------|-----|
| 1 Year ($10K) | $24,334 | 145 | 70.3% | 5.5% | +143% |
| 10 Years ($200) | $7.08M | 1,738 | 66.7% | 16.1% | compound |

> ⚠️ ผลทดสอบรวม Spread (3 pts), Slippage (0-1.5 pts), Multi-bar holding, และ Commission แล้ว

## 🛠️ โครงสร้างโปรเจกต์
```text
├── api/              # FastAPI Backend — Bot control API + Dashboard
├── config/           # YAML Configuration (Symbols, Risk, Strategy)
├── frontend/         # Dashboard UI (React + Vite + TypeScript)
├── scripts/          # Backtest runner + utility scripts
├── src/
│   ├── broker/       # MT5 Connector
│   ├── core/         # Trading Engine, Exit Logic, Operational Guards
│   ├── data/         # Data fetching
│   ├── risk/         # Risk Manager (DD limits, lot calculation, exposure)
│   ├── strategies/   # Trend Following strategy
│   └── utils/        # Backtester, Logger, Telegram Notifier
├── main.py           # Entry point — starts bot + API server
└── .env              # Credentials (MT5, Telegram, API Key)
```

## 🏁 Quick Start

### 1. ติดตั้ง (Installation)
```powershell
# Python 3.12+ on Windows required (MT5 dependency)
pip install -r requirements.txt

# Build Dashboard (ครั้งแรกเท่านั้น)
cd frontend && npm install && npm run build && cd ..
```

### 2. ตั้งค่า (Configuration)
สร้างไฟล์ `.env` จากตัวอย่าง:
```env
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial7
MT5_PATH=C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe

API_KEY=your_secret_api_key     # สำหรับ Dashboard authentication
TELEGRAM_BOT_TOKEN=your_token   # แจ้งเตือนผ่าน Telegram
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. รันระบบ (Run)
```powershell
python main.py
```
- **Dashboard**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Telegram**: แจ้งเตือนอัตโนมัติทุก trade + daily summary

### 4. Backtesting
```bash
# Standard Backtest (1 ปี, ทุน $10,000)
python scripts/run_backtest.py --symbol XAUUSDm --days 365 --balance 10000

# DCA Backtest (เติมเงินรายเดือน)
python scripts/run_backtest.py --type dca --days 365 --balance 10000 --dca 200

# ปรับ Risk per trade
python scripts/run_backtest.py --symbol XAUUSDm --days 365 --balance 10000 --risk 1.5
```

## 🛡️ Risk Management
| Parameter | ค่า | อธิบาย |
|-----------|------|--------|
| Risk per Trade | 2% | ความเสี่ยงต่อ trade (ลดอัตโนมัติหลัง loss) |
| Max Daily Loss | 5% | หยุดเทรดถ้าขาดทุนเกิน 5% ต่อวัน |
| Max Drawdown | 20% | Circuit breaker — หยุดทั้งระบบ |
| Max Total Exposure | 10% | จำกัด risk รวมของทุก position |
| Max Spread | 50 pts | ไม่เทรดเมื่อ spread สูงผิดปกติ |

## 📐 Config อยู่ที่ `config/config.yaml`
ปรับได้ทุกค่าโดยไม่ต้องแก้โค้ด — ดู comment ในไฟล์สำหรับคำอธิบาย

---
**⚠️ Disclaimer**: การลงทุนมีความเสี่ยง ควรทดสอบบน Demo Account อย่างน้อย 1-2 สัปดาห์ก่อนใช้เงินจริง