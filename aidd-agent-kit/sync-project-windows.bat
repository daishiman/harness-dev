@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem AIDDキットの編集元を、このリポジトリの実行時配置へ反映する管理者用スクリプト。
rem Codex Skillは .agents\skills、custom agent TOMLは .codex\agents へ入る。

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"

echo AIDDキットをプロジェクトへ反映します: %PROJECT_ROOT%
echo   Codex skills: %PROJECT_ROOT%\.agents\skills
echo   Codex custom agents: %PROJECT_ROOT%\.codex\agents
echo.

set "AIDD_TARGET_HOME=%PROJECT_ROOT%"
set "AIDD_CODEX_TARGET=%PROJECT_ROOT%\.codex"
rem AIDD_NONINTERACTIVE=1 が親環境にあれば、setlocal内でもそのままinstallerへ引き継がれる。
call "%~dp0install-windows.bat" %*
set "RESULT=%ERRORLEVEL%"

endlocal & exit /b %RESULT%
