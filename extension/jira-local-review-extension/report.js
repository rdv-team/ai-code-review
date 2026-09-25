/* global chrome, marked */
(function reportMain(root) {
  "use strict";

  const FRONT_MATTER_RE = /^---\r?\n[\s\S]*?\r?\n---\r?\n?/;

  const $ = (id) => document.getElementById(id);

  async function copyToClipboard(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return false;
    }
  }

  async function handleCopyClick(button, text) {
    const success = await copyToClipboard(text);
    root.RdvUiFeedback.flashButtonFeedback(button, {
      success,
      successLabel: "Скопировано",
      failLabel: "Не удалось",
    });
  }

  function stripFrontMatter(markdown) {
    if (!markdown) {
      return "";
    }
    return markdown.replace(FRONT_MATTER_RE, "");
  }

  function renderMarkdown(markdown, markedImpl) {
    const parser = markedImpl || (typeof marked !== "undefined" ? marked : null);
    if (!parser || typeof parser.parse !== "function") {
      return "";
    }
    if (typeof parser.setOptions === "function") {
      parser.setOptions({ gfm: true, breaks: false });
    }
    return parser.parse(stripFrontMatter(markdown));
  }

  async function getSettings() {
    const stored = await chrome.storage.local.get({ servicePort: 8765, serviceToken: "" });
    return { port: stored.servicePort, token: stored.serviceToken };
  }

  const pageUtils = root.RdvArtifactPageUtils;

  function jobIdFromLocation(locationRef) {
    return pageUtils.jobIdFromLocation(locationRef);
  }

  function issueKeyFromLocation(locationRef) {
    return pageUtils.issueKeyFromLocation(locationRef);
  }

  function renderError(message) {
    $("error").hidden = false;
    $("error").textContent = message;
  }

  async function init() {
    const jobId = jobIdFromLocation(window.location);
    if (!jobId) {
      renderError("jobId не указан.");
      return;
    }
    const issueKeyFromUrl = issueKeyFromLocation(window.location);
    pageUtils.applyArtifactPageTitle(
      $("title"),
      "report",
      pageUtils.resolveArtifactLabel({ issueKeyFromUrl, issueKeyFromApi: "", jobId }),
    );
    const api = new root.RdvLocalReviewApi.LocalReviewApi(await getSettings());
    try {
      const report = await api.getReport(jobId);
      const markdownSource = report.content || "";
      pageUtils.applyArtifactPageTitle(
        $("title"),
        "report",
        pageUtils.resolveArtifactLabel({
          issueKeyFromUrl,
          issueKeyFromApi: report.issueKey,
          jobId,
        }),
      );
      $("reportPath").textContent = report.reportPath || "";
      $("content").innerHTML = renderMarkdown(markdownSource);
      $("copyPath").addEventListener("click", () => handleCopyClick($("copyPath"), report.reportPath || ""));
      $("copyMarkdown").addEventListener("click", () => handleCopyClick($("copyMarkdown"), markdownSource));
    } catch (error) {
      renderError(error.message || String(error));
    }
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", init);
  }

  if (typeof module !== "undefined") {
    module.exports = {
      jobIdFromLocation,
      issueKeyFromLocation,
      stripFrontMatter,
      renderMarkdown,
      copyToClipboard,
      handleCopyClick,
    };
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
