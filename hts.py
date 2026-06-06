"""
키움 자동매매 HTS (통합 GUI).

탭 구성:
  1) 계좌 관리   - 예수금/잔고/보유종목/수익률
  2) 종목 검색   - 코드/이름 검색 → 현재가, 감시종목 추가
  3) 조건 검색   - 키움 조건식 불러오기/단발·실시간 실행 → 자동매매 연동
  4) 자동매매    - 시작/중지, 감시종목 실시간 시세, 신호/주문 로그
  5) 설정        - config.json 편집 (settings_gui 재사용)

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

from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QLabel, QLineEdit,
    QPushButton, QComboBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QFormLayout,
    QTextEdit, QHeaderView, QMessageBox, QDockWidget, QAbstractItemView,
    QSpinBox, QDoubleSpinBox, QInputDialog,
)

from config import settings
from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.trader import Trader
from core.auto_trader import ConditionAutoTrader
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy
from utils.logger import get_logger
from settings_gui import SettingsWindow
from chart_view import CandleChart

logger = get_logger("hts")

SCREEN_ACCOUNT = "5001"
SCREEN_REAL = "5002"
SCREEN_COND = "5100"

REAL_FIDS = "10;11;12;15"  # 현재가;전일대비;등락율;거래량


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
        add_btn = QPushButton("선택 종목 → 감시종목 추가")
        add_btn.clicked.connect(self.add_to_watch)
        bottom.addWidget(add_btn)
        v.addLayout(bottom)

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
        self.table.setRowCount(0)
        for code in codes:
            try:
                info = self.win.mdata.get_stock_info(code)
                name = self.win.kiwoom.get_master_code_name(code)
            except Exception as e:
                logger.error(f"[{code}] 조회 오류: {e}")
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(code))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, _num_item(info["price"], money=True))
            self.table.setItem(r, 3, _num_item(info["change_rate"], pct=True))
            self.table.setItem(r, 4, _num_item(info["volume"], money=True))
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "검색", "결과가 없습니다.")

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
    COLS = ["사용", "조건식", "편입매수", "이탈매도", "매수금액", "손절", "익절", "매칭"]

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

        self.status_lbl = QLabel("중지됨")
        self.status_lbl.setFont(QFont("", 10, QFont.Bold))
        v.addWidget(self.status_lbl)

        v.addWidget(QLabel("◆ 조건식별 자동매매 규칙  (사용 체크는 최대 10개 · 편입=매수, 이탈/손절/익절=매도)"))
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
        self.rule_table.setItem(r, 7, match_item)

        row = {"idx": idx, "name": name, "disp": disp, "use": use_cb, "buy": buy_cb,
               "sell": sell_cb, "amount": amount, "stop": stop, "take": take,
               "match": match_item, "count": 0}
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
            }
        return rules

    def save_rules(self):
        if not self.cond_rows:
            QMessageBox.information(self, "규칙 저장", "먼저 조건식을 불러오세요.")
            return
        cfg = settings.load_config()
        cfg["condition_rules"] = self._collect_rules()
        settings.save_config(cfg)
        QMessageBox.information(self, "규칙 저장", "조건식별 자동매매 규칙을 저장했습니다.")

    # ------------------------------------------------------- 시작 / 중지
    def toggle_auto(self):
        if self.engine and self.engine.running:
            self.engine.stop()
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
        self.status_lbl.setText(
            f"실행중 — 조건식 {len(self.engine.active)}개 실시간 등록 / 편입매수·이탈매도·손절익절 작동")

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

        labels = {"entry": "편입", "exit": "이탈", "buy": "매수", "sell": "매도", "chejan": "체결"}
        code = info.get("code", "")
        name = info.get("name") or (self.win.kiwoom.get_master_code_name(code) if code else "")
        note = info.get("reason") or (f"{info['price']:,}원" if info.get("price") else "")
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
        self.cond_tab = ConditionTab(self)
        self.monitor_tab = MonitorTab(self)
        self.settings_tab = SettingsWindow()
        self.tabs.addTab(self.account_tab, "계좌 관리")
        self.tabs.addTab(self.search_tab, "종목 검색")
        self.tabs.addTab(self.screener_tab, "조건 검색")
        self.tabs.addTab(self.chart_tab, "차트")
        self.tabs.addTab(self.cond_tab, "조건 자동매매")
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
        event.accept()


def main():
    app = QApplication(sys.argv)
    win = HTSWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
