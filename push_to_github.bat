@echo off
chcp 65001 > nul
echo ========================================================
echo   Отправка коммитов в https://github.com/k11298379-sudo/vadim.git
echo ========================================================
echo.
git push vadim main
if %errorlevel% neq 0 (
    echo.
    echo Если требуется токен доступа (PAT), введите:
    set /p GHTOKEN="GitHub Personal Access Token: "
    git push https://k11298379-sudo:%GHTOKEN%@github.com/k11298379-sudo/vadim.git main
)
echo.
pause
