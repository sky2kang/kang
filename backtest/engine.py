"""
백테스팅 엔진 - 전략을 과거 데이터로 검증

실전 투입 전에 "내 전략이 과거에 얼마나 벌었을까"를 시뮬레이션한다.
일봉 데이터와 전략(BaseStrategy)을 받아 매수/매도를 모의 실행하고
수익률, 승률, 최대낙폭(MDD) 등 성과 지표를 산출한다.
"""
import numpy as np


class BacktestEngine:
    def __init__(self, strategy, initial_cash=10_000_000,
                 buy_amount=1_000_000, fee_rate=0.00015, tax_rate=0.0018):
        """
        strategy:     BaseStrategy 인스턴스
        initial_cash: 시작 자금
        buy_amount:   1회 매수 금액
        fee_rate:     거래 수수료율 (매수/매도 각각, 키움 약 0.015%)
        tax_rate:     증권거래세 (매도 시, 약 0.18%)
        """
        self.strategy = strategy
        self.initial_cash = initial_cash
        self.buy_amount = buy_amount
        self.fee_rate = fee_rate
        self.tax_rate = tax_rate

    def run(self, df, code="TEST"):
        """
        df: 일봉 데이터 (date, open, high, low, close, volume), 과거→최신 정렬
        반환: 성과 리포트 dict
        """
        cash = self.initial_cash
        position = None        # {"qty", "buy_price", "buy_date"}
        trades = []            # 청산된 매매 기록
        equity_curve = []      # 일별 총자산 추이

        min_bars = 60          # 지표 계산용 최소 봉 수
        for i in range(len(df)):
            window = df.iloc[:i + 1]
            row = df.iloc[i]
            price = row["close"]
            date = row["date"] if "date" in row.index else str(row.name)[:10]

            if i < min_bars:
                equity_curve.append(cash)
                continue

            # 보유 중이면 매도 판단
            if position:
                if self.strategy.should_sell(window, code,
                                             position["buy_price"], price):
                    proceeds = position["qty"] * price
                    proceeds -= proceeds * (self.fee_rate + self.tax_rate)
                    cost = position["qty"] * position["buy_price"]
                    cost += cost * self.fee_rate
                    profit = proceeds - cost
                    cash += proceeds
                    trades.append({
                        "code": code,
                        "buy_date": position["buy_date"],
                        "sell_date": date,
                        "buy_price": position["buy_price"],
                        "sell_price": price,
                        "qty": position["qty"],
                        "profit": profit,
                        "return_rate": profit / cost,
                    })
                    position = None
            # 미보유면 매수 판단
            elif self.strategy.should_buy(window, code):
                qty = int(self.buy_amount // price)
                if qty >= 1 and cash >= qty * price:
                    cost = qty * price
                    cash -= cost
                    position = {
                        "qty": qty,
                        "buy_price": price,
                        "buy_date": date,
                    }

            # 일별 평가자산 = 현금 + 보유주식 평가액
            holding_value = position["qty"] * price if position else 0
            equity_curve.append(cash + holding_value)

        # 마지막 보유분 강제 청산 (평가)
        if position:
            price = df.iloc[-1]["close"]
            proceeds = position["qty"] * price
            cash += proceeds

        return self._build_report(trades, equity_curve, df, code)

    def _build_report(self, trades, equity_curve, df, code):
        equity = np.array(equity_curve)
        final_equity = equity[-1] if len(equity) else self.initial_cash
        total_return = (final_equity - self.initial_cash) / self.initial_cash

        wins = [t for t in trades if t["profit"] > 0]
        losses = [t for t in trades if t["profit"] <= 0]
        win_rate = len(wins) / len(trades) if trades else 0

        # 최대낙폭 (MDD)
        if len(equity):
            running_max = np.maximum.accumulate(equity)
            drawdown = (equity - running_max) / running_max
            mdd = drawdown.min()
        else:
            mdd = 0

        avg_win = np.mean([t["return_rate"] for t in wins]) if wins else 0
        avg_loss = np.mean([t["return_rate"] for t in losses]) if losses else 0

        return {
            "code": code,
            "strategy": self.strategy.name,
            "period": (
                str(df.iloc[0]["date"] if "date" in df.columns else df.index[0])[:10] if len(df) else "N/A",
                str(df.iloc[-1]["date"] if "date" in df.columns else df.index[-1])[:10] if len(df) else "N/A",
            ),
            "initial_cash": self.initial_cash,
            "final_equity": int(final_equity),
            "total_return": round(total_return, 4),
            "trade_count": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(win_rate, 4),
            "avg_win_return": round(avg_win, 4),
            "avg_loss_return": round(avg_loss, 4),
            "mdd": round(float(mdd), 4),
            "trades": trades,
            "equity_curve": equity.tolist(),
        }

    @staticmethod
    def report_text(result):
        """백테스트 결과를 사람이 읽는 텍스트로"""
        r = result
        lines = [
            f"═══ 백테스트 결과: {r['strategy']} / {r['code']} ═══",
            f"기간: {r['period'][0]} ~ {r['period'][1]}",
            f"시작자금: {r['initial_cash']:,}원",
            f"최종자산: {r['final_equity']:,}원",
            f"총수익률: {r['total_return']:.2%}",
            "",
            f"총 매매: {r['trade_count']}회 "
            f"(승 {r['win_count']} / 패 {r['loss_count']})",
            f"승률: {r['win_rate']:.1%}",
            f"평균수익(이긴거래): {r['avg_win_return']:.2%}",
            f"평균손실(진거래): {r['avg_loss_return']:.2%}",
            f"최대낙폭(MDD): {r['mdd']:.2%}",
        ]
        return "\n".join(lines)
