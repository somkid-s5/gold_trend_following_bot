from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
import os
import logging

logger = logging.getLogger("gold_trading_bot")

API_KEY_NAME = "X-Titan-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

_INSECURE_DEFAULTS = {
    "TITAN_SECURE_BY_DEFAULT_CHANGE_ME",
    "your_secure_api_key_for_dashboard",
    "",
}

def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_api_key = os.getenv("API_KEY", "")
    
    if expected_api_key in _INSECURE_DEFAULTS:
        logger.warning("API_KEY is not configured! Set a secure API_KEY in .env")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API_KEY is not configured. Set a secure API_KEY in .env before using the dashboard.",
        )
    
    if api_key_header == expected_api_key:
        return api_key_header
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials. Invalid API Key.",
    )
