@echo off
chcp 65001 >nul
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\키움자동매매.lnk
if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [완료] 시작프로그램 등록이 해제되었습니다.
) else (
    echo 등록된 시작프로그램이 없습니다.
)
pause
