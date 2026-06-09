"""
HTS 스타일 자동매매 메인 윈도우

Lightning Trader 레이아웃을 참조한 전문 트레이딩 인터페이스.

레이아웃:
  ┌────────────────────────────────────────────────────┐
  │ [상단] 계좌 / API 상태 / 마스터 ON·OFF              │
  ├──────────┬─────────────────────────────────────────┤
  │          │  탭1 대시보드   탭2 조건식매매           │
  │ 좌측     │  탭3 종목별매매 탭4 손익/청산             │
  │ 조건식   │  탭5 스케줄러   탭6 백테스트             │
  │ / 관심   │  탭7 스크리닝   탭8 종목분석             │
  │ 종목 목록│                                         │
  ├──────────┴─────────────────────────────────────────┤
  │ [하단] 포착 로그 | 주문/체결 로그 | API 통신 상태   │
  └────────────────────────────────────────────────────┘
"""
import sys
import os
import datetime
import logging

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QSpinBox,
    QDoubleSpinBox, QGroupBox, QComboBox, QMessageBox,
    QHeaderView, QLineEdit, QTabWidget, QCheckBox,
    QTimeEdit, QListWidget, QListWidgetItem, QFrame,
    QProgressBar, QRadioButton, QButtonGroup, QScrollArea,
    QAbstractItemView, QSizePolicy, QStatusBar, QAction,
    QMenuBar, QDialog, QDialogButtonBox, QFileDialog,
    QToolBar
)
from PyQt5.QtCore import (
    QTimer, Qt, QThread, pyqtSignal, QTime, QSize
)
from PyQt5.QtGui import (
    QColor, QFont, QPalette, QIcon, QPixmap, QBrush
)

logger = logging.getLogger(__name__)
LOG_FILE = os.path.join("logs", "trader.log")

# ── 컬러 팔레트 (HTS 다크 테마) ─────────────────────────────────────────────
C_BG        = "#0d1117"   # 배경
C_PANEL     = "#161b22"   # 패널
C_PANEL2    = "#1c2128"   # 패널 보조
C_BORDER    = "#30363d"   # 테두리
C_TEXT      = "#e6edf3"   # 기본 텍스트
C_TEXT_DIM  = "#8b949e"   # 흐린 텍스트
C_BUY       = "#f85149"   # 매수 (빨강 – 한국 관행)
C_SELL      = "#388bfd"   # 매도 (파랑)
C_PROFIT    = "#f85149"   # 수익
C_LOSS      = "#388bfd"   # 손실
C_GREEN     = "#3fb950"   # 긍정 신호
C_YELLOW    = "#d29922"   # 경고
C_ACCENT    = "#58a6ff"   # 강조
C_HEADER    = "#21262d"   # 테이블 헤더


DARK_QSS = f"""
QMainWindow, QWidget {{ background:{C_BG}; color:{C_TEXT}; }}
QMenuBar  {{ background:{C_PANEL}; color:{C_TEXT}; border-bottom:1px solid {C_BORDER}; }}
QMenuBar::item:selected {{ background:{C_PANEL2}; }}
QMenu {{ background:{C_PANEL}; color:{C_TEXT}; border:1px solid {C_BORDER}; }}
QMenu::item:selected {{ background:{C_PANEL2}; }}
QToolBar {{ background:{C_PANEL}; border:none; spacing:4px; padding:2px; }}
QStatusBar {{ background:{C_PANEL}; color:{C_TEXT_DIM}; font-size:11px; }}

QGroupBox {{
    border:1px solid {C_BORDER}; border-radius:4px;
    margin-top:8px; padding-top:4px;
    color:{C_TEXT}; font-weight:bold; font-size:11px;
}}
QGroupBox::title {{ subcontrol-origin:margin; left:8px; padding:0 4px; }}

QTabWidget::pane {{ border:1px solid {C_BORDER}; background:{C_PANEL}; }}
QTabBar::tab {{
    background:{C_PANEL2}; color:{C_TEXT_DIM};
    padding:6px 14px; border:1px solid {C_BORDER};
    border-bottom:none; border-radius:4px 4px 0 0; font-size:11px;
}}
QTabBar::tab:selected {{ background:{C_PANEL}; color:{C_TEXT}; border-bottom:2px solid {C_ACCENT}; }}
QTabBar::tab:hover {{ background:{C_HEADER}; color:{C_TEXT}; }}

QTableWidget {{
    background:{C_PANEL}; color:{C_TEXT}; gridline-color:{C_BORDER};
    border:1px solid {C_BORDER}; font-size:11px;
    selection-background-color:{C_PANEL2};
}}
QTableWidget::item {{ padding:2px 6px; }}
QTableWidget::item:selected {{ background:{C_PANEL2}; color:{C_TEXT}; }}
QHeaderView::section {{
    background:{C_HEADER}; color:{C_TEXT_DIM}; border:none;
    border-right:1px solid {C_BORDER}; border-bottom:1px solid {C_BORDER};
    padding:4px 6px; font-size:11px;
}}

QTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTimeEdit {{
    background:{C_PANEL2}; color:{C_TEXT}; border:1px solid {C_BORDER};
    border-radius:3px; padding:3px 6px; font-size:11px;
    selection-background-color:{C_ACCENT};
}}
QComboBox::drop-down {{ border:none; width:20px; }}
QComboBox QAbstractItemView {{ background:{C_PANEL2}; color:{C_TEXT}; border:1px solid {C_BORDER}; }}

QPushButton {{
    background:{C_PANEL2}; color:{C_TEXT}; border:1px solid {C_BORDER};
    border-radius:4px; padding:5px 12px; font-size:11px;
}}
QPushButton:hover {{ background:{C_HEADER}; border-color:{C_ACCENT}; }}
QPushButton:pressed {{ background:{C_BG}; }}
QPushButton:disabled {{ color:{C_TEXT_DIM}; background:{C_PANEL}; }}

QPushButton#btnBuy {{
    background:{C_BUY}; color:white; border:none; font-weight:bold;
}}
QPushButton#btnBuy:hover {{ background:#ff6b6b; }}
QPushButton#btnSell {{
    background:{C_SELL}; color:white; border:none; font-weight:bold;
}}
QPushButton#btnSell:hover {{ background:#5ba3ff; }}
QPushButton#btnStart {{
    background:#238636; color:white; border:none; font-size:13px; font-weight:bold;
    padding:8px 24px; border-radius:5px;
}}
QPushButton#btnStart:hover {{ background:#2ea043; }}
QPushButton#btnStop {{
    background:#da3633; color:white; border:none; font-size:13px; font-weight:bold;
    padding:8px 24px; border-radius:5px;
}}
QPushButton#btnStop:hover {{ background:#f85149; }}
QPushButton#btnEmergency {{
    background:#6e1a1a; color:#f85149; border:2px solid {C_BUY}; font-weight:bold;
    font-size:13px; padding:8px 24px; border-radius:5px;
}}
QPushButton#btnEmergency:hover {{ background:#8b2020; }}

QCheckBox {{ color:{C_TEXT}; spacing:6px; }}
QCheckBox::indicator {{
    width:14px; height:14px; border:1px solid {C_BORDER};
    background:{C_PANEL2}; border-radius:2px;
}}
QCheckBox::indicator:checked {{
    background:{C_ACCENT}; border-color:{C_ACCENT};
}}

QRadioButton {{ color:{C_TEXT}; spacing:6px; }}
QRadioButton::indicator {{
    width:13px; height:13px; border:1px solid {C_BORDER};
    background:{C_PANEL2}; border-radius:7px;
}}
QRadioButton::indicator:checked {{ background:{C_ACCENT}; border-color:{C_ACCENT}; }}

QListWidget {{
    background:{C_PANEL}; color:{C_TEXT}; border:1px solid {C_BORDER};
    font-size:11px;
}}
QListWidget::item {{ padding:3px 6px; }}
QListWidget::item:selected {{ background:{C_PANEL2}; color:{C_ACCENT}; }}
QListWidget::item:hover {{ background:{C_HEADER}; }}

QScrollBar:vertical {{
    background:{C_PANEL}; width:8px; margin:0;
}}
QScrollBar::handle:vertical {{
    background:{C_BORDER}; border-radius:4px; min-height:20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}

QSplitter::handle {{ background:{C_BORDER}; }}
QFrame[frameShape="4"], QFrame[frameShape="5"] {{ color:{C_BORDER}; }}

QProgressBar {{
    background:{C_PANEL2}; border:1px solid {C_BORDER}; border-radius:3px;
    text-align:center; color:{C_TEXT}; font-size:10px;
}}
QProgressBar::chunk {{ background:{C_ACCENT}; border-radius:2px; }}

QLabel#labelTitle {{ font-size:18px; font-weight:bold; color:{C_ACCENT}; }}
QLabel#labelSub   {{ font-size:11px; color:{C_TEXT_DIM}; }}
QLabel#labelBuy   {{ color:{C_BUY}; font-weight:bold; }}
QLabel#labelSell  {{ color:{C_SELL}; font-weight:bold; }}
QLabel#labelProfit {{ color:{C_PROFIT}; font-weight:bold; }}
QLabel#labelLoss  {{ color:{C_LOSS}; font-weight:bold; }}
QLabel#labelGreen {{ color:{C_GREEN}; font-weight:bold; }}
QLabel#labelYellow {{ color:{C_YELLOW}; font-weight:bold; }}
"""


# ── 공통 헬퍼 ────────────────────────────────────────────────────────────────
def _sep(vertical=True):
    f = QFrame()
    f.setFrameShape(QFrame.VLine if vertical else QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _label(text, obj_name=None, bold=False, size=11):
    lb = QLabel(text)
    if obj_name:
        lb.setObjectName(obj_name)
    if bold:
        f = lb.font(); f.setBold(True); lb.setFont(f)
    f2 = lb.font(); f2.setPointSize(size); lb.setFont(f2)
    return lb


def _make_table(headers, stretch_col=None):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setHighlightSections(False)
    if stretch_col is not None:
        t.horizontalHeader().setSectionResizeMode(
            stretch_col, QHeaderView.Stretch)
    else:
        t.horizontalHeader().setStretchLastSection(True)
    return t


# ── 백그라운드 스레드들 ───────────────────────────────────────────────────────
class _LogTailThread(QThread):
    new_lines = pyqtSignal(str)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self._path = path
        self._running = True
        self._pos = 0

    def run(self):
        import time
        while self._running:
            try:
                if os.path.exists(self._path):
                    with open(self._path, encoding="utf-8", errors="ignore") as f:
                        f.seek(self._pos)
                        chunk = f.read(8192)
                        if chunk:
                            self._pos = f.tell()
                            self.new_lines.emit(chunk)
            except Exception:
                pass
            time.sleep(1)

    def stop(self):
        self._running = False


class _ScreenerThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, screener, codes=None, market="kospi", top_n=50, parent=None):
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
                results = self._screener.screen_from_market(self._market, self._top_n)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class _AnalysisThread(QThread):
    finished = pyqtSignal(dict, str, str)  # analysis, code, name
    error = pyqtSignal(str)

    def __init__(self, mdata, code, days, parent=None):
        super().__init__(parent)
        self._mdata = mdata
        self._code = code
        self._days = days

    def run(self):
        try:
            import datetime as dt
            from core.analyzer import StockAnalyzer

            start = (dt.datetime.now() - dt.timedelta(days=self._days)).strftime("%Y%m%d")
            df = self._mdata.get_daily_ohlcv(self._code, start)
            name = self._code
            try:
                kiwoom = getattr(self._mdata, "api", None)
                if kiwoom:
                    name = kiwoom.dynamicCall("GetMasterCodeName(QString)", self._code).strip()
            except Exception:
                pass
            analysis = StockAnalyzer(df).analyze()
            self.finished.emit(analysis, self._code, name)
        except Exception as e:
            self.error.emit(str(e))


