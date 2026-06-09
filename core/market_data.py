"""
시세 및 계좌 데이터 조회 모듈
"""
import pandas as pd
from utils.logger import get_logger

try:
    from config.settings import ACCOUNT_PASSWORD
except Exception:
    ACCOUNT_PASSWORD = "0000"

logger = get_logger(__name__)

# 주요 FID 상수
FID_CURRENT_PRICE = 10    # 현재가
FID_VOLUME = 15           # 거래량
FID_CHANGE_RATE = 12      # 등락률
FID_HIGH = 17             # 고가
FID_LOW = 18              # 저가
FID_OPEN = 16             # 시가


class MarketDataAPI:
    def __init__(self, kiwoom):
        self.api = kiwoom

    # -------------------------------------------------------------------------
    # 현재가 조회 (opt10001 - 주식기본정보)
    # -------------------------------------------------------------------------
    def get_stock_info(self, code):
        """종목 현재가 및 기본 정보 조회"""
        self.api.set_input_value("종목코드", code)
        self.api.comm_rq_data("주식기본정보", "opt10001", 0, "1000")

        raw_price = self.api.get_comm_data("opt10001", "주식기본정보", 0, "현재가")
        price = int(raw_price.replace("-", "").replace("+", ""))
        volume = int(self.api.get_comm_data("opt10001", "주식기본정보", 0, "거래량").replace(",", ""))
        change_rate = float(self.api.get_comm_data("opt10001", "주식기본정보", 0, "등락율").replace("%", ""))

        return {
            "code": code,
            "price": price,
            "volume": volume,
            "change_rate": change_rate,
        }

    # -------------------------------------------------------------------------
    # 일봉 데이터 조회 (opt10081)
    # -------------------------------------------------------------------------
    def get_daily_ohlcv(self, code, start_date, end_date=None, adj_price=1):
        """
        일봉 OHLCV 데이터 조회
        start_date: 'YYYYMMDD'
        반환: DataFrame(date, open, high, low, close, volume)
        """
        if end_date is None:
            import datetime
            end_date = datetime.datetime.now().strftime("%Y%m%d")

        self.api.set_input_value("종목코드", code)
        self.api.set_input_value("기준일자", end_date)
        self.api.set_input_value("수정주가구분", str(adj_price))

        rows = []
        prev_next = 0

        while True:
            self.api.comm_rq_data("주식일봉차트조회", "opt10081", prev_next, "1001")
            cnt = self.api.get_repeat_cnt("opt10081", "주식일봉차트조회")

            for i in range(cnt):
                date = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "일자")
                open_p = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "시가")
                high = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "고가")
                low = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "저가")
                close = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "현재가")
                volume = self.api.get_comm_data("opt10081", "주식일봉차트조회", i, "거래량")

                rows.append({
                    "date": date.strip(),
                    "open": abs(int(open_p)),
                    "high": abs(int(high)),
                    "low": abs(int(low)),
                    "close": abs(int(close)),
                    "volume": abs(int(volume)),
                })

            prev_next = self.api.tr_data.get("prev_next", "0")
            if prev_next != "2" or (rows and rows[-1]["date"] <= start_date):
                break

        df = pd.DataFrame(rows)
        df = df[df["date"] >= start_date].reset_index(drop=True)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    # -------------------------------------------------------------------------
    # 분봉 데이터 조회 (opt10080)
    # -------------------------------------------------------------------------
    def get_minute_ohlcv(self, code, tick_scope=1):
        """분봉 데이터 조회 (tick_scope: 1/3/5/10/15/30/45/60분)"""
        self.api.set_input_value("종목코드", code)
        self.api.set_input_value("틱범위", str(tick_scope))
        self.api.set_input_value("수정주가구분", "1")
        self.api.comm_rq_data("주식분봉차트조회", "opt10080", 0, "1002")

        cnt = self.api.get_repeat_cnt("opt10080", "주식분봉차트조회")
        rows = []
        for i in range(cnt):
            dt = self.api.get_comm_data("opt10080", "주식분봉차트조회", i, "체결시간")
            close = self.api.get_comm_data("opt10080", "주식분봉차트조회", i, "현재가")
            volume = self.api.get_comm_data("opt10080", "주식분봉차트조회", i, "거래량")
            rows.append({"datetime": dt.strip(), "close": abs(int(close)),
                         "volume": abs(int(volume))})

        df = pd.DataFrame(rows)
        df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d%H%M%S")
        return df.sort_values("datetime").reset_index(drop=True)

    # -------------------------------------------------------------------------
    # 예수금 상세 조회 (opw00001) - 보유종목이 없어도 예수금/주문가능금액 반환
    # -------------------------------------------------------------------------
    def get_deposit(self, account, password=ACCOUNT_PASSWORD):
        """
        예수금상세현황요청. 보유종목 유무와 무관하게 예수금/주문가능금액 반환.
        반환: {deposit: int, available: int}
        데이터는 OnReceiveTrData 콜백 안에서 읽어야 안정적이므로 single_fields 로 전달.
        """
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", password)
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "2")
        self.api.comm_rq_data(
            "예수금상세현황", "opw00001", 0, "2001",
            single_fields=["예수금", "출금가능금액", "주문가능금액"],
        )

        single = self.api.tr_data.get("single", {})
        logger.info("opw00001 single=%s", single)

        def _to_int(s):
            s = (s or "").replace(",", "").lstrip("0") or "0"
            try:
                return int(s)
            except ValueError:
                return 0

        deposit = _to_int(single.get("예수금"))
        ordable = _to_int(single.get("주문가능금액"))
        available = _to_int(single.get("출금가능금액"))
        avail_val = ordable or available
        return {"deposit": deposit, "available": avail_val}

    # -------------------------------------------------------------------------
    # 계좌 잔고 조회 (opw00018)
    # -------------------------------------------------------------------------
    def get_account_balance(self, account, password=ACCOUNT_PASSWORD, is_simul=True):
        """
        계좌 잔고 조회
        반환: {summary: dict, holdings: DataFrame}
        """
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", password)
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "2")
        self.api.comm_rq_data(
            "계좌잔고조회", "opw00018", 0, "2000",
            single_fields=["총평가금액", "총수익률(%)", "주문가능금액"],
            multi_fields=["종목명", "종목번호", "보유수량", "매입단가", "수익률(%)"],
        )

        single = self.api.tr_data.get("single", {})
        multi = self.api.tr_data.get("multi", [])

        def _num(s):
            return (s or "").replace(",", "").strip()

        total_eval = _num(single.get("총평가금액"))
        total_profit = _num(single.get("총수익률(%)"))
        available = _num(single.get("주문가능금액"))

        summary = {
            "total_eval": int(total_eval) if total_eval else 0,
            "total_profit_rate": float(total_profit) if total_profit else 0.0,
            "available": int(available) if available else 0,
        }

        holdings = []
        for row in multi:
            qty = _num(row.get("보유수량"))
            avg_price = _num(row.get("매입단가"))
            profit_rate = _num(row.get("수익률(%)"))
            holdings.append({
                "name": (row.get("종목명") or "").strip(),
                "code": (row.get("종목번호") or "").replace("A", "").strip(),
                "qty": int(qty) if qty else 0,
                "avg_price": int(avg_price) if avg_price else 0,
                "profit_rate": float(profit_rate) if profit_rate else 0.0,
            })

        return {"summary": summary, "holdings": pd.DataFrame(holdings)}
