"""
조건검색 기반 실시간 자동매매 엔진.

- 최대 10개 조건식을 실시간 등록 (키움 실시간 조건검색 동시등록 한도)
- 조건식별 규칙에 따라 자동 주문:
    · 편입(I) 시 매수 (buy_on_entry)
    · 이탈(D) 시 매도 (sell_on_exit)
    · 보유 종목 실시간 시세로 손절(stop_loss)/익절(take_profit) 도달 시 매도
- 매수/매도는 기존 Trader 를 통해 실행되어 DB 기록·리스크 한도가 그대로 적용된다.
"""
from utils.logger import get_logger

logger = get_logger("auto_trader")

REAL_SCREEN = "5300"
REAL_FIDS = "10;12"   # 현재가;등락율
MAX_CONDITIONS = 10


class ConditionAutoTrader:
    def __init__(self, kiwoom, trader, rules_provider, status_cb=None):
        """
        rules_provider: () -> {idx(str): rule(dict)} 현재 규칙을 반환하는 콜러블
        status_cb:      (kind, info_dict) GUI 갱신 콜백
        """
        self.kiwoom = kiwoom
        self.trader = trader
        self.rules_provider = rules_provider
        self.status_cb = status_cb
        self.running = False
        self.halted = False         # 당일청산 후 신규 매수 차단
        self.active = []            # [(screen, name, idx)]
        self.code_cond = {}         # code -> idx(str), 매수 근거 조건식
        self.code_peak = {}         # code -> 보유 후 최고가 (트레일링 스탑용)
        self.watched = set()        # 실시간 시세 등록된 종목

    # ------------------------------------------------------------ 시작/중지
    def start(self, selected):
        """selected: [(idx, name), ...] — 호출 측에서 enabled 만, 최대 10개 전달"""
        if self.running:
            return
        self.halted = False
        self.kiwoom.condition_real_callback = self._on_condition
        self.kiwoom.register_real_callback(REAL_SCREEN, self._on_real_price)
        self.kiwoom.chejan_callback = self._on_chejan
        self.active = []
        for idx, name in selected[:MAX_CONDITIONS]:
            screen = f"52{idx % 100:02d}"
            codes = self.kiwoom.send_condition(screen, name, idx, 1)
            if codes is None:
                logger.error(f"조건식 실시간 등록 실패: idx={idx}")
                continue
            self.active.append((screen, name, idx))
            logger.info(f"조건식 실시간 등록 [{idx}] {self.kiwoom.decode_text(name)} "
                        f"(편입 {len(codes)}종목)")
            rule = self.rules_provider().get(str(idx))
            if rule and rule.get("enabled") and rule.get("buy_on_entry"):
                for code in codes:
                    self._handle_entry(code, idx)
        self.running = True
        self._notify("start", count=len(self.active))
        logger.info(f"조건 자동매매 시작: {len(self.active)}개 조건식 등록")

    def stop(self):
        for screen, name, idx in self.active:
            try:
                self.kiwoom.send_condition_stop(screen, name, idx)
            except Exception:
                pass
        self.active = []
        try:
            self.kiwoom.set_real_remove(REAL_SCREEN, "ALL")
        except Exception:
            pass
        self.watched.clear()
        self.code_peak.clear()
        self.running = False
        self._notify("stop")
        logger.info("조건 자동매매 중지")

    # ------------------------------------------------------- 편입/이탈 처리
    def _on_condition(self, code, event_type, cond_name, cond_index):
        rule = self.rules_provider().get(str(cond_index))
        if not rule or not rule.get("enabled"):
            return
        if event_type == "I":
            logger.info(f"[편입] {code} ← 조건[{cond_index}]")
            self._notify("entry", code=code, cond=cond_index)
            if rule.get("buy_on_entry"):
                self._handle_entry(code, cond_index)
        elif event_type == "D":
            logger.info(f"[이탈] {code} ← 조건[{cond_index}]")
            self._notify("exit", code=code, cond=cond_index)
            if rule.get("sell_on_exit"):
                self._handle_exit(code, reason="이탈")

    def _handle_entry(self, code, cond_index):
        if self.halted:
            return
        if code in self.trader.positions:
            return
        rule = self.rules_provider().get(str(cond_index), {})
        try:
            info = self.trader.mdata.get_stock_info(code)
        except Exception as e:
            logger.error(f"[{code}] 시세 조회 실패: {e}")
            return
        name = self.kiwoom.get_master_code_name(code)
        amount = int(rule.get("buy_amount") or 0) or None
        if self.trader.buy(code, name, info["price"], amount=amount):
            self.code_cond[code] = str(cond_index)
            self.code_peak[code] = info["price"]
            self._register_price(code)
            self._notify("buy", code=code, name=name, price=info["price"], cond=cond_index)

    def _handle_exit(self, code, reason="이탈"):
        if code not in self.trader.positions:
            return
        name = self.trader.positions[code]["name"]
        if self.trader.sell(code, reason=reason):
            self.code_cond.pop(code, None)
            self.code_peak.pop(code, None)
            self._notify("sell", code=code, name=name, reason=reason)

    def liquidate_all(self, reason="당일청산"):
        """보유 종목 전량 매도 + 신규 매수 차단 (당일청산)."""
        if self.halted:
            return
        self.halted = True
        codes = list(self.trader.positions.keys())
        for code in codes:
            self._handle_exit(code, reason=reason)
        self._notify("liquidate", count=len(codes))
        logger.info(f"{reason}: {len(codes)}종목 매도, 신규 매수 차단")

    # ------------------------------------------------- 실시간 시세→손절/익절
    def _register_price(self, code):
        opt = "1" if self.watched else "0"
        self.kiwoom.set_real_reg(REAL_SCREEN, code, REAL_FIDS, opt)
        self.watched.add(code)

    def _on_real_price(self, code, real_type, real_data):
        if code not in self.trader.positions:
            return
        rule = self.rules_provider().get(self.code_cond.get(code, ""), {})
        try:
            price = abs(int(self.kiwoom.get_comm_real_data(code, 10) or 0))
        except Exception:
            return
        if price <= 0:
            return
        pos = self.trader.positions[code]
        avg = pos.get("avg_price", 0)
        if avg <= 0:
            return
        # 보유 후 최고가 갱신 (트레일링 스탑 기준)
        peak = max(self.code_peak.get(code, price), price)
        self.code_peak[code] = peak

        profit = (price - avg) / avg
        stop = rule.get("stop_loss")
        take = rule.get("take_profit")
        trail = rule.get("trailing_stop") or 0

        # 1) 손절 (하드 플로어)
        if stop is not None and profit <= stop / 100.0:
            self._handle_exit(code, reason=f"손절({profit:.1%})")
            return
        # 2) 트레일링 스탑 (수익 구간 진입 후 고점 대비 trail% 하락 시)
        if trail > 0 and peak > avg and price <= peak * (1 - trail / 100.0):
            peak_dd = (price - peak) / peak
            self._handle_exit(code, reason=f"트레일링(고점{peak_dd:.1%}, 수익{profit:+.1%})")
            return
        # 3) 익절 (고정 목표)
        if take is not None and profit >= take / 100.0:
            self._handle_exit(code, reason=f"익절({profit:.1%})")

    def _on_chejan(self, data):
        self._notify("chejan", **data)

    # ------------------------------------------------------------- 알림
    def _notify(self, kind, **info):
        if self.status_cb:
            try:
                self.status_cb(kind, info)
            except Exception as e:
                logger.error(f"status_cb 오류: {e}")
