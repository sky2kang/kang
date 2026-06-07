"""
키움증권 OpenAPI+ 연동 핵심 클래스
- Windows 환경에서만 동작 (OCX 컨트롤)
- PyQt5 이벤트 루프 기반
"""
from PyQt5.QAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop
from utils.logger import get_logger

logger = get_logger(__name__)


class KiwoomAPI(QAxWidget):
    def __init__(self):
        super().__init__()
        self._login_event = QEventLoop()
        self._tr_event = QEventLoop()
        self._order_event = QEventLoop()
        self._condition_event = QEventLoop()

        self.tr_data = {}          # TR 수신 데이터 임시 저장
        self.real_data_callbacks = {}  # 실시간 데이터 콜백 {화면번호: callback}

        # 조건검색
        self.condition_list = {}       # {조건인덱스: 조건명}
        self.condition_tr_result = []  # 조건검색 단발성 결과 (종목코드 리스트)
        self.real_condition_callback = None  # 실시간 조건 편입/이탈 콜백

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
        return self.dynamicCall("GetLoginInfo(QString)", tag)

    # -------------------------------------------------------------------------
    # TR 조회 (요청/응답)
    # -------------------------------------------------------------------------
    def set_input_value(self, key, value):
        self.dynamicCall("SetInputValue(QString, QString)", key, str(value))

    def comm_rq_data(self, rq_name, tr_code, prev_next, screen_no):
        """TR 요청 전송 후 응답 대기"""
        ret = self.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            rq_name, tr_code, prev_next, screen_no
        )
        if ret != 0:
            logger.error(f"TR 요청 실패: {rq_name}, ret={ret}")
            return ret
        self._tr_event.exec_()
        return 0

    def _on_receive_tr_data(self, screen_no, rq_name, tr_code, record_name,
                            prev_next, *args):
        logger.debug(f"TR 수신: {rq_name} ({tr_code}), 다음페이지={prev_next}")
        self.tr_data["prev_next"] = prev_next
        self.tr_data["rq_name"] = rq_name
        self.tr_data["tr_code"] = tr_code
        self._tr_event.quit()

    def get_comm_data(self, tr_code, record_name, index, item_name):
        """TR 단건 데이터 조회"""
        return self.dynamicCall(
            "GetCommData(QString, QString, int, QString)",
            tr_code, record_name, index, item_name
        ).strip()

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

    def get_chejan_data(self, fid):
        """체결 잔고 데이터 조회"""
        return self.dynamicCall("GetChejanData(int)", fid).strip()

    def _on_receive_msg(self, screen_no, rq_name, tr_code, msg):
        logger.info(f"[서버메시지] {rq_name}: {msg}")

    # -------------------------------------------------------------------------
    # 조건검색 (HTS에서 저장한 조건식 활용)
    # -------------------------------------------------------------------------
    def load_condition_list(self):
        """
        서버에 저장된 조건검색식 목록 요청.
        HTS(영웅문)의 [0150] 조건검색 화면에서 만들어 저장한 조건식을 불러온다.
        완료 시 self.condition_list 에 {인덱스: 조건명} 형태로 채워진다.
        """
        logger.info("조건검색식 목록 요청...")
        ret = self.dynamicCall("GetConditionLoad()")
        if ret != 1:
            raise RuntimeError("조건검색식 로드 요청 실패")
        self._condition_event.exec_()  # _on_receive_condition_ver 에서 quit
        logger.info(f"조건검색식 {len(self.condition_list)}개 로드: "
                    f"{list(self.condition_list.values())}")
        return self.condition_list

    def _on_receive_condition_ver(self, ret, msg):
        """조건검색식 목록 수신 완료 이벤트"""
        if ret == 1:
            raw = self.dynamicCall("GetConditionNameList()")
            # 형식: "인덱스^조건명;인덱스^조건명;..."
            for item in raw.strip(";").split(";"):
                if not item:
                    continue
                idx, name = item.split("^")
                self.condition_list[int(idx)] = name
        else:
            logger.error("조건검색식 목록 수신 실패")
        self._condition_event.quit()

    def get_condition_index_by_name(self, name):
        """조건명으로 인덱스 조회"""
        for idx, cond_name in self.condition_list.items():
            if cond_name == name:
                return idx
        return None

    def send_condition(self, screen_no, cond_name, cond_index, search_type=1):
        """
        조건검색 요청.
        search_type: 0=단발성 조회(현재 만족 종목 1회 조회),
                     1=실시간 조회(종목 편입/이탈을 실시간으로 통보)
        반환: 단발성(0)일 때 종목코드 리스트
        """
        self.condition_tr_result = []
        ret = self.dynamicCall(
            "SendCondition(QString, QString, int, int)",
            screen_no, cond_name, cond_index, search_type
        )
        if ret != 1:
            logger.error(f"조건검색 요청 실패: {cond_name}")
            return []

        if search_type == 0:
            self._condition_event.exec_()  # 단발성은 결과 수신까지 대기
            return self.condition_tr_result
        else:
            logger.info(f"실시간 조건검색 시작: [{cond_name}] (idx={cond_index})")
            return []

    def send_condition_stop(self, screen_no, cond_name, cond_index):
        """실시간 조건검색 중지"""
        self.dynamicCall(
            "SendConditionStop(QString, QString, int)",
            screen_no, cond_name, cond_index
        )
        logger.info(f"실시간 조건검색 중지: [{cond_name}]")

    def _on_receive_tr_condition(self, screen_no, code_list, cond_name,
                                 cond_index, prev_next):
        """조건검색 단발성 결과 수신 이벤트"""
        codes = [c for c in code_list.strip(";").split(";") if c]
        self.condition_tr_result = codes
        logger.info(f"조건검색 [{cond_name}] 결과: {len(codes)}개 종목")
        self._condition_event.quit()

    def _on_receive_real_condition(self, code, event_type, cond_name, cond_index):
        """
        실시간 조건검색 편입/이탈 이벤트
        event_type: "I"=편입(조건 만족), "D"=이탈(조건 불만족)
        """
        event_str = "편입" if event_type == "I" else "이탈"
        logger.info(f"[실시간조건] [{cond_name}] {code} {event_str}")
        if self.real_condition_callback:
            self.real_condition_callback(code, event_type, cond_name, cond_index)

    def register_real_condition_callback(self, callback):
        """실시간 조건 편입/이탈 시 호출할 콜백 등록"""
        self.real_condition_callback = callback
