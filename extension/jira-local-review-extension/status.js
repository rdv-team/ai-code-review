(function attachStatus(root) {
  "use strict";

  const DETAIL_TEXT = {
    service_unavailable: "Локальный сервис не запущен",
    not_jira_issue: "Открыта не JIRA-задача",
    issue_detected: "Задача найдена",
    config_missing: "Нужно заполнить prefix config",
    config_ready: "Готово к ревью",
    previous_failed: "Предыдущий запуск завершился ошибкой",
    previous_cancelled: "Предыдущий запуск отменен",
    queued: "В очереди",
    preflight_running: "Проверяем окружение",
    init_running: "Готовим каталог ревью",
    init_done: "Каталог ревью подготовлен",
    review_starting: "Запускаем агента",
    review_running: "Агент выполняет ревью",
    postprocess_running: "Проверяем результат",
    handoff_required: "Каталог подготовлен, автоматический запуск не выполнялся",
    done: "Ревью выполнено",
    done_with_warnings: "Ревью выполнено с предупреждениями",
    already_done: "Ревью уже было выполнено",
    no_commits: "Нет новых коммитов для ревью",
    no_reviewable_files: "Нет подходящих файлов для ревью",
    summary_unavailable: "Отчет есть, сводка недоступна",
    init_failed: "Инициализация не выполнена",
    review_failed: "Ревью завершилось ошибкой",
    timeout: "Превышен timeout",
    cancelled: "Запуск отменен",
    already_running: "Ревью уже выполняется"
  };

  const RUNNING = new Set([
    "queued",
    "preflight_running",
    "init_running",
    "init_done",
    "review_starting",
    "review_running",
    "postprocess_running",
    "already_running"
  ]);
  const DONE = new Set(["done", "done_with_warnings", "already_done", "summary_unavailable"]);
  const ERROR = new Set([
    "service_unavailable",
    "previous_failed",
    "preflight_failed",
    "init_failed",
    "review_failed",
    "timeout",
    "service_error"
  ]);

  function displayStatus(detailStatus) {
    if (RUNNING.has(detailStatus)) {
      return "Выполняется";
    }
    if (DONE.has(detailStatus)) {
      return "Выполнено";
    }
    return "Новая";
  }

  function normalizeStatus(status) {
    const detailStatus = status && status.detailStatus ? status.detailStatus : "issue_detected";
    const error = status ? status.error : null;
    const feedback = status && status.feedback && typeof status.feedback === "object"
      ? status.feedback
      : error && typeof error === "object"
        ? {
            code: error.code || detailStatus,
            tone: "error",
            title: status && status.detailText ? status.detailText : DETAIL_TEXT[detailStatus] || "Не удалось выполнить операцию",
            message: error.message || "Проверьте технические детали и повторите попытку."
          }
        : null;
    return {
      displayStatus: status && status.displayStatus ? status.displayStatus : displayStatus(detailStatus),
      detailStatus,
      detailText: status && status.detailText ? status.detailText : DETAIL_TEXT[detailStatus] || detailStatus,
      availableActions: status && Array.isArray(status.availableActions) ? status.availableActions : [],
      issueKey: status ? status.issueKey : null,
      jobId: status ? status.jobId : null,
      startedAt: status ? status.startedAt : null,
      updatedAt: status ? status.updatedAt : null,
      durationSec: status ? status.durationSec : null,
      taskDir: status ? status.taskDir : null,
      runDir: status ? status.runDir : null,
      reportPath: status ? status.reportPath : null,
      reasoningPath: status ? status.reasoningPath : null,
      summary: status ? status.summary : null,
      tokenUsage: status ? status.tokenUsage : null,
      warnings: status && Array.isArray(status.warnings) ? status.warnings : [],
      manualCommand: status ? status.manualCommand : null,
      latestAttempt: status && status.latestAttempt && typeof status.latestAttempt === "object" ? status.latestAttempt : null,
      error,
      feedback,
      diagnostics: status && Array.isArray(status.diagnostics) ? status.diagnostics : []
    };
  }

  function isActiveStatus(status) {
    return RUNNING.has(normalizeStatus(status).detailStatus);
  }

  function iconState(status) {
    const normalized = normalizeStatus(status);
    if (DONE.has(normalized.detailStatus)) {
      return "done";
    }
    if (ERROR.has(normalized.detailStatus)) {
      return "error";
    }
    if (normalized.error && !["config_missing", "cancelled", "previous_cancelled"].includes(normalized.detailStatus)) {
      return "error";
    }
    if (isActiveStatus(normalized)) {
      return "running";
    }
    return "default";
  }

  const api = { DETAIL_TEXT, displayStatus, normalizeStatus, isActiveStatus, iconState };
  root.RdvReviewStatus = api;
  if (typeof module !== "undefined") {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
