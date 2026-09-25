---
name: review-start-task
description: Автономное поэтапное ревью одной подготовленной задачи.
license: MIT
compatibility: Требуется Python 3.
metadata:
  author: review-tasks
  version: "5.0"
---

Выполни автономное поэтапное ревью одной подготовленной задачи. Skill работает только внутри каталога задачи.

---

**Вход**: каталог задачи `<reviews_root>/<TASK>`. Пример: `/review-tasks/RDV-123`.

1. Выполни `review-tasks check-ready`.
2. Если команда вывела `True`, без дополнительного сообщения о структуре каталога выполни описанный ниже процесс ревью.
3. Если команда вывела `False` или завершилась с ошибкой, заверши процесс, не читая staged prompts или BSL input; при наличии диагностики сообщи её.

## Жизненный цикл

1. **ОБЯЗАТЕЛЬНО** применяй правила из уже загруженного `AGENTS.md` и не читай его повторно.
2. **Стадия 1.** Выполни `_review_info/review_prompt_stage1.md` с `_review_info/review_bsl.md`, используя основную команду CLI `review-tasks` и подкоманды `stage1-*`. К Stage 2 переходи только после успешного завершения и валидации Stage 1.
3. **Стадия 2.** Получи кандидатов через `review-tasks stage1-list-candidates` и выполни `_review_info/review_prompt_stage2.md`, используя основную команду CLI `review-tasks` и подкоманды `stage2-*`.
4. После успешного завершения и валидации Stage 2 выполни рендеринг отчёта согласно `_review_info/review_prompt_stage2.md`. Только после успешного рендеринга выполни `review-tasks set-status` без аргументов.

У всех команд есть `--help`, например: `review-tasks --help`.

## Ограничения

**Запрещено** читать файл `_review_info/review_prompt_stage2.md` перед выполнением и при выполнении Stage 1 и пока не выполнил все условия `_review_info/review_prompt_stage1.md`.