class _BacktestThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mdata, code, strategy_name, days, cash, parent=None):
        super().__init__(parent)
        self._mdata = mdata
        self._code = code
        self._strat_name = strategy_name
        self._days = days
        self._cash = cash

    def run(self):
        try:
            import datetime as dt
            from backtest.engine import BacktestEngine
            from strategy.ma_strategy import MAStrategy
            from strategy.rsi_strategy import RSIStrategy

            start = (dt.datetime.now() - dt.timedelta(days=self._days)).strftime("%Y%m%d")
            df = self._mdata.get_daily_ohlcv(self._code, start)
            strat = MAStrategy() if self._strat_name.startswith("MA") else RSIStrategy()
            engine = BacktestEngine(strat, initial_cash=self._cash)
            result = engine.run(df, self._code)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── 탭 1 : 대시보드 ───────────────────────────────────────────────────────────
class _DashboardTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(8)

        # 자산 요약 카드
        card_row = QHBoxLayout()
        self._cards = {}
        for key, title in [
            ("total", "총 평가금액"), ("profit", "평가손익"),
            ("rate", "수익률"), ("avail", "주문가능금액")
        ]:
            g = QGroupBox(title)
            v = QVBoxLayout(g)
            lbl = QLabel("--")
            lbl.setAlignment(Qt.AlignCenter)
            f = lbl.font(); f.setPointSize(16); f.setBold(True); lbl.setFont(f)
            v.addWidget(lbl)
            card_row.addWidget(g)
            self._cards[key] = lbl
        vbox.addLayout(card_row)

        # 보유종목 테이블
        g2 = QGroupBox("보유 종목")
        v2 = QVBoxLayout(g2)
        self.tbl_holdings = _make_table(
            ["종목코드", "종목명", "보유수량", "매수평단가", "현재가",
             "평가금액", "손익금액", "수익률(%)"], stretch_col=1)
        v2.addWidget(self.tbl_holdings)

        btn_row = QHBoxLayout()
        self.btn_sell_sel = QPushButton("선택 매도")
        self.btn_sell_all = QPushButton("전체 청산")
        self.btn_sell_all.setObjectName("btnEmergency")
        self.btn_refresh = QPushButton("잔고 새로고침")
        btn_row.addWidget(self.btn_sell_sel)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_sell_all)
        v2.addLayout(btn_row)
        vbox.addWidget(g2)

        # 당일 거래 내역
        g3 = QGroupBox("당일 체결 내역")
        v3 = QVBoxLayout(g3)
        self.tbl_trades = _make_table(
            ["시간", "종목명", "구분", "수량", "단가", "금액", "수수료", "손익"])
        v3.addWidget(self.tbl_trades)
        vbox.addWidget(g3)

    def update_balance(self, summary: dict):
        """summary: {total_eval, total_profit_rate, available} (MarketDataAPI 반환 형식)"""
        total = summary.get("total_eval", 0)
        rate = summary.get("total_profit_rate", 0.0)
        avail = summary.get("available", 0)
        # 수익 금액 = total_eval × rate / (100 + rate)  (근사)
        profit = int(total * rate / (100 + rate)) if (100 + rate) != 0 else 0
        self._cards["total"].setText(f"{total:,.0f}원")
        self._cards["profit"].setText(f"{profit:+,.0f}원")
        self._cards["profit"].setObjectName("labelProfit" if profit >= 0 else "labelLoss")
        self._cards["rate"].setText(f"{rate:+.2f}%")
        self._cards["avail"].setText(f"{avail:,.0f}원")

    def update_holdings(self, holdings: list):
        """holdings: list of dict (MarketDataAPI opw00018 반환 형식)
           키: code, name, qty, avg_price, profit_rate
           price / eval_amount 가 없으면 avg_price 로 대체
        """
        self.tbl_holdings.setRowCount(0)
        for h in holdings:
            r = self.tbl_holdings.rowCount()
            self.tbl_holdings.insertRow(r)
            profit_rate = h.get("profit_rate", 0.0)
            qty = h.get("qty", 0)
            avg_price = h.get("avg_price", 0)
            price = h.get("price", avg_price)               # 현재가 없으면 평단가로 대체
            eval_amount = h.get("eval_amount", qty * price)
            profit_amt = h.get("profit", int(eval_amount - qty * avg_price))
            items = [
                h.get("code", ""), h.get("name", ""),
                str(qty),
                f"{avg_price:,.0f}",
                f"{price:,.0f}",
                f"{eval_amount:,.0f}",
                f"{profit_amt:+,.0f}",
                f"{profit_rate:+.2f}%",
            ]
            for c, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c in (6, 7):
                    item.setForeground(
                        QColor(C_PROFIT) if profit_rate >= 0 else QColor(C_LOSS)
                    )
                self.tbl_holdings.setItem(r, c, item)


# ── 탭 2 : 조건식 매매 ────────────────────────────────────────────────────────
class _ConditionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        hbox = QHBoxLayout(self)
        hbox.setSpacing(8)

        # 좌측: 조건식 목록
        left = QGroupBox("조건검색식 목록")
        lv = QVBoxLayout(left)
        self.cond_list = QListWidget()
        self.cond_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        lv.addWidget(self.cond_list)
        btn_row = QHBoxLayout()
        self.btn_load_cond = QPushButton("조건식 불러오기")
        self.btn_load_cond.setObjectName("btnBuy")
        btn_row.addWidget(self.btn_load_cond)
        lv.addLayout(btn_row)
        left.setMinimumWidth(200)
        left.setMaximumWidth(260)
        hbox.addWidget(left)

        # 우측: 설정
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setSpacing(8)

        # 진입 가격
        g1 = QGroupBox("진입 가격 (호가) 설정")
        g1v = QVBoxLayout(g1)
        self._price_grp = QButtonGroup(self)
        for i, (lbl, tip) in enumerate([
            ("시장가", "포착 즉시 시장가 매수"),
            ("현재가", "포착 시점 현재가로 지정가"),
            ("매도1호가", "매도 1호가에 걸기"),
            ("매도2호가", "매도 2호가에 걸기"),
        ]):
            rb = QRadioButton(lbl)
            rb.setToolTip(tip)
            if i == 0:
                rb.setChecked(True)
            self._price_grp.addButton(rb, i)
            g1v.addWidget(rb)
        rv.addWidget(g1)

        # 매수 금액
        g2 = QGroupBox("매수 자금 설정")
        g2g = QGridLayout(g2)
        g2g.addWidget(QLabel("종목당 금액(원):"), 0, 0)
        self.spin_amount = QSpinBox()
        self.spin_amount.setRange(100_000, 100_000_000)
        self.spin_amount.setSingleStep(100_000)
        self.spin_amount.setValue(1_000_000)
        g2g.addWidget(self.spin_amount, 0, 1)
        g2g.addWidget(QLabel("또는 예수금 비율(%):"), 1, 0)
        self.spin_ratio = QDoubleSpinBox()
        self.spin_ratio.setRange(0, 50)
        self.spin_ratio.setSingleStep(1)
        self.spin_ratio.setValue(5)
        self.spin_ratio.setSuffix(" %")
        g2g.addWidget(self.spin_ratio, 1, 1)
        rv.addWidget(g2)

        # 최대 보유 / 재매수 제한
        g3 = QGroupBox("포지션 제한")
        g3g = QGridLayout(g3)
        g3g.addWidget(QLabel("최대 동시 보유 종목 수:"), 0, 0)
        self.spin_max_stocks = QSpinBox()
        self.spin_max_stocks.setRange(1, 30)
        self.spin_max_stocks.setValue(5)
        g3g.addWidget(self.spin_max_stocks, 0, 1)
        g3g.addWidget(QLabel("동일 종목 재진입 금지(분):"), 1, 0)
        self.spin_reenter = QSpinBox()
        self.spin_reenter.setRange(0, 120)
        self.spin_reenter.setValue(20)
        g3g.addWidget(self.spin_reenter, 1, 1)
        rv.addWidget(g3)

        # 분할 매수
        g4 = QGroupBox("분할 매수 설정")
        g4v = QVBoxLayout(g4)
        self.chk_split = QCheckBox("분할 매수 활성화")
        g4v.addWidget(self.chk_split)
        g4g = QGridLayout()
        for i, (stage, default_drop) in enumerate([("1차", 0), ("2차", -2), ("3차", -4)]):
            g4g.addWidget(QLabel(f"{stage} 하락:"), i, 0)
            sp = QDoubleSpinBox()
            sp.setRange(-20, 0); sp.setValue(default_drop); sp.setSuffix("%")
            g4g.addWidget(sp, i, 1)
            g4g.addWidget(QLabel("금액:"), i, 2)
            amt = QSpinBox()
            amt.setRange(0, 10_000_000); amt.setSingleStep(100_000)
            amt.setValue(500_000)
            g4g.addWidget(amt, i, 3)
        g4v.addLayout(g4g)
        rv.addWidget(g4)

        rv.addStretch()
        hbox.addWidget(right)

    def set_conditions(self, cond_list: list):
        self.cond_list.clear()
        for name in cond_list:
            item = QListWidgetItem(name)
            item.setCheckState(Qt.Unchecked)
            self.cond_list.addItem(item)

    def get_selected_conditions(self):
        result = []
        for i in range(self.cond_list.count()):
            item = self.cond_list.item(i)
            if item.checkState() == Qt.Checked:
                result.append(item.text())
        return result


