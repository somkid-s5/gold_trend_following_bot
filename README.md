# 🏆 TITAN BERSERKER v3.0

ระบบเทรดอัตโนมัติ (Algorithmic Trading) ระดับสถาบันการเงิน ออกแบบมาเพื่อบริหารพอร์ตโฟลิโอ (Multi-Symbol) ด้วยกลยุทธ์ **Institutional Trend Following** และการบริหารเงินแบบ **v19 Titan Overdrive**

## 🚀 จุดเด่นของระบบ (Unified Edition)
- **Multi-Symbol Portfolio**: รันหลายคู่เงินพร้อมกัน (เช่น XAUUSD, EURUSD, BTCUSD) จัดการความเสี่ยงแบบรวมศูนย์
- **One-Click Execution**: รันทุกอย่าง (Dashboard + API + Bot Manager) ผ่าน Docker หรือ PowerShell สคริปต์เดียวจบ
- **Institutional Strategy**: กลยุทธ์ตามเทรนระดับสถาบัน พร้อมระบบ Trailing Stop และ Breakeven อัตโนมัติ
- **v19 Overdrive Engine**: ระบบคำนวณ Lot ทบต้นอัตโนมัติ (Scaling Delta) พร้อม Hard Risk Cap ต่อไม้
- **Secure Control**: ปกป้องแผงควบคุมด้วย API Key Authentication และรันในสภาพแวดล้อมที่แยกส่วน
- **Unified Backtest**: ระบบทดสอบย้อนหลังที่แม่นยำ รองรับทั้งการรันแบบปกติและการรันแบบ DCA (Monthly Investment)

## 🛠️ โครงสร้างโปรเจกต์
```text
├── api/            # Backend (FastAPI) & Bot Manager ควบคุมการ Start/Stop
├── config/         # Unified YAML Configuration (จัดการ Symbols และ Risk)
├── data/           # ข้อมูลข่าวสารและไฟล์ข้อมูล CSV สำหรับการทดสอบ
├── frontend/       # Dashboard สวยงาม (React + Vite + TypeScript)
├── scripts/        # สคริปต์ช่วยรันระบบ และระบบ Backtest รวมศูนย์
├── src/            # หัวใจบอท (Trading Logic, Risk Manager, MT5 Connector)
├── main.py         # สมองกลหลักสำหรับเชื่อมต่อ Live MT5 (Portfolio Engine)
└── docker-compose.yml # ไฟล์สำหรับสั่งรันทั้งระบบแบบเบ็ดเสร็จ
```

## 🏁 วิธีเริ่มใช้งาน (Quick Start)

### 1. ตั้งค่าบัญชี (Setup)
สร้างไฟล์ `.env` (ดูตัวอย่างจาก `.env.example`) เพื่อใส่ข้อมูลบัญชีเทรด:
```env
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial7
API_KEY=your_secret_api_key  # สำหรับล็อคหน้า Dashboard
```

### 2. รันระบบ (Execution)
**ผ่าน Docker (แนะนำ):**
```bash
docker-compose up --build -d
```
จากนั้นเปิดไปที่: `http://localhost:8000`

**ผ่าน PowerShell (Local):**
```powershell
.\scripts\start_webapp.ps1
```

### 3. การทดสอบย้อนหลัง (Backtesting)
สามารถรันผ่าน Dashboard หรือใช้ Command Line:
```bash
# ทดสอบแบบมาตรฐาน
python scripts/run_backtest.py --symbol XAUUSDm --days 365

# ทดสอบแบบพอร์ตโฟลิโอ DCA
python scripts/run_backtest.py --type dca --days 720 --balance 10000 --dca 200
```

## 🛡️ มาตรฐานความปลอดภัยและการตรวจสอบ
- **Security**: ทุกการสั่งงานผ่าน API ต้องแนบ Header `X-Titan-API-Key`
- **Verification**: ระบบผ่านการแก้ไข Linting และ Type Safety 100% เพื่อความเสถียรสูงสุด
- **Logs**: มีระบบหมุนเวียนไฟล์อัตโนมัติ (Rotate) ในโฟลเดอร์ `logs/`

---
**Disclaimer**: การลงทุนมีความเสี่ยงสูง ระบบนี้ถูกออกแบบมาเพื่อการรันระยะยาว 10 ปี ควรทดสอบบนบัญชี Demo จนมั่นใจก่อนใช้งานจริงเสมอ
_🛰 TITAN AI Engine v3.0 | Portfolio Edition_
