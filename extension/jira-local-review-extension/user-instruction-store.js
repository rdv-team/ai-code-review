(function attachUserInstructionStore(root) {
  "use strict";

  const MAX_LENGTH = 2000;
  const STORAGE_PREFIX = "rdv:user-instruction:";
  const TRUSTED_STORAGE_ACCESS = "TRUSTED_CONTEXTS";

  class UserInstructionError extends Error {
    constructor(code) {
      super(code);
      this.name = "UserInstructionError";
      this.code = code;
    }
  }

  function isValidIssueKey(issueKey) {
    return Boolean(
      typeof issueKey === "string" &&
      root.RdvIssue &&
      root.RdvIssue.ISSUE_RE instanceof RegExp &&
      root.RdvIssue.ISSUE_RE.test(issueKey)
    );
  }

  function requireIssueKey(issueKey) {
    if (!isValidIssueKey(issueKey)) {
      throw new UserInstructionError("invalid_issue_key");
    }
    return issueKey;
  }

  function storageKey(issueKey) {
    return `${STORAGE_PREFIX}${requireIssueKey(issueKey)}`;
  }

  async function ensureTrustedStorageAccess(storageArea) {
    if (!storageArea || typeof storageArea.setAccessLevel !== "function") {
      throw new UserInstructionError("storage_access_unavailable");
    }
    await storageArea.setAccessLevel({ accessLevel: TRUSTED_STORAGE_ACCESS });
    return true;
  }

  function normalizeInstruction(value) {
    if (typeof value !== "string") {
      throw new UserInstructionError("invalid_type");
    }
    return value.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  }

  function codePointCount(value) {
    return Array.from(normalizeInstruction(value)).length;
  }

  function validateInstruction(value) {
    const normalized = normalizeInstruction(value);
    if (normalized.length === 0) {
      throw new UserInstructionError("empty");
    }
    if (codePointCount(normalized) > MAX_LENGTH) {
      throw new UserInstructionError("too_long");
    }
    if (normalized.includes("\0")) {
      throw new UserInstructionError("nul");
    }
    return normalized;
  }

  async function load(storageArea, issueKey) {
    const key = storageKey(issueKey);
    const stored = await storageArea.get(key);
    if (!stored || !Object.prototype.hasOwnProperty.call(stored, key)) {
      return null;
    }
    return validateInstruction(stored[key]);
  }

  async function remove(storageArea, issueKey) {
    await storageArea.remove(storageKey(issueKey));
    return null;
  }

  async function save(storageArea, issueKey, value) {
    requireIssueKey(issueKey);
    const normalized = normalizeInstruction(value);
    if (normalized === "") {
      return remove(storageArea, issueKey);
    }
    const validated = validateInstruction(normalized);
    await storageArea.set({ [storageKey(issueKey)]: validated });
    return validated;
  }

  function issueKeyFromLocation(locationRef) {
    try {
      const issueKey = new URL(locationRef.href).searchParams.get("issueKey") || "";
      return isValidIssueKey(issueKey) ? issueKey : "";
    } catch (_error) {
      return "";
    }
  }

  function buildEditorUrl(issueKey, runtime) {
    if (!isValidIssueKey(issueKey) || !runtime || typeof runtime.getURL !== "function") {
      return "";
    }
    const url = new URL(runtime.getURL("instruction.html"));
    url.searchParams.set("issueKey", issueKey);
    return url.href;
  }

  const api = {
    MAX_LENGTH,
    STORAGE_PREFIX,
    TRUSTED_STORAGE_ACCESS,
    UserInstructionError,
    buildEditorUrl,
    codePointCount,
    ensureTrustedStorageAccess,
    isValidIssueKey,
    issueKeyFromLocation,
    load,
    normalizeInstruction,
    remove,
    save,
    storageKey,
    validateInstruction
  };
  root.RdvUserInstructionStore = api;
  if (typeof module !== "undefined") {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
