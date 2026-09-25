@echo off
setlocal EnableExtensions EnableDelayedExpansion

chcp 65001 >nul 2>nul
title RDV - настройка локального сервиса ревью из Jira

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
echo RDV - настройка локального сервиса ревью из Jira
echo Сохраняет service.json; для запуска используйте start-jira-local-review-service.bat
echo.
echo Подсказки: Enter — значение в ^[скобках^]; y/n — да/нет на вопросах ^[y/N^].
echo.

echo --- [1/4] Сервис ---
echo.

set "DEFAULT_REVIEW_TASKS_CMD=review-tasks"
where review-tasks >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if not errorlevel 1 (
    if exist "%SCRIPT_DIR%src\review_tasks\__main__.py" (
      set "DEFAULT_REVIEW_TASKS_CMD=python -m review_tasks"
    )
  )
)

set /p "REVIEW_TASKS_CMD=Команда review-tasks [%DEFAULT_REVIEW_TASKS_CMD%]: "
if "%REVIEW_TASKS_CMD%"=="" set "REVIEW_TASKS_CMD=%DEFAULT_REVIEW_TASKS_CMD%"

set "DEFAULT_HOST=127.0.0.1"
set /p "SERVICE_HOST=Адрес сервиса (host) [%DEFAULT_HOST%]: "
if "%SERVICE_HOST%"=="" set "SERVICE_HOST=%DEFAULT_HOST%"

set "DEFAULT_PORT=8765"
set /p "SERVICE_PORT=Порт [%DEFAULT_PORT%]: "
if "%SERVICE_PORT%"=="" set "SERVICE_PORT=%DEFAULT_PORT%"

set "DEFAULT_TOKEN=%REVIEW_TASKS_SERVICE_TOKEN%"
if "%DEFAULT_TOKEN%"=="" (
  set "TOKEN_PROMPT=Token для расширения Chrome [сгенерировать новый]: "
) else (
  set "TOKEN_PROMPT=Token для расширения Chrome [%DEFAULT_TOKEN%]: "
)
set /p "SERVICE_TOKEN=!TOKEN_PROMPT!"
if "%SERVICE_TOKEN%"=="" set "SERVICE_TOKEN=%DEFAULT_TOKEN%"
if "%SERVICE_TOKEN%"=="" (
  for /f "usebackq delims=" %%G in (`powershell -NoProfile -Command "[guid]::NewGuid().ToString()" 2^>nul`) do set "SERVICE_TOKEN=%%G"
)
if "%SERVICE_TOKEN%"=="" set "SERVICE_TOKEN=%RANDOM%-%RANDOM%-%RANDOM%-%RANDOM%"
set "REVIEW_TASKS_SERVICE_TOKEN=%SERVICE_TOKEN%"
echo   ^(скопируйте в popup: Локальный сервис -^> Token^)
echo.

echo --- [2/4] Агенты для фонового ревью (необязательно) ---
echo IDE ^(Codex / Cursor / OpenCode^) выбирается в расширении, не здесь.
echo Это не выбор IDE: здесь только проверка CLI.
echo Если codex/agent/opencode есть в PATH, путь вводить не нужно.
echo.

call :prompt_optional_executable "Codex CLI" codex REVIEW_TASKS_CODEX_BIN CODEX_BIN
call :prompt_optional_executable "Cursor Agent CLI" agent REVIEW_TASKS_CURSOR_BIN CURSOR_BIN
call :prompt_optional_executable "OpenCode CLI" opencode REVIEW_TASKS_OPENCODE_BIN OPENCODE_BIN

