"""
키움증권 자동매매 메인 실행 파일

실행 방법:
  python main.py                  # 기본 실행 (MA 전략)
  python main.py --strategy rsi   # RSI 전략
  python main.py --simul false    # 실거래 모드 (주의!)
"""
import os
import sys
import argparse

# Qt 플랫폼 플러그인 경로 보정
# (시스템에 Anaconda 등 다른 Qt가 PATH에 있으면 자동 탐지가 실패하므로,
#  venv 내 PyQt5 플러그인 경로를 명시적으로 지정한다. 이미 설정돼 있으면 존중.)
if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    import PyQt5
    _plugins = os.path.join(
        os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms"
    )
    if os.path.isdir(_plugins):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugins

import schedule
import time

from PyQt5.QtWidgets import QApplication

from config.settings import (
    IS_SIMUL, ACCOUNT_NUMBER, STRATEGY, WATCH_LIST, CHECK_INTERVAL_MIN,
    MA_SHORT, MA_LONG, RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
)
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.trader import Trader
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.logger import get_logger

logger = get_logger("main")

# 감시 종목 / 전략 / 주기 등 모든 설정은 config/config.json 에서 읽는다.
# (GUI: settings_gui.py 로 편집)


def parse_args():
    parser = argparse.ArgumentParser(description="키움증권 자동매매")
    parser.add_argument("--strategy", choices=["ma", "rsi"], default=STRATEGY)
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

    # 접속 서버 진단 (GetServerGubun: "1"=모의투자, 그 외=실거래 실서버)
    server_gubun = kiwoom.get_login_info("GetServerGubun")
    server_str = "모의투자" if server_gubun == "1" else "실거래(실서버)"
    user_name = kiwoom.get_login_info("USER_NAME")
    logger.info(f"접속 서버: {server_str} (GetServerGubun={server_gubun!r}), 사용자: {user_name}")
    if is_simul and server_gubun != "1":
        logger.warning("주의: .env는 모의투자(KIWOOM_SIMUL=True)인데 실서버에 접속됨! "
                       "로그인 창에서 '모의투자 접속'을 체크했는지 확인하세요.")

    account = ACCOUNT_NUMBER if ACCOUNT_NUMBER else accounts[0]
    logger.info(f"사용 계좌: {account}")

    # 3) 전략 선택 (파라미터는 config.json 값 사용)
    if args.strategy == "ma":
        strategy = MAStrategy(short_period=MA_SHORT, long_period=MA_LONG)
    else:
        strategy = RSIStrategy(period=RSI_PERIOD, oversold=RSI_OVERSOLD, overbought=RSI_OVERBOUGHT)

    # 4) 모듈 초기화
    mdata = MarketDataAPI(kiwoom)
    trader = Trader(kiwoom, account, mdata, strategy, is_simul=is_simul)

    # 5) 포지션 동기화
    summary = trader.sync_positions()
    logger.info(f"계좌 현황 - 총평가: {summary['total_eval']:,}원, "
                f"수익률: {summary['total_profit_rate']:.2f}%, "
                f"주문가능: {summary['available']:,}원")

    # 6) 스케줄러 설정
    # 설정한 주기마다 전략 실행
    schedule.every(CHECK_INTERVAL_MIN).minutes.do(trader.run_strategy, watch_list=WATCH_LIST)
    # 매일 장 종료 후 잔고 저장
    schedule.every().day.at("15:40").do(_save_daily_summary, trader, mdata, account, is_simul)

    logger.info(f"자동매매 스케줄러 시작 ({CHECK_INTERVAL_MIN}분 간격)")
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
