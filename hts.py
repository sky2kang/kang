"""
키움 자동매매 HTS (통합 GUI).

탭 구성:
  1) 계좌 관리   - 예수금/잔고/보유종목/수익률
  2) 종목 검색   - 코드/이름 검색 → 현재가, 감시종목 추가, 호가창 연동
  3) 조건 검색   - 키움 조건식 불러오기/단발·실시간 실행 → 자동매매 연동
  4) 차트        - 일봉 캔들 차트
  5) 호가/주문   - 실시간 10호가창 + 수동 매수/매도 (호가 클릭 주문가 입력)
  6) 조건 자동매매 - 조건식 기반 실시간 자동매매 (트레일링 스탑·당일청산 포함)
  7) 조건식 시뮬레이션 - 편입종목 조회 + 과거 데이터 청산룰 백테스트
  8) 자동매매    - 시작/중지, 감시종목 실시간 시세, 신호/주문 로그
  9) 설정        - config.json 편집 (settings_gui 재사용)

실행:  .venv\\Scripts\\python.exe hts.py
"""
import os
import sys
import logging
import datetime

# Qt 플랫폼 플러그인 경로 보정 (main.py 와 동일)
if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    import PyQt5
    _plugins = os.path.join(
        os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms"
    )
    if os.path.isdir(_plugins):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugins

from PyQt5.QtCore import Qt, QTimer, QTime, QObject, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFormLayout,
    QTextEdit, QHeaderView, QMessageBox, QDockWidget, QAbstractItemView,
    QSpinBox, QDoubleSpinBox, QInputDialog, QTimeEdit,
)

from config import settings
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.trader import Trader
from core.auto_trader import ConditionAutoTrader
from core.condition_sim import simulate_exit_rules, summarize
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.logger import get_logger
from settings_gui import SettingsWindow
from chart_view import CandleChart

logger = get_logger("hts")

SCREEN_ACCOUNT = "5001"
SCREEN_REAL = "5002"
SCREEN_HOGA = "5003"          # 호가창 실시간 화면
SCREEN_MANUAL_ORDER = "5004"  # 수동 주문 화면
SCREEN_COND = "5100"
SCREEN_SIM = "5400"           # 조건식 시뮬레이션 단발 조회 화면

REAL_FIDS = "10;11;12;15"  # 현재가;전일대비;등락율;거래량
# 호가창 실시간 구독 FID (체결: 현재가/등락율/거래량 + 호가잔량 real type)
HOGA_REAL_FIDS = "10;12;13;41;51"

# 10호가 FID (위→아래 표시 순서)
ASK_PRICE_FIDS = [50, 49, 48, 47, 46, 45, 44, 43, 42, 41]  # 매도호가10→1
ASK_QTY_FIDS = [70, 69, 68, 67, 66, 65, 64, 63, 62, 61]   # 매도잔량10→1
BID_PRICE_FIDS = [51, 52, 53, 54, 55, 56, 57, 58, 59, 60]  # 매수호가1→10
BID_QTY_FIDS = [71, 72, 73, 74, 75, 76, 77, 78, 79, 80]   # 매수잔량1→10


# =========================================================================
# 로그 → GUI 브리지
# =========================================================================
class QtLogHandler(logging.Handler, QObject):
    log = pyqtSignal(str)

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)
        self.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            self.log.emit(self.format(record))
        except Exception:
            pass


def _num_item(value, money=False, pct=False):
    """우측 정렬 숫자 셀"""
    if money:
        text = f"{value:,}"
    elif pct:
        text = f"{value:+.2f}%"
    else:
        text = str(value)
    item = QTableWidgetItem(text)
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
    if pct and isinstance(value, (int, float)):
        item.setForeground(QColor("#d32f2f") if value >= 0 else QColor("#1565c0"))
    return item


def _checkbox_cell(checked=False):
    """테이블 셀에 가운데 정렬된 체크박스를 넣기 위한 (위젯, 체크박스) 반환"""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setAlignment(Qt.AlignCenter)
    cb = QCheckBox()
    cb.setChecked(checked)
    h.addWidget(cb)
    return w, cb


# =========================================================================
# 1) 계좌 관리 탭
# =========================================================================
class AccountTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        top.addWidget(QLabel("계좌"))
        self.account_combo = QComboBox()
        top.addWidget(self.account_combo)
        self.refresh_btn = QPushButton("조회")
        self.refresh_btn.clicked.connect(self.refresh)
        top.addWidget(self.refresh_btn)
        self.auto_chk = QCheckBox("30초 자동조회")
        self.auto_chk.stateChanged.connect(self._toggle_auto)
        top.addWidget(self.auto_chk)
        top.addStretch()
        v.addLayout(top)

        # 요약
        box = QGroupBox("계좌 요약")
        g = QGridLayout(box)
        self.lbl_deposit = QLabel("-")
        self.lbl_orderable = QLabel("-")
        self.lbl_eval = QLabel("-")
        self.lbl_profit = QLabel("-")
        for col, (cap, lbl) in enumerate([
            ("예수금", self.lbl_deposit), ("주문가능", self.lbl_orderable),
            ("총평가금액", self.lbl_eval), ("총수익률", self.lbl_profit),
        ]):
            g.addWidget(QLabel(cap), 0, col, alignment=Qt.AlignCenter)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(QFont("", 11, QFont.Bold))
            g.addWidget(lbl, 1, col)
        v.addWidget(box)

        # 보유종목
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["종목명", "코드", "보유수량", "매입단가", "수익률"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.table)

        self.timer = QTimer(self)
        self.timer.setInterval(30_000)
        self.timer.timeout.connect(self.refresh)

    def _toggle_auto(self, state):
        self.timer.start() if state == Qt.Checked else self.timer.stop()

    def refresh(self):
        if not self.win.ensure_login():
            return
        acc = self.account_combo.currentText()
        if not acc:
            return
        try:
            dep = self.win.query_deposit(acc)
            bal = self.win.mdata.get_account_balance(acc)
            s = bal["summary"]
            self.lbl_deposit.setText(f"{dep.get('예수금', 0):,} 원")
            self.lbl_orderable.setText(f"{dep.get('주문가능금액', 0):,} 원")
            self.lbl_eval.setText(f"{s['total_eval']:,} 원")
            self.lbl_profit.setText(f"{s['total_profit_rate']:+.2f} %")
            holdings = bal["holdings"]
            self.table.setRowCount(0)
            for _, row in holdings.iterrows():
                r = self.table.rowCount()
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row["name"])))
                self.table.setItem(r, 1, QTableWidgetItem(str(row["code"])))
                self.table.setItem(r, 2, _num_item(int(row["qty"]), money=True))
                self.table.setItem(r, 3, _num_item(int(row["avg_price"]), money=True))
                self.table.setItem(r, 4, _num_item(float(row["profit_rate"]), pct=True))
        except Exception as e:
            logger.error(f"계좌 조회 오류: {e}")


