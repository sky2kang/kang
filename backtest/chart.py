"""
백테스트 결과 차트 이미지 저장

matplotlib를 사용해 수익 곡선(equity curve)과 낙폭(drawdown) 차트를
PNG 파일로 저장한다.  headless 환경에서도 동작하도록 Agg 백엔드 사용.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.font_manager as fm  # noqa: E402
import numpy as np  # noqa: E402

# Windows 한글 폰트 (맑은 고딕), Linux fallback
_KR_FONTS = ["Malgun Gothic", "NanumGothic", "AppleGothic", "DejaVu Sans"]
_available = {f.name for f in fm.fontManager.ttflist}
for _fn in _KR_FONTS:
    if _fn in _available:
        plt.rcParams["font.family"] = _fn
        break
plt.rcParams["axes.unicode_minus"] = False


class BacktestChart:
    def __init__(self, result: dict):
        """
        result: BacktestEngine.run() 이 반환한 dict
        """
        self.result = result

    def plot(self, save_path: str) -> str:
        """
        2-패널 차트를 생성하고 save_path 에 PNG 로 저장.
        반환값: save_path (동일 경로)
        """
        r = self.result
        equity = np.array(r["equity_curve"], dtype=float)
        initial = float(r.get("initial_cash", equity[0] if len(equity) else 1))
        period = r.get("period", ("", ""))
        n = len(equity)
        xs = list(range(n))

        # 낙폭 계산
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max * 100  # percent

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(12, 7), gridspec_kw={"height_ratios": [3, 1]}
        )

        title = (
            f"{r.get('strategy', '')} / {r.get('code', '')}  "
            f"[{period[0]} ~ {period[1]}]  "
            f"수익률 {r.get('total_return', 0):.2%}  "
            f"MDD {r.get('mdd', 0):.2%}"
        )
        fig.suptitle(title, fontsize=11, y=0.98)

        # --- 상단: 수익 곡선 ---
        ax1.plot(xs, equity, color="#1565c0", linewidth=1.5, label="총자산")
        ax1.axhline(initial, color="#aaaaaa", linewidth=1, linestyle="--",
                    label=f"기준 {initial:,.0f}원")
        ax1.fill_between(xs, initial, equity,
                         where=(equity >= initial), alpha=0.15, color="#1565c0")
        ax1.fill_between(xs, initial, equity,
                         where=(equity < initial), alpha=0.15, color="#c62828")
        ax1.set_ylabel("총자산 (원)")
        ax1.legend(loc="upper left", fontsize=9)
        ax1.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: f"{v:,.0f}")
        )
        ax1.grid(axis="y", linestyle=":", alpha=0.5)

        # --- 하단: 낙폭 곡선 ---
        ax2.fill_between(xs, drawdown, 0, alpha=0.7, color="#c62828")
        ax2.plot(xs, drawdown, color="#c62828", linewidth=0.8)
        ax2.set_ylabel("낙폭 (%)")
        ax2.set_xlabel("거래일 (인덱스)")
        ax2.grid(axis="y", linestyle=":", alpha=0.5)

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return save_path
