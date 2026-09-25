(function uiFeedbackMain(root) {
  "use strict";

  const ACTION_FEEDBACK_MS = 1500;

  function flashButtonFeedback(button, options) {
    const success = Boolean(options && options.success);
    const successLabel = (options && options.successLabel) || "Готово";
    const failLabel = (options && options.failLabel) || "Не удалось";
    const ms = (options && options.ms) || ACTION_FEEDBACK_MS;

    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    const originalLabel = button.dataset.defaultLabel;
    if (button._actionFeedbackTimer) {
      clearTimeout(button._actionFeedbackTimer);
    }
    button.disabled = true;
    button.classList.remove("action-done", "action-failed");
    button.classList.add(success ? "action-done" : "action-failed");
    button.textContent = success ? successLabel : failLabel;
    button._actionFeedbackTimer = setTimeout(() => {
      button.textContent = originalLabel;
      button.classList.remove("action-done", "action-failed");
      button.disabled = false;
      button._actionFeedbackTimer = null;
    }, ms);
  }

  const api = { flashButtonFeedback, ACTION_FEEDBACK_MS };
  root.RdvUiFeedback = api;

  if (typeof module !== "undefined") {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
