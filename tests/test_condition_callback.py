"""
조건식 자동매매 콜백 중복/누수 검증 테스트.

검증 시나리오 (사용자 요청):
    조건 편입 이벤트 → 매수 → 조건 재등록(매매 재시작) 시 콜백이 중복되지 않는지

핵심 대상 코드
  - KiwoomAPI.register_real_condition_callback / unregister_real_condition_callback
  - KiwoomAPI._on_receive_real_condition (콜백 디스패치 루프)
  - ConditionTrader.__init__ / start / stop / _on_condition_event

OCX(QAxWidget)는 conftest 의 가짜 PyQt5 로 대체되며, 콜백 로직은 실제 코드가 실행된다.
"""
import pytest

from core.kiwoom import KiwoomAPI
from core.condition_trader import ConditionTrader


# ---------------------------------------------------------------------------
# 테스트용 더미 객체
# ---------------------------------------------------------------------------
def make_kiwoom():
    """
    OCX 초기화(_init_api)를 건너뛴 KiwoomAPI 인스턴스.
    콜백 레지스트리/디스패치는 실제 메서드를 그대로 사용한다.
    """
    api = object.__new__(KiwoomAPI)
    api.real_condition_callbacks = []        # 실제 __init__ 에서 초기화하는 값
    api.condition_list = {1: "급등주포착"}    # get_condition_index_by_name 이 참조
    api.condition_tr_result = []
    # ConditionTrader 가 호출하는 OCX 의존 메서드만 가짜로 대체
    api.load_condition_list = lambda: api.condition_list
    api.send_condition = lambda *a, **k: []
    api.send_condition_stop = lambda *a, **k: None
    api.dynamicCall = lambda *a, **k: "테스트종목"   # GetMasterCodeName
    return api


class FakeTrader:
    """core.trader.Trader 의 최소 인터페이스 모사. 매수/매도 '시도' 횟수를 기록."""
    def __init__(self):
        self.positions = {}
        self.buy_attempts = []   # 호출된 종목코드 (성공/실패 무관, 호출 자체를 집계)
        self.sell_attempts = []

    def buy(self, code, name, price):
        self.buy_attempts.append(code)
        if code in self.positions:      # 실제 Trader 와 동일하게 중복 보유 방지
            return False
        self.positions[code] = {"name": name, "qty": 1, "avg_price": price}
        return True

    def sell(self, code, reason=""):
        self.sell_attempts.append(code)
        self.positions.pop(code, None)
        return True


class FakeMarketData:
    def get_stock_info(self, code):
        return {"code": code, "price": 1000, "volume": 0, "change_rate": 0.0}


def make_condition_trader(api, trader):
    ct = ConditionTrader(api, trader, FakeMarketData())
    ct._is_trade_time = lambda: True   # 매매 시간 체크 우회
    return ct


# ---------------------------------------------------------------------------
# 1) 레지스트리 자체의 중복 방지
# ---------------------------------------------------------------------------
def test_register_dedup_same_callback():
    api = make_kiwoom()

    def cb(*a):
        pass

    api.register_real_condition_callback(cb)
    api.register_real_condition_callback(cb)   # 같은 콜백 재등록
    assert api.real_condition_callbacks.count(cb) == 1


def test_unregister_removes_callback():
    api = make_kiwoom()

    def cb(*a):
        pass

    api.register_real_condition_callback(cb)
    api.unregister_real_condition_callback(cb)
    assert cb not in api.real_condition_callbacks
    # 없는 콜백 해제는 예외 없이 무시
    api.unregister_real_condition_callback(cb)


# ---------------------------------------------------------------------------
# 2) GUI 표시 콜백 + 자동매매 콜백 공존 (덮어쓰기 버그 회귀 방지)
# ---------------------------------------------------------------------------
def test_gui_and_trader_callbacks_coexist():
    api = make_kiwoom()
    trader = FakeTrader()

    gui_events = []
    api.register_real_condition_callback(
        lambda code, et, name, idx: gui_events.append((code, et))
    )

    ct = make_condition_trader(api, trader)
    ct.start("급등주포착")

    # GUI 콜백 + ConditionTrader 콜백 = 2개
    assert len(api.real_condition_callbacks) == 2

    # 편입 이벤트 1회 발생
    api._on_receive_real_condition("005930", "I", "급등주포착", 1)

    assert gui_events == [("005930", "I")]      # GUI 표시 콜백 동작
    assert trader.buy_attempts == ["005930"]    # 매수는 정확히 1회


# ---------------------------------------------------------------------------
# 3) 핵심: 조건 재등록(매매 재시작) 시 콜백 중복 없음 → 이중 매수 방지
# ---------------------------------------------------------------------------
def test_restart_does_not_duplicate_callback():
    api = make_kiwoom()
    trader = FakeTrader()

    # GUI 표시 콜백 1개는 세션 내내 유지된다고 가정
    api.register_real_condition_callback(lambda *a: None)
    assert len(api.real_condition_callbacks) == 1

    # --- 1차 매매 시작/정지 ---
    ct1 = make_condition_trader(api, trader)
    ct1.start("급등주포착")
    assert len(api.real_condition_callbacks) == 2   # GUI + ct1
    ct1.stop()
    assert len(api.real_condition_callbacks) == 1   # ct1 콜백 해제됨 (GUI만 남음)

    # --- 2차 매매 재시작 ---
    ct2 = make_condition_trader(api, trader)
    ct2.start("급등주포착")
    # 콜백이 3개로 늘어나면(= ct1 이 남아있으면) 버그
    assert len(api.real_condition_callbacks) == 2   # GUI + ct2 뿐

    # 재시작 후 편입 이벤트 → 매수 '시도'는 정확히 1회여야 한다.
    # (ct1 이 누수됐다면 동일 종목에 대해 2회 시도된다)
    api._on_receive_real_condition("000660", "I", "급등주포착", 1)
    assert trader.buy_attempts == ["000660"]


# ---------------------------------------------------------------------------
# 4) 편입 → 매수 → 이탈 → 매도 의 전체 흐름
# ---------------------------------------------------------------------------
def test_enter_buy_then_exit_sell():
    api = make_kiwoom()
    trader = FakeTrader()
    ct = make_condition_trader(api, trader)
    ct.start("급등주포착")

    api._on_receive_real_condition("005930", "I", "급등주포착", 1)   # 편입 → 매수
    assert "005930" in trader.positions

    api._on_receive_real_condition("005930", "D", "급등주포착", 1)   # 이탈 → 매도
    assert "005930" not in trader.positions
    assert trader.sell_attempts == ["005930"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
