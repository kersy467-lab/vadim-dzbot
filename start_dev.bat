@echo off
chcp 65001 > nul
title Тестовый Бот 11 «Б» (Dev - Localhost)
echo ========================================================
echo   Запуск тестового бота (Dev) на порту 8001
echo   - Локальный режим разработки (Localhost)
echo   - Mini App: http://localhost:8001/app
echo   - Telegram API проксируется через Cloudflare Worker
echo ========================================================
echo.
cd /d "%~dp0"
python -m backend.main
pause
