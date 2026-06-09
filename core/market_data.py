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
        """
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", password)
        self.api.set_input_value("비밀번호입력매체구분", "00")
        self.api.set_input_value("조회구분", "2")
        self.api.comm_rq_data("예수금상세현황", "opw00001", 0, "2001")

        # 콜백에서 받은 실제 record_name 을 우선 사용, 없으면 후보 목록 순차 시도
        rec = self.api.tr_data.get("record_name") or "예수금상세현황"
        logger.info("opw00001 get_comm_data record_name=%r", rec)

        def _get(field):
            for r in (rec, "예수금상세현황", ""):
                v = self.api.get_comm_data("opw00001", r, 0, field).replace(",", "")
                if v:
                    return v
            return ""

        deposit = _get("예수금")
        available = _get("출금가능금액")
        ordable = _get("주문가능금액")
        logger.info("opw00001 raw: 예수금=%r 출금가능=%r 주문가능=%r", deposit, available, ordable)

        def _to_int(s):
            s = (s or "").lstrip("0") or "0"
            try:
                return int(s)
            except ValueError:
                return 0

        avail_val = _to_int(ordable) or _to_int(available)
        return {"deposit": _to_int(deposit), "available": avail_val}

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
        self.api.comm_rq_data("계좌잔고조회", "opw00018", 0, "2000")

        total_eval = self.api.get_comm_data("opw00018", "계좌잔고조회", 0, "총평가금액").replace(",", "")
        total_profit = self.api.get_comm_data("opw00018", "계좌잔고조회", 0, "총수익률(%)").replace(",", "")
        available = self.api.get_comm_data("opw00018", "계좌잔고조회", 0, "주문가능금액").replace(",", "")

        summary = {
            "total_eval": int(total_eval) if total_eval else 0,
            "total_profit_rate": float(total_profit) if total_profit else 0.0,
            "available": int(available) if available else 0,
        }

        cnt = self.api.get_repeat_cnt("opw00018", "계좌잔고조회")
        holdings = []
        for i in range(cnt):
            name = self.api.get_comm_data("opw00018", "계좌잔고조회", i, "종목명")
            code = self.api.get_comm_data("opw00018", "계좌잔고조회", i, "종목번호").replace("A", "")
            qty = self.api.get_comm_data("opw00018", "계좌잔고조회", i, "보유수량").replace(",", "")
            avg_price = self.api.get_comm_data("opw00018", "계좌잔고조회", i, "매입단가").replace(",", "")
            profit_rate = self.api.get_comm_data("opw00018", "계좌잔고조회", i, "수익률(%)").replace(",", "")
            holdings.append({
                "name": name.strip(),
                "code": code.strip(),
                "qty": int(qty) if qty else 0,
                "avg_price": int(avg_price) if avg_price else 0,
                "profit_rate": float(profit_rate) if profit_rate else 0.0,
            })

        return {"summary": summary, "holdings": pd.DataFrame(holdings)}
