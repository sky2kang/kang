"""
시세 및 계좌 데이터 조회 모듈
"""
import pandas as pd
from utils.logger import get_logger

logger = get_logger(__name__)

# 주요 FID 상수
FID_CURRENT_PRICE = 10    # 현재가
FID_VOLUME = 15           # 거래량
FID_CHANGE_RATE = 12      # 등락률
FID_HIGH = 17             # 고가
FID_LOW = 18              # 저가
FID_OPEN = 16             # 시가


def _safe_int(s, default=0):
    """빈 문자열/오류 시 default 반환하는 안전한 int 파싱."""
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return default


def _safe_float(s, default=0.0):
    """빈 문자열/오류 시 default 반환하는 안전한 float 파싱."""
    try:
        return float(str(s).strip())
    except (ValueError, TypeError):
        return default


class MarketDataAPI:
    def __init__(self, kiwoom):
        self.api = kiwoom

    # -------------------------------------------------------------------------
    # 현재가 조회 (opt10001 - 주식기본정보)
    # -------------------------------------------------------------------------
    def get_stock_info(self, code):
        """종목 현재가 및 기본 정보 조회.

        모의투자 서버는 일부 종목 시세를 빈 값('')으로 반환하므로,
        파싱 실패 시 예외를 던지지 않고 0/없음으로 처리한다.
        반환 dict 의 'available' 가 False 면 시세를 받지 못한 것이다.
        """
        self.api.set_input_value("종목코드", code)
        self.api.comm_rq_data("주식기본정보", "opt10001", 0, "1000")

        raw_price = self.api.get_comm_data("opt10001", "주식기본정보", 0, "현재가")
        raw_volume = self.api.get_comm_data("opt10001", "주식기본정보", 0, "거래량")
        raw_rate = self.api.get_comm_data("opt10001", "주식기본정보", 0, "등락율")

        price = _safe_int(raw_price.replace("-", "").replace("+", ""))
        volume = _safe_int(raw_volume.replace(",", ""))
        change_rate = _safe_float(raw_rate.replace("%", ""))

        return {
            "code": code,
            "price": price,
            "volume": volume,
            "change_rate": change_rate,
            "available": raw_price.strip() != "",
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

        # 최대 20페이지 안전장치 + TR 요청 실패 시 즉시 중단 (무한루프/과부하 방지)
        for _page in range(20):
            ret = self.api.comm_rq_data("주식일봉차트조회", "opt10081", int(prev_next), "1001")
            if ret != 0:
                logger.warning(f"[{code}] 일봉 TR 요청 실패(ret={ret}) - 과부하/타임아웃 가능. "
                               f"잠시 후 재시도하세요.")
                break
            cnt = self.api.get_repeat_cnt("opt10081", "주식일봉차트조회")
            if cnt == 0:
                logger.warning(f"[{code}] 일봉 데이터 0건 수신 (거래정지/신규상장 또는 잘못된 종목코드)")
                break

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

        if not rows:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

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
    # 계좌 잔고 조회 (opw00018)
    # -------------------------------------------------------------------------
    def get_account_balance(self, account, is_simul=True):
        """
        계좌 잔고 조회
        반환: {summary: dict, holdings: DataFrame}

        주의: 계좌 비밀번호는 SetInputValue로 전달해도 무시됩니다.
        키움 OpenAPI 트레이 아이콘 > '계좌비밀번호 저장'에서 AUTO 등록 필요.
        (미등록 시 조회 시 에러 코드 44 발생)
        """
        self.api.set_input_value("계좌번호", account)
        self.api.set_input_value("비밀번호", "")            # AOD에 등록된 비밀번호 사용
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
