/* global chrome */
(function instructionEditorMain(root) {
  "use strict";

  const INVALID_ISSUE_MESSAGE =
    "Не указан корректный ключ Jira-задачи. Откройте редактор из popup поддерживаемой страницы /browse/ABC-123.";
  const state = {
    issueKey: "",
    savedValue: null,
    pending: false,
    conflict: false,
    externalValue: null,
    loadRequestId: 0,
    refreshRequestId: 0
  };
  const $ = (id) => document.getElementById(id);

  function characterCount(value) {
    return `${root.RdvUserInstructionStore.codePointCount(String(value || ""))} / ${root.RdvUserInstructionStore.MAX_LENGTH}`;
  }

  function draftValidationState(value) {
    const count = root.RdvUserInstructionStore.codePointCount(String(value || ""));
    return { count, overLimit: count > root.RdvUserInstructionStore.MAX_LENGTH };
  }

  function isDirty(draft, savedValue) {
    const canonicalDraft = root.RdvUserInstructionStore.normalizeInstruction(String(draft || ""));
    const canonicalSaved = savedValue === null
      ? ""
      : root.RdvUserInstructionStore.normalizeInstruction(savedValue);
    return canonicalDraft !== canonicalSaved;
  }

  function editorActionState({ draft, savedValue, pending, conflict }) {
    const validation = draftValidationState(draft);
    return {
      saveDisabled: Boolean(pending || conflict || validation.overLimit || !isDirty(draft, savedValue)),
      deleteDisabled: Boolean(pending || conflict || savedValue === null),
      conflictActionsHidden: !conflict,
      overwriteDisabled: Boolean(pending || validation.overLimit)
    };
  }

  function showMessage(kind, text) {
    const message = $("pageMessage");
    message.className = `message ${kind}`;
    message.textContent = text;
  }

  function showSaveStatus(kind, text) {
    const status = $("saveStatus");
    status.className = `save-status ${kind || ""}`.trim();
    status.textContent = text || "";
  }

  function renderActionState() {
    const actions = editorActionState({
      draft: $("instructionText").value,
      savedValue: state.savedValue,
      pending: state.pending,
      conflict: state.conflict
    });
    $("saveInstruction").disabled = actions.saveDisabled;
    $("deleteInstruction").disabled = actions.deleteDisabled;
    $("conflictPanel").hidden = actions.conflictActionsHidden;
    $("reloadCurrentInstruction").disabled = state.pending;
    $("overwriteInstruction").disabled = actions.overwriteDisabled;
  }

  function setPending(pending) {
    state.pending = pending;
    renderActionState();
  }

  function renderDraftState() {
    const draft = $("instructionText").value;
    const dirty = isDirty(draft, state.savedValue);
    const validation = draftValidationState(draft);
    $("characterCount").textContent = characterCount(draft);
    $("characterCount").classList.toggle("is-over-limit", validation.overLimit);
    $("draftValidation").hidden = !validation.overLimit;
    $("instructionText").setAttribute("aria-invalid", validation.overLimit ? "true" : "false");
    $("unsavedMarker").hidden = !dirty;
    document.title = `${state.issueKey || "Jira"}${dirty ? " *" : ""} · Инструкция агенту`;
    renderActionState();
    return dirty;
  }

  function clearConflict() {
    state.conflict = false;
    state.externalValue = null;
    renderActionState();
  }

  function enterConflict(externalValue) {
    state.conflict = true;
    state.externalValue = externalValue;
    showMessage(
      "validation",
      "Сохранённая инструкция изменилась после открытия страницы. Ваш текст оставлен без изменений."
    );
    showSaveStatus("validation", "Выберите, какую версию оставить.");
    renderDraftState();
  }

  async function persistDraft(storageArea, issueKey, draft) {
    return root.RdvUserInstructionStore.save(storageArea, issueKey, draft);
  }

  async function loadCurrentSnapshot(storageArea, issueKey) {
    const savedValue = await root.RdvUserInstructionStore.load(storageArea, issueKey);
    return { savedValue, draft: savedValue === null ? "" : savedValue };
  }

  async function persistDraftIfCurrent(storageArea, issueKey, baseline, draft) {
    const current = await root.RdvUserInstructionStore.load(storageArea, issueKey);
    if (current !== baseline) {
      return { saved: false, conflict: true, current };
    }
    const savedValue = await persistDraft(storageArea, issueKey, draft);
    return { saved: true, conflict: false, current: savedValue, savedValue };
  }

  async function deleteIfCurrent(storageArea, issueKey, baseline) {
    const current = await root.RdvUserInstructionStore.load(storageArea, issueKey);
    if (current !== baseline) {
      return { deleted: false, conflict: true, current };
    }
    await root.RdvUserInstructionStore.remove(storageArea, issueKey);
    return { deleted: true, conflict: false, current: null };
  }

  function reconcileExternalSnapshot(savedValue, draft, current) {
    if (current === savedValue) {
      return { changed: false, conflict: false, savedValue, draft };
    }
    if (isDirty(draft, savedValue)) {
      return { changed: true, conflict: true, savedValue, draft, current };
    }
    return {
      changed: true,
      conflict: false,
      savedValue: current,
      draft: current === null ? "" : current,
      current
    };
  }

  function applyExternalSnapshot(current) {
    if (current === state.savedValue) {
      if (state.conflict) {
        clearConflict();
        showMessage("success", "Сохранённая инструкция снова совпадает с открытой версией.");
        showSaveStatus("", "");
        renderDraftState();
      }
      return false;
    }
    const result = reconcileExternalSnapshot(state.savedValue, $("instructionText").value, current);
    if (result.conflict) {
      enterConflict(current);
      return true;
    }
    state.savedValue = result.savedValue;
    $("instructionText").value = result.draft;
    clearConflict();
    showMessage("success", "Актуальная сохранённая инструкция загружена.");
    showSaveStatus("success", "Обновлено из локального хранилища.");
    renderDraftState();
    return true;
  }

  async function loadInstruction() {
    const requestId = ++state.loadRequestId;
    setPending(true);
    showMessage("loading", `Загрузка инструкции для ${state.issueKey}…`);
    try {
      await root.RdvUserInstructionStore.ensureTrustedStorageAccess(chrome.storage.local);
      const snapshot = await loadCurrentSnapshot(chrome.storage.local, state.issueKey);
      if (requestId !== state.loadRequestId) {
        return false;
      }
      state.savedValue = snapshot.savedValue;
      $("instructionText").value = snapshot.draft;
      clearConflict();
      $("instructionForm").hidden = false;
      showMessage("success", snapshot.savedValue === null ? "Инструкция для этой задачи не задана." : "Сохранённая инструкция загружена.");
      showSaveStatus("", "");
      renderDraftState();
      $("instructionText").focus();
      return true;
    } catch (error) {
      if (requestId !== state.loadRequestId) {
        return false;
      }
      $("instructionForm").hidden = false;
      showMessage("error", `Не удалось прочитать локально сохранённую инструкцию. ${error.message || ""}`.trim());
      showSaveStatus("error", "Проверьте доступ к хранилищу и перезагрузите страницу.");
      $("instructionText").focus();
      return false;
    } finally {
      if (requestId === state.loadRequestId) {
        setPending(false);
      }
    }
  }

  function validationMessage(error) {
    if (!error || error.name !== "UserInstructionError") {
      return "Не удалось проверить инструкцию.";
    }
    if (error.code === "nul") {
      return "Удалите недопустимый NUL-символ.";
    }
    if (error.code === "too_long") {
      return "Сократите инструкцию до 2000 символов.";
    }
    return "Введите текст инструкции или используйте кнопку «Удалить».";
  }

  function confirmInstructionDeletion(confirmFn) {
    return Boolean(
      typeof confirmFn === "function" &&
      confirmFn("Удалить сохранённую инструкцию и текущий черновик? Это действие нельзя отменить.")
    );
  }

  async function saveInstruction(event) {
    if (event && typeof event.preventDefault === "function") {
      event.preventDefault();
    }
    const draft = $("instructionText").value;
    if (state.pending || state.conflict || !isDirty(draft, state.savedValue)) {
      return false;
    }
    const baseline = state.savedValue;
    let saved = false;
    let conflict = false;
    setPending(true);
    showSaveStatus("loading", "Проверка и сохранение…");
    try {
      const result = await persistDraftIfCurrent(chrome.storage.local, state.issueKey, baseline, draft);
      if (result.conflict) {
        conflict = true;
        enterConflict(result.current);
      } else {
        state.savedValue = result.savedValue;
        $("instructionText").value = result.savedValue === null ? "" : result.savedValue;
        clearConflict();
        showMessage("success", result.savedValue === null ? "Инструкция удалена." : "Инструкция сохранена и будет использоваться в следующих ревью этой задачи.");
        showSaveStatus("success", "Сохранено.");
        renderDraftState();
        saved = true;
      }
    } catch (error) {
      const validation = error && error.name === "UserInstructionError";
      showMessage(validation ? "validation" : "error", validation ? validationMessage(error) : `Не удалось сохранить инструкцию. ${error.message || ""}`.trim());
      showSaveStatus(validation ? "validation" : "error", "Изменения не сохранены. Текст оставлен для исправления.");
      renderDraftState();
    } finally {
      setPending(false);
    }
    if (conflict) {
      $("reloadCurrentInstruction").focus();
    }
    return saved;
  }

  async function deleteInstruction() {
    if (state.pending || state.conflict || state.savedValue === null) {
      return false;
    }
    if (!confirmInstructionDeletion(root.confirm)) {
      return false;
    }
    const draft = $("instructionText").value;
    const baseline = state.savedValue;
    let deleted = false;
    let conflict = false;
    setPending(true);
    showSaveStatus("loading", "Проверка и удаление…");
    try {
      const result = await deleteIfCurrent(chrome.storage.local, state.issueKey, baseline);
      if (result.conflict) {
        conflict = true;
        enterConflict(result.current);
      } else {
        state.savedValue = null;
        clearConflict();
        if ($("instructionText").value === draft) {
          $("instructionText").value = "";
        }
        showMessage("success", "Инструкция удалена. Следующие ревью будут запущены без неё.");
        showSaveStatus("success", "Удалено.");
        renderDraftState();
        $("instructionText").focus();
        deleted = true;
      }
    } catch (error) {
      showMessage("error", `Не удалось удалить инструкцию. ${error.message || ""}`.trim());
      showSaveStatus("error", "Удаление не выполнено. Текст оставлен без изменений.");
      renderDraftState();
    } finally {
      setPending(false);
    }
    if (conflict) {
      $("reloadCurrentInstruction").focus();
    }
    return deleted;
  }

  async function reloadCurrentInstruction() {
    if (state.pending) {
      return false;
    }
    setPending(true);
    showSaveStatus("loading", "Загрузка актуального значения…");
    try {
      const snapshot = await loadCurrentSnapshot(chrome.storage.local, state.issueKey);
      state.savedValue = snapshot.savedValue;
      $("instructionText").value = snapshot.draft;
      clearConflict();
      showMessage("success", "Актуальная сохранённая инструкция загружена. Локальный черновик заменён.");
      showSaveStatus("success", "Актуальная версия загружена.");
      renderDraftState();
      $("instructionText").focus();
      return true;
    } catch (error) {
      showMessage("error", `Не удалось загрузить актуальную инструкцию. ${error.message || ""}`.trim());
      showSaveStatus("error", "Локальный текст оставлен без изменений.");
      renderDraftState();
      return false;
    } finally {
      setPending(false);
    }
  }

  async function overwriteInstruction() {
    if (state.pending || !state.conflict) {
      return false;
    }
    const draft = $("instructionText").value;
    setPending(true);
    showSaveStatus("loading", "Сохранение поверх актуального значения…");
    try {
      const savedValue = await persistDraft(chrome.storage.local, state.issueKey, draft);
      state.savedValue = savedValue;
      $("instructionText").value = savedValue === null ? "" : savedValue;
      clearConflict();
      showMessage("success", savedValue === null ? "Актуальная инструкция удалена." : "Ваш текст сохранён поверх актуальной инструкции.");
      showSaveStatus("success", "Сохранено поверх.");
      renderDraftState();
      return true;
    } catch (error) {
      const validation = error && error.name === "UserInstructionError";
      showMessage(validation ? "validation" : "error", validation ? validationMessage(error) : `Не удалось сохранить инструкцию. ${error.message || ""}`.trim());
      showSaveStatus(validation ? "validation" : "error", "Локальный текст оставлен без изменений.");
      renderDraftState();
      return false;
    } finally {
      setPending(false);
    }
  }

  async function refreshExternalState() {
    if (state.pending || !state.issueKey) {
      return false;
    }
    const requestId = ++state.refreshRequestId;
    try {
      const current = await root.RdvUserInstructionStore.load(chrome.storage.local, state.issueKey);
      if (requestId !== state.refreshRequestId || state.pending) {
        return false;
      }
      return applyExternalSnapshot(current);
    } catch (error) {
      if (requestId !== state.refreshRequestId) {
        return false;
      }
      showMessage("error", `Не удалось проверить актуальность инструкции. ${error.message || ""}`.trim());
      showSaveStatus("error", "Локальный текст оставлен без изменений.");
      renderDraftState();
      return false;
    }
  }

  function handleStorageChanged(changes, areaName) {
    if (areaName !== "local" || !state.issueKey || state.pending) {
      return;
    }
    const key = root.RdvUserInstructionStore.storageKey(state.issueKey);
    if (changes && Object.prototype.hasOwnProperty.call(changes, key)) {
      void refreshExternalState();
    }
  }

  function handleBeforeUnload(event) {
    if (!isDirty($("instructionText").value, state.savedValue)) {
      return undefined;
    }
    event.preventDefault();
    event.returnValue = "";
    return "";
  }

  async function init() {
    state.issueKey = root.RdvUserInstructionStore.issueKeyFromLocation(window.location);
    if (!state.issueKey) {
      showMessage("error", INVALID_ISSUE_MESSAGE);
      return;
    }
    $("issueKey").textContent = state.issueKey;
    $("instructionForm").addEventListener("submit", saveInstruction);
    $("instructionText").addEventListener("input", () => {
      renderDraftState();
      showSaveStatus("", "");
    });
    $("deleteInstruction").addEventListener("click", deleteInstruction);
    $("reloadCurrentInstruction").addEventListener("click", reloadCurrentInstruction);
    $("overwriteInstruction").addEventListener("click", overwriteInstruction);
    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("focus", () => {
      void refreshExternalState();
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        void refreshExternalState();
      }
    });
    if (chrome.storage.onChanged && typeof chrome.storage.onChanged.addListener === "function") {
      chrome.storage.onChanged.addListener(handleStorageChanged);
    }
    renderDraftState();
    await loadInstruction();
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", init);
  }

  if (typeof module !== "undefined") {
    module.exports = {
      INVALID_ISSUE_MESSAGE,
      characterCount,
      confirmInstructionDeletion,
      deleteIfCurrent,
      draftValidationState,
      editorActionState,
      handleBeforeUnload,
      isDirty,
      loadCurrentSnapshot,
      persistDraft,
      persistDraftIfCurrent,
      reconcileExternalSnapshot,
      validationMessage
    };
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