# =========================================================================
# 2) 종목 검색 탭
# =========================================================================
class SearchTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("종목코드(6자리) 또는 종목명 일부 입력")
        self.input.returnPressed.connect(self.search)
        top.addWidget(self.input)
        btn = QPushButton("검색")
        btn.clicked.connect(self.search)
        top.addWidget(btn)
        v.addLayout(top)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["코드", "종목명", "현재가", "등락률", "거래량"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(
            lambda r, c: self.win.open_chart(self.table.item(r, 0).text()))
        v.addWidget(self.table)

        bottom = QHBoxLayout()
        bottom.addStretch()
        order_btn = QPushButton("선택 종목 → 호가/주문")
        order_btn.clicked.connect(self.open_orderbook)
        bottom.addWidget(order_btn)
        add_btn = QPushButton("선택 종목 → 감시종목 추가")
        add_btn.clicked.connect(self.add_to_watch)
        bottom.addWidget(add_btn)
        v.addLayout(bottom)

    def _selected_code(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "선택", "종목을 먼저 선택하세요.")
            return None
        return self.table.item(rows[0], 0).text()

    def open_orderbook(self):
        code = self._selected_code()
        if code:
            self.win.open_orderbook(code)

    def search(self):
        if not self.win.ensure_login():
            return
        text = self.input.text().strip()
        if not text:
            return
        codes = []
        if text.isdigit() and len(text) == 6:
            codes = [text]
        else:
            codes = self.win.find_codes_by_name(text)[:30]
        if not codes:
            self.table.setRowCount(0)
            QMessageBox.information(self, "검색", "결과가 없습니다.")
            return

        cmap = self.win.build_code_map()
        self.table.setRowCount(0)
        no_quote = 0
        for code in codes:
            name = cmap.get(code) or self.win.kiwoom.get_master_code_name(code)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            try:
                info = self.win.mdata.get_stock_info(code)
            except Exception as e:
                logger.warning(f"[{code}] 시세 조회 실패: {e}")
                info = {"available": False, "price": 0, "change_rate": 0, "volume": 0}
            if info.get("available") and info["price"]:
                self.table.setItem(r, 2, _num_item(info["price"], money=True))
                self.table.setItem(r, 3, _num_item(info["change_rate"], pct=True))
                self.table.setItem(r, 4, _num_item(info["volume"], money=True))
            else:
                no_quote += 1
                for c in (2, 3, 4):
                    dash = QTableWidgetItem("-")
                    dash.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(r, c, dash)

        if no_quote == len(codes):
            self.win.statusBar().showMessage(
                "시세를 받지 못했습니다 — 모의투자 서버 시세 제한일 수 있습니다 (실서버 접속 시 정상).", 8000)

    def add_to_watch(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            return
        cfg = settings.load_config()
        existing = {w["code"] for w in cfg["watch_list"]}
        added = 0
        for r in rows:
            code = self.table.item(r, 0).text()
            name = self.table.item(r, 1).text()
            if code not in existing:
                cfg["watch_list"].append({"code": code, "name": name})
                existing.add(code)
                added += 1
        settings.save_config(cfg)
        QMessageBox.information(self, "감시종목", f"{added}개 추가됨 (config.json 저장).\n자동매매 재시작 시 반영됩니다.")


# =========================================================================
# 3) 조건 검색 탭
# =========================================================================
class ConditionTab(QWidget):
    """조건검색 기반 실시간 자동매매 관리 화면 (최대 10개 조건식)."""
    COLS = ["사용", "조건식", "편입매수", "이탈매도", "매수금액", "손절", "익절", "트레일링", "매칭"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.engine = None
        self.cond_rows = []        # 행별 위젯 묶음 dict
        self.row_by_idx = {}       # idx -> 행 dict
        v = QVBoxLayout(self)

        # 상단 버튼
        top = QHBoxLayout()
        self.load_btn = QPushButton("조건식 불러오기")
        self.load_btn.clicked.connect(self.load_conditions)
        top.addWidget(self.load_btn)
        self.save_btn = QPushButton("규칙 저장")
        self.save_btn.clicked.connect(self.save_rules)
        top.addWidget(self.save_btn)
        top.addStretch()
        self.count_lbl = QLabel("사용 0/10")
        top.addWidget(self.count_lbl)
        self.start_btn = QPushButton("▶ 조건 자동매매 시작")
        self.start_btn.clicked.connect(self.toggle_auto)
        top.addWidget(self.start_btn)
        v.addLayout(top)

        # 당일청산 옵션
        liq_row = QHBoxLayout()
        self.liq_chk = QCheckBox("당일청산")
        self.liq_chk.setToolTip("지정 시각에 보유 종목 전량 매도 + 신규 매수 중단")
        self.liq_time = QTimeEdit()
        self.liq_time.setDisplayFormat("HH:mm")
        self.liq_time.setTime(QTime(15, 15))
        _liq = settings.load_config().get("day_liquidation", {})
        self.liq_chk.setChecked(bool(_liq.get("enabled", False)))
        if _liq.get("time"):
            self.liq_time.setTime(QTime.fromString(_liq["time"], "HH:mm"))
        liq_row.addWidget(self.liq_chk)
        liq_row.addWidget(self.liq_time)
        liq_row.addWidget(QLabel("에 전량 청산"))
        liq_row.addStretch()
        v.addLayout(liq_row)

        self.status_lbl = QLabel("중지됨")
        self.status_lbl.setFont(QFont("", 10, QFont.Bold))
        v.addWidget(self.status_lbl)

        # 당일청산 점검 타이머 (엔진 가동 중에만 동작)
        self._liq_done = False
        self.liq_timer = QTimer(self)
        self.liq_timer.timeout.connect(self._check_liquidation)

        v.addWidget(QLabel("◆ 조건식별 자동매매 규칙  (사용 체크는 최대 10개 · 편입=매수, 이탈/손절/익절/트레일링=매도)"))
        self.rule_table = QTableWidget(0, len(self.COLS))
        self.rule_table.setHorizontalHeaderLabels(self.COLS)
        self.rule_table.verticalHeader().setVisible(False)
        self.rule_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        v.addWidget(self.rule_table, 2)

        v.addWidget(QLabel("◆ 실시간 현황  (편입/이탈/매수/매도)"))
        self.status_table = QTableWidget(0, 5)
        self.status_table.setHorizontalHeaderLabels(["시각", "종목", "조건식", "동작", "비고"])
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.status_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.status_table, 1)

    # -------------------------------------------------------- 조건식 로드
    def load_conditions(self):
        if not self.win.ensure_login():
            return
        conds = self.win.kiwoom.get_condition_load()
        if not conds:
            QMessageBox.information(self, "조건검색",
                "불러올 조건식이 없습니다.\n영웅문 HTS [0150] 조건검색에서 조건식을 만들어 저장해야 하며,\n"
                "모의투자 서버에서는 제한될 수 있습니다.")
            return
        saved = settings.load_config().get("condition_rules", {})
        self.rule_table.setRowCount(0)
        self.cond_rows = []
        self.row_by_idx = {}
        for idx, name in conds:
            self._add_rule_row(idx, name, saved.get(str(idx), {}))
        self._update_count()
        logger.info(f"조건식 {len(conds)}개 규칙표 로드")

    def _add_rule_row(self, idx, name, rule):
        r = self.rule_table.rowCount()
        self.rule_table.insertRow(r)
        disp = self.win.kiwoom.decode_text(name)

        use_w, use_cb = _checkbox_cell(rule.get("enabled", False))
        buy_w, buy_cb = _checkbox_cell(rule.get("buy_on_entry", True))
        sell_w, sell_cb = _checkbox_cell(rule.get("sell_on_exit", True))
        use_cb.stateChanged.connect(self._update_count)

        amount = QSpinBox()
        amount.setRange(0, 2_000_000_000)
        amount.setSingleStep(100_000)
        amount.setGroupSeparatorShown(True)
        amount.setSuffix(" 원")
        amount.setValue(int(rule.get("buy_amount", 0)))
        amount.setToolTip("0 이면 설정 탭의 기본 매수금액 사용")

        stop = QDoubleSpinBox(); stop.setRange(-100.0, 0.0); stop.setDecimals(1); stop.setSuffix(" %")
        stop.setValue(float(rule.get("stop_loss", settings.STOP_LOSS_RATE * 100)))
        take = QDoubleSpinBox(); take.setRange(0.0, 1000.0); take.setDecimals(1); take.setSuffix(" %")
        take.setValue(float(rule.get("take_profit", settings.TAKE_PROFIT_RATE * 100)))
        trail = QDoubleSpinBox(); trail.setRange(0.0, 50.0); trail.setDecimals(1); trail.setSuffix(" %")
        trail.setValue(float(rule.get("trailing_stop", 0)))
        trail.setToolTip("0이면 비활성. 수익 구간에서 고점 대비 이 비율만큼 하락 시 매도")

        name_item = QTableWidgetItem(f"[{idx}] {disp}")
        name_item.setFlags(Qt.ItemIsEnabled)
        match_item = QTableWidgetItem("0")
        match_item.setTextAlignment(Qt.AlignCenter)
        match_item.setFlags(Qt.ItemIsEnabled)

        self.rule_table.setCellWidget(r, 0, use_w)
        self.rule_table.setItem(r, 1, name_item)
        self.rule_table.setCellWidget(r, 2, buy_w)
        self.rule_table.setCellWidget(r, 3, sell_w)
        self.rule_table.setCellWidget(r, 4, amount)
        self.rule_table.setCellWidget(r, 5, stop)
        self.rule_table.setCellWidget(r, 6, take)
        self.rule_table.setCellWidget(r, 7, trail)
        self.rule_table.setItem(r, 8, match_item)

        row = {"idx": idx, "name": name, "disp": disp, "use": use_cb, "buy": buy_cb,
               "sell": sell_cb, "amount": amount, "stop": stop, "take": take,
               "trail": trail, "match": match_item, "count": 0}
        self.cond_rows.append(row)
        self.row_by_idx[idx] = row

    def _update_count(self):
        n = sum(1 for row in self.cond_rows if row["use"].isChecked())
        self.count_lbl.setText(f"사용 {n}/10")
        self.count_lbl.setStyleSheet("color:#d32f2f;font-weight:bold" if n > 10 else "")

    # ---------------------------------------------------------- 규칙 저장
    def _collect_rules(self):
        rules = {}
        for row in self.cond_rows:
            rules[str(row["idx"])] = {
                "name": row["disp"],
                "enabled": row["use"].isChecked(),
                "buy_on_entry": row["buy"].isChecked(),
                "sell_on_exit": row["sell"].isChecked(),
                "buy_amount": row["amount"].value(),
                "stop_loss": round(row["stop"].value(), 1),
                "take_profit": round(row["take"].value(), 1),
                "trailing_stop": round(row["trail"].value(), 1),
            }
        return rules

    def _day_liquidation_cfg(self):
        return {
            "enabled": self.liq_chk.isChecked(),
            "time": self.liq_time.time().toString("HH:mm"),
        }

    def save_rules(self):
        if not self.cond_rows:
            QMessageBox.information(self, "규칙 저장", "먼저 조건식을 불러오세요.")
            return
        cfg = settings.load_config()
        cfg["condition_rules"] = self._collect_rules()
        cfg["day_liquidation"] = self._day_liquidation_cfg()
        settings.save_config(cfg)
        QMessageBox.information(self, "규칙 저장", "조건식별 자동매매 규칙을 저장했습니다.")

    # ------------------------------------------------------- 시작 / 중지
    def toggle_auto(self):
        if self.engine and self.engine.running:
            self.engine.stop()
            self.liq_timer.stop()
            self.start_btn.setText("▶ 조건 자동매매 시작")
            self.status_lbl.setText("중지됨")
            return
        if not self.win.ensure_login():
            return
        enabled = [(row["idx"], row["name"]) for row in self.cond_rows if row["use"].isChecked()]
        if not enabled:
            QMessageBox.information(self, "조건 자동매매", "사용할 조건식을 1개 이상 체크하세요.")
            return
        if len(enabled) > 10:
            QMessageBox.warning(self, "조건 자동매매",
                f"사용 조건식은 최대 10개입니다. (현재 {len(enabled)}개)\n초과분 체크를 해제하세요.")
            return
        # 규칙 저장 + 라이브 규칙 구성
        self._live_rules = self._collect_rules()
        cfg = settings.load_config()
        cfg["condition_rules"] = self._live_rules
        cfg["day_liquidation"] = self._day_liquidation_cfg()
        settings.save_config(cfg)
        # 매칭 카운트 초기화
        for row in self.cond_rows:
            row["count"] = 0
            row["match"].setText("0")

        if not self.win.build_trader():
            return
        self.engine = ConditionAutoTrader(
            self.win.kiwoom, self.win.trader,
            rules_provider=lambda: self._live_rules,
            status_cb=self._on_status,
        )
        self.engine.start(enabled)
        if not self.engine.active:
            QMessageBox.warning(self, "조건 자동매매",
                "조건식 실시간 등록에 모두 실패했습니다(로그 확인).\n장 마감 후/동시등록 초과일 수 있습니다.")
            self.status_lbl.setText("중지됨")
            return
        self.start_btn.setText("■ 중지")
        self._liq_done = False
        if self.liq_chk.isChecked():
            self.liq_timer.start(20_000)  # 20초마다 당일청산 시각 점검
        liq_msg = f" · 당일청산 {self.liq_time.time().toString('HH:mm')}" if self.liq_chk.isChecked() else ""
        self.status_lbl.setText(
            f"실행중 — 조건식 {len(self.engine.active)}개 실시간 등록 / "
            f"편입매수·이탈매도·손절익절·트레일링 작동{liq_msg}")

    def _check_liquidation(self):
        """당일청산 시각 도달 시 전량 매도 (1회만)."""
        if self._liq_done or not self.engine or not self.engine.running:
            return
        if not self.liq_chk.isChecked():
            return
        now = QTime.currentTime()
        if now >= self.liq_time.time():
            self._liq_done = True
            logger.info("당일청산 시각 도달 — 전량 매도 실행")
            self.engine.liquidate_all(reason="당일청산")
            self.status_lbl.setText("당일청산 완료 — 신규 매수 중단됨 (중지하려면 ■)")

    # ------------------------------------------------------- 상태 콜백
    def _on_status(self, kind, info):
        # 키움 이벤트는 메인(GUI) 스레드에서 전달되므로 직접 갱신해도 안전
        if kind in ("start", "stop"):
            return
        # 매칭 카운트 갱신
        cond = info.get("cond")
        if cond is not None and cond in self.row_by_idx:
            row = self.row_by_idx[cond]
            if kind == "entry":
                row["count"] += 1
            elif kind == "exit":
                row["count"] = max(0, row["count"] - 1)
            row["match"].setText(str(row["count"]))

        labels = {"entry": "편입", "exit": "이탈", "buy": "매수", "sell": "매도",
                  "chejan": "체결", "liquidate": "당일청산"}
        code = info.get("code", "")
        name = info.get("name") or (self.win.kiwoom.get_master_code_name(code) if code else "")
        note = info.get("reason") or (f"{info['price']:,}원" if info.get("price") else "")
        if kind == "liquidate":
            note = f"{info.get('count', 0)}종목 전량 매도 · 신규매수 중단"
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        r = self.status_table.rowCount()
        self.status_table.insertRow(r)
        self.status_table.setItem(r, 0, QTableWidgetItem(ts))
        self.status_table.setItem(r, 1, QTableWidgetItem(f"{name}({code})" if code else ""))
        self.status_table.setItem(r, 2, QTableWidgetItem(str(cond if cond is not None else "")))
        act = QTableWidgetItem(labels.get(kind, kind))
        if kind == "buy":
            act.setForeground(QColor("#d32f2f"))
        elif kind == "sell":
            act.setForeground(QColor("#1565c0"))
        self.status_table.setItem(r, 3, act)
        self.status_table.setItem(r, 4, QTableWidgetItem(str(note)))
        self.status_table.scrollToBottom()


# =========================================================================
# 조건식 시뮬레이션 탭 (편입종목 조회 + 과거 데이터 청산룰 백테스트)
# =========================================================================
class ConditionSimTab(QWidget):
    """조건식이 현재 잡아내는 종목을 조회하고, 그 종목들에 대해 손절/익절/
    트레일링 청산 룰을 과거 일봉으로 시뮬레이션한다.

    ※ 키움 OpenAPI는 조건식 수식 내용과 과거 편입 시점을 제공하지 않는다.
       따라서 '현재 편입 종목을 기간 시작일에 매수했다고 가정'하고 청산 룰만
       시뮬레이션한다. (수식 자체의 조회/수정은 영웅문 [0150]에서)
    """
    SIM_COLS = ["코드", "종목명", "매수일", "매수가", "청산일", "청산가", "보유일", "수익률", "사유"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.codes = []   # 현재 편입 종목코드
        v = QVBoxLayout(self)

        # 안내
        note = QLabel(
            "ℹ 조건식 '수식 내용'은 키움 API가 제공하지 않아 영웅문 [0150]에서만 편집됩니다.\n"
            "   여기서는 조건식이 현재 잡아내는 종목을 조회하고, 그 종목들을 기간 시작일에\n"
            "   매수했다고 가정하여 손절/익절/트레일링 청산 룰을 과거 데이터로 시뮬레이션합니다.")
        note.setStyleSheet("color:#555;background:#f4f6f8;padding:6px;border-radius:4px;")
        v.addWidget(note)

        # 조건식 선택
        row1 = QHBoxLayout()
        self.load_btn = QPushButton("조건식 불러오기")
        self.load_btn.clicked.connect(self.load_conditions)
        row1.addWidget(self.load_btn)
        self.cond_combo = QComboBox()
        self.cond_combo.setMinimumWidth(220)
        row1.addWidget(self.cond_combo, 1)
        self.fetch_btn = QPushButton("현재 편입종목 조회")
        self.fetch_btn.clicked.connect(self.fetch_stocks)
        row1.addWidget(self.fetch_btn)
        v.addLayout(row1)

        # 시뮬 파라미터
        params = QGroupBox("시뮬레이션 조건")
        pf = QHBoxLayout(params)
        self.period = QSpinBox(); self.period.setRange(20, 1000); self.period.setValue(180); self.period.setSuffix(" 일")
        self.stop = QDoubleSpinBox(); self.stop.setRange(-100, 0); self.stop.setDecimals(1); self.stop.setValue(settings.STOP_LOSS_RATE * 100); self.stop.setSuffix(" %")
        self.take = QDoubleSpinBox(); self.take.setRange(0, 1000); self.take.setDecimals(1); self.take.setValue(settings.TAKE_PROFIT_RATE * 100); self.take.setSuffix(" %")
        self.trail = QDoubleSpinBox(); self.trail.setRange(0, 50); self.trail.setDecimals(1); self.trail.setValue(0); self.trail.setSuffix(" %")
        pf.addWidget(QLabel("기간")); pf.addWidget(self.period)
        pf.addWidget(QLabel("손절")); pf.addWidget(self.stop)
        pf.addWidget(QLabel("익절")); pf.addWidget(self.take)
        pf.addWidget(QLabel("트레일링")); pf.addWidget(self.trail)
        pf.addStretch()
        self.run_btn = QPushButton("▶ 과거 데이터 시뮬레이션")
        self.run_btn.clicked.connect(self.run_sim)
        pf.addWidget(self.run_btn)
        v.addWidget(params)

        # 편입종목 / 결과 요약
        self.summary = QLabel("조건식을 불러와 편입종목을 조회한 뒤 시뮬레이션을 실행하세요.")
        self.summary.setFont(QFont("", 10, QFont.Bold))
        v.addWidget(self.summary)

        # 결과 테이블
        self.table = QTableWidget(0, len(self.SIM_COLS))
        self.table.setHorizontalHeaderLabels(self.SIM_COLS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(
            lambda r, c: self.win.open_chart(self.table.item(r, 0).text()))
        v.addWidget(self.table, 1)

    # ----------------------------------------------------------- 조건식 로드
    def load_conditions(self):
        if not self.win.ensure_login():
            return
        conds = self.win.kiwoom.get_condition_load()
        if not conds:
            QMessageBox.information(self, "조건검색", "불러올 조건식이 없습니다 (모의투자 제한 가능).")
            return
        self.cond_combo.clear()
        for idx, name in conds:
            self.cond_combo.addItem(f"[{idx}] {self.win.kiwoom.decode_text(name)}", (idx, name))
        logger.info(f"시뮬레이션 탭: 조건식 {len(conds)}개 로드")

    def _current_cond(self):
        data = self.cond_combo.currentData()
        if not data:
            QMessageBox.information(self, "조건식", "먼저 조건식을 불러오고 선택하세요.")
        return data

    # --------------------------------------------------- 현재 편입종목 조회
    def fetch_stocks(self):
        if not self.win.ensure_login():
            return
        data = self._current_cond()
        if not data:
            return
        idx, name = data
        codes = self.win.kiwoom.send_condition(SCREEN_SIM, name, idx, 0)
        if codes is None:
            QMessageBox.warning(self, "조회 실패",
                "조건검색 단발 조회에 실패했습니다 (상한가/체결기반 조건은 실시간 전용이거나 모의투자 제한).")
            return
        self.codes = codes
        self.table.setRowCount(0)
        for code in codes:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(self.win.kiwoom.get_master_code_name(code)))
        disp = self.win.kiwoom.decode_text(name)
        self.summary.setText(f"[{idx}] {disp} — 현재 편입 {len(codes)}종목. '시뮬레이션'으로 과거 성과를 확인하세요.")
        if not codes:
            self.summary.setText(f"[{idx}] {disp} — 현재 편입 종목이 없습니다 (장 마감 후엔 정상일 수 있음).")

    # ------------------------------------------------------- 과거 시뮬레이션
    def run_sim(self):
        if not self.win.ensure_login():
            return
        if not self.codes:
            QMessageBox.information(self, "시뮬레이션", "먼저 '현재 편입종목 조회'를 실행하세요.")
            return
        codes = self.codes[:30]  # 과부하 방지 상위 30종목
        start = (datetime.datetime.now()
                 - datetime.timedelta(days=self.period.value())).strftime("%Y%m%d")
        stop = self.stop.value()
        take = self.take.value()
        trail = self.trail.value()

        self.run_btn.setEnabled(False)
        self.table.setRowCount(0)
        results = []
        for n, code in enumerate(codes):
            name = self.win.kiwoom.get_master_code_name(code)
            self.summary.setText(f"시뮬레이션 중... {n + 1}/{len(codes)}  {name}({code})")
            QApplication.processEvents()
            try:
                df = self.win.mdata.get_daily_ohlcv(code, start)
            except Exception as e:
                logger.warning(f"[{code}] 일봉 조회 실패: {e}")
                df = None
            res = simulate_exit_rules(df, stop_pct=stop, take_pct=take, trail_pct=trail) if df is not None and len(df) else None
            results.append(res)
            self._add_result_row(code, name, res)

        self.run_btn.setEnabled(True)
        self._render_summary(summarize(results), len(codes), stop, take, trail)

    def _add_result_row(self, code, name, res):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(code))
        self.table.setItem(r, 1, QTableWidgetItem(name))
        if not res:
            self.table.setItem(r, 2, QTableWidgetItem("데이터 없음"))
            return
        self.table.setItem(r, 2, QTableWidgetItem(res["entry_date"].strftime("%y/%m/%d")))
        self.table.setItem(r, 3, _num_item(int(res["entry_price"]), money=True))
        self.table.setItem(r, 4, QTableWidgetItem(res["exit_date"].strftime("%y/%m/%d")))
        self.table.setItem(r, 5, _num_item(int(res["exit_price"]), money=True))
        self.table.setItem(r, 6, _num_item(res["days"]))
        self.table.setItem(r, 7, _num_item(round(res["return_pct"], 2), pct=True))
        self.table.setItem(r, 8, QTableWidgetItem(res["reason"]))

    def _render_summary(self, s, n_total, stop, take, trail):
        if s["count"] == 0:
            self.summary.setText("시뮬레이션 결과 없음 (일봉 데이터를 받지 못했습니다 — 모의투자 제한 가능).")
            return
        reasons = ", ".join(f"{k} {v}" for k, v in s["by_reason"].items())
        color = "#d32f2f" if s["avg_return"] >= 0 else "#1565c0"
        self.summary.setText(
            f"<b>시뮬 결과</b> (손절 {stop:.1f}% · 익절 {take:.1f}% · 트레일링 {trail:.1f}%) — "
            f"{s['count']}종목 · 승률 <b>{s['win_rate']:.0f}%</b> · "
            f"평균수익률 <b style='color:{color}'>{s['avg_return']:+.2f}%</b> · "
            f"평균보유 {s['avg_days']:.0f}일 · 최고 {s['best']:+.1f}% / 최저 {s['worst']:+.1f}% · [{reasons}]")


# =========================================================================
# 4) 자동매매 모니터 탭
# =========================================================================
class MonitorTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.running = False
        self.rows = {}  # code -> row index
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.start_btn = QPushButton("▶ 자동매매 시작")
        self.start_btn.clicked.connect(self.toggle)
        top.addWidget(self.start_btn)
        self.status = QLabel("중지됨")
        self.status.setFont(QFont("", 10, QFont.Bold))
        top.addWidget(self.status)
        top.addStretch()
        v.addLayout(top)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["코드", "종목명", "현재가", "등락률", "신호"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        v.addWidget(self.table)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._run_strategy)

    def toggle(self):
        if not self.running:
            self.start()
        else:
            self.stop()

    def start(self):
        if not self.win.ensure_login():
            return
        if not self.win.build_trader():
            return
        codes = [w["code"] for w in self.win.watch_list()]
        self._init_table(codes)
        # 실시간 시세 등록
        self.win.kiwoom.register_real_callback(SCREEN_REAL, self._on_real)
        if codes:
            self.win.kiwoom.set_real_reg(SCREEN_REAL, ";".join(codes), REAL_FIDS, "0")
        # 스케줄 타이머
        self.timer.setInterval(max(1, settings.CHECK_INTERVAL_MIN) * 60_000)
        self.timer.start()
        self.running = True
        self.start_btn.setText("■ 자동매매 중지")
        self.status.setText(f"실행중 — 전략 {settings.STRATEGY.upper()}, {settings.CHECK_INTERVAL_MIN}분 주기")
        logger.info("자동매매 시작 (HTS)")
        self._run_strategy()  # 즉시 1회

    def stop(self):
        self.timer.stop()
        try:
            self.win.kiwoom.set_real_remove(SCREEN_REAL, "ALL")
        except Exception:
            pass
        self.running = False
        self.start_btn.setText("▶ 자동매매 시작")
        self.status.setText("중지됨")
        logger.info("자동매매 중지 (HTS)")

    def _init_table(self, codes):
        self.table.setRowCount(0)
        self.rows = {}
        for code in codes:
            name = self.win.kiwoom.get_master_code_name(code)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, QTableWidgetItem("-"))
            self.table.setItem(r, 3, QTableWidgetItem("-"))
            self.table.setItem(r, 4, QTableWidgetItem("-"))
            self.rows[code] = r

    def _on_real(self, code, real_type, real_data):
        if code not in self.rows:
            return
        try:
            price = abs(int(self.win.kiwoom.get_comm_real_data(code, 10) or 0))
            rate = float(self.win.kiwoom.get_comm_real_data(code, 12) or 0)
        except Exception:
            return
        r = self.rows[code]
        self.table.setItem(r, 2, _num_item(price, money=True))
        self.table.setItem(r, 3, _num_item(rate, pct=True))

    def _run_strategy(self):
        if not self.win.trader:
            return
        try:
            self.win.trader.run_strategy(self.win.watch_list())
            self.table.setItem  # no-op safeguard
        except Exception as e:
            logger.error(f"전략 실행 오류: {e}")


# =========================================================================
# 5) 조건 검색(단발) 탭 — 현재 조건을 만족하는 종목 조회
# =========================================================================
class ScreenerTab(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.load_btn = QPushButton("조건식 불러오기")
        self.load_btn.clicked.connect(self.load_conditions)
        top.addWidget(self.load_btn)
        self.combo = QComboBox()
        top.addWidget(self.combo, 1)
        self.search_btn = QPushButton("검색")
        self.search_btn.clicked.connect(self.search)
        top.addWidget(self.search_btn)
        v.addLayout(top)

        self.info = QLabel("조건식을 불러와 선택한 뒤 [검색] (단발 조회). 행을 더블클릭하면 차트가 열립니다.")
        v.addWidget(self.info)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["코드", "종목명", "현재가", "등락률"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.cellDoubleClicked.connect(self._open_chart)
        v.addWidget(self.table)

    def load_conditions(self):
        if not self.win.ensure_login():
            return
        conds = self.win.kiwoom.get_condition_load()
        self.combo.clear()
        if not conds:
            QMessageBox.information(self, "조건검색", "불러올 조건식이 없습니다.")
            return
        for idx, name in conds:
            self.combo.addItem(f"[{idx}] {self.win.kiwoom.decode_text(name)}", (idx, name))

    def search(self):
        if not self.win.ensure_login():
            return
        data = self.combo.currentData()
        if not data:
            QMessageBox.information(self, "조건검색", "먼저 조건식을 불러와 선택하세요.")
            return
        idx, name = data
        codes = self.win.kiwoom.send_condition(f"54{idx % 100:02d}", name, idx, 0)
        if codes is None:
            QMessageBox.warning(self, "조건검색", "요청이 거부되었습니다(로그 확인).")
            return
        self.table.setRowCount(0)
        if not codes:
            self.info.setText("검색 결과 0종목 (장 마감 후엔 정상일 수 있음).")
            return
        self.info.setText(f"검색 결과 {len(codes)}종목 · 현재가는 상위 30종목만 표시 · 더블클릭 → 차트")
        for i, code in enumerate(codes):
            name_ = self.win.kiwoom.get_master_code_name(code)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(name_))
            if i < 30:
                try:
                    info = self.win.mdata.get_stock_info(code)
                    self.table.setItem(r, 2, _num_item(info["price"], money=True))
                    self.table.setItem(r, 3, _num_item(info["change_rate"], pct=True))
                except Exception:
                    pass

    def _open_chart(self, row, col):
        item = self.table.item(row, 0)
        if item:
            self.win.open_chart(item.text())


# =========================================================================
# 6) 차트 탭 — 종목별 일봉 캔들 차트
# =========================================================================
class ChartTab(QWidget):
    PERIODS = [("3개월", 90), ("6개월", 180), ("1년", 365)]

    def __init__(self, win):
        super().__init__()
        self.win = win
        v = QVBoxLayout(self)

        top = QHBoxLayout()
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("종목코드(6자리) 또는 종목명")
        self.code_input.setMaximumWidth(220)
        self.code_input.returnPressed.connect(self.show_chart)
        top.addWidget(self.code_input)
        self.period = QComboBox()
        for label, _days in self.PERIODS:
            self.period.addItem(label)
        top.addWidget(self.period)
        self.btn = QPushButton("차트 조회")
        self.btn.clicked.connect(self.show_chart)
        top.addWidget(self.btn)
        self.title = QLabel("")
        self.title.setFont(QFont("", 11, QFont.Bold))
        top.addWidget(self.title)
        top.addStretch()
        v.addLayout(top)

        self.chart = CandleChart()
        v.addWidget(self.chart, 1)

    def show_chart(self, code=None):
        if not self.win.ensure_login():
            return
        if isinstance(code, str) and code:
            self.code_input.setText(code)
        code = self.win.resolve_code(self.code_input.text(), parent=self)
        if not code:
            return
        self.code_input.setText(code)
        days = self.PERIODS[self.period.currentIndex()][1]
        start = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y%m%d")
        try:
            df = self.win.mdata.get_daily_ohlcv(code, start)
        except Exception as e:
            logger.error(f"차트 데이터 조회 실패: {e}")
            QMessageBox.warning(self, "차트", f"데이터 조회 실패: {e}")
            return
        name = self.win.kiwoom.get_master_code_name(code)
        self.title.setText(f"{name} ({code})")
        self.chart.set_data(df)
        if len(df) == 0:
            QMessageBox.information(self, "차트",
                "데이터가 없습니다. 거래정지/신규상장이거나, TR 과부하(잠시 후 재시도)일 수 있습니다.")
            return
        logger.info(f"차트 표시: {name}({code}) {len(df)}봉")


# =========================================================================
# 메인 윈도우
# =========================================================================
# =========================================================================
# 호가/주문 탭 (10호가 실시간 주문판 + 수동 매수/매도)
# =========================================================================
class OrderBookTab(QWidget):
    """실시간 10호가창과 수동 주문 패널.

    영웅문 [4989] 키움주문 화면처럼 호가/현재가를 클릭하면 주문가격이
    자동 입력되어 빠른 수동 매매가 가능하다.
    """
    ASK_BG = QColor("#e3f0fb")   # 매도 영역 배경 (연파랑)
    BID_BG = QColor("#fde7ea")   # 매수 영역 배경 (연빨강)
    HIT_BG = QColor("#fff3c4")   # 클릭된 호가 강조

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.code = None
        self.prev_close = 0
        self.running = False

        root = QVBoxLayout(self)

        # --- 종목 입력 ---
        top = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("종목코드(6자리) 또는 종목명")
        self.input.returnPressed.connect(self.load_symbol)
        top.addWidget(self.input)
        load_btn = QPushButton("조회")
        load_btn.clicked.connect(self.load_symbol)
        top.addWidget(load_btn)
        chart_btn = QPushButton("차트")
        chart_btn.clicked.connect(lambda: self.code and self.win.open_chart(self.code))
        top.addWidget(chart_btn)
        root.addLayout(top)

        # --- 현재가 헤더 ---
        self.header = QLabel("종목을 조회하세요")
        self.header.setFont(QFont("", 12, QFont.Bold))
        root.addWidget(self.header)

        body = QHBoxLayout()

        # --- 10호가 테이블 ---
        self.book = QTableWidget(20, 3)
        self.book.setHorizontalHeaderLabels(["매도잔량", "호가", "매수잔량"])
        self.book.verticalHeader().setVisible(False)
        self.book.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.book.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.book.setSelectionMode(QAbstractItemView.NoSelection)
        self.book.setFixedWidth(360)
        for r in range(20):
            self.book.setRowHeight(r, 22)
            ask = r < 10
            for c in range(3):
                it = QTableWidgetItem("")
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if c != 1
                                    else Qt.AlignCenter)
                it.setBackground(self.ASK_BG if ask else self.BID_BG)
                self.book.setItem(r, c, it)
        self.book.cellClicked.connect(self._on_cell_clicked)
        body.addWidget(self.book)

        # --- 주문 패널 ---
        panel = QGroupBox("수동 주문")
        form = QFormLayout(panel)
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 1_000_000)
        self.qty_spin.setValue(1)
        self.qty_spin.setGroupSeparatorShown(True)
        self.price_spin = QSpinBox()
        self.price_spin.setRange(0, 100_000_000)
        self.price_spin.setSingleStep(10)
        self.price_spin.setGroupSeparatorShown(True)
        self.market_chk = QCheckBox("시장가 주문")
        self.market_chk.toggled.connect(self._on_market_toggled)
        form.addRow("수량", self.qty_spin)
        form.addRow("가격", self.price_spin)
        form.addRow("", self.market_chk)

        # 금액 / 빠른 수량 버튼
        qrow = QHBoxLayout()
        for label, frac in [("10%", 0.1), ("25%", 0.25), ("50%", 0.5), ("최대", 1.0)]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, f=frac: self._set_qty_by_cash(f))
            qrow.addWidget(b)
        form.addRow("주문가능 기준", self._wrap(qrow))

        self.est_lbl = QLabel("예상 주문금액: -")
        form.addRow("", self.est_lbl)
        self.qty_spin.valueChanged.connect(self._update_estimate)
        self.price_spin.valueChanged.connect(self._update_estimate)

        btn_row = QHBoxLayout()
        self.buy_btn = QPushButton("매수")
        self.buy_btn.setStyleSheet("background:#d32f2f;color:white;font-weight:bold;padding:8px;")
        self.buy_btn.clicked.connect(lambda: self.send_order(1))
        self.sell_btn = QPushButton("매도")
        self.sell_btn.setStyleSheet("background:#1565c0;color:white;font-weight:bold;padding:8px;")
        self.sell_btn.clicked.connect(lambda: self.send_order(2))
        btn_row.addWidget(self.buy_btn)
        btn_row.addWidget(self.sell_btn)
        form.addRow(self._wrap(btn_row))

        hint = QLabel("호가를 클릭하면 주문가격이 입력됩니다.\n실거래 모드에서는 실제 주문이 전송됩니다.")
        hint.setStyleSheet("color:#666;font-size:11px;")
        form.addRow(hint)

        body.addWidget(panel)
        root.addLayout(body)

    # ----------------------------------------------------------- 유틸
    @staticmethod
    def _wrap(layout):
        w = QWidget()
        w.setLayout(layout)
        return w

    def _on_market_toggled(self, checked):
        self.price_spin.setEnabled(not checked)
        self._update_estimate()

    def _update_estimate(self):
        if self.market_chk.isChecked():
            self.est_lbl.setText("예상 주문금액: 시장가")
            return
        amt = self.qty_spin.value() * self.price_spin.value()
        self.est_lbl.setText(f"예상 주문금액: {amt:,} 원")

    def _set_qty_by_cash(self, frac):
        price = self.price_spin.value()
        if price <= 0:
            QMessageBox.information(self, "주문", "가격을 먼저 입력하세요 (호가 클릭).")
            return
        try:
            dep = self.win.query_deposit(self.win.account)
            cash = int(dep.get("주문가능금액", 0))
        except Exception:
            cash = 0
        if cash <= 0:
            QMessageBox.information(self, "주문", "주문가능금액을 확인할 수 없습니다 (모의투자 제한 가능).")
            return
        qty = int(cash * frac) // price
        self.qty_spin.setValue(max(1, qty))

    # ----------------------------------------------------------- 종목 조회
    def load_symbol(self):
        if not self.win.ensure_login():
            return
        code = self.win.resolve_code(self.input.text(), self)
        if not code:
            return
        self.set_symbol(code)

    def set_symbol(self, code):
        """외부(검색/차트)에서도 호출 가능한 종목 설정 + 실시간 구독."""
        if not self.win.ensure_login():
            return
        # 이전 종목 실시간 해제
        if self.code:
            try:
                self.win.kiwoom.set_real_remove(SCREEN_HOGA, self.code)
            except Exception:
                pass
        self.code = code
        name = self.win.kiwoom.get_master_code_name(code)
        self.input.setText(f"{name} ({code})")
        self.header.setText(f"{name} ({code})  조회 중...")
        # 초기 스냅샷 (현재가)
        try:
            info = self.win.mdata.get_stock_info(code)
            self.prev_close = info["price"]
            if not self.market_chk.isChecked():
                self.price_spin.setValue(info["price"])
            self._render_header(info["price"], info["change_rate"], info["volume"])
        except Exception as e:
            logger.warning(f"[{code}] 초기 시세 조회 실패: {e} (모의투자 제한 가능)")
        # 실시간 구독
        self.win.kiwoom.register_real_callback(SCREEN_HOGA, self._on_real)
        self.win.kiwoom.set_real_reg(SCREEN_HOGA, code, HOGA_REAL_FIDS, "0")
        self.running = True
        logger.info(f"호가창 구독: {name} ({code})")

    def _render_header(self, price, rate, volume):
        color = "#d32f2f" if rate >= 0 else "#1565c0"
        name = self.win.kiwoom.get_master_code_name(self.code) if self.code else ""
        self.header.setText(
            f"<span>{name} ({self.code})</span> &nbsp; "
            f"<span style='color:{color}'>{price:,}원  {rate:+.2f}%</span> &nbsp; "
            f"<span style='color:#555'>거래량 {volume:,}</span>"
        )

    # ----------------------------------------------------------- 실시간 수신
    def _on_real(self, code, real_type, real_data):
        # real_type 문자열은 CP949 mojibake 가능성이 있어 FID 값 존재 여부로 판단한다.
        if code != self.code:
            return
        k = self.win.kiwoom

        def _v(fid):
            try:
                return abs(int(k.get_comm_real_data(code, fid) or 0))
            except (ValueError, TypeError):
                return 0

        # 체결(현재가 10) 데이터가 있으면 헤더 갱신
        price = _v(10)
        if price:
            try:
                rate = float(k.get_comm_real_data(code, 12) or 0)
            except ValueError:
                rate = 0.0
            self._render_header(price, rate, _v(13))

        # 호가(매도호가1 = FID 41) 데이터가 있으면 10호가 테이블 갱신
        if _v(ASK_PRICE_FIDS[-1]) or _v(BID_PRICE_FIDS[0]):
            self._fill_book(_v)

    def _fill_book(self, _v):
        cur = self.prev_close
        # 매도호가 (행 0~9: 위=호가10, 아래=호가1)
        for i in range(10):
            price = _v(ASK_PRICE_FIDS[i])
            qty = _v(ASK_QTY_FIDS[i])
            self._set_book_cell(i, 0, qty)
            self._set_book_price(i, price, cur)
            self._set_book_cell(i, 2, "")
        # 매수호가 (행 10~19: 위=호가1, 아래=호가10)
        for i in range(10):
            r = 10 + i
            price = _v(BID_PRICE_FIDS[i])
            qty = _v(BID_QTY_FIDS[i])
            self._set_book_cell(r, 0, "")
            self._set_book_price(r, price, cur)
            self._set_book_cell(r, 2, qty)

    def _set_book_cell(self, r, c, value):
        it = self.book.item(r, c)
        it.setText(f"{value:,}" if isinstance(value, int) and value else
                   ("" if value == "" or value == 0 else str(value)))

    def _set_book_price(self, r, price, cur):
        it = self.book.item(r, 1)
        if not price:
            it.setText("")
            return
        it.setText(f"{price:,}")
        if cur:
            if price > cur:
                it.setForeground(QColor("#d32f2f"))
            elif price < cur:
                it.setForeground(QColor("#1565c0"))
            else:
                it.setForeground(QColor("black"))

    def _on_cell_clicked(self, r, c):
        it = self.book.item(r, 1)
        if not it or not it.text():
            return
        try:
            price = int(it.text().replace(",", ""))
        except ValueError:
            return
        if self.market_chk.isChecked():
            self.market_chk.setChecked(False)
        self.price_spin.setValue(price)
        # 강조 표시
        for rr in range(20):
            base = self.ASK_BG if rr < 10 else self.BID_BG
            self.book.item(rr, 1).setBackground(base)
        self.book.item(r, 1).setBackground(self.HIT_BG)

    # ----------------------------------------------------------- 주문 전송
    def send_order(self, order_type):
        """order_type: 1=매수, 2=매도"""
        if not self.win.ensure_login():
            return
        if not self.code:
            QMessageBox.information(self, "주문", "먼저 종목을 조회하세요.")
            return
        if not self.win.account:
            QMessageBox.warning(self, "주문", "계좌 정보가 없습니다.")
            return

        qty = self.qty_spin.value()
        is_market = self.market_chk.isChecked()
        price = 0 if is_market else self.price_spin.value()
        hoga_gb = "03" if is_market else "00"
        if not is_market and price <= 0:
            QMessageBox.information(self, "주문", "지정가 주문은 가격을 입력해야 합니다.")
            return

        name = self.win.kiwoom.get_master_code_name(self.code)
        side = "매수" if order_type == 1 else "매도"
        price_str = "시장가" if is_market else f"{price:,}원"
        mode = "모의투자" if settings.IS_SIMUL else "⚠️ 실거래"
        msg = (f"[{mode}] {side} 주문을 전송할까요?\n\n"
               f"종목: {name} ({self.code})\n수량: {qty:,}주\n가격: {price_str}")
        if QMessageBox.question(self, f"{side} 확인", msg,
                                QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return

        try:
            ret = self.win.kiwoom.send_order(
                rq_name=f"수동{side}", screen_no=SCREEN_MANUAL_ORDER,
                account=self.win.account, order_type=order_type,
                code=self.code, qty=qty, price=price, hoga_gb=hoga_gb,
            )
            if ret == 0:
                logger.info(f"[수동주문] {side} 전송: {name}({self.code}) {qty}주 @ {price_str}")
                self.win.statusBar().showMessage(f"{side} 주문 전송됨: {name} {qty}주 @ {price_str}")
            else:
                logger.error(f"[수동주문] {side} 실패: ret={ret}")
                QMessageBox.warning(self, "주문 실패", f"주문 전송 실패 (ret={ret})")
        except Exception as e:
            logger.error(f"[수동주문] 오류: {e}")
            QMessageBox.critical(self, "주문 오류", str(e))

    def stop(self):
        if self.code:
            try:
                self.win.kiwoom.set_real_remove(SCREEN_HOGA, self.code)
            except Exception:
                pass
        self.running = False


class HTSWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("키움 자동매매 HTS")
        self.resize(900, 680)

        self.kiwoom = None
        self.mdata = None
        self.trader = None
        self.account = None
        self.logged_in = False
        self._code_map = None      # {code: name}
        self._cond_watch = None    # 조건검색 기반 감시종목 override

        # 탭
        self.tabs = QTabWidget()
        self.account_tab = AccountTab(self)
        self.search_tab = SearchTab(self)
        self.screener_tab = ScreenerTab(self)
        self.chart_tab = ChartTab(self)
        self.orderbook_tab = OrderBookTab(self)
        self.cond_tab = ConditionTab(self)
        self.sim_tab = ConditionSimTab(self)
        self.monitor_tab = MonitorTab(self)
        self.settings_tab = SettingsWindow()
        self.tabs.addTab(self.account_tab, "계좌 관리")
        self.tabs.addTab(self.search_tab, "종목 검색")
        self.tabs.addTab(self.screener_tab, "조건 검색")
        self.tabs.addTab(self.chart_tab, "차트")
        self.tabs.addTab(self.orderbook_tab, "호가/주문")
        self.tabs.addTab(self.cond_tab, "조건 자동매매")
        self.tabs.addTab(self.sim_tab, "조건식 시뮬레이션")
        self.tabs.addTab(self.monitor_tab, "자동매매")
        self.tabs.addTab(self.settings_tab, "설정")
        self.setCentralWidget(self.tabs)

        # 상단 로그인 바
        bar = QWidget()
        hb = QHBoxLayout(bar)
        self.login_btn = QPushButton("키움 로그인")
        self.login_btn.clicked.connect(self.do_login)
        hb.addWidget(self.login_btn)
        self.conn_lbl = QLabel("미접속")
        hb.addWidget(self.conn_lbl)
        hb.addStretch()
        self.setMenuWidget(bar)

        # 로그 도크
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000) if hasattr(self.log_view, "setMaximumBlockCount") else None
        dock = QDockWidget("로그", self)
        dock.setWidget(self.log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)

        handler = QtLogHandler()
        handler.log.connect(self.log_view.append)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        self.statusBar().showMessage("키움 로그인을 눌러 시작하세요.")

    # ---------------------------------------------------------- 로그인
    def do_login(self):
        if self.logged_in:
            QMessageBox.information(self, "로그인", "이미 로그인되어 있습니다.")
            return
        try:
            self.statusBar().showMessage("로그인 중...")
            self.kiwoom = KiwoomAPI()
            self.kiwoom.login()
            self.mdata = MarketDataAPI(self.kiwoom)
            self.logged_in = True

            accounts = self.kiwoom.get_account_list()
            server = self.kiwoom.get_login_info("GetServerGubun")
            server_str = "모의투자" if server == "1" else "실거래"
            user = self.kiwoom.get_login_info("USER_NAME")

            # 계좌 콤보 채우기 (설정 계좌 우선 선택)
            self.account_tab.account_combo.clear()
            self.account_tab.account_combo.addItems(accounts)
            if settings.ACCOUNT_NUMBER in accounts:
                self.account_tab.account_combo.setCurrentText(settings.ACCOUNT_NUMBER)
            self.account = self.account_tab.account_combo.currentText()

            self.conn_lbl.setText(f"접속됨 · {server_str} · {user} · {self.account}")
            self.login_btn.setEnabled(False)
            self.statusBar().showMessage(f"로그인 성공 ({server_str})")
            logger.info(f"HTS 로그인 성공 / {server_str} / 계좌 {accounts}")
            self.account_tab.refresh()
        except Exception as e:
            logger.error(f"로그인 실패: {e}")
            QMessageBox.critical(self, "로그인 실패", str(e))
            self.statusBar().showMessage("로그인 실패")

    def ensure_login(self):
        if not self.logged_in:
            QMessageBox.warning(self, "로그인 필요", "먼저 '키움 로그인'을 해주세요.")
            return False
        return True

    def open_chart(self, code):
        """종목코드로 차트 탭을 열고 표시"""
        self.chart_tab.show_chart(code)
        self.tabs.setCurrentWidget(self.chart_tab)

    def open_orderbook(self, code):
        """종목코드로 호가/주문 탭을 열고 실시간 호가 표시"""
        self.orderbook_tab.set_symbol(code)
        self.tabs.setCurrentWidget(self.orderbook_tab)

    def resolve_code(self, text, parent=None):
        """입력(종목코드 6자리 또는 종목명)을 종목코드로 변환.
        동명이 여러 개면 선택창을 띄운다. 실패 시 None."""
        text = (text or "").strip()
        if not text:
            return None
        if text.isdigit() and len(text) == 6:
            return text
        cmap = self.build_code_map()  # {code: name}
        t = text.lower()
        matches = [(c, n) for c, n in cmap.items() if t in n.lower()]
        if not matches:
            QMessageBox.information(parent or self, "검색", f"'{text}' 에 해당하는 종목이 없습니다.")
            return None

        def rank(item):
            n = item[1].lower()
            if n == t:
                return (0, len(n))
            if n.startswith(t):
                return (1, len(n))
            return (2, len(n))

        matches.sort(key=rank)
        if len(matches) == 1:
            return matches[0][0]
        items = [f"{n} ({c})" for c, n in matches[:50]]
        choice, ok = QInputDialog.getItem(
            parent or self, "종목 선택",
            f"'{text}' 검색 결과 {len(matches)}개 — 종목을 선택하세요", items, 0, False)
        if not ok:
            return None
        return matches[items.index(choice)][0]

    # ---------------------------------------------------------- 헬퍼
    def query_deposit(self, account):
        api = self.kiwoom
        api.set_input_value("계좌번호", account)
        api.set_input_value("비밀번호", "")
        api.set_input_value("비밀번호입력매체구분", "00")
        api.set_input_value("조회구분", "2")
        if api.comm_rq_data("예수금조회", "opw00001", 0, SCREEN_ACCOUNT) != 0:
            return {}

        def _i(name):
            v = api.get_comm_data("opw00001", "예수금조회", 0, name).replace(",", "").lstrip("0")
            try:
                return int(v) if v else 0
            except ValueError:
                return 0
        return {"예수금": _i("예수금"), "주문가능금액": _i("주문가능금액"), "출금가능금액": _i("출금가능금액")}

    def build_code_map(self):
        if self._code_map is not None:
            return self._code_map
        self._code_map = {}
        for market in ("0", "10"):  # 코스피, 코스닥
            for code in self.kiwoom.get_code_list_by_market(market):
                self._code_map[code] = self.kiwoom.get_master_code_name(code)
        logger.info(f"종목 마스터 {len(self._code_map)}개 로드")
        return self._code_map

    def find_codes_by_name(self, text):
        cmap = self.build_code_map()
        text = text.lower()
        return [c for c, n in cmap.items() if text in n.lower()]

    def build_trader(self):
        try:
            if settings.STRATEGY == "ma":
                strat = MAStrategy(short_period=settings.MA_SHORT, long_period=settings.MA_LONG)
            else:
                strat = RSIStrategy(period=settings.RSI_PERIOD,
                                    oversold=settings.RSI_OVERSOLD,
                                    overbought=settings.RSI_OVERBOUGHT)
            self.account = self.account_tab.account_combo.currentText() or settings.ACCOUNT_NUMBER
            self.trader = Trader(self.kiwoom, self.account, self.mdata, strat,
                                 is_simul=settings.IS_SIMUL)
            self.trader.sync_positions()
            return True
        except Exception as e:
            logger.error(f"트레이더 초기화 오류: {e}")
            QMessageBox.critical(self, "오류", f"자동매매 초기화 실패: {e}")
            return False

    # 자동매매 감시종목 (조건검색 override 있으면 우선)
    def watch_list(self):
        if self._cond_watch:
            return self._cond_watch
        return settings.WATCH_LIST

    def set_condition_watch(self, codes):
        self._cond_watch = [{"code": c, "name": self.kiwoom.get_master_code_name(c)} for c in codes]
        logger.info(f"조건검색 감시종목 {len(self._cond_watch)}개로 설정")

    def add_condition_watch_code(self, code, name):
        if self._cond_watch is None:
            self._cond_watch = []
        if code not in {w["code"] for w in self._cond_watch}:
            self._cond_watch.append({"code": code, "name": name})

    def closeEvent(self, event):
        try:
            if self.monitor_tab.running:
                self.monitor_tab.stop()
        except Exception:
            pass
        try:
            if self.cond_tab.engine and self.cond_tab.engine.running:
                self.cond_tab.engine.stop()
        except Exception:
            pass
        try:
            self.orderbook_tab.stop()
        except Exception:
            pass
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = HTSWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
