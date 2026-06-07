@echo off
chcp 65001 >nul
REM ============================================
REM  Windows 시작프로그램 등록
REM  PC를 켤 때 자동매매가 자동 실행되도록 합니다.
REM ============================================

set SCRIPT_DIR=%~dp0
set STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set SHORTCUT=%STARTUP_DIR%\키움자동매매.lnk

echo 시작프로그램에 등록합니다...

powershell -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%SHORTCUT%'); ^
   $s.TargetPath = '%SCRIPT_DIR%run.bat'; ^
   $s.WorkingDirectory = '%SCRIPT_DIR%'; ^
   $s.Save()"

if exist "%SHORTCUT%" (
    echo [완료] 시작프로그램에 등록되었습니다.
    echo 해제하려면 uninstall_autostart.bat 을 실행하세요.
) else (
    echo [오류] 등록에 실패했습니다.
)
pause
