"""
보유 계좌 전체의 예수금/평가잔고를 한 번의 로그인으로 조회하는 진단 헬퍼.

- 예수금: opw00001 (예수금상세현황요청)
- 평가잔고: opw00018 (계좌평가잔고내역요청)

계좌비밀번호는 키움 트레이 '계좌비밀번호 저장'에 등록된 값을 사용하므로
TR 입력의 비밀번호는 빈값("")으로 넘긴다.

실행:  .venv\Scripts\python.exe account_check.py
"""
import os
import sys
import time

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


def _to_int(s):
    s = (s or "").replace(",", "").replace("+", "").replace("-", "").strip()
    try:
        return int(s)
    except ValueError:
        return 0


def query_deposit(api, account):
    """opw00001 예수금상세현황요청 → 예수금/주문가능금액/출금가능금액"""
    api.set_input_value("계좌번호", account)
    api.set_input_value("비밀번호", "")
    api.set_input_value("비밀번호입력매체구분", "00")
    api.set_input_value("조회구분", "2")
    ret = api.comm_rq_data("예수금조회", "opw00001", 0, "9001")
    if ret != 0:
        return None
    return {
        "예수금": _to_int(api.get_comm_data("opw00001", "예수금조회", 0, "예수금")),
        "주문가능금액": _to_int(api.get_comm_data("opw00001", "예수금조회", 0, "주문가능금액")),
        "출금가능금액": _to_int(api.get_comm_data("opw00001", "예수금조회", 0, "출금가능금액")),
        "d+2추정예수금": _to_int(api.get_comm_data("opw00001", "예수금조회", 0, "d+2추정예수금")),
    }


def query_balance(api, account):
    """opw00018 계좌평가잔고 → 총평가금액/총수익률/보유종목수"""
    api.set_input_value("계좌번호", account)
    api.set_input_value("비밀번호", "")
    api.set_input_value("비밀번호입력매체구분", "00")
    api.set_input_value("조회구분", "2")
    ret = api.comm_rq_data("잔고조회", "opw00018", 0, "9002")
    if ret != 0:
        return None
    total_eval = _to_int(api.get_comm_data("opw00018", "잔고조회", 0, "총평가금액"))
    cnt = api.get_repeat_cnt("opw00018", "잔고조회")
    return {"총평가금액": total_eval, "보유종목수": cnt}


def main():
    app = QApplication(sys.argv)
    kiwoom = KiwoomAPI()
    kiwoom.login()

    accounts = kiwoom.get_account_list()
    server = kiwoom.get_login_info("GetServerGubun")
    server_str = "모의투자" if server == "1" else "실거래(실서버)"

    print("\n" + "=" * 64, flush=True)
    print(f"접속서버: {server_str} (GetServerGubun={server!r}) / 계좌 {len(accounts)}개", flush=True)
    print("=" * 64, flush=True)

    for acc in accounts:
        print(f"\n[계좌 {acc}]", flush=True)
        try:
            dep = query_deposit(kiwoom, acc)
            time.sleep(0.4)  # TR 과부하(1초 5회) 회피
            bal = query_balance(kiwoom, acc)
            time.sleep(0.4)
            if dep is None:
                print("  예수금 조회 실패(요청 거부)", flush=True)
            else:
                print(f"  예수금        : {dep['예수금']:>15,} 원", flush=True)
                print(f"  주문가능금액  : {dep['주문가능금액']:>15,} 원", flush=True)
                print(f"  출금가능금액  : {dep['출금가능금액']:>15,} 원", flush=True)
                print(f"  D+2추정예수금 : {dep['d+2추정예수금']:>15,} 원", flush=True)
            if bal is None:
                print("  평가잔고 조회 실패(요청 거부)", flush=True)
            else:
                print(f"  총평가금액    : {bal['총평가금액']:>15,} 원  (보유종목 {bal['보유종목수']}개)", flush=True)
        except Exception as e:
            print(f"  오류: {e}", flush=True)

    print("\n" + "=" * 64, flush=True)
    print("조회 완료. 예수금/주문가능금액이 가장 큰 계좌를 .env의 KIWOOM_ACCOUNT에 쓰세요.", flush=True)
    print("=" * 64, flush=True)

    app.quit()


if __name__ == "__main__":
    main()
