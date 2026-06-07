"""
설정 마법사 - .env 파일을 질문-답변으로 생성

초보자가 텍스트 편집기로 직접 .env를 수정하지 않아도 되도록,
대화형 질문에 답하면 .env 파일을 자동 생성한다.

실행: python setup_wizard.py
"""
import os

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def ask(prompt, default="", secret_hint=False):
    hint = f" (기본값: {default})" if default else ""
    if secret_hint:
        hint += " [비워두면 사용 안 함]"
    value = input(f"{prompt}{hint}\n> ").strip()
    return value if value else default


def ask_yes_no(prompt, default=True):
    d = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({d})\n> ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "예", "ㅛ")


def main():
    print("=" * 50)
    print("  키움 자동매매 설정 마법사")
    print("=" * 50)
    print("질문에 답하면 .env 설정 파일을 자동으로 만들어 드립니다.")
    print("그냥 Enter를 누르면 기본값이 사용됩니다.\n")

    if os.path.exists(ENV_PATH):
        if not ask_yes_no(".env 파일이 이미 있습니다. 덮어쓸까요?", default=False):
            print("취소되었습니다.")
            return

    config = {}

    print("\n── 1. 계좌 설정 ──")
    config["KIWOOM_ACCOUNT"] = ask("키움 계좌번호를 입력하세요", "")

    # 안전을 위해 최초 설정은 모의투자 강제 권고
    real = ask_yes_no("실거래로 사용하시겠습니까? (권장: 아니오=모의투자)",
                      default=False)
    config["KIWOOM_SIMUL"] = "False" if real else "True"
    if real:
        print("  ⚠️  실거래 모드입니다. 실제 돈으로 매매됩니다. 충분히 테스트하세요!")

    print("\n── 2. 매매 한도 ──")
    config["MAX_BUY_AMOUNT"] = ask("1회 최대 매수금액(원)", "1000000")
    config["MAX_STOCK_COUNT"] = ask("최대 동시 보유 종목수", "5")
    config["STOP_LOSS_RATE"] = ask("손절 기준(예: -0.05 = -5%)", "-0.05")
    config["TAKE_PROFIT_RATE"] = ask("익절 기준(예: 0.10 = +10%)", "0.10")

    print("\n── 3. 안전장치 ──")
    config["DAILY_LOSS_LIMIT_RATE"] = ask(
        "일일 최대 손실 한도(예: -0.10 = -10%, 도달 시 자동중단)", "-0.10")
    config["MAX_ORDERS_PER_DAY"] = ask("하루 최대 주문 횟수", "20")

    print("\n── 4. 알림 (선택) ──")
    if ask_yes_no("슬랙 알림을 사용하시겠습니까?", default=False):
        config["SLACK_WEBHOOK_URL"] = ask("Slack Webhook URL", "", secret_hint=True)
    if ask_yes_no("텔레그램 알림을 사용하시겠습니까?", default=False):
        config["TELEGRAM_BOT_TOKEN"] = ask("Telegram 봇 토큰", "", secret_hint=True)
        config["TELEGRAM_CHAT_ID"] = ask("Telegram Chat ID", "", secret_hint=True)

    config["LOG_LEVEL"] = "INFO"

    # .env 파일 작성
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("# 키움 자동매매 설정 (setup_wizard.py 로 자동 생성)\n")
        for key, value in config.items():
            f.write(f"{key}={value}\n")

    print("\n" + "=" * 50)
    print(f"✅ 설정 완료! 파일 저장됨: {ENV_PATH}")
    print(f"모드: {'실거래' if config['KIWOOM_SIMUL'] == 'False' else '모의투자'}")
    print("이제 'python main.py' 로 자동매매를 시작할 수 있습니다.")
    print("=" * 50)


if __name__ == "__main__":
    main()
