"""
키움 자동매매 설정 GUI.

config/config.json 의 모든 설정을 보고 편집/저장한다.

실행:  .venv\\Scripts\\python.exe settings_gui.py
저장 후 main.py 를 (재)실행하면 변경 사항이 적용된다.
"""
import os
import sys

# Qt 플랫폼 플러그인 경로 보정 (main.py 와 동일)
if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    import PyQt5
    _plugins = os.path.join(
        os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms"
    )
    if os.path.isdir(_plugins):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugins

from PyQt5.QtCore import Qt, QTime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QCheckBox, QSpinBox,
    QDoubleSpinBox, QComboBox, QTimeEdit, QPushButton, QGroupBox,
    QFormLayout, QGridLayout, QVBoxLayout, QHBoxLayout, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView,
)

from config import settings


class SettingsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.cfg = settings.load_config()
        self.setWindowTitle("키움 자동매매 설정")
        self.setMinimumWidth(520)
        self._build_ui()
        self._load_values()

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        root = QVBoxLayout(self)

        # 계좌 / 모드
        acc_box = QGroupBox("계좌 / 모드")
        acc_form = QFormLayout(acc_box)
        self.account = QLineEdit()
        self.account.setPlaceholderText("예: 8127954011 (10자리)")
        self.is_simul = QCheckBox("모의투자 (체크 해제 시 실거래 — 주의!)")
        acc_form.addRow("계좌번호", self.account)
        acc_form.addRow("거래 모드", self.is_simul)
        root.addWidget(acc_box)

        # 리스크 / 매매 한도
        risk_box = QGroupBox("리스크 / 매매 한도")
        risk_form = QFormLayout(risk_box)
        self.max_buy = QSpinBox()
        self.max_buy.setRange(0, 2_000_000_000)
        self.max_buy.setSingleStep(100_000)
        self.max_buy.setSuffix(" 원")
        self.max_buy.setGroupSeparatorShown(True)
        self.max_stock = QSpinBox()
        self.max_stock.setRange(1, 50)
        self.stop_loss = QDoubleSpinBox()
        self.stop_loss.setRange(-100.0, 0.0)
        self.stop_loss.setDecimals(1)
        self.stop_loss.setSingleStep(0.5)
        self.stop_loss.setSuffix(" %")
        self.take_profit = QDoubleSpinBox()
        self.take_profit.setRange(0.0, 1000.0)
        self.take_profit.setDecimals(1)
        self.take_profit.setSingleStep(0.5)
        self.take_profit.setSuffix(" %")
        risk_form.addRow("1회 최대 매수금액", self.max_buy)
        risk_form.addRow("최대 동시 보유 종목수", self.max_stock)
        risk_form.addRow("손절 기준", self.stop_loss)
        risk_form.addRow("익절 기준", self.take_profit)
        root.addWidget(risk_box)

        # 매매 시간 / 주기
        time_box = QGroupBox("매매 시간 / 점검 주기")
        time_form = QFormLayout(time_box)
        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time = QTimeEdit()
        self.end_time.setDisplayFormat("HH:mm")
        self.interval = QSpinBox()
        self.interval.setRange(1, 240)
        self.interval.setSuffix(" 분")
        time_form.addRow("매매 시작 시각", self.start_time)
        time_form.addRow("매매 종료 시각", self.end_time)
        time_form.addRow("전략 점검 주기", self.interval)
        root.addWidget(time_box)

        # 전략
        strat_box = QGroupBox("전략")
        strat_grid = QGridLayout(strat_box)
        self.strategy = QComboBox()
        self.strategy.addItem("MA 골든크로스", "ma")
        self.strategy.addItem("RSI 과매수/과매도", "rsi")
        self.ma_short = QSpinBox(); self.ma_short.setRange(1, 240)
        self.ma_long = QSpinBox(); self.ma_long.setRange(1, 240)
        self.rsi_period = QSpinBox(); self.rsi_period.setRange(2, 240)
        self.rsi_oversold = QSpinBox(); self.rsi_oversold.setRange(1, 99)
        self.rsi_overbought = QSpinBox(); self.rsi_overbought.setRange(1, 99)
        strat_grid.addWidget(QLabel("사용 전략"), 0, 0)
        strat_grid.addWidget(self.strategy, 0, 1, 1, 3)
        strat_grid.addWidget(QLabel("MA 단기"), 1, 0)
        strat_grid.addWidget(self.ma_short, 1, 1)
        strat_grid.addWidget(QLabel("MA 장기"), 1, 2)
        strat_grid.addWidget(self.ma_long, 1, 3)
        strat_grid.addWidget(QLabel("RSI 기간"), 2, 0)
        strat_grid.addWidget(self.rsi_period, 2, 1)
        strat_grid.addWidget(QLabel("RSI 과매도"), 3, 0)
        strat_grid.addWidget(self.rsi_oversold, 3, 1)
        strat_grid.addWidget(QLabel("RSI 과매수"), 3, 2)
        strat_grid.addWidget(self.rsi_overbought, 3, 3)
        root.addWidget(strat_box)

        # 감시 종목
        watch_box = QGroupBox("감시 종목")
        watch_layout = QVBoxLayout(watch_box)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["종목코드", "종목명"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        watch_layout.addWidget(self.table)
        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 종목 추가")
        del_btn = QPushButton("- 선택 삭제")
        add_btn.clicked.connect(self._add_row)
        del_btn.clicked.connect(self._del_rows)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        watch_layout.addLayout(btn_row)
        root.addWidget(watch_box)

        # 로그 레벨
        log_box = QGroupBox("기타")
        log_form = QFormLayout(log_box)
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        log_form.addRow("로그 레벨", self.log_level)
        root.addWidget(log_box)

        # 저장 / 취소
        action_row = QHBoxLayout()
        action_row.addStretch()
        save_btn = QPushButton("💾 저장")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("닫기")
        cancel_btn.clicked.connect(self.close)
        action_row.addWidget(save_btn)
        action_row.addWidget(cancel_btn)
        root.addLayout(action_row)

    # ----------------------------------------------------------- 값 로드
    def _load_values(self):
        c = self.cfg
        self.account.setText(str(c.get("account", "")))
        self.is_simul.setChecked(bool(c.get("is_simul", True)))
        self.max_buy.setValue(int(c.get("max_buy_amount", 1_000_000)))
        self.max_stock.setValue(int(c.get("max_stock_count", 5)))
        self.stop_loss.setValue(float(c.get("stop_loss_rate", -0.05)) * 100)
        self.take_profit.setValue(float(c.get("take_profit_rate", 0.10)) * 100)
        self.start_time.setTime(QTime.fromString(c.get("trade_start_time", "09:05"), "HH:mm"))
        self.end_time.setTime(QTime.fromString(c.get("trade_end_time", "15:20"), "HH:mm"))
        self.interval.setValue(int(c.get("check_interval_min", 5)))
        idx = self.strategy.findData(c.get("strategy", "ma"))
        self.strategy.setCurrentIndex(idx if idx >= 0 else 0)
        self.ma_short.setValue(int(c.get("ma_short", 5)))
        self.ma_long.setValue(int(c.get("ma_long", 20)))
        self.rsi_period.setValue(int(c.get("rsi_period", 14)))
        self.rsi_oversold.setValue(int(c.get("rsi_oversold", 30)))
        self.rsi_overbought.setValue(int(c.get("rsi_overbought", 70)))
        li = self.log_level.findText(c.get("log_level", "INFO"))
        self.log_level.setCurrentIndex(li if li >= 0 else 1)
        for item in c.get("watch_list", []):
            self._add_row(item.get("code", ""), item.get("name", ""))

    # --------------------------------------------------------- 감시종목 행
    def _add_row(self, code="", name=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(str(code)))
        self.table.setItem(r, 1, QTableWidgetItem(str(name)))

    def _del_rows(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)

    # -------------------------------------------------------------- 저장
    def _collect_watch_list(self):
        items = []
        for r in range(self.table.rowCount()):
            code_item = self.table.item(r, 0)
            name_item = self.table.item(r, 1)
            code = code_item.text().strip() if code_item else ""
            name = name_item.text().strip() if name_item else ""
            if code:
                items.append({"code": code, "name": name or code})
        return items

    def _save(self):
        # 간단한 유효성 검사
        if self.ma_short.value() >= self.ma_long.value():
            QMessageBox.warning(self, "확인", "MA 단기는 MA 장기보다 작아야 합니다.")
            return
        if self.start_time.time() >= self.end_time.time():
            QMessageBox.warning(self, "확인", "매매 시작 시각은 종료 시각보다 빨라야 합니다.")
            return
        if not self.is_simul.isChecked():
            ok = QMessageBox.question(
                self, "실거래 경고",
                "실거래 모드로 저장합니다. 실제 주문이 나갈 수 있습니다. 계속할까요?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if ok != QMessageBox.Yes:
                return

        self.cfg.update({
            "account": self.account.text().strip(),
            "is_simul": self.is_simul.isChecked(),
            "max_buy_amount": self.max_buy.value(),
            "max_stock_count": self.max_stock.value(),
            "stop_loss_rate": round(self.stop_loss.value() / 100, 4),
            "take_profit_rate": round(self.take_profit.value() / 100, 4),
            "trade_start_time": self.start_time.time().toString("HH:mm"),
            "trade_end_time": self.end_time.time().toString("HH:mm"),
            "check_interval_min": self.interval.value(),
            "strategy": self.strategy.currentData(),
            "ma_short": self.ma_short.value(),
            "ma_long": self.ma_long.value(),
            "rsi_period": self.rsi_period.value(),
            "rsi_oversold": self.rsi_oversold.value(),
            "rsi_overbought": self.rsi_overbought.value(),
            "log_level": self.log_level.currentText(),
            "watch_list": self._collect_watch_list(),
        })
        settings.save_config(self.cfg)
        QMessageBox.information(
            self, "저장 완료",
            "설정을 저장했습니다.\n실행 중인 main.py 에는 재시작해야 적용됩니다.",
        )


def main():
    app = QApplication(sys.argv)
    win = SettingsWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
