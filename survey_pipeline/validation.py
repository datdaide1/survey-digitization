"""Project-level schema and extraction validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


SUPPORTED_TYPES = {"text", "free_text", "single_select", "multi_select", "composite", "matrix", "device_grid"}


def validate_schema(schema: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    questions = schema.get("questions")
    if not isinstance(questions, list) or not questions:
        return ["questions must be a non-empty array"]
    ids: set[str] = set()
    total_pages = schema.get("total_pages")
    if not isinstance(total_pages, int) or total_pages < 1:
        errors.append("total_pages must be a positive integer")
        total_pages = 1
    for index, question in enumerate(questions):
        if not isinstance(question, Mapping):
            errors.append(f"questions[{index}] must be an object")
            continue
        qid = question.get("id")
        if not isinstance(qid, str) or not qid:
            errors.append(f"questions[{index}].id must be a non-empty string")
        elif qid in ids:
            errors.append(f"duplicate question id: {qid}")
        else:
            ids.add(qid)
        if question.get("type") not in SUPPORTED_TYPES:
            errors.append(f"{qid}: unsupported type {question.get('type')!r}")
        page = question.get("page")
        if not question.get("per_page") and (not isinstance(page, int) or not 1 <= page <= total_pages):
            errors.append(f"{qid}: page must be within 1..{total_pages}")
    return errors


def validate_records(schema: Mapping[str, Any], full_dir: str | Path) -> dict[str, list[str]]:
    from .record_validation import check_record

    result: dict[str, list[str]] = {}
    for path in sorted(Path(full_dir).glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            errors = check_record(dict(schema), record)
        except Exception as exc:
            errors = [f"Cannot read record: {exc}"]
        if errors:
            result[path.name] = errors
    return result