set "DEFAULT_CURSOR_MODEL=%REVIEW_TASKS_CURSOR_MODEL%"
if "%DEFAULT_CURSOR_MODEL%"=="" set "DEFAULT_CURSOR_MODEL=composer-2.5-fast"
set /p "CURSOR_MODEL=Модель Cursor Agent [%DEFAULT_CURSOR_MODEL%]: "
if "%CURSOR_MODEL%"=="" set "CURSOR_MODEL=%DEFAULT_CURSOR_MODEL%"
set "REVIEW_TASKS_CURSOR_MODEL=%CURSOR_MODEL%"
echo   ^(используется только для IDE Cursor^)
echo.

echo --- [3/4] GitLab MR discovery (необязательно) ---
echo Service ищет MR через GitLab API. Сам token здесь не вводится.
echo Укажите только имя переменной окружения ^(tokenEnv^); значение задаётся в env сервиса.
echo Можно добавить несколько instances ^(gitlab.com и self-hosted^).
echo.

set "GITLAB_INSTANCE_ARGS="
set "GITLAB_INDEX=0"
set "DEFAULT_GITLAB_BASE_URL=https://gitlab.com"
set "DEFAULT_GITLAB_TOKEN_ENV=RDV_GITLAB_API_TOKEN_REVIEW"

set "GITLAB_CONFIGURE="
set /p "GITLAB_CONFIGURE=Настроить GitLab MR discovery? [y/N]: "
if /I not "!GITLAB_CONFIGURE!"=="y" if /I not "!GITLAB_CONFIGURE!"=="yes" goto gitlab_instance_done
echo.

:gitlab_instance_prompt
set "GITLAB_BASE_URL="
if "!GITLAB_INDEX!"=="0" (
  set /p "GITLAB_BASE_URL=GitLab baseUrl [%DEFAULT_GITLAB_BASE_URL%]: "
  if "!GITLAB_BASE_URL!"=="" set "GITLAB_BASE_URL=%DEFAULT_GITLAB_BASE_URL%"
) else (
  set "GITLAB_ADD_ANOTHER="
  set /p "GITLAB_ADD_ANOTHER=Добавить ещё один GitLab instance? [y/N]: "
  if /I not "!GITLAB_ADD_ANOTHER!"=="y" if /I not "!GITLAB_ADD_ANOTHER!"=="yes" goto gitlab_instance_done
  set /p "GITLAB_BASE_URL=GitLab baseUrl: "
  if "!GITLAB_BASE_URL!"=="" (
    echo   baseUrl обязателен; instance не добавлен.
    echo.
    goto gitlab_instance_prompt
  )
)

set "DEFAULT_GITLAB_API=%GITLAB_BASE_URL%/api/v4"
set /p "GITLAB_API_BASE_URL=GitLab apiBaseUrl [%DEFAULT_GITLAB_API%]: "
if "%GITLAB_API_BASE_URL%"=="" set "GITLAB_API_BASE_URL=%DEFAULT_GITLAB_API%"

set "GITLAB_TOKEN_ENV="
set /p "GITLAB_TOKEN_ENV=Имя переменной окружения с token GitLab [%DEFAULT_GITLAB_TOKEN_ENV%]: "
if "%GITLAB_TOKEN_ENV%"=="" set "GITLAB_TOKEN_ENV=%DEFAULT_GITLAB_TOKEN_ENV%"
if "%GITLAB_TOKEN_ENV%"=="" (
  echo   tokenEnv обязателен; instance пропущен.
  echo.
  goto gitlab_instance_prompt
)

set /a GITLAB_INDEX+=1
set "GITLAB_ID="
for /f "usebackq delims=" %%G in (`powershell -NoProfile -Command "$u=[uri]'%GITLAB_BASE_URL%'; (($u.Host -replace '^www\\.','') -replace '[^A-Za-z0-9]+','-').Trim('-').ToLower()" 2^>nul`) do set "GITLAB_ID=%%G"
if "%GITLAB_ID%"=="" set "GITLAB_ID=gitlab-%GITLAB_INDEX%"
set "GITLAB_INSTANCE_ARGS=%GITLAB_INSTANCE_ARGS% --gitlab-instance "%GITLAB_BASE_URL%" "%GITLAB_API_BASE_URL%" "%GITLAB_TOKEN_ENV%""
set "GITLAB_SUMMARY_%GITLAB_INDEX%=%GITLAB_ID%: %GITLAB_BASE_URL% -> %GITLAB_API_BASE_URL% (tokenEnv=%GITLAB_TOKEN_ENV%)"
echo   добавлен instance id: !GITLAB_ID!
echo.
goto gitlab_instance_prompt

