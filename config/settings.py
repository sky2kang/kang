"""
키움증권 API 설정 파일
"""
import os
from dotenv import load_dotenv

load_dotenv()

# 계좌 설정
ACCOUNT_NUMBER = os.getenv("KIWOOM_ACCOUNT", "")  # 계좌번호 (환경변수로 관리)
IS_SIMUL = os.getenv("KIWOOM_SIMUL", "True") == "True"  # True: 모의투자, False: 실거래

# 매매 설정 (지표 전략 모드 기본값)
MAX_BUY_AMOUNT = int(os.getenv("MAX_BUY_AMOUNT", "1000000"))   # 1회 최대 매수금액 (원)
MAX_STOCK_COUNT = int(os.getenv("MAX_STOCK_COUNT", "5"))        # 최대 보유 종목수
STOP_LOSS_RATE = float(os.getenv("STOP_LOSS_RATE", "-0.05"))   # 손절 기준 (-5%)
TAKE_PROFIT_RATE = float(os.getenv("TAKE_PROFIT_RATE", "0.10"))  # 익절 기준 (+10%)

# 조건검색 모드 전용 설정 (미지정 시 위 기본값을 그대로 사용)
COND_MAX_BUY_AMOUNT = int(os.getenv("COND_MAX_BUY_AMOUNT", str(MAX_BUY_AMOUNT)))
COND_MAX_STOCK_COUNT = int(os.getenv("COND_MAX_STOCK_COUNT", str(MAX_STOCK_COUNT)))
COND_STOP_LOSS_RATE = float(os.getenv("COND_STOP_LOSS_RATE", str(STOP_LOSS_RATE)))
COND_TAKE_PROFIT_RATE = float(os.getenv("COND_TAKE_PROFIT_RATE", str(TAKE_PROFIT_RATE)))

# 전략 설정
TRADE_START_TIME = "09:05"   # 매매 시작 시각 (장 시작 후 5분)
TRADE_END_TIME = "15:20"     # 매매 종료 시각 (장 마감 10분 전)

# 알림 설정 (둘 다 비워두면 알림 비활성화)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# 로그 설정
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# DB 설정
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trades.db")
