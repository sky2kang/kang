"""
매매 알림 모듈 - 슬랙(Slack) / 텔레그램(Telegram) 동시 지원

설정된 채널로만 전송하며, 둘 다 비어있으면 아무것도 하지 않는다.
네트워크 오류가 발생해도 예외를 삼켜 매매 로직에 영향을 주지 않는다.
"""
import requests
from config.settings import (
    SLACK_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
)
from utils.logger import get_logger

logger = get_logger(__name__)

_TIMEOUT = 5  # 초


class Notifier:
    def __init__(self, slack_url=None, telegram_token=None, telegram_chat_id=None):
        self.slack_url = slack_url if slack_url is not None else SLACK_WEBHOOK_URL
        self.telegram_token = (
            telegram_token if telegram_token is not None else TELEGRAM_BOT_TOKEN
        )
        self.telegram_chat_id = (
            telegram_chat_id if telegram_chat_id is not None else TELEGRAM_CHAT_ID
        )

        channels = []
        if self.slack_url:
            channels.append("Slack")
        if self.telegram_token and self.telegram_chat_id:
            channels.append("Telegram")
        self.enabled = bool(channels)
        if self.enabled:
            logger.info(f"알림 채널 활성화: {', '.join(channels)}")
        else:
            logger.info("알림 채널 없음 (비활성화)")

    def send(self, message):
        """설정된 모든 채널로 메시지 전송"""
        if not self.enabled:
            return
        if self.slack_url:
            self._send_slack(message)
        if self.telegram_token and self.telegram_chat_id:
            self._send_telegram(message)

    def _send_slack(self, message):
        try:
            resp = requests.post(
                self.slack_url, json={"text": message}, timeout=_TIMEOUT
            )
            if resp.status_code != 200:
                logger.warning(f"Slack 전송 실패: status={resp.status_code}")
        except Exception as e:
            logger.warning(f"Slack 전송 오류: {e}")

    def _send_telegram(self, message):
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            resp = requests.post(
                url,
                data={"chat_id": self.telegram_chat_id, "text": message},
                timeout=_TIMEOUT,
            )
            if resp.status_code != 200:
                logger.warning(f"Telegram 전송 실패: status={resp.status_code}")
        except Exception as e:
            logger.warning(f"Telegram 전송 오류: {e}")
