"""Questionnaire schema helpers shared by extraction, review and analytics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator, Mapping


def load_schema(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not isinstance(value.get("questions"), list):
        raise ValueError("Schema must be an object with a questions array")
    return value


def data_rows(question: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [row for row in question.get("rows", []) if isinstance(row, Mapping) and row.get("code")]


def questions_by_page(schema: Mapping[str, Any]) -> dict[int, list[Mapping[str, Any]]]:
    result: dict[int, list[Mapping[str, Any]]] = {}
    for question in schema.get("questions", []):
        page = question.get("page")
        if isinstance(page, int):
            result.setdefault(page, []).append(question)
    return result


def pii_question_ids(schema: Mapping[str, Any]) -> set[str]:
    return {str(q["id"]) for q in schema.get("questions", []) if q.get("pii") is True}


def iter_output_fields(schema: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield stable output column definitions without survey-specific IDs."""
    for question in schema.get("questions", []):
        qid = str(question["id"])
        qtype = question.get("type")
        if question.get("per_page"):
            continue
        if qtype == "composite":
            for component in question.get("components", []):
                yield f"{qid}__{component['id']}", {"kind": "scalar", "path": [qid, "components", component["id"]]}
        elif qtype in {"matrix", "device_grid"}:
            for row in data_rows(question):
                if qtype == "device_grid":
                    for column in question.get("columns", []):
                        yield f"{qid}__{row['code']}__{column['code']}", {
                            "kind": "contains", "path": [qid, "rows", row["code"]], "code": column["code"]
                        }
                else:
                    yield f"{qid}__{row['code']}", {"kind": "scalar", "path": [qid, "rows", row["code"]]}
            extra = question.get("extra_option")
            if extra:
                yield f"{qid}__{extra['code']}", {"kind": "raw", "path": [qid, extra["code"]]}
        elif qtype == "multi_select":
            for option in question.get("options", []):
                yield f"{qid}__{option['code']}", {"kind": "contains", "path": [qid], "code": option["code"]}
        else:
            yield qid, {"kind": "scalar", "path": [qid]}
        subfields = question.get("subfield")
        if subfields:
            for item in subfields if isinstance(subfields, list) else [subfields]:
                yield f"{qid}__{item['id']}", {"kind": "scalar", "path": [qid, "subfield", item["id"]]}
        derived = question.get("derived_subfield")
        if derived:
            for item in derived if isinstance(derived, list) else [derived]:
                yield f"{qid}__{item['id']}", {"kind": "scalar", "path": [qid, "derived_subfield", item["id"]]}
