"""
RSI 과매수/과매도 전략
- 매수: RSI < 30 (과매도 구간 진입 후 반등)
- 매도: RSI > 70 (과매수 구간) 또는 손절/익절
"""
import numpy as np
from config.settings import STOP_LOSS_RATE, TAKE_PROFIT_RATE
from strategy.base_strategy import BaseStrategy
from utils.logger import get_logger

logger = get_logger(__name__)


class RSIStrategy(BaseStrategy):
    def __init__(self, period=14, oversold=30, overbought=70):
        super().__init__("RSI전략")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def _calc_rsi(self, df):
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(self.period).mean()
        avg_loss = loss.rolling(self.period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def should_buy(self, df, code) -> bool:
        if len(df) < self.period + 2:
            return False

        rsi = self._calc_rsi(df)
        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]

        # 과매도 구간에서 반등 (상향 돌파)
        signal = (prev_rsi < self.oversold) and (curr_rsi >= self.oversold)
        if signal:
            logger.info(f"[{code}] RSI 매수 신호: RSI={curr_rsi:.1f}")
        return signal

    def should_sell(self, df, code, avg_price, current_price) -> bool:
        if avg_price <= 0:
            return False

        profit_rate = (current_price - avg_price) / avg_price

        if profit_rate <= STOP_LOSS_RATE:
            logger.info(f"[{code}] 손절 매도: 수익률={profit_rate:.2%}")
            return True

        if profit_rate >= TAKE_PROFIT_RATE:
            logger.info(f"[{code}] 익절 매도: 수익률={profit_rate:.2%}")
            return True

        if len(df) < self.period + 2:
            return False

        rsi = self._calc_rsi(df)
        curr_rsi = rsi.iloc[-1]

        # 과매수 구간 도달
        signal = curr_rsi >= self.overbought
        if signal:
            logger.info(f"[{code}] RSI 매도 신호: RSI={curr_rsi:.1f}")
        return signal