:gitlab_instance_done
echo --- [4/4] Сводка ---
echo.

echo ========== Готово к записи service.json ==========
echo   URL:     http://%SERVICE_HOST%:%SERVICE_PORT%
echo   Token:   %SERVICE_TOKEN%
echo            -^> popup: Локальный сервис -^> Token
echo.
if defined CODEX_BIN (
  echo   Codex:   %CODEX_BIN%
) else (
  echo   Codex:   не настроен ^(ревью через Codex не запустится^)
)
if defined CURSOR_BIN (
  echo   Cursor:  %CURSOR_BIN%
) else (
  echo   Cursor:  не настроен ^(ревью через Cursor не запустится^)
)
if defined OPENCODE_BIN (
  echo   OpenCode: %OPENCODE_BIN%
) else (
  echo   OpenCode: не настроен ^(ревью через OpenCode не запустится^)
)
echo   Модель:  %CURSOR_MODEL%
echo.
if defined GITLAB_INSTANCE_ARGS (
  echo   GitLab instances:
  for /L %%I in (1,1,%GITLAB_INDEX%) do call echo     %%GITLAB_SUMMARY_%%I%%
  echo.
  echo   Задайте указанные tokenEnv переменные окружения и перезапустите сервис после изменения env.
) else (
  echo   GitLab instances: не настроены ^(MR discovery вернёт gitlab_instances_not_configured^)
)
echo.
echo   Enter - записать service.json. Ctrl+C - отменить.
echo ========================================
echo.
set /p "START_CONFIRM=Нажмите Enter для записи... "

echo Запись service.json...
echo.

set "CONFIG_CMD=%REVIEW_TASKS_CMD% local-service config --host "%SERVICE_HOST%" --port %SERVICE_PORT% --token "%SERVICE_TOKEN%" --cursor-model "%CURSOR_MODEL%""
if defined REVIEW_TASKS_CODEX_BIN set "CONFIG_CMD=%CONFIG_CMD% --codex-bin "%REVIEW_TASKS_CODEX_BIN%""
if defined REVIEW_TASKS_CURSOR_BIN set "CONFIG_CMD=%CONFIG_CMD% --cursor-bin "%REVIEW_TASKS_CURSOR_BIN%""
if defined REVIEW_TASKS_OPENCODE_BIN set "CONFIG_CMD=%CONFIG_CMD% --opencode-bin "%REVIEW_TASKS_OPENCODE_BIN%""
if defined GITLAB_INSTANCE_ARGS set "CONFIG_CMD=%CONFIG_CMD%%GITLAB_INSTANCE_ARGS%"
%CONFIG_CMD%
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if %EXIT_CODE% equ 0 (
  echo service.json сохранён. Запуск сервиса: start-jira-local-review-service.bat
) else (
  echo local-service config завершился с кодом %EXIT_CODE%.
)
popd >nul 2>nul
pause
exit /b %EXIT_CODE%

:prompt_optional_executable
set "HUMAN_LABEL=%~1"
set "WHERE_NAME=%~2"
set "ENV_VAR=%~3"
set "OUT_VAR=%~4"

set "ENV_BIN="
set "DEFAULT_BIN="
set "DEFAULT_SOURCE="
set "PATH_AVAILABLE="
call set "ENV_BIN=%%%ENV_VAR%%%"

where !WHERE_NAME! >nul 2>nul
if not errorlevel 1 set "PATH_AVAILABLE=1"

