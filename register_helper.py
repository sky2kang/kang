"""
계좌비밀번호 등록용 헬퍼.

로그인만 하고 이벤트 루프에서 대기한다. (잔고조회/TR을 호출하지 않으므로
'계좌비밀번호 미등록(에러 44)' 모달이 뜨지 않는다.)

이 헬퍼가 로그인된 상태로 떠 있는 동안, 작업표시줄 트레이의
키움 OpenAPI 아이콘 > '계좌비밀번호 저장'에서 계좌(8127954011)와
비밀번호(모의투자 기본 0000)를 등록하고 AUTO를 체크하면 된다.
등록을 마치면 이 창은 닫아도 된다.
"""
import os
import sys

# Qt 플랫폼 플러그인 경로 보정 (main.py와 동일)
if "QT_QPA_PLATFORM_PLUGIN_PATH" not in os.environ:
    import PyQt5
    _plugins = os.path.join(
        os.path.dirname(PyQt5.__file__), "Qt5", "plugins", "platforms"
    )
    if os.path.isdir(_plugins):
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _plugins

from PyQt5.QtWidgets import QApplication
from core.kiwoom import KiwoomAPI


def main():
    app = QApplication(sys.argv)
    kiwoom = KiwoomAPI()
    kiwoom.login()

    accounts = kiwoom.get_account_list()
    server = kiwoom.get_login_info("GetServerGubun")
    server_str = "모의투자" if server == "1" else "실거래(실서버)"
    print("=" * 60)
    print(f"로그인 완료 / 접속서버: {server_str} (GetServerGubun={server!r})")
    print(f"보유 계좌: {accounts}")
    print("=" * 60)
    print("이제 트레이의 키움 OpenAPI 아이콘 우클릭 > '계좌비밀번호 저장'에서")
    print("계좌 8127954011, 비밀번호 0000 등록 + AUTO 체크 후 이 창을 닫으세요.")
    print("(이 헬퍼는 잔고조회를 하지 않으므로 44 에러 모달이 뜨지 않습니다.)")
    print("=" * 60)

    # 연결 유지 (트레이 메뉴가 살아있도록). 닫으려면 Ctrl+C 또는 창 종료.
    app.exec_()


if __name__ == "__main__":
    main()
