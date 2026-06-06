"""
이동평균선 골든크로스/데드크로스 전략
- 매수: 단기 MA가 장기 MA를 상향 돌파 (골든크로스)
- 매도: 단기 MA가 장기 MA를 하향 돌파 (데드크로스) 또는 손절/익절
"""
import pandas as pd
from config.settings import STOP_LOSS_RATE, TAKE_PROFIT_RATE
from strategy.base_strategy import BaseStrategy
from utils.logger import get_logger

logger = get_logger(__name__)


class MAStrategy(BaseStrategy):
    def __init__(self, short_period=5, long_period=20):
        super().__init__("MA골든크로스")
        self.short = short_period
        self.long = long_period

    def _calc_ma(self, df):
        df = df.copy()
        df["ma_short"] = df["close"].rolling(self.short).mean()
        df["ma_long"] = df["close"].rolling(self.long).mean()
        return df

    def should_buy(self, df, code) -> bool:
        """
        골든크로스 매수 조건:
        - 전일: 단기MA <= 장기MA
        - 당일: 단기MA > 장기MA
        """
        if len(df) < self.long + 1:
            return False

        df = self._calc_ma(df)
        prev = df.iloc[-2]
        curr = df.iloc[-1]

        cross = (prev["ma_short"] <= prev["ma_long"]) and (curr["ma_short"] > curr["ma_long"])
        if cross:
            logger.info(f"[{code}] 골든크로스 매수 신호: 단기MA={curr['ma_short']:.1f}, 장기MA={curr['ma_long']:.1f}")
        return cross

    def should_sell(self, df, code, avg_price, current_price) -> bool:
        """
        매도 조건 (우선순위):
        1. 손절: 수익률 < STOP_LOSS_RATE
        2. 익절: 수익률 > TAKE_PROFIT_RATE
        3. 데드크로스: 단기MA < 장기MA 전환
        """
        if avg_price <= 0:
            return False

        profit_rate = (current_price - avg_price) / avg_price

        if profit_rate <= STOP_LOSS_RATE:
            logger.info(f"[{code}] 손절 매도: 수익률={profit_rate:.2%}")
            return True

        if profit_rate >= TAKE_PROFIT_RATE:
            logger.info(f"[{code}] 익절 매도: 수익률={profit_rate:.2%}")
            return True

        if len(df) < self.long + 1:
            return False

        df = self._calc_ma(df)
        prev = df.iloc[-2]
        curr = df.iloc[-1]

        dead_cross = (prev["ma_short"] >= prev["ma_long"]) and (curr["ma_short"] < curr["ma_long"])
        if dead_cross:
            logger.info(f"[{code}] 데드크로스 매도 신호")
        return dead_cross
