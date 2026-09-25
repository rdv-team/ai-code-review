"""SGR YAML schema — single source of truth for review_result.yaml structure.

Public surface:

- ``ReviewResponse`` — renderer-owned compatibility projection.
- ``translate_validation_error`` — преобразует ``pydantic.ValidationError`` в
  ``ReviewYamlError`` с русскими сообщениями (используется
  ``review_tasks.review_result.review_yaml.validate_review_yaml_text``).
- ``FOCUS_AREA_CATALOG`` — упорядоченный каталог SGR-областей с
  описаниями и ссылками на источники стандартов.
- ``render_focus_areas_list``, ``render_sgr_response_skeleton_body``,
  ``render_field_constraints_note`` — чистые функции, рендерящие
  Markdown-фрагменты SGR-промпта из этой же схемы. Используются
  ``review_tasks.cli`` при сборке ``_review_info/review_prompt*.md``.
"""

from review_tasks.sgr_schema.enums import FOCUS_AREA_CATALOG
from review_tasks.sgr_schema.error_translation import (
    ReviewYamlError,
    translate_validation_error,
)
from review_tasks.sgr_schema.prompt_fragments import (
    render_field_constraints_note,
    render_focus_areas_list,
    render_sgr_response_skeleton_body,
)
from review_tasks.sgr_schema.stage_results import (
    ReviewResponse,
    ReviewStage1Result,
    ReviewStage2Result,
    RiskCandidate,
    StandardHints,
)

__all__ = [
    "FOCUS_AREA_CATALOG",
    "ReviewResponse",
    "ReviewStage1Result",
    "ReviewStage2Result",
    "RiskCandidate",
    "StandardHints",
    "ReviewYamlError",
    "render_field_constraints_note",
    "render_focus_areas_list",
    "render_sgr_response_skeleton_body",
    "translate_validation_error",
]
