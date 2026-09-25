---
name: mcp-review-verification
description: "Обязательная внешняя проверка выводов BSL-ревью через MCP на Stage 2: документация платформы 1С, стандарты разработки v8std, БСП (SSL), проверка синтаксиса. Используй, когда вывод зависит от одного из этих источников."
license: MIT
compatibility: Requires review-tasks CLI and task-local MCP configuration.
metadata:
  author: review-tasks
  version: "1.0"
---

# Управление MCP

**Назначение:** Этот skill используется на Stage 2 для внешней `verification`. На Stage 1 не активируй этот skill и не вызывай MCP.

## Обязательный процесс

Выполни `review-tasks mcp-ready`. Если `False` или ошибка — не вызывай MCP: MCP-каналы — `unavailable`, итог — `limited_unverified` и продолжай локальную проверку. Если `True` — выполняй процесс ниже.

1. Сформулируй точный вопрос для ревью до вызова MCP.
2. Для каждого отдельного вопроса `verification` выбери одну `reference`. Один `finding` может требовать нескольких независимых вопросов `verification` и, соответственно, нескольких `references`.
3. Если ни одна `reference` не подходит однозначно, считай соответствующий MCP-контекст недоступным и явно пометь зависимый вывод как `непроверенный`.
4. Прочитай только выбранную `reference` и её `Registry server id`.
5. Получи только соответствующую task-local запись сервера: `review-tasks mcp-registry-entry --server-id <server-id>`.
6. Проверь, доступен ли хотя бы один инструмент из `expectedTools`. Выбери конкретный инструмент согласно правилам `reference` и вызови его с минимальным входом, достаточным для ответа на вопрос `verification`.
7. Если registry entry, сервер, необходимый инструмент или пригодный результат недоступны, запиши затронутый verification channel со `status: unavailable` и `verification_summary: limited_unverified`.
8. Не повторяй успешно выполненный MCP-вызов с тем же вопросом `verification` и теми же входными данными.

## Маршрутизация

| Вопрос                                 | Reference                                   |
| -------------------------------------- | ------------------------------------------- |
| Синтаксис небольшого BSL-фрагмента     | `references/bsl-syntax-check.md`            |
| API, сигнатура или поведение платформы | `references/platform-docs.md`               |
| Механизм или общий модуль БСП          | `references/ssl-library-search.md`          |
| v8std стандарты разработки 1С          | `references/v8std-standards-diagnostics.md` |

## Правила работы с MCP

* Не представляй вывод, зависящий от MCP, как подтверждённый, если соответствующий MCP-инструмент не был доступен или не вернул пригодный результат.
* У каждой MCP `reference` есть `Registry server id`. Используй его как точный параметр `--server-id` для `review-tasks mcp-registry-entry`.
* Не ищи `.review-tasks/mcp/registry.json` в родительских каталогах.
* Не выполняй полный read/scan/dump файла `registry.json`. Получай только одну запись через `review-tasks mcp-registry-entry`.
* Не создавай custom lookup scripts для чтения `registry`.
* Если `reference` выглядит релевантной, но запись в task-local реестре отсутствует, считай MCP-контекст недоступным и не придумывай замену.
* Рассматривай успешный результат MCP как подтверждающее свидетельство, но **не заменяй им чтение изменённого кода и сгенерированных артефактов задачи**.
