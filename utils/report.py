"""
일일 매매 리포트 생성 모듈

장 마감 후 오늘의 매매 결과를 요약하여 텍스트로 만들고,
notifier를 통해 슬랙/텔레그램으로 자동 발송할 수 있다.
"""
import datetime
from utils.logger import get_logger

logger = get_logger(__name__)


class DailyReport:
    def __init__(self, db, notifier=None):
        """
        db: utils.db.TradeDB 인스턴스
        notifier: utils.notifier.Notifier 인스턴스 (선택)
        """
        self.db = db
        self.notifier = notifier

    def build(self, account_summary=None):
        """
        오늘의 매매 리포트 텍스트 생성.
        account_summary: {"total_eval", "total_profit_rate", "available"} (선택)
        """
        today = datetime.date.today().isoformat()
        orders = self.db.get_today_orders()

        # orders 컬럼: id, timestamp, code, name, side, qty, price, is_simul, reason
        buys = [o for o in orders if o[4] == "BUY"]
        sells = [o for o in orders if o[4] == "SELL"]

        lines = [f"📊 일일 매매 리포트 ({today})", "─" * 24]

        if account_summary:
            lines.append(f"총 평가금액: {account_summary['total_eval']:,}원")
            lines.append(f"누적 수익률: {account_summary['total_profit_rate']:.2f}%")
            lines.append(f"주문 가능액: {account_summary['available']:,}원")
            lines.append("")

        lines.append(f"오늘 주문: 총 {len(orders)}건 "
                     f"(매수 {len(buys)} / 매도 {len(sells)})")

        if buys:
            lines.append("")
            lines.append("[매수]")
            for o in buys:
                lines.append(f" 🟢 {o[3]}({o[2]}) {o[5]}주 @ {o[6]:,}원")

        if sells:
            lines.append("")
            lines.append("[매도]")
            for o in sells:
                reason = o[8] or ""
                lines.append(f" 🔴 {o[3]}({o[2]}) {o[5]}주 ({reason})")

        if not orders:
            lines.append("오늘 체결된 매매가 없습니다.")

        return "\n".join(lines)

    def send(self, account_summary=None):
        """리포트를 생성하고 알림 채널로 발송"""
        text = self.build(account_summary)
        logger.info("일일 리포트 생성 완료")
        if self.notifier:
            self.notifier.send(text)
        return text
