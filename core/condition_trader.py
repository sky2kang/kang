"""
조건검색식 기반 자동매매 모듈

HTS(영웅문) [0150] 조건검색에서 직접 만든 조건식을 실시간으로 받아 매매한다.
- 종목이 조건식에 '편입(I)'되면 → 매수 후보
- 보유 종목이 조건식에서 '이탈(D)'되면 → 매도
- 손절/익절은 Trader 의 리스크 관리 로직을 그대로 사용
"""
import datetime
from config.settings import TRADE_START_TIME, TRADE_END_TIME
from utils.logger import get_logger

logger = get_logger(__name__)

SCREEN_CONDITION = "5000"


class ConditionTrader:
    def __init__(self, kiwoom, trader, market_data_api):
        """
        kiwoom: KiwoomAPI 인스턴스
        trader: core.trader.Trader 인스턴스 (실제 주문/리스크관리 담당)
        market_data_api: MarketDataAPI 인스턴스
        """
        self.api = kiwoom
        self.trader = trader
        self.mdata = market_data_api
        self.active_condition = None  # (cond_name, cond_index)

        # 실시간 조건 편입/이탈 콜백 등록
        self.api.register_real_condition_callback(self._on_condition_event)

    # -------------------------------------------------------------------------
    # 조건검색 시작
    # -------------------------------------------------------------------------
    def start(self, condition_name):
        """
        지정한 조건명으로 실시간 조건검색을 시작한다.
        condition_name: HTS에서 저장한 조건식 이름 (예: "급등주포착")
        """
        # 조건식 목록 로드
        self.api.load_condition_list()

        cond_index = self.api.get_condition_index_by_name(condition_name)
        if cond_index is None:
            available = list(self.api.condition_list.values())
            raise ValueError(
                f"조건식 '{condition_name}' 을(를) 찾을 수 없습니다. "
                f"사용 가능한 조건식: {available}"
            )

        self.active_condition = (condition_name, cond_index)

        # 1) 현재 조건 만족 종목 1회 조회 (단발성)
        initial_codes = self.api.send_condition(
            SCREEN_CONDITION, condition_name, cond_index, search_type=0
        )
        logger.info(f"조건검색 초기 종목 {len(initial_codes)}개: {initial_codes}")

        # 2) 실시간 조건검색 시작 (편입/이탈 통보)
        self.api.send_condition(
            SCREEN_CONDITION, condition_name, cond_index, search_type=1
        )
        logger.info(f"실시간 조건검색 가동: [{condition_name}]")

        return initial_codes

    def stop(self):
        """실시간 조건검색 중지"""
        if self.active_condition:
            name, idx = self.active_condition
            self.api.send_condition_stop(SCREEN_CONDITION, name, idx)
            self.active_condition = None

    # -------------------------------------------------------------------------
    # 실시간 편입/이탈 처리
    # -------------------------------------------------------------------------
    def _is_trade_time(self):
        now = datetime.datetime.now().strftime("%H:%M")
        return TRADE_START_TIME <= now <= TRADE_END_TIME

    def _on_condition_event(self, code, event_type, cond_name, cond_index):
        """
        실시간 조건 편입/이탈 시 호출됨.
        event_type: "I"=편입 → 매수, "D"=이탈 → 매도
        """
        if not self._is_trade_time():
            logger.debug(f"매매시간 외 - 조건이벤트 무시 ({code})")
            return

        try:
            if event_type == "I":
                self._handle_enter(code)
            elif event_type == "D":
                self._handle_exit(code)
        except Exception as e:
            logger.error(f"[{code}] 조건이벤트 처리 오류: {e}")

    def _handle_enter(self, code):
        """조건 편입 → 매수"""
        if code in self.trader.positions:
            logger.info(f"[{code}] 이미 보유 중 - 매수 생략")
            return

        info = self.mdata.get_stock_info(code)
        name = self._get_stock_name(code)
        logger.info(f"[조건편입 매수시도] {name}({code}) 현재가={info['price']:,}")
        self.trader.buy(code, name, info["price"])

    def _handle_exit(self, code):
        """조건 이탈 → 매도 (보유 중인 경우만)"""
        if code not in self.trader.positions:
            return
        logger.info(f"[조건이탈 매도시도] {code}")
        self.trader.sell(code, reason="조건이탈")

    def _get_stock_name(self, code):
        """종목코드로 종목명 조회"""
        name = self.api.dynamicCall("GetMasterCodeName(QString)", code)
        return name.strip() if name else code
