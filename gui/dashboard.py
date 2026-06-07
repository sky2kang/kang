"""
GUI 대시보드 (PyQt5)

초보자가 코드를 만지지 않고 버튼·입력창으로 자동매매를 제어할 수 있는 화면.
 - 계좌 현황(평가금액/수익률/주문가능액)
 - 보유종목 테이블
 - 매매 설정(손절/익절/매수금액/종목수) 입력
 - 매매 시작/중지 버튼
 - 실시간 로그 창 (logs/trader.log 2초마다 갱신)
 - 안전장치 상태 표시
 - 스크리닝 탭 (종목 자동 스크리닝)

* 이 모듈은 Windows + PyQt5 환경에서 실행됩니다.
  실행: python -m gui.dashboard  (또는 main.py 에서 --gui 옵션)
"""
import sys
import os
import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTableWidget, QTableWidgetItem, QTextEdit, QSpinBox,
    QDoubleSpinBox, QGroupBox, QComboBox, QMessageBox, QHeaderView,
    QLineEdit, QTabWidget, QDialog
)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QColor

LOG_FILE = os.path.join("logs", "trader.log")


# ---------------------------------------------------------------------------
# 스크리닝 백그라운드 스레드
# ---------------------------------------------------------------------------
class _ScreenerThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, screener, codes=None, market="kospi", top_n=50,
                 parent=None):
        super().__init__(parent)
        self._screener = screener
        self._codes = codes
        self._market = market
        self._top_n = top_n

    def run(self):
        try:
            if self._codes:
                results = self._screener.screen(self._codes)
            else:
                results = self._screener.screen_from_market(
                    self._market, self._top_n
                )
            self.finished.emit(results)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# 분석 상세 팝업
# ---------------------------------------------------------------------------
class _AnalysisDialog(QDialog):
    def __init__(self, report_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("종목 상세 분석")
        self.resize(520, 420)
        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(report_text)
        text_edit.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 12px;"
        )
        layout.addWidget(text_edit)
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


