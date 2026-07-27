"""Schema-driven extraction for the complete survey questionnaire.

This extends the original multiple-choice pilot to every printed field while
keeping the transport and filesystem at the edge. Each page is read twice and
disagreements are retained for review instead of being silently resolved.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .mc_extraction import (
    AnthropicHTTPClient,
    MCExtractionError,
    ModelOutputError,
    _assembly_pages_by_number,
    _resolve_page_image,
    _send_message,
    build_api_request,
    extract_tool_input,
    now_bangkok_iso,
    validate_record_id,
)

TOOL_NAME = "submit_full_page"
CONFIDENCE = ["cao", "trung_binh", "thap"]
FLAGS = [
    "ambiguous_mark", "needs_review", "multi_mark_on_single_select",
    "conflicting_answer", "exclusive_conflict", "margin_note",
]

SYSTEM_PROMPT = """Bạn số hóa phiếu khảo sát tiếng Việt từ ảnh.
Chỉ ghi nội dung nhìn thấy, không bịa hoặc sửa câu trả lời. Dùng đúng code trong
schema. Với chữ không chắc, ghi best-effort, confidence=thap và needs_review.
Luôn gọi tool submit_full_page đúng một lần."""


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


def _codes(items: Sequence[Mapping[str, Any]]) -> list[str]:
    values = [item.get("code") for item in items if item.get("code")]
    if not values or len(values) != len(set(values)):
        raise MCExtractionError("Schema có code rỗng hoặc trùng")
    return values


def _meta_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "confidence": {"type": "string", "enum": CONFIDENCE},
            "flags": {"type": "array", "items": {"type": "string", "enum": FLAGS}},
            "note": _nullable({"type": "string"}),
        },
        "required": ["confidence", "flags", "note"],
        "additionalProperties": False,
    }


def _scalar_value(question: Mapping[str, Any]) -> dict[str, Any]:
    qtype = question.get("type")
    if qtype in {"text", "free_text"}:
        return _nullable({"type": "string"})
    codes = _codes(question.get("options", []))
    if qtype == "multi_select":
        return _nullable({"type": "array", "items": {"type": "string", "enum": codes}})
    if qtype == "single_select":
        return {
            "anyOf": [
                {"type": "string", "enum": codes},
                {"type": "array", "items": {"type": "string", "enum": codes}},
                {"type": "null"},
            ]
        }
    raise MCExtractionError(f"Không hỗ trợ scalar type {qtype!r}")


def _optional_text_fields(question: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    subfields: list[Mapping[str, Any]] = []
    raw = question.get("subfield")
    if raw:
        subfields.extend(raw if isinstance(raw, list) else [raw])
    for option in question.get("options", []):
        if option.get("subfield"):
            subfields.append(option["subfield"])
    if subfields:
        fields["subfield"] = {
            "type": "object",
            "properties": {item["id"]: _nullable({"type": "string"}) for item in subfields},
            "required": [item["id"] for item in subfields],
            "additionalProperties": False,
        }
    derived = question.get("derived_subfield")
    if derived:
        defs = derived if isinstance(derived, list) else [derived]
        fields["derived_subfield"] = {
            "type": "object",
            "properties": {item["id"]: _nullable({"type": "string"}) for item in defs},
            "required": [item["id"] for item in defs],
            "additionalProperties": False,
        }
    if any(option.get("other_text") for option in question.get("options", [])):
        fields["other_text"] = _nullable({"type": "string"})
    return fields


def answer_schema(question: Mapping[str, Any]) -> dict[str, Any]:
    qtype = question.get("type")
    meta = _meta_schema()["properties"]
    properties: dict[str, Any] = dict(meta)
    required = ["confidence", "flags", "note"]
    if qtype == "composite":
        components = question.get("components", [])
        properties["components"] = {
            "type": "object",
            "properties": {component["id"]: _scalar_value(component) for component in components},
            "required": [component["id"] for component in components],
            "additionalProperties": False,
        }
        required.append("components")
    elif qtype in {"matrix", "device_grid"}:
        rows = [row for row in question.get("rows", []) if row.get("code")]
        columns = _codes(question.get("columns", []))
        properties["rows"] = {
            "type": "object",
            "properties": {
                row["code"]: _nullable({"type": "array", "items": {"type": "string", "enum": columns}})
                for row in rows
            },
            "required": [row["code"] for row in rows],
            "additionalProperties": False,
        }
        required.append("rows")
        extra = question.get("extra_option")
        if extra:
            properties[extra["code"]] = {"type": "boolean"}
            required.append(extra["code"])
    else:
        properties["value"] = _scalar_value(question)
        required.append("value")
        extra = _optional_text_fields(question)
        properties.update(extra)
        required.extend(extra)
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def page_questions(questionnaire: Mapping[str, Any], page: int) -> list[dict[str, Any]]:
    return [copy.deepcopy(q) for q in questionnaire.get("questions", []) if q.get("page") == page and not q.get("per_page")]


def build_tool(questionnaire: Mapping[str, Any], page: int) -> dict[str, Any]:
    questions = page_questions(questionnaire, page)
    if not questions:
        raise MCExtractionError(f"Schema không có câu ở trang {page}")
    properties = {
        "page_matches": {"type": "boolean"},
        "page_note": _nullable({"type": "string"}),
        **{q["id"]: answer_schema(q) for q in questions},
    }
    return {
        "name": TOOL_NAME,
        "description": "Kết quả số hóa đầy đủ một trang phiếu.",
        "strict": True,
        "input_schema": {
            "type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False,
        },
    }


def _prompt(questionnaire: Mapping[str, Any], page: int) -> str:
    questions = page_questions(questionnaire, page)
    compact = [{k: q[k] for k in q if k in {"id", "text", "type", "options", "components", "rows", "columns", "extra_option", "subfield", "derived_subfield", "row_content_column"}} for q in questions]
    return (
        f"Đọc trang {page}. Kiểm tra page_matches. Trả đủ mọi field kể cả null/rỗng. "
        "Matrix phải đọc theo nhãn hàng, không suy theo vị trí. page_note chỉ chứa chữ ngoài vùng câu hỏi. "
        "Q9 luôn trả cả hai derived field; quy đổi theo năm 2026 khi chỉ có một mốc.\n\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)
    )


def extract_page(client: Any, image: Path, questionnaire: Mapping[str, Any], page: int, model: str, max_tokens: int) -> dict[str, Any]:
    tool = build_tool(questionnaire, page)
    request = build_api_request(
        model=model, image_path=image, prompt=_prompt(questionnaire, page),
        tool=tool, max_tokens=max_tokens,
    )
    request["system"] = SYSTEM_PROMPT
    request["tool_choice"] = {"type": "tool", "name": TOOL_NAME}
    return extract_tool_input(_send_message(client, request))


def _canonical(value: Any) -> Any:
    if isinstance(value, list):
        return sorted((_canonical(v) for v in value), key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in sorted(value.items()) if k not in {"confidence", "flags", "note"}}
    return value


def merge_runs(first: Mapping[str, Any], second: Mapping[str, Any], qids: Sequence[str]) -> tuple[dict[str, Any], bool, str | None]:
    answers: dict[str, Any] = {}
    for qid in qids:
        if qid not in first or qid not in second:
            raise ModelOutputError(f"Model thiếu {qid}")
        value = copy.deepcopy(first[qid])
        flags = list(dict.fromkeys(value.get("flags", [])))
        if _canonical(first[qid]) != _canonical(second[qid]):
            if "needs_review" not in flags:
                flags.append("needs_review")
            value["note"] = "; ".join(filter(None, [value.get("note"), "Hai lượt đọc độc lập không khớp"]))
            value["confidence"] = "thap"
        value["flags"] = flags
        if "needs_review" in flags:
            value["needs_review"] = True
        answers[qid] = value
    notes = [n for n in (first.get("page_note"), second.get("page_note")) if n]
    note = notes[0] if notes else None
    if len(notes) == 2 and notes[0] != notes[1]:
        note = f"{notes[0]} [Lượt 2 khác: {notes[1]}]"
    return answers, bool(first.get("page_matches") and second.get("page_matches")), note


def extract_record(*, assembly: Mapping[str, Any], questionnaire: Mapping[str, Any], client: Any, model: str, image_base_dir: str | Path = ".", allowed_image_roots: Sequence[str | Path] | None = None, max_tokens: int = 8192) -> dict[str, Any]:
    record_id = validate_record_id(str(assembly.get("record_id") or ""))
    pages = _assembly_pages_by_number(assembly)
    total_pages = int(questionnaire.get("total_pages", 7))
    answers: dict[str, Any] = {}
    page_notes: dict[str, Any] = {}
    source_images: list[str] = []
    for page in range(1, total_pages + 1):
        image = _resolve_page_image(pages[page].get("image_path"), image_base_dir, allowed_image_roots, record_id)
        source_images.append(str(pages[page].get("image_path")))
        first = extract_page(client, image, questionnaire, page, model, max_tokens)
        second = extract_page(client, image, questionnaire, page, model, max_tokens)
        qids = [q["id"] for q in page_questions(questionnaire, page)]
        merged, matches, note = merge_runs(first, second, qids)
        answers.update(merged)
        page_notes[str(page)] = {"value": note, "flags": ([] if matches else ["needs_review"])}
    expected = [q["id"] for q in questionnaire.get("questions", []) if not q.get("per_page")]
    if list(answers) != expected:
        raise ModelOutputError("Output không đủ hoặc sai thứ tự câu hỏi")
    return {
        "record_id": record_id,
        "schema_version": questionnaire["schema_version"],
        "authored_by": f"automated-vlm:{model}",
        "purpose": "automated_full_extraction",
        "extracted_at": now_bangkok_iso(),
        "source_images": source_images,
        "answers": answers,
        "page_notes": page_notes,
    }


__all__ = ["AnthropicHTTPClient", "answer_schema", "build_tool", "extract_record", "merge_runs", "page_questions"]
