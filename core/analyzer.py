"""
개별 종목 상세 분석 모듈

일봉 OHLCV 데이터를 받아 주요 기술적 지표를 계산하고,
초보자도 이해할 수 있는 종합 의견(매수/중립/매도)을 제시한다.

- 이동평균선 (5/20/60일)
- RSI (14)
- MACD (12/26/9)
- 볼린저밴드 (20, 2σ)
- 거래량 분석
- 지지/저항선 (최근 N일 고저)
- 종합 점수 및 의견
"""
import numpy as np


class StockAnalyzer:
    """df 컬럼 요구: date, open, high, low, close, volume"""

    def __init__(self, df):
        self.df = df.copy().reset_index(drop=True)

    # -------------------------------------------------------------------------
    # 개별 지표
    # -------------------------------------------------------------------------
    def moving_averages(self, periods=(5, 20, 60)):
        result = {}
        close = self.df["close"]
        for p in periods:
            if len(close) >= p:
                result[f"ma{p}"] = round(close.rolling(p).mean().iloc[-1], 1)
            else:
                result[f"ma{p}"] = None
        return result

    def rsi(self, period=14):
        close = self.df["close"]
        if len(close) < period + 1:
            return None
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return round(rsi.iloc[-1], 1)

    def macd(self, fast=12, slow=26, signal=9):
        close = self.df["close"]
        if len(close) < slow + signal:
            return None
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return {
            "macd": round(macd_line.iloc[-1], 2),
            "signal": round(signal_line.iloc[-1], 2),
            "histogram": round(hist.iloc[-1], 2),
            "histogram_prev": round(hist.iloc[-2], 2),
        }

    def bollinger(self, period=20, num_std=2):
        close = self.df["close"]
        if len(close) < period:
            return None
        ma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = ma + num_std * std
        lower = ma - num_std * std
        price = close.iloc[-1]
        # %B: 밴드 내 위치 (0=하단, 1=상단)
        band_range = upper.iloc[-1] - lower.iloc[-1]
        pct_b = (price - lower.iloc[-1]) / band_range if band_range else 0.5
        return {
            "upper": round(upper.iloc[-1], 1),
            "middle": round(ma.iloc[-1], 1),
            "lower": round(lower.iloc[-1], 1),
            "pct_b": round(pct_b, 2),
        }

    def volume_analysis(self, period=20):
        vol = self.df["volume"]
        if len(vol) < period:
            return None
        avg = vol.rolling(period).mean().iloc[-1]
        today = vol.iloc[-1]
        ratio = today / avg if avg else 0
        return {
            "today": int(today),
            "avg": int(avg),
            "ratio": round(ratio, 2),  # 평균 대비 배수
        }

    def support_resistance(self, period=20):
        if len(self.df) < period:
            period = len(self.df)
        recent = self.df.iloc[-period:]
        return {
            "support": int(recent["low"].min()),
            "resistance": int(recent["high"].max()),
        }

    # -------------------------------------------------------------------------
    # 종합 분석
    # -------------------------------------------------------------------------
    def analyze(self):
        """모든 지표를 계산하고 종합 의견 반환"""
        price = int(self.df["close"].iloc[-1])
        ma = self.moving_averages()
        rsi_val = self.rsi()
        macd_val = self.macd()
        boll = self.bollinger()
        vol = self.volume_analysis()
        sr = self.support_resistance()

        signals = []   # (지표명, 점수[-1~+1], 코멘트)

        # 이동평균: 정배열/역배열
        if ma.get("ma5") and ma.get("ma20"):
            if ma["ma5"] > ma["ma20"]:
                signals.append(("이동평균", 1, "단기선이 장기선 위 (상승추세)"))
            else:
                signals.append(("이동평균", -1, "단기선이 장기선 아래 (하락추세)"))

        # RSI
        if rsi_val is not None:
            if rsi_val < 30:
                signals.append(("RSI", 1, f"과매도 {rsi_val} (반등 기대)"))
            elif rsi_val > 70:
                signals.append(("RSI", -1, f"과매수 {rsi_val} (조정 주의)"))
            else:
                signals.append(("RSI", 0, f"중립 {rsi_val}"))

        # MACD
        if macd_val:
            if macd_val["histogram"] > 0 and macd_val["histogram_prev"] <= 0:
                signals.append(("MACD", 1, "골든크로스 발생"))
            elif macd_val["histogram"] < 0 and macd_val["histogram_prev"] >= 0:
                signals.append(("MACD", -1, "데드크로스 발생"))
            elif macd_val["histogram"] > 0:
                signals.append(("MACD", 0.5, "상승 모멘텀 유지"))
            else:
                signals.append(("MACD", -0.5, "하락 모멘텀"))

        # 볼린저밴드
        if boll:
            if boll["pct_b"] < 0.1:
                signals.append(("볼린저", 1, "하단 근접 (저평가)"))
            elif boll["pct_b"] > 0.9:
                signals.append(("볼린저", -1, "상단 근접 (과열)"))
            else:
                signals.append(("볼린저", 0, "밴드 중앙권"))

        # 거래량
        if vol:
            if vol["ratio"] >= 2:
                signals.append(("거래량", 0.5, f"평균 대비 {vol['ratio']}배 급증"))
            elif vol["ratio"] < 0.5:
                signals.append(("거래량", -0.3, "거래량 부진"))
            else:
                signals.append(("거래량", 0, "거래량 보통"))

        total_score = sum(s[1] for s in signals)
        opinion = self._score_to_opinion(total_score)

        return {
            "price": price,
            "moving_averages": ma,
            "rsi": rsi_val,
            "macd": macd_val,
            "bollinger": boll,
            "volume": vol,
            "support_resistance": sr,
            "signals": signals,
            "total_score": round(total_score, 1),
            "opinion": opinion,
        }

    @staticmethod
    def _score_to_opinion(score):
        if score >= 2.5:
            return ("적극 매수", "📈")
        elif score >= 1:
            return ("매수 우위", "🟢")
        elif score > -1:
            return ("중립/관망", "⚪")
        elif score > -2.5:
            return ("매도 우위", "🔴")
        else:
            return ("적극 매도", "📉")

    # -------------------------------------------------------------------------
    # 사람이 읽는 리포트 텍스트
    # -------------------------------------------------------------------------
    def report_text(self, code="", name=""):
        a = self.analyze()
        opinion_text, emoji = a["opinion"]
        lines = []
        title = f"{name}({code})" if name else code
        lines.append(f"═══ 종목 분석: {title} ═══")
        lines.append(f"현재가: {a['price']:,}원")
        lines.append(f"종합의견: {emoji} {opinion_text} (점수 {a['total_score']})")
        lines.append("")
        lines.append("[기술적 지표]")
        ma = a["moving_averages"]
        lines.append(f" · 이동평균: 5일={ma.get('ma5')}, "
                     f"20일={ma.get('ma20')}, 60일={ma.get('ma60')}")
        lines.append(f" · RSI(14): {a['rsi']}")
        if a["macd"]:
            lines.append(f" · MACD: {a['macd']['macd']} / "
                         f"시그널 {a['macd']['signal']}")
        if a["bollinger"]:
            b = a["bollinger"]
            lines.append(f" · 볼린저: 하단 {b['lower']:,} ~ "
                         f"상단 {b['upper']:,} (위치 {b['pct_b']})")
        if a["volume"]:
            lines.append(f" · 거래량: 평균 대비 {a['volume']['ratio']}배")
        sr = a["support_resistance"]
        lines.append(f" · 지지선 {sr['support']:,} / 저항선 {sr['resistance']:,}")
        lines.append("")
        lines.append("[신호 상세]")
        for name_, score, comment in a["signals"]:
            mark = "▲" if score > 0 else ("▼" if score < 0 else "−")
            lines.append(f" {mark} {name_}: {comment}")
        return "\n".join(lines)
