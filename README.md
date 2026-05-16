# 🏆 TITAN SINGULARITY v4.0 (God Mode)

ระบบเทรดอัตโนมัติ (Algorithmic Trading) ระดับสูงสุดที่ถูกปลดลิมิตเพื่อการทำกำไรแบบทวีคูณ (Exponential Growth) ด้วยกลยุทธ์ **Institutional Trend Pyramiding** และการบริหารเงินแบบ **Full Real-time Compounding (Singularity Scaling)** พร้อมระบบความปลอดภัยอัจฉริยะ (Dynamic Risk)

## 🚀 จุดเด่นของระบบ (God Mode Edition)
- **Singularity Scaling**: ถอดระบบ Scaling Delta แบบขั้นบันไดออก คำนวณ Lot ใหม่ทุกวินาทีจาก Equity 100% ทำให้พอร์ตเติบโตแบบก้าวกระโดด
- **Exponential Pyramiding**: ระบบถมไม้ตามน้ำ สูงสุด 10 ไม้ ทุกๆ การขยับของราคา 2.0 ATR ในเทรนด์หลัก (EMA 200 Anchor)
- **Smart Aggression**: ความเสี่ยงเริ่มต้น 15% ต่อไม้เพื่อเร่งกำไร แต่จะลดความเสี่ยงอัตโนมัติเหลือ 5% หากแพ้ เพื่อป้องกัน Drawdown แบบต่อเนื่อง
- **Ultra-Fast Breakeven**: เลื่อน SL บังทุนไวเป็นพิเศษที่ RR 0.5 และปิดกำไร 50% ทันทีที่ RR 2.0 เพื่อล็อกกำไรเข้ากระเป๋าให้เร็วที่สุด
- **Zero Friction**: ไม่หลบข่าว ปะทะทุกความผันผวนของ NFP/FOMC เพื่อจับรอบ Breakout รุนแรง

## 🛠️ โครงสร้างโปรเจกต์
```text
├── api/            # Backend (FastAPI) & Bot Manager ควบคุมการ Start/Stop
├── config/         # Unified YAML Configuration (จัดการ Symbols และ Risk)
├── data/           # ข้อมูลข่าวสารและไฟล์ข้อมูล CSV สำหรับการทดสอบ
├── frontend/       # Dashboard สวยงาม (React + Vite + TypeScript)
├── scripts/        # สคริปต์ช่วยรันระบบ และระบบ Backtest รวมศูนย์
├── src/            # หัวใจบอท (Trading Logic, Risk Manager, MT5 Connector)
├── main.py         # สมองกลหลักและตัวเปิดระบบ Dashboard (Entry Point)
└── .env            # ไฟล์เก็บค่า Config ลับ (Credentials)
```

## 🏁 วิธีเริ่มใช้งาน (Quick Start)

### 1. ติดตั้งสภาพแวดล้อม (Installation)
แนะนำให้ใช้งานผ่าน Python 3.12+ บน Windows:
```powershell
# ติดตั้ง Library ที่จำเป็น
pip install -r requirements.txt
```
_หมายเหตุ: สำหรับการพัฒนาหน้าจอ Dashboard ครั้งแรก ต้อง build frontend ด้วยคำสั่ง `cd frontend; npm install; npm run build` เพื่อให้ main.py แสดงผล UI ได้_

### 2. ตั้งค่าบัญชี (Setup)
สร้างไฟล์ `.env` จากตัวอย่าง `.env.example`:
```env
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial7
API_KEY=your_secret_api_key  # สำหรับล็อคหน้า Dashboard
```

### 3. รันระบบ (Execution)
รันเพียงคำสั่งเดียวเพื่อเริ่มต้นการเทรดและเปิดหน้า Dashboard:

```powershell
python main.py
```

- **Dashboard**: `http://localhost:8000` (แสดงผล UI อัตโนมัติหากมีการ build แล้ว)
- **API Docs**: `http://localhost:8000/docs`

### 4. การทดสอบย้อนหลัง (Backtesting)
สามารถรันผ่าน Dashboard (หน้า Backtest Lab) หรือใช้ Command Line:
```bash
# ทดสอบแบบมาตรฐาน (Single Symbol)
python scripts/run_backtest.py --symbol XAUUSDm --days 365

# ทดสอบแบบพอร์ตโฟลิโอ DCA (Monthly Investment)
python scripts/run_backtest.py --type dca --days 720 --balance 10000 --dca 200
```

## 🛡️ การปรับปรุงล่าสุด (Singularity V4.0)
- **God Mode Activated**: การออกแบบเชิงคณิตศาสตร์ที่รีดศักยภาพกำไรของทองคำในระดับทวีคูณ (Pyramiding + 100% Compounding)
- **Ultra-Integrated**: `main.py` ทำหน้าที่เป็น Orchestrator จัดการทั้งการเทรดและ API Dashboard ในตัวเดียว
- **High Contrast UI**: ปรับโทนสีข้อความและเส้นขอบให้สว่างขึ้น มองเห็นชัดเจนบนพื้นหลัง AMOLED Dark
- **Docker Removed**: คลีนไฟล์ Docker ออกทั้งหมดเพื่อความเบาและรวดเร็วในการรันแบบ Local

---
**Disclaimer**: การลงทุนมีความเสี่ยงสูง ระบบนี้ถูกออกแบบมาเพื่อการรันความเสี่ยงสูง (High Risk, Extreme Reward) โปรดใช้งานด้วยความระมัดระวังและทดสอบจนเข้าใจพฤติกรรมพอร์ตก่อนเสมอ
_🛰 TITAN AI Engine v4.0 | Singularity (God Mode) Edition_