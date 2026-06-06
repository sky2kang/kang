"""
전략 기본 클래스 - 모든 전략은 이 클래스를 상속받아 구현
"""
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    def __init__(self, name):
        self.name = name

    @abstractmethod
    def should_buy(self, df, code) -> bool:
        """매수 신호 여부 반환"""

    @abstractmethod
    def should_sell(self, df, code, avg_price, current_price) -> bool:
        """매도 신호 여부 반환"""
