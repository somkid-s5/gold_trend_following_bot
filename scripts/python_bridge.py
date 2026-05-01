"""
Python MT5 Bridge: 
สคริปต์นี้ทำหน้าที่เป็น 'ศูนย์รับคำสั่ง' (Web Server) 
เพื่อรอรับคำสั่งเปิด-ปิดออเดอร์ จาก Go Engine (Goroutines)
และส่งคำสั่งเข้า MT5 แบบสายฟ้าแลบครับ!
"""

import http.server
import socketserver
import json
import threading

PORT = 8080

class MT5ExecutionHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        # 1. รับข้อมูลจาก Go Engine
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        signal = json.loads(post_data.decode('utf-8'))
        
        print(f"⚡ [PYTHON MT5 BRIDGE] Received Order Command from GO: {signal}")
        
        # 2. นำสัญญาณที่ได้ไป Execute เข้า MT5 (จำลอง)
        action = signal.get("action")
        symbol = signal.get("symbol")
        confidence = signal.get("confidence", 1.0)
        
        print(f"🚀 Executing {action} on {symbol} with confidence {confidence} via MT5 Connector...")
        # ในระบบจริง: engine._execute_signal(symbol, action, ...)
        
        # 3. ตอบกลับ Go ว่าทำงานเสร็จแล้ว
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"status": "SUCCESS"}')

def run_bridge():
    with socketserver.TCPServer(("", PORT), MT5ExecutionHandler) as httpd:
        print(f"🛡️ PYTHON MT5 BRIDGE IS RUNNING ON PORT {PORT}...")
        print("🎯 Waiting for high-speed signals from GO TITAN ENGINE...")
        httpd.serve_forever()

if __name__ == "__main__":
    run_bridge()
