"""
pytest 공용 설정.

실제 프로그램은 Windows 32비트 + 키움 OpenAPI+ OCX(ActiveX) 위에서 동작하지만,
콜백 등록/해제 로직 자체는 순수 파이썬이다. 리눅스/CI에서도 테스트할 수 있도록
PyQt5(QAxContainer/QtCore)를 가짜 모듈로 주입해 `core.kiwoom` import 를 가능하게 한다.

여기서 교체하는 것은 OCX 바인딩뿐이며, 검증 대상인
`register_real_condition_callback` / `unregister_real_condition_callback` /
`_on_receive_real_condition` (콜백 디스패치)는 **실제 코드**를 그대로 실행한다.
"""
import os
import sys
import types

# 프로젝트 루트를 import 경로에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _install_pyqt5_stub():
    if "PyQt5" in sys.modules:
        return

    pyqt5 = types.ModuleType("PyQt5")

    # --- PyQt5.QAxContainer.QAxWidget ---
    qax = types.ModuleType("PyQt5.QAxContainer")

    class _QAxWidget:  # OCX 컨트롤 대체 (아무 동작도 하지 않음)
        def __init__(self, *a, **k):
            pass

        def setControl(self, *a, **k):
            pass

        def dynamicCall(self, *a, **k):
            return ""

    qax.QAxWidget = _QAxWidget

    # --- PyQt5.QtCore.QEventLoop ---
    qtcore = types.ModuleType("PyQt5.QtCore")

    class _QEventLoop:
        def exec_(self):
            return 0

        def quit(self):
            pass

    qtcore.QEventLoop = _QEventLoop

    pyqt5.QAxContainer = qax
    pyqt5.QtCore = qtcore
    sys.modules["PyQt5"] = pyqt5
    sys.modules["PyQt5.QAxContainer"] = qax
    sys.modules["PyQt5.QtCore"] = qtcore


_install_pyqt5_stub()
