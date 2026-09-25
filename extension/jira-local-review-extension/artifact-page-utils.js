(function artifactPageUtilsMain(root) {
  "use strict";

  function jobIdFromLocation(locationRef) {
    const params = new URL(locationRef.href).searchParams;
    return params.get("jobId") || "";
  }

  function issueKeyFromLocation(locationRef) {
    const params = new URL(locationRef.href).searchParams;
    return params.get("issueKey") || "";
  }

  function resolveArtifactLabel({ issueKeyFromUrl, issueKeyFromApi, jobId }) {
    const fromUrl = typeof issueKeyFromUrl === "string" ? issueKeyFromUrl.trim() : "";
    if (fromUrl) {
      return fromUrl;
    }
    const fromApi = typeof issueKeyFromApi === "string" ? issueKeyFromApi.trim() : "";
    if (fromApi) {
      return fromApi;
    }
    return jobId || "";
  }

  function buildReportPageTitle(label) {
    return label ? `[${label}] Отчет ревью` : "Отчет ревью";
  }

  function buildReasoningPageTitle(label) {
    return label ? `[${label}] Рассуждения ревью` : "Рассуждения ревью";
  }

  function buildArtifactPagePath(pageName, jobId, issueKey) {
    const params = new URLSearchParams();
    params.set("jobId", jobId);
    const normalizedIssueKey = typeof issueKey === "string" ? issueKey.trim() : "";
    if (normalizedIssueKey) {
      params.set("issueKey", normalizedIssueKey);
    }
    return `${pageName}?${params.toString()}`;
  }

  function buildReportPageUrl(jobId, runtime, issueKey) {
    const path = buildArtifactPagePath("report.html", jobId, issueKey);
    if (runtime && typeof runtime.getURL === "function") {
      return runtime.getURL(path);
    }
    return path;
  }

  function buildReasoningPageUrl(jobId, runtime, issueKey) {
    const path = buildArtifactPagePath("reasoning.html", jobId, issueKey);
    if (runtime && typeof runtime.getURL === "function") {
      return runtime.getURL(path);
    }
    return path;
  }

  function applyArtifactPageTitle(titleElement, kind, label) {
    const text = kind === "reasoning" ? buildReasoningPageTitle(label) : buildReportPageTitle(label);
    if (typeof document !== "undefined") {
      document.title = text;
    }
    if (titleElement) {
      titleElement.textContent = text;
    }
    return text;
  }

  const utils = {
    jobIdFromLocation,
    issueKeyFromLocation,
    resolveArtifactLabel,
    buildReportPageTitle,
    buildReasoningPageTitle,
    buildArtifactPagePath,
    buildReportPageUrl,
    buildReasoningPageUrl,
    applyArtifactPageTitle,
  };

  root.RdvArtifactPageUtils = utils;
  if (typeof module !== "undefined") {
    module.exports = utils;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