# ── 탭 3 : 종목별 독립 매매 ───────────────────────────────────────────────────
class _IndividualTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        # 종목 추가
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("종목코드:"))
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText("예: 005930")
        self.edit_code.setMaximumWidth(100)
        add_row.addWidget(self.edit_code)
        self.btn_add = QPushButton("종목 추가")
        self.btn_add.setObjectName("btnBuy")
        add_row.addWidget(self.btn_add)
        self.btn_del = QPushButton("선택 삭제")
        add_row.addWidget(self.btn_del)
        add_row.addStretch()
        self.btn_import = QPushButton("CSV 불러오기")
        add_row.addWidget(self.btn_import)
        vbox.addLayout(add_row)

        # 종목 테이블
        self.tbl = _make_table([
            "활성", "종목코드", "종목명", "현재가",
            "목표가", "손절가", "투자금(원)", "분할매수",
            "트레일링(%)", "상태"
        ], stretch_col=2)
        self.tbl.setColumnWidth(0, 40)
        vbox.addWidget(self.tbl)

        # 하단 설정
        g = QGroupBox("선택 종목 상세 설정")
        gg = QGridLayout(g)

        # (라벨, 종류) — pct: %값 / won: 원화 정수값
        fields = [
            ("목표 수익률(%)", "pct", 3.0),
            ("손절 비율(%)", "pct", 3.0),
            ("1회 투자금(원)", "won", 1_000_000),
            ("가격 밴드 상단(원)", "won", 0),
            ("가격 밴드 하단(원)", "won", 0),
            ("트레일링 스탑(%)", "pct", 3.0),
        ]
        self._detail_spins = []
        for i, (lbl, kind, default) in enumerate(fields):
            gg.addWidget(QLabel(lbl), i // 2, (i % 2) * 2)
            if kind == "won":
                sp = QSpinBox()
                sp.setRange(0, 1_000_000_000)
                sp.setSingleStep(100_000)
                sp.setValue(int(default))
                sp.setSuffix(" 원")
                sp.setGroupSeparatorShown(True)
            else:
                sp = QDoubleSpinBox()
                sp.setRange(-30, 100)
                sp.setValue(default)
                sp.setSuffix(" %")
            gg.addWidget(sp, i // 2, (i % 2) * 2 + 1)
            self._detail_spins.append(sp)

        self.btn_apply_detail = QPushButton("선택 종목에 적용")
        gg.addWidget(self.btn_apply_detail, 3, 0, 1, 4)
        vbox.addWidget(g)


# ── 탭 4 : 손익 / 청산 ────────────────────────────────────────────────────────
class _StopLossTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setSpacing(12)

        # 전역 익절 / 손절
        g1 = QGroupBox("전역 익절 / 손절 기준 (모든 종목 공통)")
        g1g = QGridLayout(g1)
        g1g.addWidget(QLabel("목표 수익률 (익절):"), 0, 0)
        self.spin_tp = QDoubleSpinBox()
        self.spin_tp.setRange(0.1, 50); self.spin_tp.setValue(3.0)
        self.spin_tp.setSuffix(" %")
        g1g.addWidget(self.spin_tp, 0, 1)
        self.chk_tp_market = QCheckBox("시장가 익절 (미체결 방지)")
        g1g.addWidget(self.chk_tp_market, 0, 2)

        g1g.addWidget(QLabel("최대 손실률 (손절):"), 1, 0)
        self.spin_sl = QDoubleSpinBox()
        self.spin_sl.setRange(0.1, 30); self.spin_sl.setValue(2.0)
        self.spin_sl.setSuffix(" %")
        g1g.addWidget(self.spin_sl, 1, 1)
        self.chk_sl_market = QCheckBox("시장가 손절 (즉시 청산)")
        self.chk_sl_market.setChecked(True)
        g1g.addWidget(self.chk_sl_market, 1, 2)
        vbox.addWidget(g1)

        # 트레일링 스탑
        g2 = QGroupBox("트레일링 스탑 (수익 보전)")
        g2g = QGridLayout(g2)
        self.chk_trailing = QCheckBox("트레일링 스탑 활성화")
        g2g.addWidget(self.chk_trailing, 0, 0, 1, 4)

        g2g.addWidget(QLabel("가동 기준 수익(%) :"), 1, 0)
        self.spin_trail_start = QDoubleSpinBox()
        self.spin_trail_start.setRange(0.5, 30); self.spin_trail_start.setValue(4.0)
        self.spin_trail_start.setSuffix(" %")
        g2g.addWidget(self.spin_trail_start, 1, 1)

        g2g.addWidget(QLabel("최고점 하락 허용(%):"), 1, 2)
        self.spin_trail_drop = QDoubleSpinBox()
        self.spin_trail_drop.setRange(0.1, 10); self.spin_trail_drop.setValue(1.5)
        self.spin_trail_drop.setSuffix(" %")
        g2g.addWidget(self.spin_trail_drop, 1, 3)
        vbox.addWidget(g2)

        # 일일 손실 한도
        g3 = QGroupBox("계좌 전체 일일 안전장치")
        g3g = QGridLayout(g3)
        g3g.addWidget(QLabel("일일 최대 손실 한도(%):"), 0, 0)
        self.spin_daily_loss = QDoubleSpinBox()
        self.spin_daily_loss.setRange(0.1, 20); self.spin_daily_loss.setValue(3.0)
        self.spin_daily_loss.setSuffix(" %")
        g3g.addWidget(self.spin_daily_loss, 0, 1)
        g3g.addWidget(QLabel("하루 최대 주문 횟수:"), 1, 0)
        self.spin_max_orders = QSpinBox()
        self.spin_max_orders.setRange(1, 200); self.spin_max_orders.setValue(30)
        g3g.addWidget(self.spin_max_orders, 1, 1)
        vbox.addWidget(g3)

        # 긴급 청산
        g4 = QGroupBox("긴급 청산")
        g4v = QVBoxLayout(g4)
        warn = QLabel("⚠  아래 버튼을 누르면 보유 모든 종목을 즉시 시장가 전량 매도합니다.")
        warn.setObjectName("labelYellow")
        g4v.addWidget(warn)
        self.btn_liquidate = QPushButton("전체 종목 즉시 청산 (시장가)")
        self.btn_liquidate.setObjectName("btnEmergency")
        self.btn_liquidate.setMinimumHeight(48)
        g4v.addWidget(self.btn_liquidate)
        vbox.addWidget(g4)

        vbox.addStretch()


# ── 탭 5 : 스케줄러 ───────────────────────────────────────────────────────────
class _SchedulerTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        g1 = QGroupBox("자동 시작 / 로그인 예약")
        g1g = QGridLayout(g1)
        self.chk_auto_start = QCheckBox("지정 시각에 자동으로 매매 시작")
        g1g.addWidget(self.chk_auto_start, 0, 0, 1, 2)
        g1g.addWidget(QLabel("시작 시각:"), 1, 0)
        self.time_start = QTimeEdit(QTime(8, 30))
        self.time_start.setDisplayFormat("HH:mm")
        g1g.addWidget(self.time_start, 1, 1)
        vbox.addWidget(g1)

        g2 = QGroupBox("장 마감 자동 처리")
        g2g = QGridLayout(g2)
        self.chk_eod_sell = QCheckBox("장 마감 전 전량 청산 (오버나이트 방지)")
        g2g.addWidget(self.chk_eod_sell, 0, 0, 1, 2)
        g2g.addWidget(QLabel("청산 시각:"), 1, 0)
        self.time_close = QTimeEdit(QTime(15, 15))
        self.time_close.setDisplayFormat("HH:mm")
        g2g.addWidget(self.time_close, 1, 1)
        vbox.addWidget(g2)

        g3 = QGroupBox("프로그램 자동 종료")
        g3g = QGridLayout(g3)
        self.chk_auto_quit = QCheckBox("지정 시각에 프로그램 자동 종료")
        g3g.addWidget(self.chk_auto_quit, 0, 0, 1, 2)
        g3g.addWidget(QLabel("종료 시각:"), 1, 0)
        self.time_quit = QTimeEdit(QTime(16, 0))
        self.time_quit.setDisplayFormat("HH:mm")
        g3g.addWidget(self.time_quit, 1, 1)
        self.chk_pc_shutdown = QCheckBox("프로그램 종료 후 PC 전원 끄기")
        g3g.addWidget(self.chk_pc_shutdown, 2, 0, 1, 2)
        vbox.addWidget(g3)

        g4 = QGroupBox("거래 시간 제한")
        g4g = QGridLayout(g4)
        g4g.addWidget(QLabel("매수 허용 시간:"), 0, 0)
        self.time_buy_start = QTimeEdit(QTime(9, 0))
        self.time_buy_start.setDisplayFormat("HH:mm")
        g4g.addWidget(self.time_buy_start, 0, 1)
        g4g.addWidget(QLabel("~"), 0, 2)
        self.time_buy_end = QTimeEdit(QTime(14, 50))
        self.time_buy_end.setDisplayFormat("HH:mm")
        g4g.addWidget(self.time_buy_end, 0, 3)
        vbox.addWidget(g4)

        self.btn_save_sched = QPushButton("스케줄 저장")
        vbox.addWidget(self.btn_save_sched)
        vbox.addStretch()


# ── 탭 6 : 백테스트 ───────────────────────────────────────────────────────────
class _BacktestTab(QWidget):
    run_requested = pyqtSignal(str, str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        g1 = QGroupBox("백테스트 설정")
        g1g = QGridLayout(g1)
        g1g.addWidget(QLabel("종목코드:"), 0, 0)
        self.edit_bt_code = QLineEdit("005930")
        self.edit_bt_code.setMaximumWidth(100)
        g1g.addWidget(self.edit_bt_code, 0, 1)

        g1g.addWidget(QLabel("전략:"), 0, 2)
        self.combo_strat = QComboBox()
        self.combo_strat.addItems(["MA 골든크로스", "RSI 전략"])
        g1g.addWidget(self.combo_strat, 0, 3)

        g1g.addWidget(QLabel("기간(일):"), 1, 0)
        self.spin_bt_days = QSpinBox()
        self.spin_bt_days.setRange(60, 1825); self.spin_bt_days.setValue(365)
        g1g.addWidget(self.spin_bt_days, 1, 1)

        g1g.addWidget(QLabel("초기 자금(원):"), 1, 2)
        self.spin_bt_cash = QSpinBox()
        self.spin_bt_cash.setRange(1_000_000, 1_000_000_000)
        self.spin_bt_cash.setSingleStep(1_000_000)
        self.spin_bt_cash.setValue(10_000_000)
        g1g.addWidget(self.spin_bt_cash, 1, 3)

        self.btn_run_bt = QPushButton("백테스트 실행")
        self.btn_run_bt.setObjectName("btnBuy")
        g1g.addWidget(self.btn_run_bt, 2, 0, 1, 4)
        vbox.addWidget(g1)

        # 결과 요약 카드
        card_row = QHBoxLayout()
        self._bt_cards = {}
        for key, title in [
            ("ret", "총 수익률"), ("mdd", "최대 낙폭"),
            ("trades", "총 매매 횟수"), ("wr", "승률")
        ]:
            g = QGroupBox(title)
            gv = QVBoxLayout(g)
            lb = QLabel("--")
            lb.setAlignment(Qt.AlignCenter)
            f = lb.font(); f.setPointSize(16); f.setBold(True); lb.setFont(f)
            gv.addWidget(lb)
            card_row.addWidget(g)
            self._bt_cards[key] = lb
        vbox.addLayout(card_row)

        # 상세 결과
        g2 = QGroupBox("상세 결과")
        g2v = QVBoxLayout(g2)
        self.txt_bt_result = QTextEdit()
        self.txt_bt_result.setReadOnly(True)
        self.txt_bt_result.setFont(QFont("Consolas", 10))
        g2v.addWidget(self.txt_bt_result)
        self.btn_save_chart = QPushButton("차트 저장 (PNG)")
        g2v.addWidget(self.btn_save_chart)
        vbox.addWidget(g2)

        self.btn_run_bt.clicked.connect(self._on_run)

    def _on_run(self):
        self.run_requested.emit(
            self.edit_bt_code.text().strip(),
            self.combo_strat.currentText(),
            self.spin_bt_days.value(),
            self.spin_bt_cash.value(),
        )

    def show_result(self, result: dict):
        ret = result.get("total_return", 0)
        mdd = result.get("mdd", 0)
        trades = result.get("trade_count", result.get("total_trades", 0))
        wr = result.get("win_rate", 0)

        self._bt_cards["ret"].setText(f"{ret:+.2%}")
        self._bt_cards["ret"].setObjectName("labelProfit" if ret >= 0 else "labelLoss")
        self._bt_cards["mdd"].setText(f"{mdd:.2%}")
        self._bt_cards["trades"].setText(str(trades))
        self._bt_cards["wr"].setText(f"{wr:.0%}")

        from backtest.engine import BacktestEngine
        self.txt_bt_result.setText(BacktestEngine.report_text(result))
        self._last_result = result

    def save_chart(self, result: dict):
        path, _ = QFileDialog.getSaveFileName(
            self, "차트 저장", f"backtest_{result.get('code','')}.png", "PNG (*.png)"
        )
        if path:
            from backtest.chart import BacktestChart
            BacktestChart(result).plot(path)
            QMessageBox.information(self, "저장 완료", f"차트 저장: {path}")


# ── 탭 7 : 스크리닝 ───────────────────────────────────────────────────────────
class _ScreeningTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        g1 = QGroupBox("스크리닝 조건")
        g1g = QGridLayout(g1)
        g1g.addWidget(QLabel("대상 시장:"), 0, 0)
        self.combo_market = QComboBox()
        self.combo_market.addItems(["KOSPI", "KOSDAQ", "직접 입력"])
        g1g.addWidget(self.combo_market, 0, 1)
        g1g.addWidget(QLabel("상위 종목 수:"), 0, 2)
        self.spin_top_n = QSpinBox()
        self.spin_top_n.setRange(10, 200); self.spin_top_n.setValue(50)
        g1g.addWidget(self.spin_top_n, 0, 3)

        g1g.addWidget(QLabel("분석일수:"), 1, 0)
        self.spin_sc_days = QSpinBox()
        self.spin_sc_days.setRange(20, 120); self.spin_sc_days.setValue(60)
        g1g.addWidget(self.spin_sc_days, 1, 1)

        g1g.addWidget(QLabel("직접 입력 코드(,구분):"), 2, 0)
        self.edit_codes = QLineEdit()
        self.edit_codes.setPlaceholderText("005930,035420,000660")
        g1g.addWidget(self.edit_codes, 2, 1, 1, 3)

        # 필터
        g1g.addWidget(QLabel("최소 점수:"), 3, 0)
        self.spin_min_score = QDoubleSpinBox()
        self.spin_min_score.setRange(0, 5); self.spin_min_score.setValue(1.5)
        g1g.addWidget(self.spin_min_score, 3, 1)
        g1g.addWidget(QLabel("최소 거래량배율:"), 3, 2)
        self.spin_min_vol = QDoubleSpinBox()
        self.spin_min_vol.setRange(0, 10); self.spin_min_vol.setValue(1.2)
        g1g.addWidget(self.spin_min_vol, 3, 3)
        g1g.addWidget(QLabel("RSI 상한:"), 4, 0)
        self.spin_rsi_max = QSpinBox()
        self.spin_rsi_max.setRange(50, 90); self.spin_rsi_max.setValue(65)
        g1g.addWidget(self.spin_rsi_max, 4, 1)

        self.btn_screen = QPushButton("스크리닝 시작")
        self.btn_screen.setObjectName("btnBuy")
        g1g.addWidget(self.btn_screen, 5, 0, 1, 4)
        vbox.addWidget(g1)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        vbox.addWidget(self.progress)

        self.tbl_screen = _make_table(
            ["종목코드", "종목명", "현재가", "분석점수",
             "RSI", "거래량배율", "의견"], stretch_col=1
        )
        self.tbl_screen.doubleClicked.connect(self._on_row_double_click)
        vbox.addWidget(self.tbl_screen)

        btn2 = QHBoxLayout()
        self.btn_add_watch = QPushButton("관심종목 추가")
        self.btn_sc_export = QPushButton("CSV 내보내기")
        btn2.addWidget(self.btn_add_watch)
        btn2.addWidget(self.btn_sc_export)
        btn2.addStretch()
        vbox.addLayout(btn2)

    def show_results(self, results: list):
        self.progress.setVisible(False)
        self.tbl_screen.setRowCount(0)
        for res in results:
            r = self.tbl_screen.rowCount()
            self.tbl_screen.insertRow(r)
            opinion = res.get("opinion", "")
            items = [
                res.get("code", ""), res.get("name", ""),
                f"{res.get('price', 0):,.0f}",
                f"{res.get('score', 0):.2f}",
                f"{res.get('rsi', 0):.1f}" if res.get("rsi") else "--",
                f"{res.get('volume_ratio', 0):.2f}x",
                opinion,
            ]
            for c, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if c == 6:
                    if "매수" in val:
                        item.setForeground(QColor(C_BUY))
                    elif "매도" in val:
                        item.setForeground(QColor(C_SELL))
                self.tbl_screen.setItem(r, c, item)

    def _on_row_double_click(self, index):
        code_item = self.tbl_screen.item(index.row(), 0)
        name_item = self.tbl_screen.item(index.row(), 1)
        if code_item:
            QMessageBox.information(
                self, "종목 정보",
                f"종목코드: {code_item.text()}\n종목명: {name_item.text() if name_item else ''}"
            )


# ── 탭 8 : 종목 분석 ─────────────────────────────────────────────────────────
class _AnalysisTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)

        # 조회
        row = QHBoxLayout()
        row.addWidget(QLabel("종목코드:"))
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText("005930")
        self.edit_code.setMaximumWidth(100)
        row.addWidget(self.edit_code)
        row.addWidget(QLabel("기간(일):"))
        self.spin_days = QSpinBox()
        self.spin_days.setRange(30, 365); self.spin_days.setValue(90)
        row.addWidget(self.spin_days)
        self.btn_analyze = QPushButton("분석 실행")
        self.btn_analyze.setObjectName("btnBuy")
        row.addWidget(self.btn_analyze)
        row.addStretch()
        vbox.addLayout(row)

        # 신호 카드
        card_row = QHBoxLayout()
        self._sig_cards = {}
        for key, title in [
            ("ma", "이동평균"), ("rsi", "RSI"),
            ("macd", "MACD"), ("bb", "볼린저밴드"),
            ("vol", "거래량"), ("score", "종합점수")
        ]:
            g = QGroupBox(title)
            gv = QVBoxLayout(g)
            lb = QLabel("--")
            lb.setAlignment(Qt.AlignCenter)
            f = lb.font(); f.setPointSize(12); f.setBold(True); lb.setFont(f)
            gv.addWidget(lb)
            card_row.addWidget(g)
            self._sig_cards[key] = lb
        vbox.addLayout(card_row)

        # 상세 리포트
        g2 = QGroupBox("상세 분석 리포트")
        g2v = QVBoxLayout(g2)
        self.txt_report = QTextEdit()
        self.txt_report.setReadOnly(True)
        self.txt_report.setFont(QFont("Consolas", 10))
        g2v.addWidget(self.txt_report)
        vbox.addWidget(g2)

    def show_analysis(self, analysis: dict, code: str, name: str):
        rsi = analysis.get("rsi") or 0
        score = analysis.get("total_score", 0)
        opinion = analysis.get("opinion", ("중립", "⚪"))

        # RSI 카드
        self._sig_cards["rsi"].setText(f"{rsi:.1f}")

        # 종합점수 카드
        self._sig_cards["score"].setText(f"{score:.1f} {opinion[1]}")

        # 이동평균 카드: moving_averages 키 사용
        ma = analysis.get("moving_averages") or {}
        ma5 = ma.get("ma5")
        ma20 = ma.get("ma20")
        if ma5 is not None and ma20 is not None:
            self._sig_cards["ma"].setText("▲상승" if ma5 > ma20 else "▼하락")
        else:
            self._sig_cards["ma"].setText("--")

        # MACD 카드
        macd = analysis.get("macd") or {}
        if macd:
            hist = macd.get("histogram", 0)
            self._sig_cards["macd"].setText(f"{'▲' if hist > 0 else '▼'}{abs(hist):.1f}")
        else:
            self._sig_cards["macd"].setText("--")

        # 볼린저밴드 카드
        bb = analysis.get("bollinger") or {}
        if bb:
            pct_b = bb.get("pct_b", 0.5)
            if pct_b < 0.1:
                self._sig_cards["bb"].setText("▲하단근접")
            elif pct_b > 0.9:
                self._sig_cards["bb"].setText("▼상단근접")
            else:
                self._sig_cards["bb"].setText(f"중앙 {pct_b:.2f}")
        else:
            self._sig_cards["bb"].setText("--")

        # 거래량 카드
        vol = analysis.get("volume") or {}
        ratio = vol.get("ratio", 0) if vol else 0
        self._sig_cards["vol"].setText(f"{ratio:.1f}x")

        # 상세 리포트
        from core.analyzer import StockAnalyzer
        self.txt_report.setText(StockAnalyzer.report_text_from(analysis, code, name))

        # 버튼 복원
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("분석 실행")


# ── 좌측 사이드바 ─────────────────────────────────────────────────────────────
class _Sidebar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setMaximumWidth(240)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(4, 4, 4, 4)

        # 조건식 목록
        g1 = QGroupBox("활성 조건식")
        g1v = QVBoxLayout(g1)
        self.cond_active_list = QListWidget()
        self.cond_active_list.setMaximumHeight(150)
        g1v.addWidget(self.cond_active_list)
        vbox.addWidget(g1)

        # 실시간 포착 종목
        g2 = QGroupBox("실시간 포착")
        g2v = QVBoxLayout(g2)
        self.detected_list = QListWidget()
        self.detected_list.setMaximumHeight(180)
        g2v.addWidget(self.detected_list)
        vbox.addWidget(g2)

        # 관심 종목
        g3 = QGroupBox("관심 종목")
        g3v = QVBoxLayout(g3)
        self.watch_list = QListWidget()
        g3v.addWidget(self.watch_list)
        vbox.addWidget(g3)

    def add_detected(self, code: str, name: str, price: float):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{now}] {name}({code}) {price:,.0f}")
        item.setForeground(QColor(C_BUY))
        self.detected_list.insertItem(0, item)
        if self.detected_list.count() > 50:
            self.detected_list.takeItem(self.detected_list.count() - 1)


# ── 하단 로그 패널 ─────────────────────────────────────────────────────────────
class _LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setMaximumHeight(220)
        self._build()

    def _build(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(2, 2, 2, 2)

        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.South)

        self.log_detect = QTextEdit()
        self.log_detect.setReadOnly(True)
        self.log_detect.setFont(QFont("Consolas", 9))
        tabs.addTab(self.log_detect, "포착 로그")

        self.log_order = QTextEdit()
        self.log_order.setReadOnly(True)
        self.log_order.setFont(QFont("Consolas", 9))
        tabs.addTab(self.log_order, "주문/체결")

        self.log_api = QTextEdit()
        self.log_api.setReadOnly(True)
        self.log_api.setFont(QFont("Consolas", 9))
        tabs.addTab(self.log_api, "API 통신")

        vbox.addWidget(tabs)
        self._tabs = [self.log_detect, self.log_order, self.log_api]

    def append(self, text: str, tab: int = 0):
        if 0 <= tab < len(self._tabs):
            te = self._tabs[tab]
            te.append(text)
            te.verticalScrollBar().setValue(te.verticalScrollBar().maximum())

    def append_raw(self, text: str):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if any(k in line for k in ["매수", "포착", "진입"]):
                self.append(f'<span style="color:{C_BUY}">{line}</span>', 0)
            elif any(k in line for k in ["매도", "청산", "손절", "익절"]):
                self.append(f'<span style="color:{C_SELL}">{line}</span>', 1)
            elif any(k in line for k in ["오류", "ERROR", "WARNING", "연결"]):
                self.append(f'<span style="color:{C_YELLOW}">{line}</span>', 2)
            else:
                self.append(line, 0)


# ── 상단 헤더 바 ──────────────────────────────────────────────────────────────
class _HeaderBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self._build()

    def _build(self):
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(8, 4, 8, 4)
        hbox.setSpacing(12)

        # 타이틀
        title = QLabel("⚡ AutoTrader")
        title.setObjectName("labelTitle")
        hbox.addWidget(title)
        hbox.addWidget(_sep())

        # API 상태
        hbox.addWidget(QLabel("API:"))
        self.lbl_api = QLabel("연결 안됨")
        self.lbl_api.setObjectName("labelYellow")
        hbox.addWidget(self.lbl_api)
        hbox.addWidget(_sep())

        # 계좌 선택
        hbox.addWidget(QLabel("계좌:"))
        self.combo_account = QComboBox()
        self.combo_account.setMinimumWidth(160)
        hbox.addWidget(self.combo_account)
        self.lbl_simul = QLabel("[모의]")
        self.lbl_simul.setObjectName("labelYellow")
        hbox.addWidget(self.lbl_simul)
        hbox.addWidget(_sep())

        # 잔고 요약
        self.lbl_balance = QLabel("예수금: --")
        hbox.addWidget(self.lbl_balance)
        self.lbl_profit = QLabel("손익: --")
        hbox.addWidget(self.lbl_profit)
        hbox.addWidget(_sep())

        # 장 시간
        hbox.addWidget(QLabel("현재:"))
        self.lbl_time = QLabel("--:--:--")
        self.lbl_time.setFont(QFont("Consolas", 12))
        hbox.addWidget(self.lbl_time)
        hbox.addWidget(_sep())

        hbox.addStretch()

        # 마스터 ON/OFF
        self.btn_start = QPushButton("▶  자동매매 시작")
        self.btn_start.setObjectName("btnStart")
        hbox.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  정지")
        self.btn_stop.setObjectName("btnStop")
        self.btn_stop.setEnabled(False)
        hbox.addWidget(self.btn_stop)

        # 타이머
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick)
        self._clock.start(1000)

    def _tick(self):
        now = datetime.datetime.now()
        self.lbl_time.setText(now.strftime("%H:%M:%S"))
        # 장 시간 강조 09:00~15:30
        t = now.time()
        if datetime.time(9, 0) <= t <= datetime.time(15, 30):
            self.lbl_time.setObjectName("labelGreen")
        else:
            self.lbl_time.setObjectName("labelSub")

    def set_api_connected(self, ok: bool):
        if ok:
            self.lbl_api.setText("연결됨")
            self.lbl_api.setObjectName("labelGreen")
        else:
            self.lbl_api.setText("연결 안됨")
            self.lbl_api.setObjectName("labelYellow")

    def set_trading(self, running: bool):
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)


