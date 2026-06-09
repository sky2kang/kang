"""
백테스트 결과 차트

matplotlib를 사용해 수익 곡선(equity curve)과 낙폭(drawdown),
주가 차트 위 매수/매도 마커를 표시한다.

BacktestChart       : PNG 파일 저장용 (Agg 백엔드, headless 가능)
BacktestChartWidget : PyQt5 위젯에 임베드 (Qt5Agg 백엔드)
"""
import os
import numpy as np

# ── PNG 저장용 (Agg) ─────────────────────────────────────────────────────────
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

_KR_FONTS = ["Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]
_available = {f.name for f in fm.fontManager.ttflist}
for _fn in _KR_FONTS:
    if _fn in _available:
        plt.rcParams["font.family"] = _fn
        break
plt.rcParams["axes.unicode_minus"] = False


def _apply_kr_font(fig_or_ax=None):
    import matplotlib
    for fn in _KR_FONTS:
        if fn in _available:
            matplotlib.rcParams["font.family"] = fn
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


class BacktestChart:
    def __init__(self, result: dict):
        self.result = result

    def plot(self, save_path: str) -> str:
        """2-패널 차트를 생성하고 save_path 에 PNG 로 저장."""
        _apply_kr_font()
        fig = _build_figure(self.result, figsize=(12, 7))
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return save_path


# ── Qt5 위젯 임베드용 ────────────────────────────────────────────────────────
class BacktestChartWidget:
    """
    PyQt5 QWidget 안에 matplotlib 차트를 임베드한다.

    사용:
        widget = BacktestChartWidget()
        layout.addWidget(widget.canvas)   # or widget.widget
        widget.update_chart(result, df)   # 차트 갱신
    """
    def __init__(self):
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        _apply_kr_font()
        self._fig = Figure(figsize=(10, 6))
        self._fig.patch.set_facecolor("#161b22")
        self.canvas = FigureCanvasQTAgg(self._fig)
        self.canvas.setMinimumHeight(280)
        self._draw_placeholder()

    def _draw_placeholder(self):
        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_facecolor("#1c2128")
        ax.text(0.5, 0.5, "백테스트를 실행하면 차트가 표시됩니다",
                ha="center", va="center", color="#8b949e", fontsize=12,
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color("#30363d")
        self.canvas.draw()

    def update_chart(self, result: dict, df=None):
        """
        result : BacktestEngine.run() 반환 dict
        df     : get_daily_ohlcv() 반환 DataFrame (close/date 포함, optional)
        """
        _apply_kr_font()
        self._fig.clear()
        _draw_on_figure(self._fig, result, df)
        self.canvas.draw()


# ── 공유 드로잉 로직 ─────────────────────────────────────────────────────────
def _build_figure(result, figsize=(12, 7)):
    """Agg 백엔드용 Figure 생성 (PNG 저장)."""
    fig = plt.figure(figsize=figsize)
    _draw_on_figure(fig, result, df=None)
    return fig


def _draw_on_figure(fig, result: dict, df=None):
    """
    fig 안에 차트를 그린다.
    df 가 주어지면 3-패널(주가+마커 / 자산곡선 / 낙폭),
    아니면 2-패널(자산곡선 / 낙폭).
    """
    _apply_kr_font()
    fig.patch.set_facecolor("#161b22")

    trades = result.get("trades", [])
    equity = np.array(result.get("equity_curve", []), dtype=float)
    initial = float(result.get("initial_cash", equity[0] if len(equity) else 1))
    period = result.get("period", ("", ""))
    title = (
        f"{result.get('strategy', '')} / {result.get('code', '')}  "
        f"[{period[0]} ~ {period[1]}]  "
        f"수익률 {result.get('total_return', 0):.2%}  "
        f"MDD {result.get('mdd', 0):.2%}"
    )

    ax_price = ax_equity = ax_dd = None
    dark_ax_kwargs = dict(facecolor="#1c2128")

    if df is not None and len(df) > 0:
        gs = fig.add_gridspec(3, 1, height_ratios=[3, 2, 1],
                               hspace=0.08, left=0.08, right=0.97,
                               top=0.93, bottom=0.06)
        ax_price = fig.add_subplot(gs[0])
        ax_equity = fig.add_subplot(gs[1], sharex=ax_price)
        ax_dd = fig.add_subplot(gs[2], sharex=ax_price)
        _draw_price_panel(ax_price, df, trades, dark_ax_kwargs)
        _draw_equity_panel(ax_equity, equity, initial, dark_ax_kwargs)
        _draw_dd_panel(ax_dd, equity, dark_ax_kwargs)
        plt.setp(ax_price.get_xticklabels(), visible=False)
        plt.setp(ax_equity.get_xticklabels(), visible=False)
    else:
        n = len(equity)
        xs = list(range(n))
        gs = fig.add_gridspec(2, 1, height_ratios=[3, 1],
                               hspace=0.08, left=0.08, right=0.97,
                               top=0.93, bottom=0.06)
        ax_equity = fig.add_subplot(gs[0])
        ax_dd = fig.add_subplot(gs[1], sharex=ax_equity)
        _draw_equity_panel(ax_equity, equity, initial, dark_ax_kwargs,
                           trades=trades, xs=xs)
        _draw_dd_panel(ax_dd, equity, dark_ax_kwargs, xs=xs)
        plt.setp(ax_equity.get_xticklabels(), visible=False)

    fig.suptitle(title, color="#e6edf3", fontsize=10, y=0.98)


def _style_ax(ax, kwargs):
    ax.set_facecolor(kwargs["facecolor"])
    ax.tick_params(colors="#8b949e", labelsize=8)
    ax.yaxis.label.set_color("#8b949e")
    ax.xaxis.label.set_color("#8b949e")
    for sp in ax.spines.values():
        sp.set_color("#30363d")
    ax.grid(axis="y", linestyle=":", alpha=0.4, color="#30363d")


def _draw_price_panel(ax, df, trades, dark_ax_kwargs):
    """주가(종가) + 매수▲ / 매도▽ 마커."""
    _style_ax(ax, dark_ax_kwargs)

    # 날짜 컬럼 처리
    if "date" in df.columns:
        dates = [str(d)[:10] for d in df["date"]]
    else:
        dates = [str(i)[:10] for i in df.index]

    closes = df["close"].astype(float).values
    xs = list(range(len(closes)))

    ax.plot(xs, closes, color="#58a6ff", linewidth=1.2, label="종가")

    # 매수/매도 마커
    date_to_x = {d: i for i, d in enumerate(dates)}
    buy_xs, buy_ys, sell_xs, sell_ys = [], [], [], []
    for t in trades:
        bx = date_to_x.get(str(t.get("buy_date", ""))[:10])
        sx = date_to_x.get(str(t.get("sell_date", ""))[:10])
        if bx is not None:
            buy_xs.append(bx); buy_ys.append(closes[bx])
        if sx is not None:
            sell_xs.append(sx); sell_ys.append(closes[sx])

    if buy_xs:
        ax.scatter(buy_xs, buy_ys, marker="^", color="#3fb950", s=70,
                   zorder=5, label=f"매수 {len(buy_xs)}회")
    if sell_xs:
        ax.scatter(sell_xs, sell_ys, marker="v", color="#f85149", s=70,
                   zorder=5, label=f"매도 {len(sell_xs)}회")

    ax.set_ylabel("주가 (원)")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    )
    leg = ax.legend(loc="upper left", fontsize=8,
                    facecolor="#1c2128", edgecolor="#30363d",
                    labelcolor="#e6edf3")


def _draw_equity_panel(ax, equity, initial, dark_ax_kwargs,
                       trades=None, xs=None):
    """자산 곡선 + 매수/매도 마커 (df 없을 때)."""
    _style_ax(ax, dark_ax_kwargs)
    if xs is None:
        xs = list(range(len(equity)))

    ax.plot(xs, equity, color="#1565c0", linewidth=1.3, label="총자산")
    ax.axhline(initial, color="#8b949e", linewidth=0.8, linestyle="--",
               label=f"기준 {initial:,.0f}원")
    ax.fill_between(xs, initial, equity,
                    where=(equity >= initial), alpha=0.12, color="#3fb950")
    ax.fill_between(xs, initial, equity,
                    where=(equity < initial), alpha=0.12, color="#f85149")

    # trades가 있으면 인덱스 기반 마커
    if trades:
        # equity_curve 인덱스와 날짜를 매핑할 수 없으므로 생략 (df 있을 때 처리)
        pass

    ax.set_ylabel("총자산 (원)")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    )
    ax.legend(loc="upper left", fontsize=8,
              facecolor="#1c2128", edgecolor="#30363d",
              labelcolor="#e6edf3")


def _draw_dd_panel(ax, equity, dark_ax_kwargs, xs=None):
    """낙폭(MDD) 패널."""
    _style_ax(ax, dark_ax_kwargs)
    if xs is None:
        xs = list(range(len(equity)))
    if len(equity) == 0:
        return
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / running_max * 100
    ax.fill_between(xs, dd, 0, alpha=0.6, color="#f85149")
    ax.plot(xs, dd, color="#f85149", linewidth=0.7)
    ax.set_ylabel("낙폭 (%)")
    ax.set_xlabel("거래일 (인덱스)")


# matplotlib ticker import for formatters
import matplotlib.ticker
