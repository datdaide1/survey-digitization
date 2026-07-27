"""Create analysis-safe records using PII declarations from the schema."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from .schema import pii_question_ids


def to_analysis_record(record: Mapping[str, Any], schema: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(record))
    answers = result.get("answers")
    if isinstance(answers, dict):
        for qid in pii_question_ids(schema):
            answers.pop(qid, None)
    result.pop("source_images", None)
    return result
