"""
종목 자동 스크리닝 CLI 진입점

실행 예:
  python run_screener.py                          # KOSPI 상위 50개 스크리닝
  python run_screener.py --codes 005930,035420    # 지정 종목 스크리닝
  python run_screener.py --top 100                # 상위 100개 스크리닝
  python run_screener.py --market kosdaq --top 50 # KOSDAQ 상위 50개
"""
import sys
import argparse
import csv
import datetime
import os

from PyQt5.QtWidgets import QApplication

from core.kiwoom import KiwoomAPI
from core.market_data import MarketDataAPI
from core.screener import StockScreener


def print_table(results):
    """스크리닝 결과를 터미널 표로 출력"""
    if not results:
        print("조건에 맞는 종목이 없습니다.")
        return

    header = f"{'순위':>4}  {'코드':>8}  {'종목명':<12}  {'현재가':>10}  "
    header += f"{'점수':>6}  {'의견':<10}  {'RSI':>6}  {'거래량배수':>9}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for i, r in enumerate(results, 1):
        rsi_str = f"{r['rsi']:.1f}" if r["rsi"] is not None else "N/A"
        print(
            f"{i:>4}  {r['code']:>8}  {r['name']:<12}  "
            f"{r['price']:>10,}  {r['score']:>6.1f}  "
            f"{r['opinion']:<10}  {rsi_str:>6}  "
            f"{r['volume_ratio']:>9.2f}"
        )
    print(sep)
    print(f"총 {len(results)}개 종목 선별")


def save_csv(results, path):
    """결과를 CSV 파일로 저장"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    fieldnames = ["code", "name", "price", "score", "opinion", "rsi", "volume_ratio"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n결과 저장: {path}")


def main():
    parser = argparse.ArgumentParser(description="종목 자동 스크리닝")
    parser.add_argument(
        "--codes", type=str, default="",
        help="종목코드 콤마 구분 (예: 005930,035420)"
    )
    parser.add_argument(
        "--top", type=int, default=50,
        help="시장 상위 N개 종목 (기본 50)"
    )
    parser.add_argument(
        "--market", type=str, default="kospi",
        choices=["kospi", "kosdaq"],
        help="시장 선택 (kospi/kosdaq)"
    )
    parser.add_argument(
        "--days", type=int, default=60,
        help="분석 기간(일, 기본 60)"
    )
    parser.add_argument(
        "--min-score", type=float, default=1.5,
        help="최소 점수 (기본 1.5)"
    )
    parser.add_argument(
        "--min-volume", type=float, default=1.2,
        help="최소 거래량 배수 (기본 1.2)"
    )
    parser.add_argument(
        "--rsi-max", type=float, default=65,
        help="RSI 최대값 (기본 65)"
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)  # noqa: F841
    kiwoom = KiwoomAPI()
    kiwoom.login()
    mdata = MarketDataAPI(kiwoom)

    screener = StockScreener(
        mdata,
        min_score=args.min_score,
        min_volume_ratio=args.min_volume,
        rsi_max=args.rsi_max,
    )

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        print(f"\n지정 종목 {len(codes)}개 스크리닝 중...\n")
        results = screener.screen(codes, days=args.days)
    else:
        print(f"\n{args.market.upper()} 거래량 상위 {args.top}개 스크리닝 중...\n")
        results = screener.screen_from_market(args.market, top_n=args.top)

    print_table(results)

    today = datetime.datetime.now().strftime("%Y%m%d")
    csv_path = os.path.join("data", f"screener_{today}.csv")
    save_csv(results, csv_path)


if __name__ == "__main__":
    main()
