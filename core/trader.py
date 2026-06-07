"""
매매 실행 모듈 - 주문 생성, 리스크 관리, 포지션 추적
"""
import datetime
from config.settings import (
    MAX_BUY_AMOUNT, MAX_STOCK_COUNT, STOP_LOSS_RATE, TAKE_PROFIT_RATE,
    TRADE_START_TIME, TRADE_END_TIME
)
from utils.logger import get_logger
from utils.db import TradeDB

logger = get_logger(__name__)

SCREEN_ORDER = "3000"
SCREEN_BALANCE = "3001"


class Trader:
    def __init__(self, kiwoom, account, market_data_api, strategy, is_simul=True,
                 max_buy_amount=None, max_stock_count=None,
                 stop_loss_rate=None, take_profit_rate=None, notifier=None,
                 safety_guard=None):
        """
        리스크 설정은 인자로 주입 가능하며, 미지정 시 config 기본값을 사용한다.
        이를 통해 지표 전략 모드와 조건검색 모드가 서로 다른 한도를 가질 수 있다.
        notifier: utils.notifier.Notifier 인스턴스 (매매 시 알림 전송, 선택)
        safety_guard: core.safety_guard.SafetyGuard 인스턴스 (안전장치, 선택)
        """
        self.api = kiwoom
        self.account = account
        self.mdata = market_data_api
        self.strategy = strategy
        self.is_simul = is_simul
        self.db = TradeDB()
        self.notifier = notifier
        self.guard = safety_guard

        # 리스크/한도 설정 (인스턴스별)
        self.max_buy_amount = max_buy_amount if max_buy_amount is not None else MAX_BUY_AMOUNT
        self.max_stock_count = max_stock_count if max_stock_count is not None else MAX_STOCK_COUNT
        self.stop_loss_rate = stop_loss_rate if stop_loss_rate is not None else STOP_LOSS_RATE
        self.take_profit_rate = (
            take_profit_rate if take_profit_rate is not None else TAKE_PROFIT_RATE
        )

        # 포지션 캐시 {code: {qty, avg_price, name}}
        self.positions = {}

    # -------------------------------------------------------------------------
    # 포지션 동기화 (장 시작 시 호출)
    # -------------------------------------------------------------------------
    def sync_positions(self):
        """계좌 잔고로 포지션 초기화"""
        result = self.mdata.get_account_balance(self.account, is_simul=self.is_simul)
        self.positions = {}
        for _, row in result["holdings"].iterrows():
            if row["qty"] > 0:
                self.positions[row["code"]] = {
                    "name": row["name"],
                    "qty": row["qty"],
                    "avg_price": row["avg_price"],
                }
        logger.info(f"포지션 동기화: {list(self.positions.keys())}")
        return result["summary"]

    # -------------------------------------------------------------------------
    # 매매 가능 시간 체크
    # -------------------------------------------------------------------------
    def _is_trade_time(self):
        now = datetime.datetime.now().strftime("%H:%M")
        return TRADE_START_TIME <= now <= TRADE_END_TIME

    # -------------------------------------------------------------------------
    # 매수
    # -------------------------------------------------------------------------
    def buy(self, code, name, current_price):
        """시장가 매수 주문"""
        # 안전장치 검사 (일일손실한도/주문횟수/장시간/잔고)
        if self.guard:
            available = self.max_buy_amount  # 보수적 추정치
            ok, reason = self.guard.check_buy(available)
            if not ok:
                logger.warning(f"[안전장치] 매수 차단: {reason}")
                return False

        if not self._is_trade_time():
            logger.warning("매매 가능 시간이 아닙니다.")
            return False

        if len(self.positions) >= self.max_stock_count:
            logger.warning(f"최대 보유 종목수({self.max_stock_count}) 초과")
            return False

        if code in self.positions:
            logger.info(f"[{code}] 이미 보유 중")
            return False

        qty = self.max_buy_amount // current_price
        if qty < 1:
            logger.warning(f"[{code}] 매수 가능 수량 부족 (price={current_price:,})")
            return False

        logger.info(f"[{code}] {name} 매수 주문: {qty}주 @ 시장가 (약 {qty * current_price:,}원)")

        ret = self.api.send_order(
            rq_name="시장가매수",
            screen_no=SCREEN_ORDER,
            account=self.account,
            order_type=1,      # 신규매수
            code=code,
            qty=qty,
            price=0,           # 시장가
            hoga_gb="03",      # 시장가
        )

        if ret == 0:
            self.positions[code] = {"name": name, "qty": qty, "avg_price": current_price}
            self.db.save_order(code, name, "BUY", qty, current_price, self.is_simul)
            if self.guard:
                self.guard.record_order()
            logger.info(f"[{code}] 매수 주문 전송 성공")
            self._notify(
                f"🟢 매수: {name}({code})\n"
                f"수량: {qty}주 @ 시장가 (약 {qty * current_price:,}원)\n"
                f"모드: {'모의투자' if self.is_simul else '실거래'}"
            )
            return True
        else:
            logger.error(f"[{code}] 매수 주문 전송 실패: ret={ret}")
            return False

    # -------------------------------------------------------------------------
    # 매도
    # -------------------------------------------------------------------------
    def sell(self, code, reason="전략"):
        """보유 종목 전량 시장가 매도"""
        if code not in self.positions:
            logger.warning(f"[{code}] 보유 종목 없음")
            return False

        pos = self.positions[code]
        qty = pos["qty"]
        name = pos["name"]

        logger.info(f"[{code}] {name} 매도 주문: {qty}주 @ 시장가 (사유: {reason})")

        ret = self.api.send_order(
            rq_name="시장가매도",
            screen_no=SCREEN_ORDER,
            account=self.account,
            order_type=2,      # 신규매도
            code=code,
            qty=qty,
            price=0,
            hoga_gb="03",
        )

        if ret == 0:
            self.db.save_order(code, name, "SELL", qty, 0, self.is_simul, reason)
            del self.positions[code]
            if self.guard:
                self.guard.record_order()
            logger.info(f"[{code}] 매도 주문 전송 성공")
            self._notify(
                f"🔴 매도: {name}({code})\n"
                f"수량: {qty}주 @ 시장가\n"
                f"사유: {reason}"
            )
            return True
        else:
            logger.error(f"[{code}] 매도 주문 전송 실패: ret={ret}")
            return False

    # -------------------------------------------------------------------------
    # 전략 실행 (매 주기 호출)
    # -------------------------------------------------------------------------
    def run_strategy(self, watch_list):
        """
        감시 종목 리스트에 대해 전략을 실행하고 매수/매도 결정
        watch_list: [{"code": "005930", "name": "삼성전자"}, ...]
        """
        if not self._is_trade_time():
            return

        # 보유 종목 매도 체크
        for code, pos in list(self.positions.items()):
            try:
                info = self.mdata.get_stock_info(code)
                df = self.mdata.get_daily_ohlcv(code, _days_ago(60))
                if self.strategy.should_sell(df, code, pos["avg_price"], info["price"]):
                    profit = (info["price"] - pos["avg_price"]) / pos["avg_price"]
                    self.sell(code, reason=f"전략매도(수익률:{profit:.2%})")
            except Exception as e:
                logger.error(f"[{code}] 매도 체크 오류: {e}")

        # 감시 종목 매수 체크
        for item in watch_list:
            code = item["code"]
            name = item["name"]
            if code in self.positions:
                continue
            try:
                info = self.mdata.get_stock_info(code)
                df = self.mdata.get_daily_ohlcv(code, _days_ago(60))
                if self.strategy.should_buy(df, code):
                    self.buy(code, name, info["price"])
            except Exception as e:
                logger.error(f"[{code}] 매수 체크 오류: {e}")

    # -------------------------------------------------------------------------
    # 리스크 점검 전용 (조건검색 모드에서 손절/익절 적용)
    # -------------------------------------------------------------------------
    def check_risk(self):
        """
        보유 종목의 손절/익절 조건만 점검하여 매도.
        조건검색 모드처럼 매수는 별도 로직이 담당할 때 사용한다.
        """
        if not self._is_trade_time():
            return
        for code, pos in list(self.positions.items()):
            try:
                info = self.mdata.get_stock_info(code)
                profit_rate = (info["price"] - pos["avg_price"]) / pos["avg_price"]
                if profit_rate <= self.stop_loss_rate:
                    self.sell(code, reason=f"손절({profit_rate:.2%})")
                elif profit_rate >= self.take_profit_rate:
                    self.sell(code, reason=f"익절({profit_rate:.2%})")
            except Exception as e:
                logger.error(f"[{code}] 리스크 점검 오류: {e}")

    # -------------------------------------------------------------------------
    # 알림 전송 헬퍼
    # -------------------------------------------------------------------------
    def _notify(self, message):
        """notifier가 설정된 경우 알림 전송 (실패해도 매매에 영향 없음)"""
        if self.notifier:
            try:
                self.notifier.send(message)
            except Exception as e:
                logger.error(f"알림 전송 실패: {e}")


def _days_ago(n):
    return (datetime.datetime.now() - datetime.timedelta(days=n)).strftime("%Y%m%d")
