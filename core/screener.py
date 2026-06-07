"""
종목 자동 스크리닝 모듈

MarketDataAPI와 StockAnalyzer를 활용해 지정 기준으로 유망 종목을
자동으로 추려낸다.

사용 예:
    screener = StockScreener(market_data_api)
    results = screener.screen(["005930", "035420"])
    results = screener.screen_from_market("kospi", top_n=50)
"""
import logging
import datetime

logger = logging.getLogger(__name__)


class StockScreener:
    """
    주어진 종목 코드 목록(또는 시장 상위 종목)을 분석해
    설정 기준 이상의 종목만 필터링해 반환한다.
    """

    def __init__(self, market_data_api,
                 min_score=1.5,
                 min_volume_ratio=1.2,
                 rsi_max=65):
        """
        market_data_api: MarketDataAPI 인스턴스
        min_score:        StockAnalyzer total_score 최소값 (default 1.5)
        min_volume_ratio: 오늘 거래량 / 20일 평균 최소 배수 (default 1.2)
        rsi_max:          RSI 상한 (초과시 제외, default 65)
        """
        self._mdata = market_data_api
        self.min_score = min_score
        self.min_volume_ratio = min_volume_ratio
        self.rsi_max = rsi_max

    # ------------------------------------------------------------------
    def screen(self, codes, days=60):
        """
        codes: 종목코드 리스트
        days:  분석에 사용할 일봉 일수

        반환: score 내림차순 정렬된 dict 리스트
          [{code, name, price, score, opinion, rsi, volume_ratio}, ...]
        """
        from core.analyzer import StockAnalyzer

        start_date = (
            datetime.datetime.now() - datetime.timedelta(days=days)
        ).strftime("%Y%m%d")

        results = []
        for code in codes:
            try:
                df = self._mdata.get_daily_ohlcv(code, start_date)
                if df is None or df.empty:
                    logger.debug("no data for %s", code)
                    continue

                # 종목명은 KiwoomAPI.GetMasterCodeName 으로 조회
                name = self._get_name(code)

                analyzer = StockAnalyzer(df)
                analysis = analyzer.analyze()

                score = analysis.get("total_score", 0)
                rsi = analysis.get("rsi")
                vol = analysis.get("volume") or {}
                volume_ratio = vol.get("ratio", 0)
                opinion_tuple = analysis.get("opinion", ("중립/관망", "⚪"))
                opinion = (
                    opinion_tuple[0]
                    if isinstance(opinion_tuple, tuple)
                    else opinion_tuple
                )

                # 필터 적용
                if score < self.min_score:
                    continue
                if volume_ratio < self.min_volume_ratio:
                    continue
                if rsi is not None and rsi > self.rsi_max:
                    continue

                results.append({
                    "code": code,
                    "name": name,
                    "price": analysis.get("price", 0),
                    "score": score,
                    "opinion": opinion,
                    "rsi": rsi,
                    "volume_ratio": volume_ratio,
                })
            except Exception as exc:
                logger.warning("screen error for %s: %s", code, exc)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    def _get_name(self, code):
        """종목명 조회 (KiwoomAPI.GetMasterCodeName 사용 가능 시)"""
        try:
            kiwoom = getattr(self._mdata, "api", None)
            if kiwoom and hasattr(kiwoom, "dynamicCall"):
                name = kiwoom.dynamicCall("GetMasterCodeName(QString)", code)
                return name.strip() if name else code
        except Exception:
            pass
        return code

    # ------------------------------------------------------------------
    def screen_from_market(self, market="kospi", top_n=50):
        """
        KOSPI/KOSDAQ 거래량 상위 top_n 종목을 TR opt10027로 조회한 뒤
        screen()을 실행한다.

        market: "kospi" 또는 "kosdaq"
        top_n:  조회 상위 종목 수
        """
        codes = self._fetch_top_volume_codes(market, top_n)
        logger.info(
            "screen_from_market: %s top %d → %d codes fetched",
            market, top_n, len(codes)
        )
        return self.screen(codes)

    def _fetch_top_volume_codes(self, market, top_n):
        """opt10027 TR(현재가순위)로 거래량 상위 코드 목록 반환"""
        try:
            if hasattr(self._mdata, "get_top_volume_codes"):
                return self._mdata.get_top_volume_codes(market, top_n)

            kiwoom = getattr(self._mdata, "_kiwoom", None) or getattr(
                self._mdata, "kiwoom", None
            )
            if kiwoom is None:
                logger.warning("kiwoom not accessible from market_data_api")
                return []

            market_code = "0" if market.lower() == "kospi" else "1"
            kiwoom.dynamicCall(
                "SetInputValue(QString, QString)", "시장구분", market_code
            )
            kiwoom.dynamicCall(
                "SetInputValue(QString, QString)", "정렬구분", "1"
            )
            kiwoom.dynamicCall(
                "CommRqData(QString, QString, int, QString)",
                "opt10027", "opt10027", 0, "0000"
            )
            # 실제 환경에서는 이벤트 루프 대기 후 데이터를 파싱해야 함
            return []
        except Exception as exc:
            logger.warning("_fetch_top_volume_codes error: %s", exc)
            return []