# ---------------------------------------------------------------------------
# 메인 대시보드
# ---------------------------------------------------------------------------
class Dashboard(QWidget):
    def __init__(self, controller=None):
        """
        controller: 매매 제어 객체 (start/stop/get_status 메서드 제공).
                    None이면 데모(미연결) 모드로 화면만 표시.
        """
        super().__init__()
        self.controller = controller
        self.is_running = False
        self._log_pos = 0          # 로그 파일 읽기 위치
        self._screener = None      # StockScreener 인스턴스 (선택)
        self._screener_thread = None
        self._screener_data = {}   # 스크리닝 결과 캐시 (code -> row dict)
        self._init_ui()

        # 1초마다 계좌/안전장치 갱신
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(1000)

        # 2초마다 로그 파일 테일
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self._tail_log)
        self.log_timer.start(2000)

    # -------------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("키움 자동매매 대시보드")
        self.resize(960, 750)
        root = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._build_main_tab(), "대시보드")
        tabs.addTab(self._build_screener_tab(), "스크리닝")
        root.addWidget(tabs)

    # -------------------------------------------------------------------------
    # 메인 탭
    # -------------------------------------------------------------------------
    def _build_main_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(self._build_account_box())
        layout.addWidget(self._build_holdings_box())

        mid = QHBoxLayout()
        mid.addWidget(self._build_settings_box(), 1)
        mid.addWidget(self._build_control_box(), 1)
        layout.addLayout(mid)

        layout.addWidget(self._build_log_box())
        return widget

    # ----- 계좌 현황 -----
    def _build_account_box(self):
        box = QGroupBox("계좌 현황")
        layout = QGridLayout(box)
        self.lbl_eval = QLabel("- 원")
        self.lbl_profit = QLabel("- %")
        self.lbl_available = QLabel("- 원")
        self.lbl_mode = QLabel("모의투자")
        self.lbl_safety = QLabel("정상")

        layout.addWidget(QLabel("총 평가금액:"), 0, 0)
        layout.addWidget(self.lbl_eval, 0, 1)
        layout.addWidget(QLabel("누적 수익률:"), 0, 2)
        layout.addWidget(self.lbl_profit, 0, 3)
        layout.addWidget(QLabel("주문 가능액:"), 1, 0)
        layout.addWidget(self.lbl_available, 1, 1)
        layout.addWidget(QLabel("거래 모드:"), 1, 2)
        layout.addWidget(self.lbl_mode, 1, 3)
        layout.addWidget(QLabel("안전장치:"), 2, 0)
        layout.addWidget(self.lbl_safety, 2, 1)
        return box

    # ----- 보유 종목 -----
    def _build_holdings_box(self):
        box = QGroupBox("보유 종목")
        layout = QVBoxLayout(box)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["종목명", "코드", "수량", "매입가", "수익률"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)
        return box

    # ----- 매매 설정 -----
    def _build_settings_box(self):
        box = QGroupBox("매매 설정")
        layout = QGridLayout(box)

        self.spin_buy_amount = QSpinBox()
        self.spin_buy_amount.setRange(10000, 100_000_000)
        self.spin_buy_amount.setSingleStep(100000)
        self.spin_buy_amount.setValue(1_000_000)
        self.spin_buy_amount.setSuffix(" 원")
        self.spin_buy_amount.setGroupSeparatorShown(True)

        self.spin_stock_count = QSpinBox()
        self.spin_stock_count.setRange(1, 30)
        self.spin_stock_count.setValue(5)
        self.spin_stock_count.setSuffix(" 종목")

        self.spin_stop_loss = QDoubleSpinBox()
        self.spin_stop_loss.setRange(-50, 0)
        self.spin_stop_loss.setValue(-5)
        self.spin_stop_loss.setSuffix(" %")

        self.spin_take_profit = QDoubleSpinBox()
        self.spin_take_profit.setRange(0, 100)
        self.spin_take_profit.setValue(10)
        self.spin_take_profit.setSuffix(" %")

        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems(["이동평균(MA)", "RSI", "조건검색식"])
        self.combo_strategy.currentTextChanged.connect(
            self._on_strategy_changed
        )

        self.lbl_cond = QLabel("조건식 이름:")
        self.edit_condition = QLineEdit()
        self.edit_condition.setPlaceholderText("조건검색식 이름 입력")
        self.lbl_cond.setVisible(False)
        self.edit_condition.setVisible(False)

        layout.addWidget(QLabel("1회 매수금액:"), 0, 0)
        layout.addWidget(self.spin_buy_amount, 0, 1)
        layout.addWidget(QLabel("최대 보유종목:"), 1, 0)
        layout.addWidget(self.spin_stock_count, 1, 1)
        layout.addWidget(QLabel("손절 기준:"), 2, 0)
        layout.addWidget(self.spin_stop_loss, 2, 1)
        layout.addWidget(QLabel("익절 기준:"), 3, 0)
        layout.addWidget(self.spin_take_profit, 3, 1)
        layout.addWidget(QLabel("전략:"), 4, 0)
        layout.addWidget(self.combo_strategy, 4, 1)
        layout.addWidget(self.lbl_cond, 5, 0)
        layout.addWidget(self.edit_condition, 5, 1)
        return box

    def _on_strategy_changed(self, text):
        is_cond = text == "조건검색식"
        self.lbl_cond.setVisible(is_cond)
        self.edit_condition.setVisible(is_cond)

    # ----- 제어 버튼 -----
    def _build_control_box(self):
        box = QGroupBox("제어")
        layout = QVBoxLayout(box)

        self.btn_start = QPushButton("▶ 자동매매 시작")
        self.btn_start.setStyleSheet(
            "background:#2e7d32; color:white; font-size:16px; padding:12px;")
        self.btn_start.clicked.connect(self.on_start)

        self.btn_stop = QPushButton("■ 중지")
        self.btn_stop.setStyleSheet(
            "background:#c62828; color:white; font-size:16px; padding:12px;")
        self.btn_stop.clicked.connect(self.on_stop)
        self.btn_stop.setEnabled(False)

        self.lbl_status = QLabel("대기 중")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet("font-size:14px; padding:8px;")

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.lbl_status)
        return box

    # ----- 로그 창 -----
    def _build_log_box(self):
        box = QGroupBox("실시간 로그")
        layout = QVBoxLayout(box)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "background:#1e1e1e; color:#d4d4d4; font-family:Consolas;")
        layout.addWidget(self.log_view)
        return box

    # -------------------------------------------------------------------------
    # 스크리닝 탭
    # -------------------------------------------------------------------------
    def _build_screener_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)

        ctrl_layout = QHBoxLayout()
        self.btn_screen = QPushButton("스크리닝 실행")
        self.btn_screen.clicked.connect(self._run_screener)
        self.lbl_screen_status = QLabel("대기 중")
        ctrl_layout.addWidget(self.btn_screen)
        ctrl_layout.addWidget(self.lbl_screen_status)
        ctrl_layout.addStretch()
        layout.addLayout(ctrl_layout)

        self.screen_table = QTableWidget(0, 8)
        self.screen_table.setHorizontalHeaderLabels(
            ["코드", "종목명", "현재가", "점수", "의견", "RSI", "거래량배수", "분석"]
        )
        self.screen_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        layout.addWidget(self.screen_table)
        return widget

    # -------------------------------------------------------------------------
    # 버튼 핸들러
    # -------------------------------------------------------------------------
    def on_start(self):
        if self.lbl_mode.text() == "실거래":
            reply = QMessageBox.question(
                self, "실거래 확인",
                "실거래 모드입니다. 실제 자금으로 매매됩니다.\n정말 시작하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        settings = {
            "buy_amount": self.spin_buy_amount.value(),
            "stock_count": self.spin_stock_count.value(),
            "stop_loss": self.spin_stop_loss.value() / 100,
            "take_profit": self.spin_take_profit.value() / 100,
            "strategy": self.combo_strategy.currentText(),
            "condition_name": self.edit_condition.text().strip(),
        }
        if self.controller:
            self.controller.start(settings)
        self.is_running = True
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("🟢 매매 중")
        self.append_log("자동매매를 시작했습니다.")

    def on_stop(self):
        if self.controller:
            self.controller.stop()
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("■ 중지됨")
        self.append_log("자동매매를 중지했습니다.")

    # -------------------------------------------------------------------------
    # 화면 갱신
    # -------------------------------------------------------------------------
    def refresh(self):
        if not self.controller:
            return
        try:
            status = self.controller.get_status()
        except Exception:
            return

        acc = status.get("account", {})
        if acc:
            self.lbl_eval.setText(f"{acc.get('total_eval', 0):,} 원")
            rate = acc.get("total_profit_rate", 0)
            self.lbl_profit.setText(f"{rate:.2f} %")
            self.lbl_profit.setStyleSheet(
                "color:red;" if rate >= 0 else "color:blue;")
            self.lbl_available.setText(f"{acc.get('available', 0):,} 원")

        self.lbl_mode.setText("실거래" if not status.get("is_simul", True)
                              else "모의투자")

        guard = status.get("safety", {})
        if guard.get("halted"):
            self.lbl_safety.setText(f"🛑 {guard.get('halt_reason', '중단')}")
            self.lbl_safety.setStyleSheet("color:red; font-weight:bold;")
        else:
            cnt = guard.get("order_count", 0)
            mx = guard.get("max_orders", 0)
            self.lbl_safety.setText(f"정상 (주문 {cnt}/{mx})")

        self._update_holdings(status.get("holdings", []))

    def _update_holdings(self, holdings):
        self.table.setRowCount(len(holdings))
        for i, h in enumerate(holdings):
            self.table.setItem(i, 0, QTableWidgetItem(str(h.get("name", ""))))
            self.table.setItem(i, 1, QTableWidgetItem(str(h.get("code", ""))))
            self.table.setItem(i, 2, QTableWidgetItem(f"{h.get('qty', 0):,}"))
            self.table.setItem(
                i, 3, QTableWidgetItem(f"{h.get('avg_price', 0):,}")
            )
            rate = h.get("profit_rate", 0)
            item = QTableWidgetItem(f"{rate:.2f}%")
            item.setForeground(QColor("red") if rate >= 0 else QColor("blue"))
            self.table.setItem(i, 4, item)

    # -------------------------------------------------------------------------
    # 로그 파일 테일
    # -------------------------------------------------------------------------
    def _tail_log(self):
        """logs/trader.log 파일에서 새 줄을 읽어 로그 뷰에 추가"""
        if not os.path.exists(LOG_FILE):
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._log_pos)
                new_lines = f.read()
                self._log_pos = f.tell()
            if new_lines.strip():
                self.log_view.append(new_lines.rstrip())
        except Exception:
            pass

    def append_log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")

    # -------------------------------------------------------------------------
    # 스크리닝
    # -------------------------------------------------------------------------
    def set_screener(self, screener):
        """외부에서 StockScreener 인스턴스를 주입"""
        self._screener = screener

    def _run_screener(self):
        if self._screener is None:
            QMessageBox.warning(
                self, "스크리닝 오류",
                "스크리너가 초기화되지 않았습니다.\n"
                "controller.start() 후 재시도하세요."
            )
            return
        if self._screener_thread and self._screener_thread.isRunning():
            return

        self.btn_screen.setEnabled(False)
        self.lbl_screen_status.setText("스크리닝 중...")

        self._screener_thread = _ScreenerThread(self._screener)
        self._screener_thread.finished.connect(self._on_screener_done)
        self._screener_thread.error.connect(self._on_screener_error)
        self._screener_thread.start()

    def _on_screener_done(self, results):
        self.btn_screen.setEnabled(True)
        self.lbl_screen_status.setText(f"완료: {len(results)}개 선별")
        self._populate_screen_table(results)

    def _on_screener_error(self, msg):
        self.btn_screen.setEnabled(True)
        self.lbl_screen_status.setText(f"오류: {msg}")

    def _populate_screen_table(self, results):
        self.screen_table.setRowCount(len(results))
        self._screener_data = {}
        for i, r in enumerate(results):
            code = r.get("code", "")
            self._screener_data[code] = r
            rsi_str = (
                f"{r['rsi']:.1f}" if r.get("rsi") is not None else "N/A"
            )
            self.screen_table.setItem(i, 0, QTableWidgetItem(code))
            self.screen_table.setItem(
                i, 1, QTableWidgetItem(r.get("name", ""))
            )
            self.screen_table.setItem(
                i, 2, QTableWidgetItem(f"{r.get('price', 0):,}")
            )
            self.screen_table.setItem(
                i, 3, QTableWidgetItem(f"{r.get('score', 0):.1f}")
            )
            self.screen_table.setItem(
                i, 4, QTableWidgetItem(r.get("opinion", ""))
            )
            self.screen_table.setItem(i, 5, QTableWidgetItem(rsi_str))
            self.screen_table.setItem(
                i, 6, QTableWidgetItem(f"{r.get('volume_ratio', 0):.2f}")
            )
            btn_analyze = QPushButton("분석")
            btn_analyze.clicked.connect(
                lambda _checked, c=code: self._show_analysis(c)
            )
            self.screen_table.setCellWidget(i, 7, btn_analyze)

    def _show_analysis(self, code):
        """지정 코드의 StockAnalyzer.report_text() 를 팝업으로 표시"""
        import datetime as _dt
        try:
            from core.analyzer import StockAnalyzer

            start_date = (
                _dt.datetime.now() - _dt.timedelta(days=60)
            ).strftime("%Y%m%d")

            mdata = None
            if self.controller:
                mdata = getattr(self.controller, "_market_data", None)

            if mdata is None:
                QMessageBox.warning(self, "분석 오류",
                                    "MarketDataAPI가 초기화되지 않았습니다.")
                return

            df = mdata.get_daily_ohlcv(code, start_date)
            r = self._screener_data.get(code, {})
            name = r.get("name", code)
            analyzer = StockAnalyzer(df)
            text = analyzer.report_text(code=code, name=name)
        except Exception as exc:
            text = f"분석 오류: {exc}"

        dlg = _AnalysisDialog(text, self)
        dlg.exec_()


def run_gui(controller=None):
    app = QApplication(sys.argv)
    win = Dashboard(controller)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()
