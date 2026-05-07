# Runbook ภาษาไทย

เอกสารนี้คือคู่มือใช้งานสั้นๆ สำหรับเปิดบอท, ตรวจสถานะ, และรับมือเวลาระบบมีปัญหา

## ก่อนเริ่ม

ตรวจ 5 อย่างนี้ก่อนทุกครั้ง:

1. MT5 เปิดอยู่และล็อกอินบัญชี Demo ที่ถูกต้อง
2. ไฟล์ [\.env](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/.env) มีค่า `MT5_*` และ `TELEGRAM_*` ครบ
3. [config.yaml](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/config/config.yaml) เปิด `risk.allow_live_trading: true`
4. เปิดใช้งานเฉพาะ `trend_following`
5. อินเทอร์เน็ตและ Telegram ใช้งานได้

## วิธีเปิดบอท

วิธีที่แนะนำ:

```powershell
cd D:\MASTER\PROJECTS\Algorithmic Trading\gold_trading_bot
powershell -ExecutionPolicy Bypass -File .\scripts\start_live_bot.ps1 -Symbol XAUUSD -Strategy trend_following
```

ถ้าต้องการให้เริ่มเองตอน logon:

```powershell
cd D:\MASTER\PROJECTS\Algorithmic Trading\gold_trading_bot
powershell -ExecutionPolicy Bypass -File .\scripts\register_live_bot_task.ps1 -TaskName GoldTradingBot -Symbol XAUUSD -Strategy trend_following
```

## วิธีเช็กว่าบอทยังทำงานอยู่ไหม

ดู 3 จุดนี้:

- [runtime_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/runtime_status.json)
- [guard_status.json](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/reports/guard_status.json)
- [gold_trading_bot.log](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/logs/gold_trading_bot.log)

ความหมาย:

- `runtime_status.json`
  - `running` = ระบบยังทำงาน
  - `paused` = guard หยุดเปิดไม้ใหม่
  - `halted` = ระบบหยุดเพราะ risk breach
- `guard_status.json`
  - ใช้ดูว่า performance ล่าสุดยังผ่านเกณฑ์หรือไม่
- `gold_trading_bot.log`
  - ใช้ดู error, reconnect, order events

## สิ่งที่คุณจะเห็นใน Telegram

บอทจะส่ง:

- สรุปรายวัน
- แจ้งเตือน startup
- แจ้งเตือน shutdown
- แจ้งเตือน error
- แจ้งเตือน guard pause

ถ้าไม่มีข้อความเข้าเลย ให้เช็ก:

1. `TELEGRAM_BOT_TOKEN`
2. `TELEGRAM_CHAT_ID`
3. คุณเคยกด `Start` กับบอทแล้ว

## ถ้าบอทไม่เปิดออเดอร์

ให้เช็กตามนี้:

1. Guard อาจอยู่สถานะ `PAUSE`
2. อยู่ในช่วงข่าวแรงตาม `news_filter`
3. spread สูงเกิน limit
4. ยังไม่มี signal จาก `trend_following`
5. MT5 disconnect ชั่วคราว

## ถ้าระบบ error หรือ MT5 หลุด

ระบบจะพยายาม reconnect เองตาม `trading.reconnect_seconds`

สิ่งที่ควรทำ:

1. ดู Telegram ว่ามี error alert หรือไม่
2. เปิด [gold_trading_bot.log](/D:/MASTER/PROJECTS/Algorithmic%20Trading/gold_trading_bot/logs/gold_trading_bot.log)
3. เช็กว่า MT5 ยังเปิดอยู่และบัญชียังล็อกอินอยู่

## ถ้าต้องการหยุดบอท

ถ้ารันจาก PowerShell:

- กด `Ctrl + C`

ถ้ารันจาก Task Scheduler:

- เปิด Task Scheduler
- หา task ชื่อ `GoldTradingBot`
- กด `End` หรือ `Disable`

## วิธีเช็ก performance แบบเร็ว

ถ้ามีไฟล์ trades CSV อยู่แล้ว:

```powershell
python .\scripts\run_forward_test_report.py --trades-csv=reports\trend_following_365d_trades.csv --strategy=trend_following
python .\scripts\run_operational_guard_check.py --trades-csv=reports\trend_following_365d_trades.csv
```

## เกณฑ์ใช้งานแบบแนะนำ

- ใช้บัญชี Demo ก่อน
- เริ่ม lot เล็ก
- เช็ก Telegram ทุกวัน
<!-- FIXED: 10 -->
- อัพเดท data/news_events.json ก่อนเปิดสัปดาห์ใหม่
- ถ้า guard เข้า `PAUSE` อย่าฝืนเปิด live ต่อจนกว่าจะเข้าใจสาเหตุ

## สรุปสั้นๆ

ถ้าจะใช้งานจริงแบบง่ายที่สุด:

1. ตั้ง `.env`
2. เปิด MT5
3. รัน `start_live_bot.ps1`
4. ดูสถานะจากมือถือผ่าน MT5 app และ Telegram
