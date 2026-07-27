"""Generic schema-to-table transformation."""

from __future__ import annotations

from typing import Any, Mapping

from .schema import iter_output_fields, pii_question_ids


def _entry_value(value: Any) -> Any:
    return value.get("value") if isinstance(value, Mapping) and "value" in value else value


def _lookup(record: Mapping[str, Any], path: list[str]) -> Any:
    value: Any = record.get("answers", {})
    for segment in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(segment)
    return value


def _cell(value: Any) -> Any:
    value = _entry_value(value)
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return value


def flatten_record(record: Mapping[str, Any], schema: Mapping[str, Any], *, include_pii: bool = False, manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"record_id": record.get("record_id")}
    for key, value in (manifest or {}).items():
        if key not in {"record_id", "source_path"}:
            result[f"meta__{key}"] = value
    pii = pii_question_ids(schema)
    for column, spec in iter_output_fields(schema):
        qid = spec["path"][0]
        if not include_pii and qid in pii:
            continue
        raw = _lookup(record, spec["path"])
        if spec["kind"] == "contains":
            value = _entry_value(raw)
            result[column] = None if value is None else int(spec["code"] in (value if isinstance(value, list) else [value]))
        else:
            result[column] = _cell(raw)
    return result
