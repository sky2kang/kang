"""
GUI 대시보드 (PyQt5)

초보자가 코드를 만지지 않고 버튼·입력창으로 자동매매를 제어할 수 있는 화면.
 - 계좌 현황(평가금액/수익률/주문가능액)
 - 보유종목 테이블
 - 매매 설정(손절/익절/매수금액/종목수) 입력
 - 매매 시작/중지 버튼
 - 실시간 로그 창
 - 안전장치 상태 표시

* 이 모듈은 Windows + PyQt5 환경에서 실행됩니다.
  실행: python -m gui.dashboard  (또는 main.py 에서 --gui 옵션)
"""
import sys
import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QGridLayout, QTableWidget, QTableWidgetItem, QTextEdit, QSpinBox,
    QDoubleSpinBox, QGroupBox, QComboBox, QMessageBox, QHeaderView
)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QColor


class Dashboard(QWidget):
    def __init__(self, controller=None):
        """
        controller: 매매 제어 객체 (start/stop/get_status 메서드 제공).
                    None이면 데모(미연결) 모드로 화면만 표시.
        """
        super().__init__()
        self.controller = controller
        self.is_running = False
        self._init_ui()

        # 1초마다 화면 갱신
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)

    # -------------------------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("키움 자동매매 대시보드")
        self.resize(900, 700)
        root = QVBoxLayout(self)

        root.addWidget(self._build_account_box())
        root.addWidget(self._build_holdings_box())

        mid = QHBoxLayout()
        mid.addWidget(self._build_settings_box(), 1)
        mid.addWidget(self._build_control_box(), 1)
        root.addLayout(mid)

        root.addWidget(self._build_log_box())

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
        return box

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
    # 버튼 핸들러
    # -------------------------------------------------------------------------
    def on_start(self):
        # 실거래 모드면 이중 확인
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
            self.table.setItem(i, 3, QTableWidgetItem(f"{h.get('avg_price', 0):,}"))
            rate = h.get("profit_rate", 0)
            item = QTableWidgetItem(f"{rate:.2f}%")
            item.setForeground(QColor("red") if rate >= 0 else QColor("blue"))
            self.table.setItem(i, 4, item)

    def append_log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{ts}] {message}")


def run_gui(controller=None):
    app = QApplication(sys.argv)
    win = Dashboard(controller)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()
