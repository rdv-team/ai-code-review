"""Нормализация сырого YAML-mapping к чистому findings-only контракту.

Вызывается после ``yaml.safe_load`` и до ``ReviewResponse.model_validate``.
Coerce только безопасное и сохраняющее решение keep/drop.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def normalize_review_result_mapping(
    data: dict[str, Any],
    *,
    source: str = "<input>",
) -> dict[str, Any]:
    """Приводит сырой mapping к чистому контракту без смены decision.

    Безопасные coercions для ``findings[]``:

    - ``decision: drop`` и непустой ``suggestion`` → ``suggestion: null``;
    - ``decision: drop`` и не-null ``severity`` → ``severity: null``.

    Остальные нарушения не чинятся: их отклоняет ``ReviewResponse.model_validate``.
    """
    normalized = deepcopy(data)
    findings = normalized.get("findings")
    if findings is None:
        return normalized
    if not isinstance(findings, list):
        return normalized

    for finding in findings:
        if not isinstance(finding, dict):
            continue
        self_check = finding.get("self_check")
        if not isinstance(self_check, dict):
            continue
        decision = self_check.get("decision")
        if decision == "drop":
            if finding.get("suggestion") is not None:
                finding["suggestion"] = None
            if finding.get("severity") is not None:
                finding["severity"] = None
    return normalized


__all__ = ["normalize_review_result_mapping"]
