@echo off
setlocal EnableExtensions

chcp 65001 >nul 2>nul
title RDV - локальный сервис ревью из Jira

set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%" >nul 2>nul
if exist "%SCRIPT_DIR%src\review_tasks\__main__.py" (
  if defined PYTHONPATH (
    set "PYTHONPATH=%SCRIPT_DIR%src;%PYTHONPATH%"
  ) else (
    set "PYTHONPATH=%SCRIPT_DIR%src"
  )
)

echo.
echo RDV - локальный сервис ревью из Jira
echo Окно должно оставаться открытым, пока работает сервис.
echo Настройка: config-jira-local-review-service.bat
echo.

set "REVIEW_TASKS_CMD=review-tasks"
where review-tasks >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if not errorlevel 1 (
    if exist "%SCRIPT_DIR%src\review_tasks\__main__.py" (
      set "REVIEW_TASKS_CMD=python -m review_tasks"
    )
  )
)

echo --- Параметры (service.json) ---
%REVIEW_TASKS_CMD% local-service config --show
if errorlevel 1 (
  echo.
  echo Не удалось прочитать service.json. Сначала запустите config-jira-local-review-service.bat
  popd >nul 2>nul
  pause
  exit /b 1
)
echo.

echo Запуск сервиса...
echo.

%REVIEW_TASKS_CMD% local-service
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo local-service завершился с кодом %EXIT_CODE%.
popd >nul 2>nul
pause
exit /b %EXIT_CODE%
