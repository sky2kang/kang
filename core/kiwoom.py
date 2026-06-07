"""
키움증권 OpenAPI+ 연동 핵심 클래스
- Windows 환경에서만 동작 (OCX 컨트롤)
- PyQt5 이벤트 루프 기반
"""
import time
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop, QTimer
from utils.logger import get_logger

logger = get_logger(__name__)


def _decode(s):
    """키움 OCX가 CP949 바이트를 와이드 문자열에 그대로 담아 반환해 한글이
    깨지는 경우를 복원한다. 이미 정상인(또는 ASCII) 문자열은 그대로 둔다."""
    if not s:
        return s
    try:
        return s.encode("latin-1").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


class KiwoomAPI(QAxWidget):
    # 키움 OpenAPI는 초당 약 5회로 TR 요청을 제한한다. 요청 사이에 최소 간격을
    # 둬 -308(요청제한/과부하) 에러와 그로 인한 빈 응답을 방지한다.
    TR_REQUEST_INTERVAL = 0.3  # 초
    TR_TIMEOUT_MS = 10000      # TR 응답 대기 최대 시간 (ms). 초과 시 빈 응답 처리

    @staticmethod
    def decode_text(s):
        """OCX 반환 문자열의 한글 깨짐 복원 (표시용)."""
        return _decode(s)
    def __init__(self):
        super().__init__()
        self._login_event = QEventLoop()
        self._tr_event = QEventLoop()
        self._order_event = QEventLoop()
        self._condition_event = QEventLoop()

        self.tr_data = {}          # TR 수신 데이터 임시 저장
        self.real_data_callbacks = {}  # 실시간 데이터 콜백 {화면번호: callback}
        self._last_tr_time = 0.0   # 마지막 TR 요청 시각 (속도 제한용)

        # 조건검색
        self.condition_list = []           # [(index, name), ...]
        self._condition_tr_result = []     # 단발성 조건검색 결과 코드 리스트
        self.condition_real_callback = None  # 실시간 조건검색 편입/이탈 콜백
        self.chejan_callback = None        # 체결/잔고 이벤트 콜백

        self._init_api()

    # -------------------------------------------------------------------------
    # 초기화
    # -------------------------------------------------------------------------
    def _init_api(self):
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")

        # 이벤트 핸들러 연결
        self.OnEventConnect.connect(self._on_event_connect)
        self.OnReceiveTrData.connect(self._on_receive_tr_data)
        self.OnReceiveRealData.connect(self._on_receive_real_data)
        self.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        self.OnReceiveMsg.connect(self._on_receive_msg)

        # 조건검색 이벤트
        self.OnReceiveConditionVer.connect(self._on_receive_condition_ver)
        self.OnReceiveTrCondition.connect(self._on_receive_tr_condition)
        self.OnReceiveRealCondition.connect(self._on_receive_real_condition)

        logger.info("KiwoomAPI 초기화 완료")

    # -------------------------------------------------------------------------
    # 종목 정보 (마스터)
    # -------------------------------------------------------------------------
    def get_master_code_name(self, code):
        """종목코드 → 종목명"""
        return _decode(self.dynamicCall("GetMasterCodeName(QString)", code).strip())

    def get_code_list_by_market(self, market="0"):
        """시장별 종목코드 리스트 (0:코스피, 10:코스닥)"""
        raw = self.dynamicCall("GetCodeListByMarket(QString)", market)
        return [c for c in raw.split(";") if c]

    # -------------------------------------------------------------------------
    # 조건검색 (영웅문에서 저장한 조건식 사용)
    # -------------------------------------------------------------------------
    def get_condition_load(self, timeout_ms=5000):
        """서버에서 조건식 목록을 불러온다 (완료 시 _on_receive_condition_ver)."""
        ret = self.dynamicCall("GetConditionLoad()")
        if ret != 1:
            logger.error("GetConditionLoad 호출 실패")
            return []
        self._condition_event.exec_()
        return self.condition_list

    def _on_receive_condition_ver(self, ret, msg):
        """조건식 목록 수신 완료"""
        if ret == 1:
            raw = self.dynamicCall("GetConditionNameList()")
            items = []
            for pair in [p for p in raw.split(";") if p]:
                idx, name = pair.split("^")
                items.append((int(idx), name))
            self.condition_list = items
            logger.info(f"조건식 {len(items)}개 로드됨")
        else:
            logger.error(f"조건식 목록 수신 실패: {msg}")
        if self._condition_event.isRunning():
            self._condition_event.quit()

    def send_condition(self, screen_no, cond_name, cond_index, search_type=0):
        """
        조건검색 실행.
        search_type: 0=단발조회, 1=실시간조회(편입/이탈 이벤트 수신)
        반환: 성공 시 코드 리스트(단발은 결과, 실시간은 초기 편입 종목),
              실패(SendCondition 거부) 시 None.
        """
        self._condition_tr_result = []
        ret = self.dynamicCall(
            "SendCondition(QString, QString, int, int)",
            screen_no, cond_name, cond_index, search_type,
        )
        if ret != 1:
            # 일시적 과부하/타이밍 실패 대비 1회 재시도
            time.sleep(0.6)
            ret = self.dynamicCall(
                "SendCondition(QString, QString, int, int)",
                screen_no, cond_name, cond_index, search_type,
            )
        if ret != 1:
            logger.error(
                f"SendCondition 실패: {_decode(cond_name)} (화면={screen_no}). "
                f"상한가/체결기반 조건식은 단발 조회 미지원(실시간·장중 전용)일 수 있고, "
                f"화면번호 중복 / 실시간 동시등록 초과(최대 약 10개) / 과부하도 원인입니다."
            )
            return None
        if search_type == 0:
            self._condition_event.exec_()
        return list(self._condition_tr_result)

    def send_condition_stop(self, screen_no, cond_name, cond_index):
        """실시간 조건검색 중지"""
        self.dynamicCall(
            "SendConditionStop(QString, QString, int)",
            screen_no, cond_name, cond_index,
        )

    def _on_receive_tr_condition(self, screen_no, code_list, cond_name, cond_index, prev_next):
        """조건검색 단발 결과 수신"""
        codes = [c for c in code_list.split(";") if c]
        self._condition_tr_result = codes
        logger.info(f"조건검색 '{_decode(cond_name)}' 결과: {len(codes)}종목")
        if self._condition_event.isRunning():
            self._condition_event.quit()

    def _on_receive_real_condition(self, code, event_type, cond_name, cond_index):
        """실시간 조건검색: event_type 'I'=편입, 'D'=이탈"""
        if self.condition_real_callback:
            self.condition_real_callback(code, event_type, cond_name, cond_index)

    # -------------------------------------------------------------------------
    # 로그인
    # -------------------------------------------------------------------------
    def login(self, timeout=60):
        """로그인 팝업 실행 후 완료까지 대기"""
        logger.info("로그인 시도...")
        self.dynamicCall("CommConnect()")
        self._login_event.exec_()  # 로그인 완료 시 _on_event_connect에서 quit()
        state = self.get_connect_state()
        if state != 1:
            raise ConnectionError("키움증권 로그인 실패")
        logger.info("로그인 성공")

    def get_connect_state(self):
        """연결 상태 반환 (1: 연결, 0: 미연결)"""
        return self.dynamicCall("GetConnectState()")

    def _on_event_connect(self, err_code):
        if err_code == 0:
            logger.info("서버 연결 성공")
        else:
            logger.error(f"서버 연결 실패: errCode={err_code}")
        self._login_event.quit()

    # -------------------------------------------------------------------------
    # 계좌 정보
    # -------------------------------------------------------------------------
    def get_account_list(self):
        """보유 계좌 목록 반환"""
        raw = self.dynamicCall("GetLoginInfo(QString)", "ACCNO")
        return [a for a in raw.strip(";").split(";") if a]

    def get_login_info(self, tag):
        """로그인 정보 조회 (USER_ID, USER_NAME, ACCNO, GetServerGubun 등)"""
        return _decode(self.dynamicCall("GetLoginInfo(QString)", tag))

    # -------------------------------------------------------------------------
    # TR 조회 (요청/응답)
    # -------------------------------------------------------------------------
    def set_input_value(self, key, value):
        self.dynamicCall("SetInputValue(QString, QString)", key, str(value))

    def comm_rq_data(self, rq_name, tr_code, prev_next, screen_no):
        """TR 요청 전송 후 응답 대기.
        요청 간 최소 간격을 강제해 과부하(-308)를 막고, 응답이 오지 않으면
        TR_TIMEOUT_MS 후 빈 응답으로 처리해 무한 대기를 막는다."""
        # 직전 요청과의 간격이 부족하면 대기
        elapsed = time.time() - self._last_tr_time
        if elapsed < self.TR_REQUEST_INTERVAL:
            time.sleep(self.TR_REQUEST_INTERVAL - elapsed)

        ret = self.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            rq_name, tr_code, prev_next, screen_no
        )
        self._last_tr_time = time.time()
        if ret != 0:
            logger.error(f"TR 요청 실패: {rq_name}({tr_code}), ret={ret} "
                         f"(-308=요청제한/과부하, 0이 아니면 미수신)")
            return ret

        # 응답 타임아웃: 일정 시간 내 OnReceiveTrData가 없으면 루프 종료
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(self._on_tr_timeout)
        timer.start(self.TR_TIMEOUT_MS)
        self.tr_data["timeout"] = False
        self._tr_event.exec_()
        timer.stop()

        if self.tr_data.get("timeout"):
            logger.error(f"TR 응답 타임아웃: {rq_name}({tr_code})")
            return -1
        return 0

    def _on_tr_timeout(self):
        """TR 응답 대기 타임아웃 처리"""
        self.tr_data["timeout"] = True
        if self._tr_event.isRunning():
            self._tr_event.quit()

    def _on_receive_tr_data(self, screen_no, rq_name, tr_code, record_name,
                            prev_next, *args):
        logger.debug(f"TR 수신: {rq_name} ({tr_code}), 다음페이지={prev_next}")
        self.tr_data["prev_next"] = prev_next
        self.tr_data["rq_name"] = rq_name
        self.tr_data["tr_code"] = tr_code
        self._tr_event.quit()

    def get_comm_data(self, tr_code, record_name, index, item_name):
        """TR 단건 데이터 조회"""
        return _decode(self.dynamicCall(
            "GetCommData(QString, QString, int, QString)",
            tr_code, record_name, index, item_name
        ).strip())

    def get_repeat_cnt(self, tr_code, record_name):
        """TR 반복 데이터 개수 조회"""
        return self.dynamicCall(
            "GetRepeatCnt(QString, QString)", tr_code, record_name
        )

    # -------------------------------------------------------------------------
    # 실시간 데이터 구독
    # -------------------------------------------------------------------------
    def set_real_reg(self, screen_no, code_list, fid_list, opt_type="0"):
        """실시간 시세 등록 (opt_type='0': 기존 화면 초기화, '1': 추가)"""
        self.dynamicCall(
            "SetRealReg(QString, QString, QString, QString)",
            screen_no, code_list, fid_list, opt_type
        )

    def set_real_remove(self, screen_no, code):
        """실시간 시세 해제"""
        self.dynamicCall("SetRealRemove(QString, QString)", screen_no, code)

    def get_comm_real_data(self, code, fid):
        """실시간 데이터 값 조회"""
        return self.dynamicCall(
            "GetCommRealData(QString, int)", code, fid
        ).strip()

    def register_real_callback(self, screen_no, callback):
        """실시간 데이터 수신 시 호출할 콜백 등록"""
        self.real_data_callbacks[screen_no] = callback

    def _on_receive_real_data(self, code, real_type, real_data):
        for callback in self.real_data_callbacks.values():
            callback(code, real_type, real_data)

    # -------------------------------------------------------------------------
    # 주문
    # -------------------------------------------------------------------------
    def send_order(self, rq_name, screen_no, account, order_type,
                   code, qty, price, hoga_gb, org_order_no=""):
        """
        주문 전송
        order_type: 1=신규매수, 2=신규매도, 3=매수취소, 4=매도취소
        hoga_gb: "00"=지정가, "03"=시장가
        """
        ret = self.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            rq_name, screen_no, account, order_type,
            code, qty, price, hoga_gb, org_order_no
        )
        if ret != 0:
            logger.error(f"주문 실패: {rq_name}, ret={ret}")
        return ret

    def _on_receive_chejan_data(self, gubun, item_cnt, fid_list):
        """체결/잔고 이벤트 (gubun: '0'=접수/체결, '1'=잔고)"""
        if gubun == "0":
            order_no = self.get_chejan_data(9203)
            code = self.get_chejan_data(9001).replace("A", "")
            status = self.get_chejan_data(913)
            qty = self.get_chejan_data(911)
            price = self.get_chejan_data(910)
            logger.info(f"[체결] 주문번호={order_no}, 종목={code}, "
                        f"상태={status}, 수량={qty}, 가격={price}")
            if self.chejan_callback:
                self.chejan_callback({
                    "order_no": order_no, "code": code, "status": status,
                    "qty": qty, "price": price,
                })

    def get_chejan_data(self, fid):
        """체결 잔고 데이터 조회"""
        return self.dynamicCall("GetChejanData(int)", fid).strip()

    def _on_receive_msg(self, screen_no, rq_name, tr_code, msg):
        logger.info(f"[서버메시지] {_decode(rq_name)}: {_decode(msg)}")

    # -------------------------------------------------------------------------
    # 조건검색 호환 API (core/condition_trader.py·screener.py 용 얇은 래퍼)
    # 정본 구현은 위 get_condition_load / send_condition / _on_receive_* 이며,
    # condition_list 는 [(index, name), ...] 형식이다.
    # -------------------------------------------------------------------------
    def load_condition_list(self):
        """조건식 목록을 불러온다 (get_condition_load 별칭). [(idx, name), ...] 반환."""
        return self.get_condition_load()

    def get_condition_index_by_name(self, name):
        """조건명으로 인덱스 조회 (없으면 None)."""
        for idx, cond_name in self.condition_list:
            if cond_name == name:
                return idx
        return None

    def register_real_condition_callback(self, callback):
        """실시간 조건 편입/이탈 콜백 등록 (condition_real_callback 설정)."""
        self.condition_real_callback = callback
