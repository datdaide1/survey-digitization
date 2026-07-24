"""Core logic for Task 3b multiple-choice extraction.

The module deliberately keeps the CLI, filesystem writes, and Anthropic transport
at the edges.  Schema slicing, dynamic tool schemas, validation, retries, and
self-consistency are plain Python functions so automated tests never need an API
key or network access.

See ``docs/implement-plan-03b-mc-extraction.md``.
"""

from __future__ import annotations

import base64
import copy
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


TASK3B_PAGE_SCOPE: dict[int, tuple[str, ...]] = {
    1: ("CONSENT_1", "CONSENT_2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8"),
    2: ("Q10", "Q11", "Q12", "Q13"),
    3: ("Q16a",),
    4: ("Q17", "Q18", "Q19", "Q20", "Q21a", "Q21b"),
    5: ("Q22a", "Q22b", "Q23", "Q24", "Q25", "Q26", "Q27a"),
    6: ("Q28", "Q29a", "Q29b", "Q30"),
    7: ("Q33",),
}
TASK3B_IDS: tuple[str, ...] = tuple(
    question_id
    for page in sorted(TASK3B_PAGE_SCOPE)
    for question_id in TASK3B_PAGE_SCOPE[page]
)
Q5_SELECT_COMPONENTS = (
    "Q5_khong_di_hoc",
    "Q5_khong_tieng_pho_thong",
    "Q5_trung_cap_dh",
)

TOOL_NAME = "submit_mc_page"
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
MODEL_FLAGS = (
    "ambiguous_mark",
    "needs_review",
    "multi_mark_on_single_select",
)
SAFE_RECORD_ID = re.compile(r"^[A-Za-z0-9_-]+$")

SYSTEM_PROMPT = """Bạn là bộ đọc dấu đánh chọn trên phiếu khảo sát tiếng Việt.
Chỉ ghi những gì nhìn thấy trên đúng ảnh trang được gửi, theo schema slice; không
tự suy luận, không sửa câu trả lời theo depends_on/exclusive, và không phiên âm
chữ viết tay ở other_text/subfield. Luôn gọi tool submit_mc_page đúng một lần.
"""

MARK_RULES = """QUY TẮC BẮT BUỘC:
1. Tick, X, khoanh tròn, gạch chéo hoặc dấu hình học tương đương đều tính là đã
   chọn. Chữ viết như "ko"/"không" thay cho dấu chọn thì coi là trống.
2. Chỉ gắn ambiguous_mark khi rõ ràng có một dấu chọn nhưng không xác định được
   dấu đó thuộc ô/cột nào. Khi còn nghi ngờ khác, gắn needs_review.
3. Nếu dấu cũ đã bị gạch huỷ rõ ràng rồi có dấu mới ở lựa chọn khác, chỉ lấy dấu
   mới; không coi đây là multi_mark_on_single_select. Áp dụng quy tắc này CẢ KHI
   hai dấu xung đột là một lựa chọn thường và một lựa chọn exclusive (vd "Không"/
   "Không là hội viên của tổ chức nào" bị tick cùng lựa chọn khác): nếu một trong
   hai dấu bị gạch/tô xoá rõ ràng, chỉ lấy dấu còn nguyên làm giá trị dứt khoát
   (không trả về cả hai, không để null chỉ vì hai lựa chọn "loại trừ nhau").
4. Với single_select có từ hai dấu hợp lệ còn nguyên trở lên, giữ TẤT CẢ code
   trong một mảng và gắn multi_mark_on_single_select. Ví dụ thật: Q10 có
   [nong_dan, buon_ban], Q30 có [san_xuat, thu_hai, tieu_thu].
5. Đọc độc lập từng câu đúng như trên giấy. Không bỏ câu theo depends_on, không
   loại lựa chọn exclusive, không đổi print_no thành giá trị; output luôn dùng code.
6. multi_select không có dấu chọn rõ ràng trả []; null chỉ dùng khi không thể xác
   định giá trị. single_select bỏ trống trả null.
7. Chỉ đọc mã lựa chọn. Không đưa nội dung chữ viết tay other_text/subfield vào value.
8. Nếu single_select KHÔNG có ô nào được tick hình học nhưng có ghi chú viết tay ở
   lề/dưới nhiều ô cùng chỉ ra rằng nhiều lựa chọn đều áp dụng (vd "như nhau",
   "2 vợ chồng như nhau", "làm tất cả mọi thứ") — coi TẤT CẢ các lựa chọn được ghi
   chú đó là đã chọn: trả về mảng đầy đủ và gắn multi_mark_on_single_select, xử lý
   như khi có tick hình học thật (mục 4), không giới hạn ở "chỉ tick mới tính"
   (mục 1) cho case này. Case thật đã biết: Q30 phiếu LCA-TPH-006/LCH-SLL-004.
"""


