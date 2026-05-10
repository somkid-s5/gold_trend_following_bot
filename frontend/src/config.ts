/** Centralized API configuration */
const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
const API_KEY = import.meta.env.VITE_API_KEY || 'TITAN_SECURE_BY_DEFAULT_CHANGE_ME';
const API_KEY_HEADER = 'X-Titan-API-Key';

export const API = {
  BASE: API_BASE,
  KEY: API_KEY,
  HEADER: API_KEY_HEADER,
  BOT: {
    STATUS: `${API_BASE}/api/bot/status`,
    START: `${API_BASE}/api/bot/start`,
    STOP: `${API_BASE}/api/bot/stop`,
    BACKTEST: `${API_BASE}/api/bot/backtest`,
  },
  CONFIG: {
    GET: `${API_BASE}/api/config`,
    UPDATE: `${API_BASE}/api/config`,
  },
  MONITOR: {
    STATUS: `${API_BASE}/api/monitor/status`,
    LOGS: `${API_BASE}/api/monitor/logs`,
    TRADES: `${API_BASE}/api/monitor/trades`,
  },
} as const;
