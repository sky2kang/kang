"""
GUI 실거래 컨트롤러

Dashboard와 실거래 백엔드를 연결하는 브릿지 클래스.
PyQt5 QThread 안에서 schedule 루프를 돌려 GUI가 멈추지 않게 한다.
"""
import time
import logging
import schedule

from PyQt5.QtCore import QThread

from config.settings import (
    IS_SIMUL, ACCOUNT_NUMBER,
    COND_MAX_BUY_AMOUNT, COND_MAX_STOCK_COUNT,
    COND_STOP_LOSS_RATE, COND_TAKE_PROFIT_RATE,
)
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.safety_guard import SafetyGuard
from core.trader import Trader
from core.condition_trader import ConditionTrader
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.notifier import Notifier

logger = logging.getLogger(__name__)


class _ScheduleThread(QThread):
    """백그라운드에서 schedule.run_pending() 을 반복 실행"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True

    def run(self):
        from PyQt5.QtWidgets import QApplication
        while self._running:
            try:
                schedule.run_pending()
                QApplication.processEvents()
            except Exception as exc:
                logger.warning("schedule thread error: %s", exc)
            time.sleep(0.5)

    def stop(self):
        self._running = False


class TradingController:
    """
    Dashboard가 호출하는 인터페이스:
      start(settings) / stop() / get_status() -> dict
    """

    def __init__(self):
        self._stopped = True
        self._kiwoom = None
        self._market_data = None
        self._safety_guard = None
        self._trader = None
        self._condition_trader = None
        self._notifier = None
        self._schedule_thread = None
        self._account = ACCOUNT_NUMBER
        self._is_simul = IS_SIMUL
        self._pre_injected = False   # 이미 로그인된 kiwoom 주입 여부

    # ------------------------------------------------------------------
    def inject_kiwoom(self, kiwoom, market_data, account: str, is_simul: bool):
        """
        이미 로그인된 KiwoomAPI 인스턴스를 주입한다.
        이후 start() 호출 시 재로그인 없이 해당 세션을 재사용한다.
        """
        self._kiwoom = kiwoom
        self._market_data = market_data
        self._account = account
        self._is_simul = is_simul
        self._pre_injected = True
        logger.info("KiwoomAPI 주입 완료: account=%s, simul=%s", account, is_simul)

    # ------------------------------------------------------------------
    def start(self, settings: dict):
        """
        settings keys: buy_amount, stock_count, stop_loss, take_profit,
                       strategy, condition_name (조건검색식일 때)
        """
        try:
            # 이미 로그인된 kiwoom 이 inject 된 경우 재로그인 생략
            if not self._pre_injected:
                self._kiwoom = KiwoomAPI()
                self._kiwoom.login()
                accounts = self._kiwoom.get_account_list()
                if accounts:
                    self._account = accounts[0]
                self._market_data = MarketDataAPI(self._kiwoom)
            else:
                # inject 후 다른 계좌 선택 시 반영
                if settings.get("account"):
                    self._account = settings["account"]
            self._safety_guard = SafetyGuard()
            self._notifier = Notifier()

            buy_amount = settings.get("buy_amount", COND_MAX_BUY_AMOUNT)
            stock_count = settings.get("stock_count", COND_MAX_STOCK_COUNT)
            stop_loss = settings.get("stop_loss", COND_STOP_LOSS_RATE)
            take_profit = settings.get("take_profit", COND_TAKE_PROFIT_RATE)
            strategy_name = settings.get("strategy", "이동평균(MA)")

            if strategy_name == "RSI":
                strategy = RSIStrategy()
            else:
                strategy = MAStrategy(5, 20)

            self._trader = Trader(
                kiwoom=self._kiwoom,
                account=self._account,
                market_data_api=self._market_data,
                strategy=strategy,
                is_simul=self._is_simul,
                max_buy_amount=buy_amount,
                max_stock_count=stock_count,
                stop_loss_rate=stop_loss,
                take_profit_rate=take_profit,
                notifier=self._notifier,
                safety_guard=self._safety_guard,
            )

            if strategy_name == "조건검색식":
                condition_name = settings.get("condition_name", "")
                self._condition_trader = ConditionTrader(
                    self._kiwoom, self._trader, self._market_data
                )
                self._condition_trader.start(condition_name)
            else:
                self._condition_trader = None

            self._stopped = False

            self._schedule_thread = _ScheduleThread()
            self._schedule_thread.start()

            logger.info("TradingController started (strategy=%s)", strategy_name)
        except Exception as exc:
            logger.error("TradingController.start failed: %s", exc)
            raise

    def stop(self):
        self._stopped = True
        if self._condition_trader:
            try:
                self._condition_trader.stop()
            except Exception as exc:
                logger.warning("condition_trader.stop error: %s", exc)
        if self._schedule_thread:
            self._schedule_thread.stop()
            self._schedule_thread.wait(3000)
        logger.info("TradingController stopped")

    def get_status(self) -> dict:
        """Dashboard.refresh() 에서 호출"""
        account_info = {"total_eval": 0, "total_profit_rate": 0.0, "available": 0}
        holdings = []
        safety = {
            "halted": False,
            "halt_reason": "",
            "order_count": 0,
            "max_orders": 0,
            "market_open": False,
        }

        if self._market_data and self._account:
            try:
                logger.info("잔고조회 대상 계좌=%s, simul=%s", self._account, self._is_simul)
                bal = self._market_data.get_account_balance(
                    self._account, is_simul=self._is_simul
                )
                summary = bal.get("summary", {})
                account_info = {
                    "total_eval": int(summary.get("total_eval", 0)),
                    "total_profit_rate": float(summary.get("total_profit_rate", 0.0)),
                    "available": int(summary.get("available", 0)),
                }
                df_h = bal.get("holdings")
                if df_h is not None and not df_h.empty:
                    holdings = df_h.to_dict("records")
            except Exception as exc:
                logger.warning("get_status account error: %s", exc)

        if self._safety_guard:
            try:
                safety = self._safety_guard.get_status()
            except Exception as exc:
                logger.warning("get_status safety error: %s", exc)

        return {
            "account": account_info,
            "holdings": holdings,
            "is_simul": self._is_simul,
            "safety": safety,
        }