class MCExtractionError(RuntimeError):
    """Base error for a record that cannot be extracted safely."""


class SchemaSliceError(MCExtractionError):
    """The questionnaire schema does not match the locked Task 3b scope."""


class ModelOutputError(MCExtractionError):
    """Claude did not return the required tool payload or structural fields."""


class AnthropicAPIError(MCExtractionError):
    """The Anthropic Messages API request failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_type: str | None = None,
        batch_fatal: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self._batch_fatal = batch_fatal

    @property
    def batch_fatal(self) -> bool:
        """Whether retrying the same credentials/config for other records is unsafe."""

        return (
            self._batch_fatal
            or self.status_code in {401, 403, 404}
            or self.error_type
            in {
                "authentication_error",
                "permission_error",
                "not_found_error",
                "billing_error",
            }
        )


def _is_shared_request_configuration_error(
    error_type: str | None, message: str
) -> bool:
    """Classify 400s that cannot improve by advancing to another record."""

    if error_type != "invalid_request_error":
        return False
    normalized = message.casefold()
    # Anthropic also uses invalid_request_error for record-specific image input.
    if any(
        marker in normalized
        for marker in ("image", "base64", "media type", "media_type", "document")
    ):
        return False
    return any(
        marker in normalized
        for marker in (
            "input_schema",
            "tool schema",
            "tool_choice",
            "tools.",
            "model",
            "anthropic-version",
            "max_tokens",
            "schema is too complex",
        )
    )


def now_bangkok_iso() -> str:
    """Return an ISO timestamp in the project timezone (UTC+07:00)."""

    return datetime.now(timezone(timedelta(hours=7))).isoformat(timespec="seconds")


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise MCExtractionError(f"JSON root phải là object: {path}")
    return value


def validate_record_id(record_id: str) -> str:
    if not (record_id and SAFE_RECORD_ID.fullmatch(record_id)):
        raise MCExtractionError(
            f"record_id không hợp lệ (chỉ chữ/số/_/-): {record_id!r}"
        )
    return record_id


def _copy_option(option: Mapping[str, Any]) -> dict[str, Any]:
    result = {"code": option.get("code"), "label": option.get("label", "")}
    if "print_no" in option:
        result["print_no"] = option["print_no"]
    if option.get("exclusive"):
        result["exclusive"] = True
    if option.get("other_text"):
        # The marker helps the prompt identify the printed option, but no text field
        # is exposed in the output schema, so handwriting cannot leak into value.
        result["other_text"] = True
    return result


def build_page_slice(
    questionnaire: Mapping[str, Any], page_number: int
) -> list[dict[str, Any]]:
    """Return the locked Task 3b schema slice for one printed page.

    The parent question IDs are locked by the implementation plan.  Option labels
    and codes are still loaded dynamically from ``questionnaire_v1.json`` so a
    label edit does not require code changes.  Q5 is the sole composite exception:
    only its three checkbox components are included; the text component is Task 5.
    """

    if page_number not in TASK3B_PAGE_SCOPE:
        raise SchemaSliceError(f"Trang ngoài phạm vi Task 3b: {page_number}")

    questions = questionnaire.get("questions")
    if not isinstance(questions, list):
        raise SchemaSliceError("questionnaire.questions phải là array")
    by_id = {
        question.get("id"): question
        for question in questions
        if isinstance(question, dict) and question.get("id")
    }

    result: list[dict[str, Any]] = []
    for question_id in TASK3B_PAGE_SCOPE[page_number]:
        question = by_id.get(question_id)
        if not isinstance(question, dict):
            raise SchemaSliceError(f"Schema thiếu câu bắt buộc {question_id}")
        if question.get("page") != page_number:
            raise SchemaSliceError(
                f"{question_id}.page={question.get('page')!r}, kỳ vọng {page_number}"
            )

        question_type = question.get("type")
        item: dict[str, Any] = {
            "id": question_id,
            "text": question.get("text", ""),
            "type": question_type,
        }

        if question_id == "Q5":
            if question_type != "composite":
                raise SchemaSliceError("Q5 phải có type=composite")
            components = {
                component.get("id"): component
                for component in question.get("components", [])
                if isinstance(component, dict)
            }
            selected_components = []
            for component_id in Q5_SELECT_COMPONENTS:
                component = components.get(component_id)
                if not isinstance(component, dict):
                    raise SchemaSliceError(f"Q5 thiếu component {component_id}")
                if component.get("type") != "single_select":
                    raise SchemaSliceError(
                        f"Q5.{component_id} phải là single_select"
                    )
                component_options = component.get("options")
                _validated_codes(component_options, f"Q5.{component_id}.options")
                selected_components.append(
                    {
                        "id": component_id,
                        "text": component.get("text", ""),
                        "type": "checkbox_boolean",
                        "options": [
                            _copy_option(option)
                            for option in component_options
                        ],
                    }
                )
            item["components"] = selected_components
        elif question_id == "Q17":
            if question_type != "device_grid":
                raise SchemaSliceError("Q17 phải có type=device_grid")
            item["rows"] = [
                {"code": row.get("code"), "label": row.get("label", "")}
                for row in question.get("rows", [])
            ]
            item["columns"] = [
                {"code": column.get("code"), "label": column.get("label", "")}
                for column in question.get("columns", [])
            ]
            extra = question.get("extra_option")
            if not isinstance(extra, dict) or not extra.get("code"):
                raise SchemaSliceError("Q17 thiếu extra_option")
            item["extra_option"] = {
                "code": extra["code"],
                "label": extra.get("label", ""),
                "exclusive": bool(extra.get("exclusive")),
            }
        else:
            if question_type not in {"single_select", "multi_select"}:
                raise SchemaSliceError(
                    f"{question_id} có type ngoài scope: {question_type!r}"
                )
            options = question.get("options")
            if not isinstance(options, list) or not options:
                raise SchemaSliceError(f"{question_id} không có options")
            item["options"] = [_copy_option(option) for option in options]
            if "depends_on" in question:
                # Included only as a reminder not to gate extraction.
                item["depends_on_ignored_during_extraction"] = question["depends_on"]

        result.append(item)

    return result


def _flags_schema(*, allow_multi_mark: bool) -> dict[str, Any]:
    allowed_flags = list(MODEL_FLAGS)
    if not allow_multi_mark:
        allowed_flags.remove("multi_mark_on_single_select")
    return {
        "type": "array",
        "items": {"type": "string", "enum": allowed_flags},
        "description": "Cờ quan sát trực tiếp; [] nếu không có bất thường.",
    }


def _answer_object(
    value_schema: Mapping[str, Any], *, allow_multi_mark: bool
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "value": dict(value_schema),
            "flags": _flags_schema(allow_multi_mark=allow_multi_mark),
        },
        "required": ["value", "flags"],
        "additionalProperties": False,
    }


def _option_codes(question: Mapping[str, Any]) -> list[str]:
    return _validated_codes(
        question.get("options"), f"{question.get('id')}.options"
    )


def _validated_codes(items: Any, context: str) -> list[str]:
    if not isinstance(items, list) or not items:
        raise SchemaSliceError(f"{context} phải là array không rỗng")
    codes = [item.get("code") if isinstance(item, Mapping) else None for item in items]
    if not codes or any(not isinstance(code, str) or not code for code in codes):
        raise SchemaSliceError(f"{context} có code không hợp lệ")
    if len(set(codes)) != len(codes):
        raise SchemaSliceError(f"{context} có code trùng")
    if len({code.casefold() for code in codes}) != len(codes):
        raise SchemaSliceError(f"{context} có code chỉ khác nhau hoa/thường")
    return codes


def _value_schema(question: Mapping[str, Any]) -> dict[str, Any]:
    question_id = question["id"]
    question_type = question["type"]

    if question_id == "Q5":
        component_ids = [component["id"] for component in question["components"]]
        return {
            "type": "object",
            "properties": {
                component_id: {"type": "boolean"}
                for component_id in component_ids
            },
            "required": component_ids,
            "additionalProperties": False,
            "description": "true nếu checkbox có dấu hợp lệ, false nếu trống.",
        }

    if question_id == "Q17":
        row_codes = _validated_codes(question.get("rows"), "Q17.rows")
        column_codes = _validated_codes(question.get("columns"), "Q17.columns")
        extra_code = question["extra_option"]["code"]
        return {
            "type": "object",
            "properties": {
                "rows": {
                    "type": "object",
                    "properties": {
                        row_code: {
                            "type": "array",
                            "items": {"type": "string", "enum": column_codes},
                        }
                        for row_code in row_codes
                    },
                    "required": row_codes,
                    "additionalProperties": False,
                },
                extra_code: {"type": "boolean"},
            },
            "required": ["rows", extra_code],
            "additionalProperties": False,
        }

    codes = _option_codes(question)
    if question_type == "single_select":
        return {
            "anyOf": [
                {"type": "string", "enum": codes},
                {
                    "type": "array",
                    "items": {"type": "string", "enum": codes},
                },
                {"type": "null"},
            ]
        }
    if question_type == "multi_select":
        return {
            "anyOf": [
                {
                    "type": "array",
                    "items": {"type": "string", "enum": codes},
                },
                {"type": "null"},
            ]
        }
    raise SchemaSliceError(f"Không biết sinh schema cho {question_id}")


def build_tool_definition(page_slice: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the per-page user-tool definition used for structured output."""

    if not page_slice:
        raise SchemaSliceError("Schema slice rỗng")
    properties: dict[str, Any] = {
        "trang_khop_du_kien": {
            "type": "boolean",
            "description": (
                "true nếu ảnh chứa đúng nhóm câu trong schema slice; false nếu là "
                "trang khác, trang trắng hoặc hỏng."
            ),
        }
    }
    required = ["trang_khop_du_kien"]
    for question in page_slice:
        question_id = question["id"]
        properties[question_id] = _answer_object(
            _value_schema(question),
            allow_multi_mark=question.get("type") == "single_select",
        )
        required.append(question_id)

    return {
        "name": TOOL_NAME,
        "description": (
            "Trả kết quả đọc dấu đánh chọn của toàn bộ câu trong đúng một trang "
            "phiếu. Không thực thi side effect."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def build_user_prompt(
    page_number: int, page_slice: Sequence[Mapping[str, Any]], retry_note: str | None = None
) -> str:
    ids = [question["id"] for question in page_slice]
    prompt = (
        f"Tentative page = {page_number}. Trang dự kiến chứa: {', '.join(ids)}.\n"
        "Đầu tiên kiểm tra nội dung trang có khớp nhóm câu này không và điền "
        "trang_khop_du_kien. Dù không khớp, vẫn trả đủ mọi property theo ảnh và "
        "gắn needs_review khi phù hợp; không tự remap sang trang khác.\n\n"
        f"{MARK_RULES}\n\n"
        "SCHEMA SLICE (chỉ dùng code ở đây):\n"
        + json.dumps(list(page_slice), ensure_ascii=False, indent=2)
    )
    if retry_note:
        prompt += "\n\nLƯU Ý RETRY TỪ VALIDATOR:\n" + retry_note
    return prompt


def _image_content_block(image_path: str | Path) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        raise MCExtractionError(f"Không tìm thấy ảnh trang: {path}")
    media_type = mimetypes.guess_type(path.name)[0]
    if media_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
        raise MCExtractionError(f"Định dạng ảnh không hỗ trợ Claude Vision: {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": encoded},
    }


def build_api_request(
    *,
    image_path: str | Path,
    page_number: int,
    page_slice: Sequence[Mapping[str, Any]],
    model: str,
    max_tokens: int = 4096,
    retry_note: str | None = None,
) -> dict[str, Any]:
    if not isinstance(model, str) or not model.strip():
        raise MCExtractionError("Tên model Claude không được rỗng")
    if max_tokens <= 0:
        raise MCExtractionError("max_tokens phải > 0")
    tool = build_tool_definition(page_slice)
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": [
                    _image_content_block(image_path),
                    {
                        "type": "text",
                        "text": build_user_prompt(page_number, page_slice, retry_note),
                    },
                ],
            }
        ],
        "tools": [tool],
        "tool_choice": {
            "type": "tool",
            "name": TOOL_NAME,
            "disable_parallel_tool_use": True,
        },
    }


