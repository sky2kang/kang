"""
키움증권 자동매매 설정.

모든 사용자 설정은 config/config.json 한 곳에 저장된다.
(GUI: settings_gui.py 로 편집)

기존 코드 호환을 위해 모듈 레벨 상수 이름(ACCOUNT_NUMBER 등)은 그대로 유지한다.
최초 실행 시 config.json 이 없으면 .env 값 + 기본값으로 자동 생성한다.
"""
import os
import json
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

# 기본 설정 (config.json 최초 생성 시 사용. .env 값이 있으면 우선 시드)
DEFAULT_CONFIG = {
    "account": os.getenv("KIWOOM_ACCOUNT", ""),
    "is_simul": os.getenv("KIWOOM_SIMUL", "True") == "True",
    "max_buy_amount": int(os.getenv("MAX_BUY_AMOUNT", "1000000")),
    "max_stock_count": int(os.getenv("MAX_STOCK_COUNT", "5")),
    "stop_loss_rate": float(os.getenv("STOP_LOSS_RATE", "-0.05")),
    "take_profit_rate": float(os.getenv("TAKE_PROFIT_RATE", "0.10")),
    "trade_start_time": "09:05",
    "trade_end_time": "15:20",
    "strategy": "ma",            # "ma" 또는 "rsi"
    "ma_short": 5,
    "ma_long": 20,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "check_interval_min": 5,     # 전략 점검 주기(분)
    "log_level": os.getenv("LOG_LEVEL", "INFO"),
    # 조건검색 자동매매 규칙 (키: 조건식 index 문자열)
    # {"0": {"name": "...", "enabled": true, "buy_on_entry": true,
    #        "sell_on_exit": true, "buy_amount": 1000000,
    #        "stop_loss": -5.0, "take_profit": 10.0}}
    "condition_rules": {},
    "watch_list": [
        {"code": "005930", "name": "삼성전자"},
        {"code": "000660", "name": "SK하이닉스"},
        {"code": "035420", "name": "NAVER"},
        {"code": "051910", "name": "LG화학"},
        {"code": "006400", "name": "삼성SDI"},
        {"code": "035720", "name": "카카오"},
        {"code": "207940", "name": "삼성바이오로직스"},
        {"code": "005490", "name": "POSCO홀딩스"},
    ],
}


def load_config():
    """config.json 을 읽어 기본값과 병합한 dict 반환."""
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    """설정 dict 를 config.json 에 저장."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# config.json 이 없으면 기본값으로 생성 (최초 1회)
if not os.path.exists(CONFIG_PATH):
    save_config(DEFAULT_CONFIG)

_cfg = load_config()

# ---- 기존 코드 호환 상수 (이름 유지) ----
ACCOUNT_NUMBER = _cfg["account"]
IS_SIMUL = _cfg["is_simul"]
MAX_BUY_AMOUNT = _cfg["max_buy_amount"]
MAX_STOCK_COUNT = _cfg["max_stock_count"]
STOP_LOSS_RATE = _cfg["stop_loss_rate"]
TAKE_PROFIT_RATE = _cfg["take_profit_rate"]
TRADE_START_TIME = _cfg["trade_start_time"]
TRADE_END_TIME = _cfg["trade_end_time"]
LOG_LEVEL = _cfg["log_level"]

# ---- 추가 노출 (main.py 에서 사용) ----
STRATEGY = _cfg["strategy"]
MA_SHORT = _cfg["ma_short"]
MA_LONG = _cfg["ma_long"]
RSI_PERIOD = _cfg["rsi_period"]
RSI_OVERSOLD = _cfg["rsi_oversold"]
RSI_OVERBOUGHT = _cfg["rsi_overbought"]
CHECK_INTERVAL_MIN = _cfg["check_interval_min"]
WATCH_LIST = _cfg["watch_list"]
CONDITION_RULES = _cfg.get("condition_rules", {})

# ---- 조건검색 모드 전용 설정 (미지정 시 위 기본값을 그대로 사용) ----
COND_MAX_BUY_AMOUNT = int(os.getenv("COND_MAX_BUY_AMOUNT", str(MAX_BUY_AMOUNT)))
COND_MAX_STOCK_COUNT = int(os.getenv("COND_MAX_STOCK_COUNT", str(MAX_STOCK_COUNT)))
COND_STOP_LOSS_RATE = float(os.getenv("COND_STOP_LOSS_RATE", str(STOP_LOSS_RATE)))
COND_TAKE_PROFIT_RATE = float(os.getenv("COND_TAKE_PROFIT_RATE", str(TAKE_PROFIT_RATE)))

# ---- 안전장치 설정 (초보자 보호) ----
DAILY_LOSS_LIMIT_RATE = float(os.getenv("DAILY_LOSS_LIMIT_RATE", "-0.10"))  # 일일 손실 한도
MAX_ORDERS_PER_DAY = int(os.getenv("MAX_ORDERS_PER_DAY", "20"))             # 일일 주문 한도
MIN_AVAILABLE_CASH = int(os.getenv("MIN_AVAILABLE_CASH", "10000"))          # 최소 주문가능액

# ---- 알림 설정 (둘 다 비워두면 알림 비활성화) ----
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ---- 경로 ----
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(BASE_DIR, "data", "trades.db")
