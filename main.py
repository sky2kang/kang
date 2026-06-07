"""
키움증권 자동매매 메인 실행 파일

실행 방법:
  python main.py                       # 기본 실행 (MA 전략)
  python main.py --strategy rsi        # RSI 전략
  python main.py --simul false         # 실거래 모드 (주의!)
  python main.py --mode condition --condition "급등주포착,눌림목"  # 조건검색
  python main.py --analyze 005930      # 개별 종목 상세 분석
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
    COND_MAX_BUY_AMOUNT, COND_MAX_STOCK_COUNT,
    COND_STOP_LOSS_RATE, COND_TAKE_PROFIT_RATE,
    DAILY_LOSS_LIMIT_RATE, MAX_ORDERS_PER_DAY, MIN_AVAILABLE_CASH,
)
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.trader import Trader
from core.condition_trader import ConditionTrader
from core.safety_guard import SafetyGuard
from core.analyzer import StockAnalyzer
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.logger import get_logger
from utils.notifier import Notifier
from utils.report import DailyReport
from utils.log_cleaner import clean_old_logs

logger = get_logger("main")

# 감시 종목 / 전략 / 주기 등 모든 설정은 config/config.json 에서 읽는다.
# (GUI: settings_gui.py 로 편집)


def parse_args():
    parser = argparse.ArgumentParser(description="키움증권 자동매매")
    parser.add_argument("--mode", choices=["strategy", "condition"], default="strategy",
                        help="strategy: 지표 전략 매매, condition: HTS 조건검색식 매매")
    parser.add_argument("--strategy", choices=["ma", "rsi"], default=STRATEGY)
    parser.add_argument("--condition", default="",
                        help="조건검색 모드 조건식 이름. 여러 개는 쉼표로 구분 "
                             "(예: \"급등주포착,눌림목공략\")")
    parser.add_argument("--simul", choices=["true", "false"], default=str(IS_SIMUL).lower())
    parser.add_argument("--analyze", default="",
                        help="개별 종목 상세 분석 후 종료 (종목코드, 예: 005930)")
    parser.add_argument("--gui", action="store_true",
                        help="GUI 대시보드 실행")
    return parser.parse_args()


def run_analyze(code):
    """개별 종목 상세 분석 (로그인 후 분석 결과 출력하고 종료)"""
    import datetime
    app = QApplication(sys.argv)  # noqa: F841  (OCX 사용 위해 필요)
    kiwoom = KiwoomAPI()
    kiwoom.login()
    mdata = MarketDataAPI(kiwoom)
    start = (datetime.datetime.now() - datetime.timedelta(days=120)).strftime("%Y%m%d")
    df = mdata.get_daily_ohlcv(code, start)
    name = kiwoom.dynamicCall("GetMasterCodeName(QString)", code).strip()
    print(StockAnalyzer(df).report_text(code, name))


def main():
    args = parse_args()

    # 개별 종목 분석 모드 (분석 후 종료)
    if args.analyze:
        run_analyze(args.analyze)
        return

    # GUI 대시보드 모드
    if args.gui:
        from gui.dashboard import run_gui
        logger.info("GUI 대시보드를 실행합니다.")
        run_gui(controller=None)  # 데모 모드 (실거래 연동은 controller 주입)
        return

    is_simul = args.simul == "true"
    mode_str = "모의투자" if is_simul else "실거래 (!주의!)"

    app = QApplication(sys.argv)

    # 오래된 로그 자동 정리
    clean_old_logs(keep_days=30)

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

    # 4) 모듈 초기화 (알림 + 안전장치 + 모드별 리스크 설정)
    mdata = MarketDataAPI(kiwoom)
    notifier = Notifier()
    guard = SafetyGuard(
        daily_loss_limit_rate=DAILY_LOSS_LIMIT_RATE,
        max_orders_per_day=MAX_ORDERS_PER_DAY,
        min_available_cash=MIN_AVAILABLE_CASH,
    )

    if args.mode == "condition":
        trader = Trader(
            kiwoom, account, mdata, strategy, is_simul=is_simul,
            max_buy_amount=COND_MAX_BUY_AMOUNT,
            max_stock_count=COND_MAX_STOCK_COUNT,
            stop_loss_rate=COND_STOP_LOSS_RATE,
            take_profit_rate=COND_TAKE_PROFIT_RATE,
            notifier=notifier, safety_guard=guard,
        )
        logger.info(f"조건검색 모드 리스크 설정 - 1회매수: {COND_MAX_BUY_AMOUNT:,}원, "
                    f"최대종목: {COND_MAX_STOCK_COUNT}개, "
                    f"손절: {COND_STOP_LOSS_RATE:.0%}, 익절: {COND_TAKE_PROFIT_RATE:.0%}")
    else:
        trader = Trader(kiwoom, account, mdata, strategy, is_simul=is_simul,
                        notifier=notifier, safety_guard=guard)

    report = DailyReport(trader.db, notifier)

    # 5) 포지션 동기화 + 안전장치 기준자산 설정
    summary = trader.sync_positions()
    guard.set_baseline(summary["total_eval"])
    logger.info(f"계좌 현황 - 총평가: {summary['total_eval']:,}원, "
                f"수익률: {summary['total_profit_rate']:.2f}%, "
                f"주문가능: {summary['available']:,}원")

    # 6) 스케줄러 설정
    # 일일 손실 한도 점검 (2분마다)
    schedule.every(2).minutes.do(_check_daily_loss, guard, mdata, account, is_simul)
    # 매일 장 종료 후 잔고 저장 + 리포트 발송
    schedule.every().day.at("15:40").do(_save_daily_summary, trader, mdata, account, is_simul)
    schedule.every().day.at("15:45").do(_send_daily_report, report, mdata, account, is_simul)

    if args.mode == "condition":
        # ----- 조건검색식 기반 실시간 매매 -----
        if not args.condition:
            logger.error("조건검색 모드는 --condition '조건식이름' 인자가 필요합니다.")
            return
        # 쉼표로 구분된 여러 조건식 지원
        cond_names = [c.strip() for c in args.condition.split(",") if c.strip()]
        cond_trader = ConditionTrader(kiwoom, trader, mdata)
        cond_trader.start(cond_names)
        # 손절/익절은 3분마다 보유종목 리스크 점검으로 적용
        schedule.every(3).minutes.do(trader.check_risk)
        logger.info(f"조건검색 자동매매 가동: {cond_names} "
                    f"(편입→매수 / 이탈→매도, 손절/익절 3분 점검)")
        notifier.send(f"⚙️ 조건검색 자동매매 시작: {cond_names} "
                      f"[{'모의투자' if is_simul else '실거래'}]")
    else:
        # ----- 지표 전략 기반 매매 (config.json 주기) -----
        schedule.every(CHECK_INTERVAL_MIN).minutes.do(trader.run_strategy, watch_list=WATCH_LIST)
        logger.info(f"자동매매 스케줄러 시작 ({CHECK_INTERVAL_MIN}분 간격)")
        logger.info(f"감시 종목: {[w['name'] for w in WATCH_LIST]}")
        trader.run_strategy(WATCH_LIST)  # 즉시 첫 실행

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


def _send_daily_report(report, mdata, account, is_simul):
    """장 마감 후 일일 리포트를 알림 채널로 발송"""
    try:
        result = mdata.get_account_balance(account, is_simul=is_simul)
        report.send(account_summary=result["summary"])
        logger.info("일일 리포트 발송 완료")
    except Exception as e:
        logger.error(f"일일 리포트 발송 실패: {e}")


def _check_daily_loss(guard, mdata, account, is_simul):
    """일일 손실 한도 도달 여부 점검 (도달 시 매매 자동 중단)"""
    try:
        result = mdata.get_account_balance(account, is_simul=is_simul)
        halted = guard.update_and_check_loss(result["summary"]["total_eval"])
        if halted:
            logger.warning("일일 손실 한도 도달 - 신규 매수가 중단됩니다.")
    except Exception as e:
        logger.error(f"일일 손실 점검 실패: {e}")


if __name__ == "__main__":
    main()
