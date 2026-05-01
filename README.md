# 🏆 TITAN GOLD BERSERKER - 100K OVERDRIVE ENGINE

ระบบเทรดทองคำอัตโนมัติ (Algorithmic Trading) ระดับสถาบันการเงิน ออกแบบมาเพื่อพิชิตเป้าหมาย $100,000 ด้วยกลยุทธ์ **Institutional Breakout** และการบริหารเงินแบบ **Dual-Phase Scaling**

## 🚀 จุดเด่นของระบบ (Production Edition)
- **Strategy:** Institutional Breakout (Tokyo Trap Guard) - เข้าเทรดเฉพาะช่วง London/New York และรอให้ราคาทะลุกรอบเอเชียเพื่อความแม่นยำสูงสุด
- **Risk Management:** v19 Titan Overdrive - ระบบทบต้น 2 ระยะที่จะเร่งความเร็วในการทำกำไรเมื่อพอร์ตโตเกิน $10,000
- **Safety:** Hard 4% Risk Cap ต่อไม้ และ Correlation Guard ป้องกันการโอเวอร์เทรดในคู่เงินที่วิ่งตามกัน
- **Dashboard:** ระบบหน้าจอควบคุมแบบ Real-time ผ่าน Streamlit

## 🏗️ โครงสร้างโปรเจกต์
- `main.py`: ศูนย์กลางควบคุมบอทในโหมด Live Portfolio
- `src/strategies/`: สมองกลที่ใช้กรองเทรนด์และจุดเข้าเทรด
- `src/risk/`: ระบบบริหารเงินระดับสถาบัน (Overdrive Engine)
- `dashboard.py`: หน้าจอแสดงผล PNL และสถานะพอร์ตแบบสดๆ

## 🏁 วิธีเริ่มใช้งาน (Quick Start)
1. **ติดตั้ง Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **ตั้งค่าบัญชี:** แก้ไขไฟล์ `.env` ใส่ MT5 Login, Password และ Server ให้เรียบร้อย
3. **เริ่มรันบอท (Titan Mode):**
   ```bash
   python main.py --mode live
   ```
4. **เปิดแผงควบคุม (Dashboard):**
   ```bash
   streamlit run dashboard.py
   ```

---
**Disclaimer**: การลงทุนมีความเสี่ยง ระบบนี้ถูกออกแบบมาเพื่อการรันแบบ DCA ระยะยาว 10 ปี ควรทดสอบบนบัญชี Demo ก่อนใช้งานจริงเสมอ
