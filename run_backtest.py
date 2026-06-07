"""
백테스트 실행 스크립트 - 전략을 과거 데이터로 검증

실거래/모의투자 투입 전에 전략 성과를 미리 확인한다.
키움 로그인 후 과거 일봉 데이터를 받아 백테스트하고,
MA 전략과 RSI 전략의 성과를 나란히 비교한다.

실행:
  python run_backtest.py 005930              # 삼성전자, 최근 1년
  python run_backtest.py 005930 --days 500   # 기간 지정
"""
import sys
import argparse
import datetime
import os

from PyQt5.QtWidgets import QApplication

from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from backtest.engine import BacktestEngine
from backtest.chart import BacktestChart
from strategy.ma_strategy import MAStrategy
from strategy.rsi_strategy import RSIStrategy


def main():
    parser = argparse.ArgumentParser(description="전략 백테스트")
    parser.add_argument("code", help="종목코드 (예: 005930)")
    parser.add_argument("--days", type=int, default=365, help="백테스트 기간(일)")
    parser.add_argument("--cash", type=int, default=10_000_000, help="시작 자금")
    args = parser.parse_args()

    app = QApplication(sys.argv)  # noqa: F841
    kiwoom = KiwoomAPI()
    kiwoom.login()
    mdata = MarketDataAPI(kiwoom)

    start = (datetime.datetime.now()
             - datetime.timedelta(days=args.days)).strftime("%Y%m%d")
    df = mdata.get_daily_ohlcv(args.code, start)
    name = kiwoom.dynamicCall("GetMasterCodeName(QString)", args.code).strip()
    print(f"\n{name}({args.code}) 데이터 {len(df)}일 수집 완료\n")

    today = datetime.datetime.now().strftime("%Y%m%d")
    chart_dir = os.path.join("backtest", "charts")
    os.makedirs(chart_dir, exist_ok=True)

    strategies = [MAStrategy(5, 20), RSIStrategy()]
    results = []
    for strat in strategies:
        engine = BacktestEngine(strat, initial_cash=args.cash)
        result = engine.run(df, args.code)
        results.append(result)
        print(BacktestEngine.report_text(result))
        print()

        strat_slug = result.get("strategy", "unknown").replace("/", "-").replace(" ", "_")
        chart_path = os.path.join(
            chart_dir, f"{args.code}_{strat_slug}_{today}.png"
        )
        saved = BacktestChart(result).plot(chart_path)
        print(f"차트 저장: {saved}")
        print()

    # 비교 요약
    print("=" * 40)
    print("  전략 비교")
    print("=" * 40)
    for r in results:
        print(f"{r['strategy']:12s} | 수익률 {r['total_return']:+.2%} | "
              f"승률 {r['win_rate']:.0%} | MDD {r['mdd']:.1%}")
    best = max(results, key=lambda r: r["total_return"])
    print(f"\n🏆 추천 전략: {best['strategy']} "
          f"(수익률 {best['total_return']:+.2%})")


if __name__ == "__main__":
    main()
