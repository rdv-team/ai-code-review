(function attachExtractor(root) {
  "use strict";

  const TITLE_SELECTORS = [
    '[data-test-id="issue.views.issue-base.foundation.summary.heading"]',
    '[data-testid="issue.views.issue-base.foundation.summary.heading"]',
    "#summary-val",
    "h1"
  ];
  const DESCRIPTION_SELECTORS = [
    '[data-test-id="issue.views.field.rich-text.description"]',
    '[data-testid="issue.views.field.rich-text.description"]',
    "#description-val",
    ".user-content-block"
  ];

  function textFromSelector(documentRef, selectors) {
    for (const selector of selectors) {
      const element = documentRef.querySelector(selector);
      const text = element && element.textContent ? element.textContent.trim().replace(/\s+/g, " ") : "";
      if (text) {
        return text;
      }
    }
    return "";
  }

  function titleFromDocument(documentRef, issueKey) {
    const selected = textFromSelector(documentRef, TITLE_SELECTORS);
    if (selected) {
      return selected.replace(new RegExp(`^${issueKey}\\s*[-:]*\\s*`, "i"), "").trim();
    }
    const title = documentRef.title || "";
    return title.replace(issueKey, "").replace(/[-|].*$/, "").trim();
  }

  function extractJiraContext(documentRef, rawUrl) {
    const parsed = root.RdvIssue.parseIssueFromUrl(rawUrl);
    if (!parsed.ok) {
      return { ok: false, detailStatus: "not_jira_issue", url: rawUrl };
    }
    const description = textFromSelector(documentRef, DESCRIPTION_SELECTORS);
    return {
      ok: true,
      detailStatus: "issue_detected",
      issueKey: parsed.issueKey,
      projectKey: parsed.projectKey,
      url: parsed.url,
      title: titleFromDocument(documentRef, parsed.issueKey),
      description,
      descriptionDetected: Boolean(description)
    };
  }

  const api = {
    TITLE_SELECTORS,
    DESCRIPTION_SELECTORS,
    textFromSelector,
    extractJiraContext
  };
  root.RdvJiraExtractor = api;
  if (typeof module !== "undefined") {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