echo !HUMAN_LABEL!
if not "!ENV_BIN!"=="" (
  set "DEFAULT_BIN=!ENV_BIN!"
  set "DEFAULT_SOURCE=env"
  echo   настроено через !ENV_VAR!: !DEFAULT_BIN!
  echo   Enter — оставить; n — не настраивать; или укажите полный путь.
  goto prompt_optional_executable_read
) else if defined PATH_AVAILABLE (
  set "!ENV_VAR!="
  set "!OUT_VAR!=!WHERE_NAME! из PATH"
  echo   найдено в PATH: !WHERE_NAME!
  echo   ^(будет использована команда !WHERE_NAME! из PATH^)
  echo.
  exit /b 0
) else (
  echo   не найдено в PATH: !WHERE_NAME!
  echo   Enter — пропустить; или укажите полный путь.
)

:prompt_optional_executable_read
set "ENTERED_BIN="
set /p "ENTERED_BIN=> "
set "ENTERED_FROM_DEFAULT="
set "SKIP_AGENT="
if /I "!ENTERED_BIN!"=="n" set "SKIP_AGENT=1"
if /I "!ENTERED_BIN!"=="no" set "SKIP_AGENT=1"
if /I "!ENTERED_BIN!"=="skip" set "SKIP_AGENT=1"
if "!ENTERED_BIN!"=="-" set "SKIP_AGENT=1"
if defined SKIP_AGENT set "ENTERED_BIN="
if not defined SKIP_AGENT if "!ENTERED_BIN!"=="" (
  set "ENTERED_BIN=!DEFAULT_BIN!"
  set "ENTERED_FROM_DEFAULT=1"
)

set "HAS_SLASH="
if not "!ENTERED_BIN:\=!"=="!ENTERED_BIN!" set "HAS_SLASH=1"
if not "!ENTERED_BIN:/=!"=="!ENTERED_BIN!" set "HAS_SLASH=1"
if not "!ENTERED_BIN::=!"=="!ENTERED_BIN!" set "HAS_SLASH=1"
if not defined ENTERED_FROM_DEFAULT if not "!ENTERED_BIN!"=="" if not defined HAS_SLASH if /I not "!ENTERED_BIN!"=="!WHERE_NAME!" (
  echo   ^(значение "!ENTERED_BIN!" не принято: ожидалась команда !WHERE_NAME! или полный путь^)
  set "ENTERED_BIN=!DEFAULT_BIN!"
)
if not defined ENTERED_FROM_DEFAULT if not "!ENTERED_BIN!"=="" if not defined HAS_SLASH if /I "!ENTERED_BIN!"=="!WHERE_NAME!" if not defined PATH_AVAILABLE (
  echo   ^(значение "!ENTERED_BIN!" не принято: команда !WHERE_NAME! не найдена в PATH; укажите полный путь^)
  set "ENTERED_BIN=!DEFAULT_BIN!"
)

if not "!ENTERED_BIN!"=="" (
  if /I "!ENTERED_BIN!"=="!WHERE_NAME!" (
    if defined PATH_AVAILABLE (
      set "!ENV_VAR!="
      set "!OUT_VAR!=!WHERE_NAME! из PATH"
      echo   ^(будет использована команда !WHERE_NAME! из PATH^)
    ) else (
      set "!ENV_VAR!=!ENTERED_BIN!"
      set "!OUT_VAR!=!ENTERED_BIN!"
      echo   ^(будет использован: !ENTERED_BIN!^)
    )
  ) else (
    set "!ENV_VAR!=!ENTERED_BIN!"
    set "!OUT_VAR!=!ENTERED_BIN!"
    echo   ^(будет использован: !ENTERED_BIN!^)
  )
) else (
  set "!ENV_VAR!="
  set "!OUT_VAR!="
  echo   ^(пропущено - ревью через эту IDE не запустится^)
)
echo.
exit /b 0
