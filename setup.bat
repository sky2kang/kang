@echo off
chcp 65001 >nul
REM ============================================
REM  키움 자동매매 - 초기 설치 스크립트
REM ============================================
echo.
echo ========================================
echo   키움 자동매매 설치를 시작합니다
echo ========================================
echo.

REM Python 설치 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [오류] Python이 설치되어 있지 않습니다.
    echo https://www.python.org 에서 Python 3.8~3.11 을 설치하세요.
    pause
    exit /b 1
)

echo [1/3] Python 패키지를 설치합니다...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo [오류] 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)

echo.
echo [2/3] 설정 마법사를 실행합니다...
python setup_wizard.py

echo.
echo [3/3] 설치 완료!
echo.
echo  - 자동매매 실행:    run.bat
echo  - 설정 다시하기:    python setup_wizard.py
echo.
pause
