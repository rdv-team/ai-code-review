(function contentMain() {
  "use strict";

  let refreshTimer = null;

  function sendRuntimeMessage(message) {
    try {
      chrome.runtime.sendMessage(message, () => {
        void chrome.runtime.lastError;
      });
    } catch {
      // Ignore transient extension reload/navigation races.
    }
  }

  function sendContext() {
    const context = window.RdvJiraExtractor.extractJiraContext(document, window.location.href);
    sendRuntimeMessage({ type: "jiraContext", context });
  }

  function scheduleContext(delayMs = 100) {
    if (refreshTimer !== null) {
      clearTimeout(refreshTimer);
    }
    refreshTimer = setTimeout(() => {
      refreshTimer = null;
      sendContext();
    }, delayMs);
  }

  sendContext();
  window.addEventListener("focus", sendContext);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      sendContext();
    }
  });
})();
