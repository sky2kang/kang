"""
조건검색식 기반 자동매매 모듈 (여러 조건식 동시 운영 지원)

HTS(영웅문) [0150] 조건검색에서 직접 만든 조건식을 실시간으로 받아 매매한다.
- 종목이 조건식에 '편입(I)'되면 → 매수 후보
- 보유 종목이 조건식에서 '이탈(D)'되면 → 매도
- 손절/익절은 Trader.check_risk() 로 주기적으로 적용

여러 조건식을 동시에 운영할 수 있으며, 각 조건식은 별도 화면번호를 사용한다.
"""
import datetime
from config.settings import TRADE_START_TIME, TRADE_END_TIME
from utils.logger import get_logger

logger = get_logger(__name__)

# 조건검색 화면번호 베이스 (조건식마다 5001, 5002, ... 로 부여)
SCREEN_CONDITION_BASE = 5000


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
        # 활성 조건식 {cond_name: {"index": idx, "screen": screen_no}}
        self.active_conditions = {}

        # 매매 결과를 GUI 등 외부로 통보하는 콜백
        # signature: callback(cond_name, code, name, action, ok)
        #   action: "매수" | "매도",  ok: True(성공)/False(실패·생략)
        self.trade_callback = None

        # 실시간 조건 편입/이탈 콜백 등록
        self.api.register_real_condition_callback(self._on_condition_event)

    def set_trade_callback(self, callback):
        """매수/매도 발생 시 호출될 콜백 등록 (GUI 표시용)"""
        self.trade_callback = callback

    def _notify_trade(self, cond_name, code, name, action, ok):
        if self.trade_callback:
            try:
                self.trade_callback(cond_name, code, name, action, ok)
            except Exception as e:
                logger.warning("trade_callback 오류: %s", e)

    # -------------------------------------------------------------------------
    # 조건검색 시작
    # -------------------------------------------------------------------------
    def start(self, condition_names):
        """
        지정한 조건명(들)으로 실시간 조건검색을 시작한다.
        condition_names: 문자열 1개 또는 문자열 리스트
            예) "급등주포착"  또는  ["급등주포착", "눌림목공략"]
        반환: {cond_name: [초기 종목코드, ...]}
        """
        if isinstance(condition_names, str):
            condition_names = [condition_names]

        # 조건식 목록 로드 (1회만)
        self.api.load_condition_list()

        results = {}
        for i, name in enumerate(condition_names):
            cond_index = self.api.get_condition_index_by_name(name)
            if cond_index is None:
                available = list(self.api.condition_list.values())
                raise ValueError(
                    f"조건식 '{name}' 을(를) 찾을 수 없습니다. "
                    f"사용 가능한 조건식: {available}"
                )

            screen_no = str(SCREEN_CONDITION_BASE + i + 1)
            self.active_conditions[name] = {"index": cond_index, "screen": screen_no}

            # 1) 현재 조건 만족 종목 1회 조회 (단발성)
            initial_codes = self.api.send_condition(
                screen_no, name, cond_index, search_type=0
            )
            logger.info(f"[{name}] 초기 종목 {len(initial_codes)}개: {initial_codes}")

            # 2) 실시간 조건검색 시작 (편입/이탈 통보)
            self.api.send_condition(screen_no, name, cond_index, search_type=1)
            logger.info(f"실시간 조건검색 가동: [{name}] (화면={screen_no})")

            results[name] = initial_codes

        logger.info(f"총 {len(self.active_conditions)}개 조건식 동시 운영 중")
        return results

    def stop(self):
        """모든 실시간 조건검색 중지"""
        for name, info in self.active_conditions.items():
            self.api.send_condition_stop(info["screen"], name, info["index"])
        self.active_conditions = {}

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
                self._handle_enter(code, cond_name)
            elif event_type == "D":
                self._handle_exit(code, cond_name)
        except Exception as e:
            logger.error(f"[{code}] 조건이벤트 처리 오류: {e}")

    def _handle_enter(self, code, cond_name):
        """조건 편입 → 매수"""
        if code in self.trader.positions:
            logger.info(f"[{code}] 이미 보유 중 - 매수 생략")
            return

        try:
            info = self.mdata.get_stock_info(code)
        except Exception as e:
            logger.error(f"[{code}] 현재가 조회 실패: {e}")
            return
        if not info or not info.get("price"):
            logger.warning(f"[{code}] 현재가 0 또는 조회 실패 - 매수 생략")
            return
        name = self._get_stock_name(code)
        logger.info(f"[조건편입:{cond_name}] {name}({code}) 매수시도 "
                    f"현재가={info['price']:,}")
        ok = self.trader.buy(code, name, info["price"])
        self._notify_trade(cond_name, code, name, "매수", bool(ok))

    def _handle_exit(self, code, cond_name):
        """조건 이탈 → 매도 (보유 중인 경우만)"""
        if code not in self.trader.positions:
            return
        name = self.trader.positions[code].get("name", code)
        logger.info(f"[조건이탈:{cond_name}] {code} 매도시도")
        ok = self.trader.sell(code, reason=f"조건이탈({cond_name})")
        self._notify_trade(cond_name, code, name, "매도", bool(ok))

    def _get_stock_name(self, code):
        """종목코드로 종목명 조회"""
        name = self.api.dynamicCall("GetMasterCodeName(QString)", code)
        return name.strip() if name else code
