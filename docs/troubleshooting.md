# Диагностика `review-tasks`

## `review-tasks` не находится в PATH

```powershell
python -m pipx ensurepath
```

Откройте новый терминал и проверьте установку:

```powershell
python -m pipx list
python -m pipx environment --value PIPX_BIN_DIR
Get-Command review-tasks
```

До обновления `PATH` entry point можно проверить по точному пути:

```powershell
$reviewTasksBin = python -m pipx environment --value PIPX_BIN_DIR
& (Join-Path $reviewTasksBin "review-tasks.exe") --help
```

После этого добавьте фактический `PIPX_BIN_DIR` в User PATH, если `ensurepath`
его не добавил, и перезапустите IDE/терминал. Проверьте `review-tasks --help`
из будущего workspace и окружения запуска сервиса. Не подменяйте весь PATH.

Если пакета нет в списке pipx, установите его из нужного Release. Если пакет
есть, но entry point отсутствует, выполните `python -m pipx reinstall review-tasks`
и повторите проверку. Ошибка `No module named review_tasks` при системном
`python -m review_tasks` после pipx означает другое окружение Python.
Если работает только `python -m review_tasks`, setup не завершён: требуется
работающий executable `review-tasks`, доступный по PATH. Для выбранного venv
проверьте установку пакета и доступность его Scripts directory в каждом
окружении запуска.

## Local service не видит CLI

Путь к `review-tasks` можно задать явно:

```powershell
$env:REVIEW_TASKS_CLI_BIN = (Get-Command review-tasks).Source
```

Если сервис не видит `review-tasks`, `codex`, `agent` или `opencode`, проверьте
`PATH`, итоговые настройки сервиса и пути к agent CLI.

После изменения Windows User/System env перезапустите IDE или терминал,
из которого запускаете сервис, затем сам сервис. Старый родительский процесс
может передать новому сервису старые значения. Внешние токены проверяйте только
как `present` / `missing`, не выводите их значения.