# ── 메인 윈도우 ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """
    HTS 스타일 자동매매 메인 윈도우.

    사용:
        app = QApplication(sys.argv)
        win = MainWindow(controller, market_data_api)
        win.show()
        app.exec_()
    """

    def __init__(self, controller=None, market_data_api=None, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        # controller 가 있으면 내부 mdata를 참조, 없으면 직접 주입된 것 사용
        self._mdata = market_data_api or (
            getattr(controller, "_market_data", None) if controller else None
        )
        self._bt_result = None

        self.setWindowTitle("AutoTrader — HTS 자동매매")
        self.resize(1400, 900)
        self.setStyleSheet(DARK_QSS)

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._connect_signals()
        self._start_log_tail()

        # 잔고 갱신 타이머 (60초 간격, 키움 TR 요청 제한 고려)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_balance)
        self._refresh_timer.start(60000)

        # 스케줄러 체크 타이머
        self._sched_timer = QTimer(self)
        self._sched_timer.timeout.connect(self._check_schedule)
        self._sched_timer.start(30000)

    # ── 메뉴바 ──────────────────────────────────────────────────────────────
    def _build_menu(self):
        mb = self.menuBar()

        m_file = mb.addMenu("파일(&F)")
        m_file.addAction("설정 저장", self._save_settings)
        m_file.addAction("설정 불러오기", self._load_settings)
        m_file.addSeparator()
        m_file.addAction("종료", self.close)

        m_trade = mb.addMenu("매매(&T)")
        m_trade.addAction("전체 청산", self._emergency_liquidate)
        m_trade.addAction("매매 시작", self._on_start)
        m_trade.addAction("매매 정지", self._on_stop)

        m_view = mb.addMenu("보기(&V)")
        m_view.addAction("잔고 새로고침", lambda: self._refresh_balance(force=True))
        m_view.addAction("로그 지우기", self._clear_logs)

        m_help = mb.addMenu("도움말(&H)")
        m_help.addAction("사용법", self._show_help)
        m_help.addAction("버전 정보", self._show_about)

    # ── 툴바 ────────────────────────────────────────────────────────────────
    def _build_toolbar(self):
        tb = QToolBar("메인 도구 모음", self)
        tb.setIconSize(QSize(16, 16))
        tb.setMovable(False)
        self.addToolBar(tb)

        for label, slot in [
            ("잔고조회", lambda _=False: self._refresh_balance(force=True)),
            ("조건식로드", self._load_conditions),
            ("로그지우기", self._clear_logs),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            tb.addWidget(btn)
            tb.addSeparator()

    # ── 중앙 위젯 ────────────────────────────────────────────────────────────
    def _build_central(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_vbox = QVBoxLayout(central)
        main_vbox.setContentsMargins(0, 0, 0, 0)
        main_vbox.setSpacing(0)

        # 헤더 바
        self.header = _HeaderBar()
        main_vbox.addWidget(self.header)
        main_vbox.addWidget(_sep(False))

        # 좌·중앙 분할
        h_splitter = QSplitter(Qt.Horizontal)

        # 좌측 사이드바
        self.sidebar = _Sidebar()
        h_splitter.addWidget(self.sidebar)

        # 중앙 탭
        self.tabs = QTabWidget()
        self.tab_dashboard = _DashboardTab()
        self.tab_condition = _ConditionTab()
        self.tab_individual = _IndividualTab()
        self.tab_stoploss = _StopLossTab()
        self.tab_scheduler = _SchedulerTab()
        self.tab_backtest = _BacktestTab()
        self.tab_screening = _ScreeningTab()
        self.tab_analysis = _AnalysisTab()

        self.tabs.addTab(self.tab_dashboard, "📊 대시보드")
        self.tabs.addTab(self.tab_condition, "🔍 조건식 매매")
        self.tabs.addTab(self.tab_individual, "📌 종목별 매매")
        self.tabs.addTab(self.tab_stoploss, "🛡 손익/청산")
        self.tabs.addTab(self.tab_scheduler, "⏰ 스케줄러")
        self.tabs.addTab(self.tab_backtest, "📈 백테스트")
        self.tabs.addTab(self.tab_screening, "🔎 스크리닝")
        self.tabs.addTab(self.tab_analysis, "🔬 종목분석")

        h_splitter.addWidget(self.tabs)
        h_splitter.setStretchFactor(0, 0)
        h_splitter.setStretchFactor(1, 1)
        h_splitter.setSizes([200, 1200])

        # 상하 분할 (메인 + 로그)
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(h_splitter)
        self.log_panel = _LogPanel()
        v_splitter.addWidget(self.log_panel)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)
        v_splitter.setSizes([700, 160])

        main_vbox.addWidget(v_splitter)

    # ── 상태바 ──────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_mode = QLabel("모드: 모의투자")
        self.status_api = QLabel("API: 대기")
        self.status_orders = QLabel("오늘 주문: 0회")
        sb.addWidget(self.status_mode)
        sb.addPermanentWidget(self.status_api)
        sb.addPermanentWidget(self.status_orders)

    # ── 시그널 연결 ──────────────────────────────────────────────────────────
    def _connect_signals(self):
        self.header.btn_start.clicked.connect(self._on_start)
        self.header.btn_stop.clicked.connect(self._on_stop)
        self.tab_dashboard.btn_sell_all.clicked.connect(self._emergency_liquidate)
        self.tab_dashboard.btn_refresh.clicked.connect(lambda _=False: self._refresh_balance(force=True))
        self.tab_stoploss.btn_liquidate.clicked.connect(self._emergency_liquidate)
        self.tab_condition.btn_load_cond.clicked.connect(self._load_conditions)
        self.tab_backtest.btn_save_chart.clicked.connect(self._save_bt_chart)
        self.tab_backtest.run_requested.connect(self._run_backtest)
        self.tab_screening.btn_screen.clicked.connect(self._run_screening)
        self.tab_screening.btn_sc_export.clicked.connect(self._export_screening)
        self.tab_screening.btn_add_watch.clicked.connect(self._add_watch_from_screen)
        self.tab_analysis.btn_analyze.clicked.connect(self._run_analysis)
        self.tab_scheduler.btn_save_sched.clicked.connect(self._save_settings)
        self.tab_individual.btn_add.clicked.connect(self._add_individual_stock)
        self.tab_individual.btn_del.clicked.connect(self._del_individual_stock)
        self.tab_individual.btn_import.clicked.connect(self._import_individual_csv)
        self.tab_individual.btn_apply_detail.clicked.connect(self._apply_individual_detail)
        # 탭 전환 시 당일 거래내역 갱신
        self.tabs.currentChanged.connect(self._on_tab_changed)
        # 시작 시 관심종목 불러오기
        self._load_watchlist()

    # ── 로그 테일 ────────────────────────────────────────────────────────────
    def _start_log_tail(self):
        self._log_thread = _LogTailThread(LOG_FILE, self)
        self._log_thread.new_lines.connect(self.log_panel.append_raw)
        self._log_thread.start()

    # ── 매매 시작 / 정지 ─────────────────────────────────────────────────────
    def _on_start(self):
        if self._ctrl is None:
            self._demo_start()
            return
        try:
            settings = self._collect_settings()
            self._ctrl.start(settings)
            self.header.set_trading(True)
            self.status_mode.setText("모드: 매매 중")
            self._log("매매 시작", 0)
        except Exception as e:
            QMessageBox.critical(self, "오류", str(e))

    def _demo_start(self):
        self.header.set_trading(True)
        self.status_mode.setText("모드: 데모 실행 중")
        self._log("[데모] 자동매매 시작 (Kiwoom 연결 없음)", 0)

    def _on_stop(self):
        if self._ctrl:
            self._ctrl.stop()
        self.header.set_trading(False)
        self.status_mode.setText("모드: 정지")
        self._log("매매 정지", 0)

    # ── 긴급 청산 ────────────────────────────────────────────────────────────
    def _emergency_liquidate(self):
        ret = QMessageBox.critical(
            self, "전체 청산 확인",
            "보유 모든 종목을 즉시 시장가 전량 매도합니다.\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            if self._ctrl:
                self._ctrl.stop()
            self._log("⚠ 긴급 전체 청산 실행", 1)

    # ── 잔고 새로고침 ────────────────────────────────────────────────────────
    def _refresh_balance(self, force=False):
        # 타이머 자동 조회는 장 시간 외 생략 (불필요한 TR 절약)
        # 수동 버튼 클릭(force=True) 은 시간 무관하게 조회
        if not force:
            now_h = datetime.datetime.now().hour
            if now_h < 8 or now_h >= 16:
                return

        # 콤보박스에 보이는 계좌를 컨트롤러에 강제 동기화 (desync 방지)
        try:
            combo = getattr(self.header, "combo_account", None)
            if self._ctrl and combo is not None:
                acc = combo.currentText().strip()
                if acc and acc != getattr(self._ctrl, "_account", None):
                    self._ctrl._account = acc
                    self._log(f"조회 계좌 변경: {acc}", 2)
        except Exception as e:
            logger.debug("계좌 동기화 실패: %s", e)

        # controller 경유 (연결된 경우)
        if self._ctrl:
            try:
                status = self._ctrl.get_status()
                summary = status.get("account", {})
                holdings = status.get("holdings", [])
                safety = status.get("safety", {})

                self.tab_dashboard.update_balance(summary)
                self.tab_dashboard.update_holdings(holdings)

                avail = summary.get("available", 0)
                rate = summary.get("total_profit_rate", 0.0)
                self.header.lbl_balance.setText(f"예수금: {avail:,.0f}원")
                self.header.lbl_profit.setText(
                    f"수익률: {rate:+.2f}%"
                )

                # 안전장치 상태 반영
                if safety.get("halted"):
                    self.status_mode.setText(f"⚠ 매매중단: {safety.get('halt_reason','')}")
                orders = safety.get("order_count", 0)
                max_ord = safety.get("max_orders", 0)
                if max_ord:
                    self.status_orders.setText(f"오늘 주문: {orders}/{max_ord}회")
            except Exception as e:
                logger.warning("잔고 조회 실패(controller): %s", e)
            return

        # mdata 직접 조회 (controller 없는 경우)
        if self._mdata is None:
            return
        try:
            account = getattr(self._ctrl, "_account", None) if self._ctrl else None
            if account is None:
                return
            data = self._mdata.get_account_balance(account)
            summary = data.get("summary", {})
            df_h = data.get("holdings")
            holdings = df_h.to_dict("records") if df_h is not None and not df_h.empty else []
            self.tab_dashboard.update_balance(summary)
            self.tab_dashboard.update_holdings(holdings)
            avail = summary.get("available", 0)
            self.header.lbl_balance.setText(f"예수금: {avail:,.0f}원")
        except Exception as e:
            logger.warning("잔고 조회 실패: %s", e)

    # ── 조건식 불러오기 ──────────────────────────────────────────────────────
    def _load_conditions(self):
        if self._mdata is None:
            demo = ["골든크로스 전략", "거래량 급증", "눌림목 돌파", "상한가 직전"]
            self.tab_condition.set_conditions(demo)
            self.sidebar.cond_active_list.clear()
            for c in demo:
                self.sidebar.cond_active_list.addItem(c)
            self._log("[데모] 조건식 4개 로드", 2)
            return
        try:
            kiwoom = getattr(self._mdata, "api", None) or getattr(
                self._mdata, "_kiwoom", None
            )
            if kiwoom:
                kiwoom.dynamicCall("GetConditionLoad()")
        except Exception as e:
            logger.warning("조건식 로드 실패: %s", e)

    # ── 백테스트 ─────────────────────────────────────────────────────────────
    def _run_backtest(self, code, strat_name, days, cash):
        if self._mdata is None:
            QMessageBox.warning(self, "안내", "Kiwoom 연결 후 백테스트 가능합니다.")
            return
        if not code:
            QMessageBox.warning(self, "안내", "종목코드를 입력하세요.")
            return
        self.tab_backtest.btn_run_bt.setEnabled(False)
        self.tab_backtest.btn_run_bt.setText("실행 중...")
        self._log(f"백테스트 시작: {code} / {strat_name} / {days}일", 0)
        QApplication.processEvents()
        try:
            import datetime as dt
            from backtest.engine import BacktestEngine
            from strategy.ma_strategy import MAStrategy
            from strategy.rsi_strategy import RSIStrategy
            start = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y%m%d")
            # 키움 OCX는 메인 스레드에서만 TR 응답 수신
            df = self._mdata.get_daily_ohlcv(code, start)
            strat = MAStrategy() if strat_name.startswith("MA") else RSIStrategy()
            engine = BacktestEngine(strat, initial_cash=cash)
            result = engine.run(df, code)
            self._on_bt_done(result)
        except Exception as e:
            logger.error("백테스트 오류: %s", e)
            self._log(f"백테스트 오류: {e}", 0)
            QMessageBox.critical(self, "오류", str(e))
        finally:
            self.tab_backtest.btn_run_bt.setEnabled(True)
            self.tab_backtest.btn_run_bt.setText("백테스트 실행")

    def _on_bt_done(self, result):
        self._bt_result = result
        self.tab_backtest.show_result(result)
        self._log(
            f"백테스트 완료: {result.get('strategy')} 수익률 {result.get('total_return',0):+.2%}", 0
        )

    def _save_bt_chart(self):
        if self._bt_result:
            self.tab_backtest.save_chart(self._bt_result)

    # ── 스크리닝 ─────────────────────────────────────────────────────────────
    def _run_screening(self):
        if self._mdata is None:
            QMessageBox.warning(self, "안내", "Kiwoom 연결 후 스크리닝 가능합니다.")
            return
        from core.screener import StockScreener
        screener = StockScreener(
            self._mdata,
            min_score=self.tab_screening.spin_min_score.value(),
            min_volume_ratio=self.tab_screening.spin_min_vol.value(),
            rsi_max=self.tab_screening.spin_rsi_max.value(),
        )
        codes_text = self.tab_screening.edit_codes.text().strip()
        codes = [c.strip() for c in codes_text.split(",") if c.strip()] if codes_text else None
        market = self.tab_screening.combo_market.currentText().lower()
        top_n = self.tab_screening.spin_top_n.value()

        self.tab_screening.progress.setVisible(True)
        self.tab_screening.progress.setRange(0, 0)
        self.tab_screening.btn_screen.setEnabled(False)
        if codes:
            self._log(f"스크리닝 시작: 직접입력 {len(codes)}종목 ({','.join(codes)})", 0)
        else:
            self._log(f"스크리닝 시작: 시장={market}, 상위 {top_n}종목", 0)
        QApplication.processEvents()
        try:
            # 키움 OCX TR은 메인 스레드에서만 응답 수신
            if codes:
                results = screener.screen(codes)
            else:
                results = screener.screen_from_market(market, top_n)
            self._on_screen_done(results)
        except Exception as e:
            logger.error("스크리닝 오류: %s", e)
            self._log(f"스크리닝 오류: {e}", 0)
            QMessageBox.critical(self, "오류", str(e))
        finally:
            self.tab_screening.progress.setVisible(False)
            self.tab_screening.btn_screen.setEnabled(True)

    def _on_screen_done(self, results):
        self.tab_screening.show_results(results)
        if results:
            self._log(f"스크리닝 완료: {len(results)}종목 선별", 0)
        else:
            self._log(
                "스크리닝 완료: 조건 통과 0종목 "
                "(최소점수/거래량배율/RSI상한 필터를 완화해 보세요)", 0
            )

    def _export_screening(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV 저장", f"screener_{datetime.date.today():%Y%m%d}.csv", "CSV (*.csv)"
        )
        if not path:
            return
        rows = []
        t = self.tab_screening.tbl_screen
        for r in range(t.rowCount()):
            rows.append([t.item(r, c).text() if t.item(r, c) else "" for c in range(t.columnCount())])
        try:
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                headers = ["종목코드", "종목명", "현재가", "분석점수", "RSI", "거래량배율", "의견"]
                w.writerow(headers)
                w.writerows(rows)
            QMessageBox.information(self, "저장 완료", path)
        except Exception as e:
            QMessageBox.critical(self, "저장 실패", str(e))

    # ── 종목 분석 ────────────────────────────────────────────────────────────
    def _run_analysis(self):
        self._log("분석 실행 버튼 클릭됨", 0)
        code = self.tab_analysis.edit_code.text().strip()
        if not code:
            # 입력이 없으면 placeholder(예시 종목) 사용
            code = self.tab_analysis.edit_code.placeholderText().strip()
            if code:
                self.tab_analysis.edit_code.setText(code)
        if not code:
            QMessageBox.warning(self, "안내", "종목코드를 입력하세요.")
            return
        if self._mdata is None:
            QMessageBox.warning(self, "안내", "Kiwoom 연결 후 분석 가능합니다.")
            return
        days = self.tab_analysis.spin_days.value()
        self.tab_analysis.btn_analyze.setEnabled(False)
        self.tab_analysis.btn_analyze.setText("분석 중...")
        QApplication.processEvents()
        try:
            import datetime as dt
            from core.analyzer import StockAnalyzer
            start = (dt.datetime.now() - dt.timedelta(days=days)).strftime("%Y%m%d")
            # 키움 OCX는 메인 스레드에서만 TR 응답을 받으므로 동기 실행
            df = self._mdata.get_daily_ohlcv(code, start)
            name = code
            try:
                kiwoom = getattr(self._mdata, "api", None)
                if kiwoom:
                    n = kiwoom.dynamicCall("GetMasterCodeName(QString)", code).strip()
                    if n:
                        name = n
            except Exception:
                pass
            analysis = StockAnalyzer(df).analyze()
            self.tab_analysis.show_analysis(analysis, code, name)
            self._log(f"분석 완료: {name}({code})", 0)
        except Exception as e:
            logger.error("분석 오류: %s", e)
            self._log(f"분석 오류: {e}", 0)
            QMessageBox.critical(self, "분석 오류", str(e))
            self.tab_analysis.btn_analyze.setEnabled(True)
            self.tab_analysis.btn_analyze.setText("분석 실행")

    # ── 스케줄 체크 ──────────────────────────────────────────────────────────
    def _check_schedule(self):
        now = datetime.datetime.now().time()
        sched = self.tab_scheduler

        def _qt_to_pytime(qt):
            return datetime.time(qt.hour(), qt.minute())

        def _within(qt, secs=35):
            target = _qt_to_pytime(qt)
            delta = abs((
                datetime.datetime.combine(datetime.date.today(), now)
                - datetime.datetime.combine(datetime.date.today(), target)
            ).total_seconds())
            return delta < secs

        if sched.chk_auto_start.isChecked():
            if _within(sched.time_start.time()):
                if not self.header.btn_stop.isEnabled():
                    self._on_start()

        if sched.chk_eod_sell.isChecked():
            if _within(sched.time_close.time()):
                self._emergency_liquidate()

        if sched.chk_auto_quit.isChecked():
            if _within(sched.time_quit.time()):
                if sched.chk_pc_shutdown.isChecked():
                    import subprocess
                    subprocess.Popen("shutdown /s /t 60", shell=True)
                self.close()

    # ── 설정 저장 / 불러오기 ─────────────────────────────────────────────────
    def _collect_settings(self) -> dict:
        """TradingController.start() 가 기대하는 키 형식으로 반환"""
        ct = self.tab_condition
        sl = self.tab_stoploss
        conds = ct.get_selected_conditions()
        # 전략 결정: 조건식이 체크되면 '조건검색식', 아니면 MA
        strategy = "조건검색식" if conds else "이동평균(MA)"
        return {
            # controller.start() 키
            "buy_amount": ct.spin_amount.value(),
            "stock_count": ct.spin_max_stocks.value(),
            "stop_loss": sl.spin_sl.value() / 100.0,      # % → 소수
            "take_profit": sl.spin_tp.value() / 100.0,
            "strategy": strategy,
            "condition_name": ",".join(conds),
            # 추가 설정 (SafetyGuard 등 확장 시 사용)
            "amount_ratio": ct.spin_ratio.value(),
            "reenter_min": ct.spin_reenter.value(),
            "trailing": sl.chk_trailing.isChecked(),
            "trail_start": sl.spin_trail_start.value() / 100.0,
            "trail_drop": sl.spin_trail_drop.value() / 100.0,
            "daily_loss_limit": sl.spin_daily_loss.value() / 100.0,
            "max_orders": sl.spin_max_orders.value(),
        }

    def _save_settings(self):
        import json
        path = "config/gui_settings.json"
        os.makedirs("config", exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect_settings(), f, ensure_ascii=False, indent=2)
            self.statusBar().showMessage("설정 저장 완료", 3000)
        except Exception as e:
            QMessageBox.critical(self, "저장 오류", str(e))

    def _load_settings(self):
        import json
        path = "config/gui_settings.json"
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                s = json.load(f)
            ct = self.tab_condition
            sl = self.tab_stoploss
            # _collect_settings() 저장 형식과 동일한 키 사용 (소수 → % 환산)
            ct.spin_amount.setValue(s.get("buy_amount", 1_000_000))
            ct.spin_ratio.setValue(s.get("amount_ratio", 5))
            ct.spin_max_stocks.setValue(s.get("stock_count", 5))
            ct.spin_reenter.setValue(s.get("reenter_min", 20))
            sl.spin_tp.setValue(s.get("take_profit", 0.03) * 100.0)
            sl.spin_sl.setValue(s.get("stop_loss", 0.02) * 100.0)
            sl.chk_trailing.setChecked(s.get("trailing", False))
            sl.spin_trail_start.setValue(s.get("trail_start", 0.04) * 100.0)
            sl.spin_trail_drop.setValue(s.get("trail_drop", 0.015) * 100.0)
            sl.spin_daily_loss.setValue(s.get("daily_loss_limit", 0.03) * 100.0)
            sl.spin_max_orders.setValue(s.get("max_orders", 30))
            self.statusBar().showMessage("설정 불러오기 완료", 3000)
        except Exception as e:
            QMessageBox.critical(self, "불러오기 오류", str(e))

    # ── 기타 ─────────────────────────────────────────────────────────────────
    def _clear_logs(self):
        for te in self.log_panel._tabs:
            te.clear()

    def _log(self, msg: str, tab: int = 0):
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_panel.append(f"[{now}] {msg}", tab)

    def _show_help(self):
        QMessageBox.information(
            self, "사용법",
            "1. 키움 API 연결 후 [조건식 불러오기]\n"
            "2. 조건식 매매 탭에서 조건식 체크 및 설정\n"
            "3. 손익/청산 탭에서 익절/손절 설정\n"
            "4. 상단 [자동매매 시작] 버튼으로 가동\n\n"
            "⚠ 처음에는 반드시 모의투자로 검증하세요."
        )

    def _show_about(self):
        QMessageBox.about(
            self, "버전 정보",
            "AutoTrader v1.0\n키움증권 OpenAPI+ 기반 자동매매\n\n"
            "Python + PyQt5"
        )

    # ── 탭 전환 이벤트 ───────────────────────────────────────────────────────
    def _on_tab_changed(self, idx):
        if self.tabs.widget(idx) is self.tab_dashboard:
            self._refresh_trades()

    # ── 당일 체결 내역 갱신 ──────────────────────────────────────────────────
    def _refresh_trades(self):
        if self._ctrl is None:
            return
        try:
            trader = getattr(self._ctrl, "_trader", None)
            if trader is None or not hasattr(trader, "db"):
                return
            rows = trader.db.get_today_orders()
            tbl = self.tab_dashboard.tbl_trades
            tbl.setRowCount(0)
            for row in rows:
                r = tbl.rowCount()
                tbl.insertRow(r)
                # orders 테이블: timestamp, code, name, order_type, qty, price, amount, fee, profit
                col_vals = [
                    str(row[0])[:19] if row[0] else "",   # timestamp
                    str(row[2]) if len(row) > 2 else "",  # name
                    str(row[3]) if len(row) > 3 else "",  # order_type
                    str(row[4]) if len(row) > 4 else "",  # qty
                    f"{int(row[5]):,.0f}" if len(row) > 5 and row[5] else "",  # price
                    f"{int(row[6]):,.0f}" if len(row) > 6 and row[6] else "",  # amount
                    f"{int(row[7]):,.0f}" if len(row) > 7 and row[7] else "",  # fee
                    f"{int(row[8]):+,.0f}" if len(row) > 8 and row[8] else "",  # profit
                ]
                for c, val in enumerate(col_vals):
                    item = QTableWidgetItem(val)
                    item.setTextAlignment(Qt.AlignCenter)
                    if c == 7 and val:
                        try:
                            item.setForeground(
                                QColor(C_PROFIT) if int(row[8]) >= 0 else QColor(C_LOSS)
                            )
                        except (ValueError, TypeError):
                            pass
                    tbl.setItem(r, c, item)
        except Exception as e:
            logger.debug("체결내역 갱신 실패: %s", e)

    # ── 관심종목 영구 저장 ───────────────────────────────────────────────────
    _WATCHLIST_PATH = os.path.join("config", "watchlist.json")

    def _load_watchlist(self):
        import json
        if not os.path.exists(self._WATCHLIST_PATH):
            return
        try:
            with open(self._WATCHLIST_PATH, encoding="utf-8") as f:
                items = json.load(f)
            self.sidebar.watch_list.clear()
            for it in items:
                self.sidebar.watch_list.addItem(f"{it['code']} {it.get('name','')}")
        except Exception as e:
            logger.debug("관심종목 불러오기 실패: %s", e)

    def _save_watchlist(self):
        import json
        items = []
        for i in range(self.sidebar.watch_list.count()):
            text = self.sidebar.watch_list.item(i).text()
            parts = text.split(" ", 1)
            items.append({"code": parts[0], "name": parts[1] if len(parts) > 1 else ""})
        os.makedirs("config", exist_ok=True)
        try:
            with open(self._WATCHLIST_PATH, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug("관심종목 저장 실패: %s", e)

    def _add_watch_from_screen(self):
        t = self.tab_screening.tbl_screen
        rows = list({idx.row() for idx in t.selectedIndexes()})
        for r in rows:
            code = t.item(r, 0).text() if t.item(r, 0) else ""
            name = t.item(r, 1).text() if t.item(r, 1) else ""
            if code:
                self.sidebar.watch_list.addItem(f"{code} {name}")
        self._save_watchlist()

    # ── 종목별 매매 탭 헬퍼 ─────────────────────────────────────────────────
    def _add_individual_stock(self):
        code = self.tab_individual.edit_code.text().strip()
        if not code:
            # placeholder에서 가져오기
            code = self.tab_individual.edit_code.placeholderText().replace("예: ", "").strip()
        if not code:
            return
        # 이미 추가된 코드면 건너뜀
        tbl = self.tab_individual.tbl
        for r in range(tbl.rowCount()):
            if tbl.item(r, 1) and tbl.item(r, 1).text() == code:
                self._log(f"이미 추가된 종목: {code}", 0)
                return
        name = code
        if self._mdata:
            try:
                kiwoom = getattr(self._mdata, "api", None)
                if kiwoom:
                    fetched = kiwoom.dynamicCall("GetMasterCodeName(QString)", code).strip()
                    if fetched:
                        name = fetched
            except Exception:
                pass
        # 현재가 조회
        price_str = "--"
        if self._mdata:
            try:
                info = self._mdata.get_stock_info(code)
                price_str = f"{info['price']:,}"
            except Exception:
                pass

        tbl = self.tab_individual.tbl
        r = tbl.rowCount()
        tbl.insertRow(r)
        chk = QTableWidgetItem()
        chk.setCheckState(Qt.Checked)
        tbl.setItem(r, 0, chk)
        for c, val in enumerate([code, name, price_str, "--", "--", "1,000,000", "X", "--", "대기"], 1):
            item = QTableWidgetItem(val)
            item.setTextAlignment(Qt.AlignCenter)
            tbl.setItem(r, c, item)
        self.tab_individual.edit_code.clear()

    def _apply_individual_detail(self):
        """선택된 종목에 하단 상세설정(목표/손절/투자금/밴드/트레일링)을 적용한다."""
        tbl = self.tab_individual.tbl
        selected_rows = {idx.row() for idx in tbl.selectedIndexes()}
        if not selected_rows:
            # 선택이 없으면 활성화된 모든 종목에 적용
            selected_rows = set()
            for r in range(tbl.rowCount()):
                chk = tbl.item(r, 0)
                if chk and chk.checkState() == Qt.Checked:
                    selected_rows.add(r)
        if not selected_rows:
            self._log("적용할 종목을 선택하거나 활성화해 주세요.", 0)
            return

        spins = self.tab_individual._detail_spins
        # 순서: 목표수익률%, 손절비율%, 1회투자금, 가격밴드상단, 가격밴드하단, 트레일링%
        take_profit = spins[0].value()  # %
        stop_loss   = spins[1].value()  # %
        invest_amt  = spins[2].value()  # 원
        band_high   = spins[3].value()  # 원
        band_low    = spins[4].value()  # 원
        trailing    = spins[5].value()  # %

        for r in selected_rows:
            # 현재가 기준으로 목표가/손절가 계산
            price_raw = tbl.item(r, 3).text().replace(",", "") if tbl.item(r, 3) else ""
            try:
                price = int(price_raw)
                target = int(price * (1 + take_profit / 100))
                stop   = int(price * (1 - stop_loss / 100))
                tbl.item(r, 4).setText(f"{target:,}")  # 목표가
                tbl.item(r, 5).setText(f"{stop:,}")    # 손절가
            except (ValueError, AttributeError):
                pass  # 현재가 없으면 목표가/손절가는 그대로

            # 투자금 업데이트
            if tbl.item(r, 6):
                tbl.item(r, 6).setText(f"{invest_amt:,}")
            # 트레일링
            if tbl.item(r, 8):
                tbl.item(r, 8).setText(f"{trailing:.2f}%")

        self._log(f"상세설정 {len(selected_rows)}개 종목에 적용 완료", 0)

    def _del_individual_stock(self):
        rows = sorted(
            {idx.row() for idx in self.tab_individual.tbl.selectedIndexes()},
            reverse=True
        )
        for r in rows:
            self.tab_individual.tbl.removeRow(r)

    def _import_individual_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV 불러오기", "", "CSV (*.csv)")
        if not path:
            return
        try:
            import csv
            with open(path, encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)  # 헤더 skip
                for row in reader:
                    if row:
                        self.tab_individual.edit_code.setText(row[0].strip())
                        self._add_individual_stock()
        except Exception as e:
            QMessageBox.critical(self, "불러오기 오류", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        self._save_watchlist()
        self._save_settings()
        if self._ctrl:
            self._ctrl.stop()
        if hasattr(self, "_log_thread"):
            self._log_thread.stop()
        event.accept()


# ── 단독 실행 ─────────────────────────────────────────────────────────────────
def run_standalone():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()

    # 데모: MarketDataAPI와 동일한 summary 형식
    demo_summary = {
        "total_eval": 12_345_678,
        "total_profit_rate": 2.87,
        "available": 3_000_000,
    }
    demo_holdings = [
        {"code": "005930", "name": "삼성전자", "qty": 10,
         "avg_price": 72000, "price": 75000,
         "eval_amount": 750_000, "profit": 30_000, "profit_rate": 4.17},
        {"code": "035420", "name": "NAVER", "qty": 2,
         "avg_price": 180_000, "price": 172_000,
         "eval_amount": 344_000, "profit": -16_000, "profit_rate": -4.44},
    ]
    win.tab_dashboard.update_balance(demo_summary)
    win.tab_dashboard.update_holdings(demo_holdings)
    win.header.set_api_connected(False)

    # 데모 조건식
    win.tab_condition.set_conditions(["골든크로스 전략", "거래량 급증", "눌림목 돌파"])

    sys.exit(app.exec_())


def run_with_kiwoom():
    """
    키움증권 실제 연동 모드로 GUI를 실행한다.

    순서:
      1. QApplication 생성
      2. 로그인 스플래시 표시
      3. KiwoomAPI 초기화 → 키움 로그인 팝업 → 완료 대기
      4. 계좌 목록 조회
      5. TradingController 에 로그인 세션 주입
      6. MainWindow 생성 → 잔고·조건식 초기 로드
      7. 이벤트 루프 진입
    """
    from config.settings import IS_SIMUL, ACCOUNT_NUMBER

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── 스플래시 창 ──────────────────────────────────────────────────────
    splash = QWidget(None, Qt.SplashScreen | Qt.FramelessWindowHint)
    splash.setFixedSize(400, 120)
    splash.setStyleSheet(f"background:{C_PANEL}; border:2px solid {C_ACCENT}; border-radius:8px;")
    sv = QVBoxLayout(splash)
    sv.setContentsMargins(20, 20, 20, 20)
    title_lbl = QLabel("⚡ AutoTrader")
    title_lbl.setAlignment(Qt.AlignCenter)
    f = title_lbl.font(); f.setPointSize(18); f.setBold(True); title_lbl.setFont(f)
    title_lbl.setStyleSheet(f"color:{C_ACCENT};")
    sv.addWidget(title_lbl)
    status_lbl = QLabel("키움증권 로그인 창을 확인하세요...")
    status_lbl.setAlignment(Qt.AlignCenter)
    status_lbl.setStyleSheet(f"color:{C_TEXT};")
    sv.addWidget(status_lbl)
    prog = QProgressBar()
    prog.setRange(0, 0)
    prog.setStyleSheet(f"QProgressBar::chunk{{background:{C_ACCENT};}}")
    sv.addWidget(prog)
    # 화면 중앙 배치
    screen = app.primaryScreen().geometry()
    splash.move(
        (screen.width() - splash.width()) // 2,
        (screen.height() - splash.height()) // 2,
    )
    splash.show()
    app.processEvents()

    # ── 키움 API 초기화 및 로그인 ────────────────────────────────────────
    try:
        from core.kiwoom import KiwoomAPI
        from core.market_data import MarketDataAPI
        from gui.controller import TradingController

        status_lbl.setText("KiwoomAPI 초기화 중...")
        app.processEvents()

        kiwoom = KiwoomAPI()

        status_lbl.setText("로그인 중... (키움 로그인 창 확인)")
        app.processEvents()

        kiwoom.login()   # 키움 로그인 팝업 → 완료까지 블로킹

        status_lbl.setText("계좌 정보 조회 중...")
        app.processEvents()

        accounts = kiwoom.get_account_list()
        if not accounts:
            QMessageBox.critical(None, "오류", "계좌 정보를 가져올 수 없습니다.")
            sys.exit(1)
        logger.info("보유 계좌 목록: %s (ACCOUNT_NUMBER 설정=%r)", accounts, ACCOUNT_NUMBER)

        # ACCOUNT_NUMBER 설정 있으면 우선, 없으면 첫 번째 계좌
        account = ACCOUNT_NUMBER if ACCOUNT_NUMBER in accounts else accounts[0]
        logger.info("선택된 기본 계좌: %s", account)
        user_name = kiwoom.get_login_info("USER_NAME")
        server = kiwoom.get_login_info("GetServerGubun")
        is_simul = IS_SIMUL or (server == "1")  # 1=모의투자 서버

        status_lbl.setText(f"{user_name}님 로그인 완료. 잔고 조회 중...")
        app.processEvents()

        mdata = MarketDataAPI(kiwoom)
        ctrl = TradingController()
        ctrl.inject_kiwoom(kiwoom, mdata, account, is_simul)

        # ── 메인 윈도우 생성 ──────────────────────────────────────────────
        status_lbl.setText("화면 초기화 중...")
        app.processEvents()

        win = MainWindow(controller=ctrl, market_data_api=mdata)

        # 계좌 목록 헤더에 표시
        win.header.combo_account.clear()
        for acc in accounts:
            win.header.combo_account.addItem(acc)
        idx = accounts.index(account)
        win.header.combo_account.setCurrentIndex(idx)
        win.header.set_api_connected(True)
        win.header.lbl_simul.setText("[모의]" if is_simul else "[실거래]")

        # 계좌 전환 시 controller에 반영
        def _on_account_changed(i):
            if 0 <= i < len(accounts):
                ctrl._account = accounts[i]
                win._refresh_balance(force=True)
        win.header.combo_account.currentIndexChanged.connect(_on_account_changed)

        # 조건식 로드
        status_lbl.setText("조건검색식 로드 중...")
        app.processEvents()
        try:
            cond_map = kiwoom.load_condition_list()   # {idx: name}
            cond_names = list(cond_map.values())
            win.tab_condition.set_conditions(cond_names)
            win.sidebar.cond_active_list.clear()
            for name in cond_names:
                win.sidebar.cond_active_list.addItem(name)
            win._log(f"조건검색식 {len(cond_names)}개 로드 완료", 2)
        except Exception as e:
            win._log(f"조건검색식 로드 실패: {e}", 2)

        # 초기 잔고 조회
        win._refresh_balance()

        # 상태바 갱신
        mode_txt = "모의투자" if is_simul else "실거래"
        win.status_mode.setText(f"모드: {mode_txt}")
        win.status_api.setText(f"API: {user_name} 연결됨")

        splash.close()
        win.show()

    except Exception as e:
        splash.close()
        QMessageBox.critical(
            None, "연결 오류",
            f"키움 API 연결 실패:\n{e}\n\n"
            "키움증권 OpenAPI+가 설치되어 있고\n"
            "32비트 Python을 사용하는지 확인하세요."
        )
        sys.exit(1)

    sys.exit(app.exec_())


if __name__ == "__main__":
    run_standalone()