class AnthropicHTTPClient:
    """Small stdlib-only client for ``POST /v1/messages``.

    The repository intentionally has no dependency manifest yet.  Keeping this
    transport in the standard library lets mock tests run in the mandated conda
    environment without installing the Anthropic SDK.  The API key is never put
    in exceptions or returned data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        api_url: str = ANTHROPIC_MESSAGES_URL,
        timeout: float = 120.0,
        retries: int = 2,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise AnthropicAPIError(
                "Thiếu ANTHROPIC_API_KEY; unit test mock vẫn chạy được nhưng không thể gọi live."
            )
        # The request contains both an API key and full survey-page images.  Do
        # not permit a configurable host to turn a typo or poisoned environment
        # variable into credential/PII exfiltration.
        if api_url != ANTHROPIC_MESSAGES_URL:
            raise AnthropicAPIError(
                f"Chỉ cho phép Anthropic Messages endpoint chính thức: {ANTHROPIC_MESSAGES_URL}"
            )
        if timeout <= 0:
            raise AnthropicAPIError("timeout phải > 0")
        if retries < 0:
            raise AnthropicAPIError("retries phải >= 0")
        self.api_url = api_url
        self.timeout = timeout
        self.retries = retries
        self.anthropic_version = anthropic_version

    def create_message(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=body,
            method="POST",
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
            },
        )
        retryable_statuses = {429, 500, 502, 503, 504, 529}
        last_error: Exception | None = None

        for attempt in range(self.retries + 1):
            retry_delay = min(2**attempt, 4)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw_response = response.read().decode("utf-8")
                try:
                    decoded = json.loads(raw_response)
                except json.JSONDecodeError as exc:
                    raise AnthropicAPIError(
                        "Claude API trả response không phải JSON hợp lệ",
                        batch_fatal=True,
                    ) from exc
                if not isinstance(decoded, dict):
                    raise AnthropicAPIError(
                        "Claude API trả JSON root không phải object",
                        batch_fatal=True,
                    )
                return decoded
            except urllib.error.HTTPError as exc:
                # Limit the body to avoid accidentally surfacing verbose request echoes.
                detail = exc.read(2000).decode("utf-8", errors="replace")
                error_type: str | None = None
                error_message = detail
                try:
                    error_document = json.loads(detail)
                    if isinstance(error_document, dict):
                        error = error_document.get("error")
                        if isinstance(error, dict) and isinstance(error.get("type"), str):
                            error_type = error["type"]
                        if isinstance(error, dict) and isinstance(error.get("message"), str):
                            error_message = error["message"]
                except json.JSONDecodeError:
                    pass
                last_error = AnthropicAPIError(
                    f"Claude API HTTP {exc.code}: {detail or exc.reason}",
                    status_code=exc.code,
                    error_type=error_type,
                    batch_fatal=(
                        (exc.code in retryable_statuses and attempt >= self.retries)
                        or _is_shared_request_configuration_error(
                            error_type, error_message
                        )
                    ),
                )
                if exc.code not in retryable_statuses or attempt >= self.retries:
                    raise last_error from exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                if retry_after is not None:
                    try:
                        retry_delay = min(max(float(retry_after), 0.0), 30.0)
                    except ValueError:
                        pass
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = AnthropicAPIError(
                    f"Không kết nối được Claude API: {exc}",
                    batch_fatal=attempt >= self.retries,
                )
                if attempt >= self.retries:
                    raise last_error from exc
            if attempt < self.retries:
                time.sleep(retry_delay)

        raise last_error or AnthropicAPIError("Claude API thất bại không rõ nguyên nhân")


def _send_message(client: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    if hasattr(client, "create_message"):
        response = client.create_message(payload)
    elif callable(client):
        response = client(payload)
    else:
        raise TypeError("client phải callable hoặc có create_message(payload)")
    if not isinstance(response, dict):
        raise ModelOutputError("Claude client phải trả response dict")
    return response


def extract_tool_input(response: Mapping[str, Any]) -> dict[str, Any]:
    content = response.get("content")
    if not isinstance(content, list):
        raise ModelOutputError("Claude response thiếu content array")
    matching = [
        block
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "tool_use"
        and block.get("name") == TOOL_NAME
    ]
    if len(matching) != 1:
        raise ModelOutputError(
            f"Kỳ vọng đúng 1 tool_use {TOOL_NAME}, nhận {len(matching)}"
        )
    tool_input = matching[0].get("input")
    if not isinstance(tool_input, dict):
        raise ModelOutputError("tool_use.input phải là object")
    return tool_input


def _dedupe(items: Sequence[Any]) -> list[Any]:
    result: list[Any] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _canonical_codes(raw: Sequence[Any], allowed: Sequence[str]) -> tuple[list[Any], list[Any]]:
    # Strict outputs have one documented enum edge case: capitalization can
    # drift. Codes are casefold-unique at preflight, so normalize such variants
    # to the exact schema spelling before classifying genuinely invalid values.
    canonical_by_case = {code.casefold(): code for code in allowed}
    normalized: list[Any] = []
    invalid: list[Any] = []
    for value in _dedupe(list(raw)):
        canonical = (
            canonical_by_case.get(value.casefold())
            if isinstance(value, str)
            else None
        )
        if canonical is None:
            normalized.append(value)
            invalid.append(value)
        else:
            normalized.append(canonical)
    normalized = _dedupe(normalized)
    invalid = _dedupe(invalid)
    allowed_values = [code for code in allowed if code in normalized]
    return allowed_values + invalid, invalid


def _normalize_flags(question_id: str, raw_flags: Any) -> list[str]:
    if not isinstance(raw_flags, list) or any(
        not isinstance(flag, str) for flag in raw_flags
    ):
        raise ModelOutputError(f"{question_id}.flags phải là array string")
    # invalid_option_code and self_consistency_mismatch are owned by ordinary
    # code below, not by the model.  Keep this defense-in-depth check even with
    # strict tool output enabled.
    unknown = [flag for flag in raw_flags if flag not in MODEL_FLAGS]
    if unknown:
        raise ModelOutputError(f"{question_id}.flags có cờ lạ: {unknown}")
    return _dedupe(raw_flags)


def _normalize_q5_value(question: Mapping[str, Any], value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        raise ModelOutputError("Q5.value phải là object 3 checkbox boolean")
    component_ids = [component["id"] for component in question["components"]]
    missing = [component_id for component_id in component_ids if component_id not in value]
    if missing:
        raise ModelOutputError(f"Q5.value thiếu component: {missing}")
    extras = [key for key in value if key not in component_ids]
    if extras:
        raise ModelOutputError(f"Q5.value có component ngoài scope: {extras}")
    for component_id in component_ids:
        if not isinstance(value[component_id], bool):
            raise ModelOutputError(f"Q5.value.{component_id} phải là boolean")
    return {component_id: value[component_id] for component_id in component_ids}


def _normalize_q17_value(
    question: Mapping[str, Any], value: Any
) -> tuple[dict[str, Any], list[Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("rows"), dict):
        raise ModelOutputError("Q17.value phải có object rows")
    row_codes = [row["code"] for row in question["rows"]]
    column_codes = [column["code"] for column in question["columns"]]
    extra_code = question["extra_option"]["code"]
    rows = value["rows"]
    missing = [row_code for row_code in row_codes if row_code not in rows]
    if missing:
        raise ModelOutputError(f"Q17.value.rows thiếu dòng: {missing}")
    extras = [key for key in rows if key not in row_codes]
    if extras:
        raise ModelOutputError(f"Q17.value.rows có dòng lạ: {extras}")
    if not isinstance(value.get(extra_code), bool):
        raise ModelOutputError(f"Q17.value.{extra_code} phải là boolean")

    normalized_rows: dict[str, list[Any]] = {}
    invalid: list[Any] = []
    for row_code in row_codes:
        row_value = rows[row_code]
        if not isinstance(row_value, list):
            raise ModelOutputError(f"Q17.value.rows.{row_code} phải là array")
        normalized_rows[row_code], row_invalid = _canonical_codes(
            row_value, column_codes
        )
        invalid.extend(row_invalid)
    return {"rows": normalized_rows, extra_code: value[extra_code]}, _dedupe(invalid)


def validate_page_payload(
    payload: Mapping[str, Any], page_slice: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, dict[str, Any]], bool, dict[str, list[Any]]]:
    """Validate and normalize one tool payload.

    Structural omissions are hard errors.  Unknown option codes are returned in
    ``invalid_by_question`` so the caller can perform the one allowed model retry.
    Values containing unknown codes are intentionally retained for review if the
    retry also fails, as required by the implementation plan.
    """

    if not isinstance(payload.get("trang_khop_du_kien"), bool):
        raise ModelOutputError("trang_khop_du_kien phải là boolean")

    expected_ids = [question["id"] for question in page_slice]
    missing = [question_id for question_id in expected_ids if question_id not in payload]
    if missing:
        raise ModelOutputError(f"Tool output thiếu câu bắt buộc: {missing}")

    answers: dict[str, dict[str, Any]] = {}
    invalid_by_question: dict[str, list[Any]] = {}
    for question in page_slice:
        question_id = question["id"]
        raw_answer = payload[question_id]
        if not isinstance(raw_answer, dict) or "value" not in raw_answer:
            raise ModelOutputError(f"{question_id} phải là object có value + flags")
        flags = _normalize_flags(question_id, raw_answer.get("flags"))
        value = raw_answer["value"]
        invalid: list[Any] = []

        if question_id == "Q5":
            value = _normalize_q5_value(question, value)
            flags = [flag for flag in flags if flag != "multi_mark_on_single_select"]
        elif question_id == "Q17":
            value, invalid = _normalize_q17_value(question, value)
            flags = [flag for flag in flags if flag != "multi_mark_on_single_select"]
        else:
            allowed = _option_codes(question)
            question_type = question["type"]
            if question_type == "single_select":
                if value is None:
                    flags = [flag for flag in flags if flag != "multi_mark_on_single_select"]
                elif isinstance(value, str):
                    normalized, invalid = _canonical_codes([value], allowed)
                    value = normalized[0]
                    flags = [flag for flag in flags if flag != "multi_mark_on_single_select"]
                elif isinstance(value, list):
                    value, invalid = _canonical_codes(value, allowed)
                    if len(value) == 0:
                        value = None
                        flags = [
                            flag for flag in flags
                            if flag != "multi_mark_on_single_select"
                        ]
                    elif len(value) == 1:
                        value = value[0]
                        flags = [
                            flag for flag in flags
                            if flag != "multi_mark_on_single_select"
                        ]
                    elif "multi_mark_on_single_select" not in flags:
                        flags.append("multi_mark_on_single_select")
                else:
                    raise ModelOutputError(
                        f"{question_id}.value phải là string/array/null"
                    )
            elif question_type == "multi_select":
                if value is None:
                    pass
                elif isinstance(value, list):
                    value, invalid = _canonical_codes(value, allowed)
                else:
                    raise ModelOutputError(f"{question_id}.value phải là array/null")
                flags = [flag for flag in flags if flag != "multi_mark_on_single_select"]
            else:
                raise ModelOutputError(f"Type không được hỗ trợ: {question_type}")

        answers[question_id] = {"value": value, "flags": _dedupe(flags)}
        if invalid:
            invalid_by_question[question_id] = _dedupe(invalid)

    return answers, payload["trang_khop_du_kien"], invalid_by_question


def _invalid_retry_note(invalid_by_question: Mapping[str, Sequence[Any]]) -> str:
    details = "; ".join(
        f"{question_id}: {list(values)!r}"
        for question_id, values in invalid_by_question.items()
    )
    return (
        "Validator thấy option code không có trong schema ở lần trước: "
        f"{details}. Hãy đọc lại ảnh và chỉ dùng đúng code được liệt kê; không dùng label, "
        "print_no hoặc chữ viết tay."
    )


def extract_page_run(
    *,
    client: Any,
    image_path: str | Path,
    page_number: int,
    page_slice: Sequence[Mapping[str, Any]],
    model: str,
    max_tokens: int = 4096,
) -> tuple[dict[str, dict[str, Any]], bool]:
    """Perform one independent page run, with at most one invalid-code retry."""

    invalid: dict[str, list[Any]] = {}
    answers: dict[str, dict[str, Any]] | None = None
    page_matches = False
    for attempt in range(2):
        request = build_api_request(
            image_path=image_path,
            page_number=page_number,
            page_slice=page_slice,
            model=model,
            max_tokens=max_tokens,
            retry_note=_invalid_retry_note(invalid) if invalid else None,
        )
        response = _send_message(client, request)
        payload = extract_tool_input(response)
        answers, page_matches, invalid = validate_page_payload(payload, page_slice)
        if not invalid:
            return answers, page_matches
        if attempt == 0:
            continue

    assert answers is not None
    for question_id in invalid:
        flags = answers[question_id]["flags"]
        if "invalid_option_code" not in flags:
            flags.append("invalid_option_code")
    return answers, page_matches


def _canonical_for_compare(value: Any) -> Any:
    if isinstance(value, list):
        normalized = [_canonical_for_compare(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, dict):
        return {
            key: _canonical_for_compare(value[key])
            for key in sorted(value)
        }
    return value


def values_equal(left: Any, right: Any) -> bool:
    """Recursive equality with array order ignored and null distinct from []."""

    return _canonical_for_compare(left) == _canonical_for_compare(right)


def merge_self_consistency(
    run1: Mapping[str, Mapping[str, Any]],
    run2: Mapping[str, Mapping[str, Any]],
    question_ids: Sequence[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Keep run 1 values, add mismatch flags, and build compact debug data."""

    answers: dict[str, dict[str, Any]] = {}
    debug: dict[str, dict[str, Any]] = {}
    for question_id in question_ids:
        if question_id not in run1 or question_id not in run2:
            raise ModelOutputError(f"Self-consistency thiếu {question_id}")
        value1 = copy.deepcopy(run1[question_id]["value"])
        value2 = copy.deepcopy(run2[question_id]["value"])
        match = values_equal(value1, value2)

        flags1 = list(run1[question_id].get("flags", []))
        flags2 = list(run2[question_id].get("flags", []))
        # Keep review signals seen by either independent pass.  Multi-mark is then
        # reconciled against the official run-1 value so flags cannot contradict it.
        flags = _dedupe(
            flags1
            + [
                flag
                for flag in flags2
                if flag in {"ambiguous_mark", "needs_review"}
            ]
        )
        if not match and "self_consistency_mismatch" not in flags:
            flags.append("self_consistency_mismatch")
        if question_id not in {"Q5", "Q17"}:
            if isinstance(value1, list) and len(value1) >= 2:
                if "multi_mark_on_single_select" in flags1 and "multi_mark_on_single_select" not in flags:
                    flags.append("multi_mark_on_single_select")
            elif "multi_mark_on_single_select" in flags:
                flags.remove("multi_mark_on_single_select")

        answers[question_id] = {"value": value1, "flags": flags}
        debug[question_id] = {"run1": value1, "run2": value2, "match": match}
    return answers, debug


