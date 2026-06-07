"""
조건식 시뮬레이션 (과거 데이터 백테스트).

키움 OpenAPI는 조건식의 과거 '편입 시점'을 제공하지 않는다. 따라서 여기서는
"현재 조건식에 편입된 종목을 기간 시작일에 매수했다고 가정"하고, 사용자가
설정한 청산 룰(손절 / 익절 / 트레일링 스탑)을 일봉 데이터로 시뮬레이션한다.

순수 함수로만 구성되어 키움 연결 없이 단위 테스트가 가능하다.
"""
from utils.logger import get_logger

logger = get_logger(__name__)


def simulate_exit_rules(df, stop_pct=None, take_pct=None, trail_pct=0.0,
                        entry_idx=0, fee_rate=0.00015, tax_rate=0.0018):
    """단일 종목 청산 룰 시뮬레이션.

    df: 일봉 DataFrame (오름차순, 컬럼 date/open/high/low/close/volume)
    stop_pct:  손절 기준 % (예: -5.0). None 이면 미적용
    take_pct:  익절 기준 % (예: 10.0). None 이면 미적용
    trail_pct: 트레일링 스탑 % (예: 5.0). 0 이면 미적용
    entry_idx: 매수 시점 인덱스 (기본 0 = 기간 시작일 종가 매수)
    fee_rate:  편도 수수료율, tax_rate: 매도세율

    반환 dict: entry_date/entry_price/exit_date/exit_price/days/return_pct/reason
    """
    n = len(df)
    if n == 0 or entry_idx >= n:
        return None

    entry_price = float(df["close"].iloc[entry_idx])
    if entry_price <= 0:
        return None

    entry_date = df["date"].iloc[entry_idx]
    peak = entry_price
    exit_price = float(df["close"].iloc[-1])
    exit_date = df["date"].iloc[-1]
    reason = "기간종료"

    stop_price = entry_price * (1 + stop_pct / 100.0) if stop_pct is not None else None
    take_price = entry_price * (1 + take_pct / 100.0) if take_pct is not None else None

    for i in range(entry_idx + 1, n):
        hi = float(df["high"].iloc[i])
        lo = float(df["low"].iloc[i])
        cl = float(df["close"].iloc[i])
        peak = max(peak, hi)

        # 1) 손절 (장중 저가가 손절가 터치) — 가장 보수적으로 먼저 판정
        if stop_price is not None and lo <= stop_price:
            exit_price, exit_date, reason = stop_price, df["date"].iloc[i], "손절"
            break
        # 2) 트레일링 스탑 (수익 구간 진입 후 고점 대비 trail% 하락)
        if trail_pct and trail_pct > 0 and peak > entry_price:
            trail_price = peak * (1 - trail_pct / 100.0)
            if lo <= trail_price:
                exit_price, exit_date, reason = trail_price, df["date"].iloc[i], "트레일링"
                break
        # 3) 익절 (장중 고가가 익절가 터치)
        if take_price is not None and hi >= take_price:
            exit_price, exit_date, reason = take_price, df["date"].iloc[i], "익절"
            break
        exit_price, exit_date = cl, df["date"].iloc[i]

    # 수수료/세금 반영 수익률
    buy_cost = entry_price * (1 + fee_rate)
    sell_net = exit_price * (1 - fee_rate - tax_rate)
    return_pct = (sell_net - buy_cost) / buy_cost * 100.0

    days = _days_between(entry_date, exit_date)
    return {
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "days": days,
        "return_pct": return_pct,
        "reason": reason,
    }


def summarize(results):
    """종목별 결과 리스트 → 집계 통계."""
    valid = [r for r in results if r]
    if not valid:
        return {"count": 0, "avg_return": 0.0, "win_rate": 0.0,
                "best": None, "worst": None, "by_reason": {}}
    returns = [r["return_pct"] for r in valid]
    wins = [x for x in returns if x > 0]
    by_reason = {}
    for r in valid:
        by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
    return {
        "count": len(valid),
        "avg_return": sum(returns) / len(returns),
        "win_rate": len(wins) / len(returns) * 100.0,
        "total_return": sum(returns),
        "best": max(returns),
        "worst": min(returns),
        "avg_days": sum(r["days"] for r in valid) / len(valid),
        "by_reason": by_reason,
    }


def _days_between(d1, d2):
    """두 날짜(datetime/Timestamp/str) 사이 일수."""
    try:
        return abs((d2 - d1).days)
    except (TypeError, AttributeError):
        return 0
