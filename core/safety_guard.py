"""
안전장치 모듈 - 초보자 실수 방지를 위한 매매 가드

매수/매도 전에 SafetyGuard.check_buy() / check_sell() 를 호출하여
한도 초과 여부를 검사한다. 위반 시 (False, 사유) 를 반환한다.
"""
import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class SafetyGuard:
    def __init__(self, daily_loss_limit_rate=-0.10, max_orders_per_day=20,
                 trade_start="09:00", trade_end="15:30",
                 min_available_cash=10000):
        """
        daily_loss_limit_rate: 일일 최대 손실률 (예: -0.10 = -10% 도달 시 매매 중단)
        max_orders_per_day:    하루 최대 주문 횟수 (무한 반복 주문 방지)
        trade_start/end:       장 운영 시간 (이 시간 외 주문 차단)
        min_available_cash:    이 금액 미만이면 매수 차단
        """
        self.daily_loss_limit_rate = daily_loss_limit_rate
        self.max_orders_per_day = max_orders_per_day
        self.trade_start = trade_start
        self.trade_end = trade_end
        self.min_available_cash = min_available_cash

        self._order_count = 0
        self._order_date = datetime.date.today()
        self._halted = False           # 일일 손실 한도 도달 시 True
        self._halt_reason = ""
        self.start_eval = None         # 장 시작 시점 총평가금액 (손실률 기준)

    # -------------------------------------------------------------------------
    # 기준 자산 설정 (장 시작 시 1회 호출)
    # -------------------------------------------------------------------------
    def set_baseline(self, total_eval):
        """일일 손실률 계산의 기준이 되는 시작 자산 설정"""
        self.start_eval = total_eval
        logger.info(f"안전장치 기준자산 설정: {total_eval:,}원 "
                    f"(일일손실한도 {self.daily_loss_limit_rate:.0%})")

    # -------------------------------------------------------------------------
    # 일일 카운터 리셋 (날짜 바뀌면 자동)
    # -------------------------------------------------------------------------
    def _reset_if_new_day(self):
        today = datetime.date.today()
        if today != self._order_date:
            self._order_date = today
            self._order_count = 0
            self._halted = False
            self._halt_reason = ""
            logger.info("안전장치 일일 카운터 리셋")

    # -------------------------------------------------------------------------
    # 장 운영 시간 체크
    # -------------------------------------------------------------------------
    def is_market_open(self):
        now = datetime.datetime.now()
        if now.weekday() >= 5:  # 토(5), 일(6)
            return False
        cur = now.strftime("%H:%M")
        return self.trade_start <= cur <= self.trade_end

    # -------------------------------------------------------------------------
    # 일일 손실 한도 점검 (현재 평가금액 입력)
    # -------------------------------------------------------------------------
    def update_and_check_loss(self, current_eval):
        """
        현재 평가금액으로 일일 손실률을 갱신.
        한도 도달 시 매매를 정지(halt)시키고 True 반환.
        """
        if self.start_eval is None or self.start_eval <= 0:
            return False
        loss_rate = (current_eval - self.start_eval) / self.start_eval
        if loss_rate <= self.daily_loss_limit_rate and not self._halted:
            self._halted = True
            self._halt_reason = f"일일 손실 한도 도달 ({loss_rate:.2%})"
            logger.warning(f"🛑 매매 중단: {self._halt_reason}")
            return True
        return self._halted

    @property
    def is_halted(self):
        return self._halted

    @property
    def halt_reason(self):
        return self._halt_reason

    # -------------------------------------------------------------------------
    # 매수 전 검사
    # -------------------------------------------------------------------------
    def check_buy(self, available_cash):
        """매수 가능 여부 검사. 반환: (허용여부, 사유)"""
        self._reset_if_new_day()

        if self._halted:
            return False, f"매매 정지 상태: {self._halt_reason}"
        if not self.is_market_open():
            return False, "장 운영 시간이 아닙니다 (평일 09:00~15:30)"
        if self._order_count >= self.max_orders_per_day:
            return False, f"일일 최대 주문 횟수({self.max_orders_per_day}회) 초과"
        if not isinstance(available_cash, (int, float)) or available_cash < self.min_available_cash:
            return False, f"주문가능금액 부족 ({available_cash:,}원)"
        return True, "OK"

    # -------------------------------------------------------------------------
    # 매도 전 검사 (매도는 리스크 축소이므로 손실한도와 무관하게 허용)
    # -------------------------------------------------------------------------
    def check_sell(self):
        """매도 가능 여부 검사. 반환: (허용여부, 사유)"""
        self._reset_if_new_day()
        if self._order_count >= self.max_orders_per_day:
            return False, f"일일 최대 주문 횟수({self.max_orders_per_day}회) 초과"
        return True, "OK"

    # -------------------------------------------------------------------------
    # 주문 성공 시 카운트 증가
    # -------------------------------------------------------------------------
    def record_order(self):
        self._order_count += 1
        logger.debug(f"오늘 주문 횟수: {self._order_count}/{self.max_orders_per_day}")

    def get_status(self):
        """현재 안전장치 상태 요약 (대시보드 표시용)"""
        return {
            "order_count": self._order_count,
            "max_orders": self.max_orders_per_day,
            "halted": self._halted,
            "halt_reason": self._halt_reason,
            "market_open": self.is_market_open(),
        }