def _resolve_page_image(
    image_path: Any,
    image_base_dir: str | Path,
    allowed_image_roots: Sequence[str | Path] | None = None,
    record_id: str | None = None,
) -> Path:
    if not isinstance(image_path, str) or not image_path:
        raise MCExtractionError("assembly page thiếu image_path")
    base = Path(image_base_dir).resolve()
    path = Path(image_path)
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    roots = [
        Path(root).resolve()
        for root in (allowed_image_roots if allowed_image_roots is not None else [base])
    ]
    if not roots:
        raise MCExtractionError("allowed_image_roots không được rỗng")
    if not any(path.is_relative_to(root) for root in roots):
        raise MCExtractionError(
            f"Ảnh assembly nằm ngoài các thư mục được phép: {path}"
        )
    if record_id is not None:
        original_image = path.stem == record_id
        rendered_image = (
            path.parent.name == record_id
            and path.stem.startswith(f"{record_id}__p")
        )
        if not (original_image or rendered_image):
            raise MCExtractionError(
                f"Ảnh assembly không thuộc record {record_id}: {path}"
            )
    if not path.is_file():
        raise MCExtractionError(f"Ảnh assembly không tồn tại: {path}")
    return path


def _assembly_pages_by_number(assembly: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    pages = assembly.get("pages")
    if not isinstance(pages, list):
        raise MCExtractionError("assembly.pages phải là array")
    by_number: dict[int, Mapping[str, Any]] = {}
    for page in pages:
        if not isinstance(page, dict):
            raise MCExtractionError("assembly.pages chứa phần tử không phải object")
        number = page.get("tentative_page")
        if not isinstance(number, int):
            raise MCExtractionError("tentative_page phải là integer")
        if number in by_number:
            raise MCExtractionError(f"assembly trùng tentative_page={number}")
        by_number[number] = page
    missing = [page for page in TASK3B_PAGE_SCOPE if page not in by_number]
    if missing:
        raise MCExtractionError(f"assembly thiếu tentative page: {missing}")
    extras = [page for page in by_number if page not in TASK3B_PAGE_SCOPE]
    if extras:
        raise MCExtractionError(f"assembly có tentative page ngoài 1..7: {extras}")
    return by_number


def extract_record(
    *,
    assembly: Mapping[str, Any],
    questionnaire: Mapping[str, Any],
    client: Any,
    model: str,
    image_base_dir: str | Path = ".",
    allowed_image_roots: Sequence[str | Path] | None = None,
    max_tokens: int = 4096,
    extracted_at: str | None = None,
) -> dict[str, Any]:
    """Extract all seven pages of one assembly record using two calls per page."""

    record_id = validate_record_id(str(assembly.get("record_id") or ""))
    if assembly.get("status") == "error":
        raise MCExtractionError(f"assembly {record_id} đang status=error")
    pages_by_number = _assembly_pages_by_number(assembly)

    schema_version = questionnaire.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        raise SchemaSliceError("questionnaire.schema_version không hợp lệ")

    # Preflight every schema slice and image before the first paid API call.  A
    # broken page 7 must not waste twelve successful calls for pages 1..6.
    page_slices: dict[int, list[dict[str, Any]]] = {}
    page_images: dict[int, Path] = {}
    for page_number in sorted(TASK3B_PAGE_SCOPE):
        page_slices[page_number] = build_page_slice(questionnaire, page_number)
        # Tool generation performs the remaining code/shape checks (including
        # option, matrix-row, and matrix-column code uniqueness).
        build_tool_definition(page_slices[page_number])
        page_images[page_number] = _resolve_page_image(
            pages_by_number[page_number].get("image_path"),
            image_base_dir,
            allowed_image_roots,
            record_id,
        )

    all_answers: dict[str, dict[str, Any]] = {}
    output_pages: dict[str, dict[str, Any]] = {}
    all_debug: dict[str, dict[str, Any]] = {}

    for page_number in sorted(TASK3B_PAGE_SCOPE):
        page_slice = page_slices[page_number]
        image_path = page_images[page_number]
        run1, page_match1 = extract_page_run(
            client=client,
            image_path=image_path,
            page_number=page_number,
            page_slice=page_slice,
            model=model,
            max_tokens=max_tokens,
        )
        run2, page_match2 = extract_page_run(
            client=client,
            image_path=image_path,
            page_number=page_number,
            page_slice=page_slice,
            model=model,
            max_tokens=max_tokens,
        )
        question_ids = list(TASK3B_PAGE_SCOPE[page_number])
        official, debug = merge_self_consistency(run1, run2, question_ids)
        all_answers.update(official)
        all_debug.update(debug)
        output_pages[str(page_number)] = {
            "tentative_page": page_number,
            "page_order_mismatch": not (page_match1 and page_match2),
        }

    if tuple(all_answers) != TASK3B_IDS:
        raise ModelOutputError(
            f"Output không đủ đúng 31 ID Task 3b: {list(all_answers)}"
        )

    return {
        "record_id": record_id,
        "schema_version": schema_version,
        "extracted_at": extracted_at or now_bangkok_iso(),
        "model": model,
        "answers": all_answers,
        "pages": output_pages,
        "_debug": {"self_consistency_runs": all_debug},
    }


def make_tool_response(tool_input: Mapping[str, Any]) -> dict[str, Any]:
    """Test helper: wrap a tool input in the real Messages API response shape."""

    return {
        "id": "msg_mock",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "toolu_mock",
                "name": TOOL_NAME,
                "input": copy.deepcopy(dict(tool_input)),
            }
        ],
        "stop_reason": "tool_use",
    }
