"""
키움증권 자동매매 메인 실행 파일

실행 방법:
  python main.py                  # 기본 실행 (MA 전략)
  python main.py --strategy rsi   # RSI 전략
  python main.py --simul false    # 실거래 모드 (주의!)
"""
import sys
import argparse
import schedule
import time

from PyQt5.QtWidgets import QApplication

from config.settings import IS_SIMUL, ACCOUNT_NUMBER
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.trader import Trader
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.logger import get_logger

logger = get_logger("main")

# -----------------------------------------------------------------------
# 감시 종목 리스트 (관심 종목 직접 입력)
# -----------------------------------------------------------------------
WATCH_LIST = [
    {"code": "005930", "name": "삼성전자"},
    {"code": "000660", "name": "SK하이닉스"},
    {"code": "035420", "name": "NAVER"},
    {"code": "051910", "name": "LG화학"},
    {"code": "006400", "name": "삼성SDI"},
    {"code": "035720", "name": "카카오"},
    {"code": "207940", "name": "삼성바이오로직스"},
    {"code": "005490", "name": "POSCO홀딩스"},
]


def parse_args():
    parser = argparse.ArgumentParser(description="키움증권 자동매매")
    parser.add_argument("--strategy", choices=["ma", "rsi"], default="ma")
    parser.add_argument("--simul", choices=["true", "false"], default=str(IS_SIMUL).lower())
    return parser.parse_args()


def main():
    args = parse_args()
    is_simul = args.simul == "true"
    mode_str = "모의투자" if is_simul else "실거래 (!주의!)"

    app = QApplication(sys.argv)

    logger.info("=" * 50)
    logger.info(f"키움증권 자동매매 시작 [{mode_str}]")
    logger.info(f"전략: {args.strategy.upper()}")
    logger.info("=" * 50)

    # 1) API 초기화 및 로그인
    kiwoom = KiwoomAPI()
    kiwoom.login()

    # 2) 계좌 확인
    accounts = kiwoom.get_account_list()
    logger.info(f"보유 계좌: {accounts}")
    account = ACCOUNT_NUMBER if ACCOUNT_NUMBER else accounts[0]
    logger.info(f"사용 계좌: {account}")

    # 3) 전략 선택
    strategy = MAStrategy(short_period=5, long_period=20) if args.strategy == "ma" else RSIStrategy()

    # 4) 모듈 초기화
    mdata = MarketDataAPI(kiwoom)
    trader = Trader(kiwoom, account, mdata, strategy, is_simul=is_simul)

    # 5) 포지션 동기화
    summary = trader.sync_positions()
    logger.info(f"계좌 현황 - 총평가: {summary['total_eval']:,}원, "
                f"수익률: {summary['total_profit_rate']:.2f}%, "
                f"주문가능: {summary['available']:,}원")

    # 6) 스케줄러 설정
    # 5분마다 전략 실행
    schedule.every(5).minutes.do(trader.run_strategy, watch_list=WATCH_LIST)
    # 매일 장 종료 후 잔고 저장
    schedule.every().day.at("15:40").do(_save_daily_summary, trader, mdata, account, is_simul)

    logger.info("자동매매 스케줄러 시작 (5분 간격)")
    logger.info(f"감시 종목: {[w['name'] for w in WATCH_LIST]}")

    # 즉시 첫 실행
    trader.run_strategy(WATCH_LIST)

    # 이벤트 루프 (PyQt5 + schedule 병행)
    while True:
        app.processEvents()
        schedule.run_pending()
        time.sleep(1)


def _save_daily_summary(trader, mdata, account, is_simul):
    try:
        result = mdata.get_account_balance(account, is_simul=is_simul)
        s = result["summary"]
        trader.db.save_daily_summary(s["total_eval"], s["total_profit_rate"], s["available"])
        logger.info(f"일일 결산 저장 완료: 총평가={s['total_eval']:,}원")
    except Exception as e:
        logger.error(f"일일 결산 저장 실패: {e}")


if __name__ == "__main__":
    main()
