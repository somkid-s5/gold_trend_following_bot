from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os

API_KEY_NAME = "X-Titan-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key(api_key_header: str = Security(api_key_header)):
    # ดึง API Key จาก .env (ถ้าไม่มีจะใช้ค่า default เพื่อความปลอดภัยขั้นต่ำ)
    expected_api_key = os.getenv("API_KEY", "TITAN_SECURE_BY_DEFAULT_CHANGE_ME")
    
    if api_key_header == expected_api_key:
        return api_key_header
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials. Invalid API Key.",
    )
