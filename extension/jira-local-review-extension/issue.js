(function attachIssue(root) {
  "use strict";

  const ISSUE_RE = /^[A-Z][A-Z0-9]+-\d+$/;

  function parseIssueFromUrl(rawUrl) {
    let url;
    try {
      url = new URL(rawUrl);
    } catch (_error) {
      return { ok: false, detailStatus: "not_jira_issue", issueKey: null, projectKey: null };
    }
    if (url.protocol !== "https:") {
      return { ok: false, detailStatus: "not_jira_issue", issueKey: null, projectKey: null };
    }
    const match = url.pathname.match(/^\/browse\/([A-Z][A-Z0-9]+-\d+)\/?$/i);
    if (!match) {
      return { ok: false, detailStatus: "not_jira_issue", issueKey: null, projectKey: null };
    }
    const issueKey = match[1].toUpperCase();
    if (!ISSUE_RE.test(issueKey)) {
      return { ok: false, detailStatus: "not_jira_issue", issueKey: null, projectKey: null };
    }
    return {
      ok: true,
      detailStatus: "issue_detected",
      issueKey,
      projectKey: issueKey.split("-", 1)[0],
      url: url.href
    };
  }

  function isJiraIssueUrl(rawUrl) {
    return parseIssueFromUrl(rawUrl).ok;
  }

  const api = { ISSUE_RE, parseIssueFromUrl, isJiraIssueUrl };
  root.RdvIssue = api;
  if (typeof module !== "undefined") {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
