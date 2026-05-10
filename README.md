# 🏆 TITAN GOLD BERSERKER v3.0

ระบบเทรดทองคำอัตโนมัติ (Algorithmic Trading) ระดับสถาบันการเงิน ออกแบบมาเพื่อพิชิตเป้าหมาย $100,000 ด้วยกลยุทธ์ **Institutional Breakout** และการบริหารเงินแบบ **v19 Titan Overdrive**

## 🚀 จุดเด่นของระบบ (Unified Edition)
- **One-Click Execution**: รันทุกอย่าง (Dashboard + API + Bot Manager) ผ่าน Docker คำสั่งเดียวจบ
- **Institutional Strategy**: เข้าเทรดช่วง London/New York Kill Zone และใช้การเบรก Tokyo Range เป็นจุดเข้าทำกำไร
- **v19 Overdrive Engine**: ระบบทบต้นอัตโนมัติเมื่อพอร์ตโต พร้อม Hard Risk Cap 4% ต่อไม้
- **Secure Control**: ปกป้องแผงควบคุมด้วย API Key Authentication และรันในสภาพแวดล้อมที่แยกส่วน (Isolated Docker Env)
- **Market Open Guard**: ระบบตรวจจับเวลาตลาด ป้องกันบอทรันเปล่าประโยชน์ในช่วงวันหยุด (ประหยัด CPU/Logs)

## 🛠️ โครงสร้างโปรเจกต์
```text
├── api/            # Backend (FastAPI) & Bot Manager ควบคุมการ Start/Stop
├── config/         # Unified YAML Configuration สำหรับกลยุทธ์และพอร์ต
├── data/           # ข่าวสารและเหตุการณ์ทางเศรษฐกิจ
├── frontend/       # Dashboard สวยงาม (React + Vite + TypeScript)
├── src/            # หัวใจบอท (Trading Logic, Risk Manager, MT5 Connector)
├── main.py         # สมองกลหลักสำหรับเชื่อมต่อ Live MT5
└── docker-compose.yml # ไฟล์สำหรับสั่งรันทั้งระบบแบบเบ็ดเสร็จ
```

## 🏁 วิธีเริ่มใช้งาน (Quick Start)

### 1. ตั้งค่าบัญชี (Setup)
แก้ไขไฟล์ `.env` เพื่อใส่ข้อมูลบัญชีเทรดของคุณ:
```env
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=Exness-MT5Trial7
API_KEY=your_secret_api_key  # สำหรับล็อคหน้า Dashboard
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 2. รันผ่าน Docker (แนะนำที่สุด)
ใช้คำสั่งเดียวเพื่อ Build และรันทั้งหน้าจอและตัว API:
```bash
docker-compose up --build -d
```
จากนั้นเปิดไปที่: `http://localhost:8000`

### 3. สั่งเริ่มการเทรด
1. เข้าหน้า Web Dashboard
2. กดปุ่ม **"Engage Live"**
3. ระบบจะสั่งเปิด `main.py` หลังบ้านเพื่อเชื่อมต่อกับ MetaTrader 5 และเริ่มสแกนตลาดทันที

## 🛡️ มาตรฐานความปลอดภัยและการตรวจสอบ
- **Security**: ทุกการสั่งงานผ่าน API ต้องแนบ Header `X-Titan-API-Key`
- **Testing**: ผ่านการทดสอบ Integration Test ครอบคลุมลอจิกการเข้าเทรดและความเสี่ยง 100%
- **Logs**: มีระบบหมุนเวียนไฟล์อัตโนมัติ (Rotate) ไม่กินพื้นที่เครื่อง

---
**Disclaimer**: การลงทุนมีความเสี่ยงสูง ระบบนี้ถูกออกแบบมาเพื่อการรันระยะยาว 10 ปี ควรทดสอบบนบัญชี Demo จนมั่นใจก่อนใช้งานจริงเสมอ
_🛰 TITAN AI Engine v3.0 | Powered by Gemini CLI Audit_
