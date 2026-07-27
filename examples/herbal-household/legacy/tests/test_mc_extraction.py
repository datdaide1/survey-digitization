#!/usr/bin/env python3
"""Unit tests for Task 3b (mock only; no API key or network required).

Run:
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" tests/test_mc_extraction.py
"""

from __future__ import annotations

import copy
import base64
import contextlib
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from extract_mc import resolve_record_ids, run as run_cli_records  # noqa: E402
from compare_ground_truth import (  # noqa: E402
    TASK3B_FIELDS as COMPARATOR_TASK3B_FIELDS,
    compare_documents,
    print_report,
)
import lib.mc_extraction as mc_extraction  # noqa: E402
from lib.mc_extraction import (  # noqa: E402
    AnthropicAPIError,
    AnthropicHTTPClient,
    MCExtractionError,
    ModelOutputError,
    Q5_SELECT_COMPONENTS,
    TASK3B_IDS,
    TASK3B_PAGE_SCOPE,
    build_api_request,
    build_page_slice,
    build_tool_definition,
    build_user_prompt,
    extract_page_run,
    extract_record,
    make_tool_response,
    merge_self_consistency,
    validate_page_payload,
    validate_record_id,
    values_equal,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS: list[tuple[str, bool, object | None]] = []
TMP_ROOT = Path(tempfile.mkdtemp(prefix="mc_extraction_test_"))


def check(name: str, condition: object, detail: object | None = None) -> None:
    RESULTS.append((name, bool(condition), detail))


def expect_error(name: str, error_type: type[Exception], fn) -> None:
    try:
        fn()
    except error_type:
        check(name, True)
    except Exception as exc:  # pragma: no cover - diagnostic path
        check(name, False, f"sai loại lỗi: {type(exc).__name__}: {exc}")
    else:
        check(name, False, "không ném lỗi")


def load_schema() -> dict:
    with (REPO_ROOT / "schema" / "questionnaire_v1.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def make_image(path: Path, marker: int = 255) -> None:
    from PIL import Image

    Image.new("RGB", (16, 16), (marker, marker, marker)).save(path)


def blank_payload(page_slice: list[dict], *, page_matches: bool = True) -> dict:
    payload: dict = {"trang_khop_du_kien": page_matches}
    for question in page_slice:
        question_id = question["id"]
        if question_id == "Q5":
            value = {component["id"]: False for component in question["components"]}
        elif question_id == "Q17":
            value = {
                "rows": {row["code"]: [] for row in question["rows"]},
                question["extra_option"]["code"]: False,
            }
        elif question["type"] == "multi_select":
            value = []
        else:
            value = None
        payload[question_id] = {"value": value, "flags": []}
    return payload


class SequenceClient:
    def __init__(self, tool_inputs: list[dict]):
        self.tool_inputs = [copy.deepcopy(value) for value in tool_inputs]
        self.requests: list[dict] = []

    def create_message(self, request: dict) -> dict:
        self.requests.append(request)
        if not self.tool_inputs:
            raise AssertionError("mock hết response")
        return make_tool_response(self.tool_inputs.pop(0))


def _blank_from_value_schema(schema: dict):
    if "anyOf" in schema:
        branches = schema["anyOf"]
        first_type = branches[0].get("type")
        if first_type == "array":
            return []
        return None
    schema_type = schema.get("type")
    if schema_type == "boolean":
        return False
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {
            key: _blank_from_value_schema(value)
            for key, value in schema.get("properties", {}).items()
        }
    if schema_type == "null":
        return None
    raise AssertionError(f"schema mock không hỗ trợ: {schema}")


class SchemaDrivenClient:
    """Build a valid blank payload from each request's dynamic tool schema."""

    def __init__(self, mismatch_call_indexes: set[int] | None = None):
        self.requests: list[dict] = []
        self.mismatch_call_indexes = mismatch_call_indexes or set()

    def create_message(self, request: dict) -> dict:
        call_index = len(self.requests)
        self.requests.append(request)
        input_schema = request["tools"][0]["input_schema"]
        payload = {
            "trang_khop_du_kien": call_index not in self.mismatch_call_indexes
        }
        for key, schema in input_schema["properties"].items():
            if key == "trang_khop_du_kien":
                continue
            payload[key] = {
                "value": _blank_from_value_schema(schema["properties"]["value"]),
                "flags": [],
            }
        return make_tool_response(payload)


class ContentAwareSchemaClient(SchemaDrivenClient):
    """Mock page recognition by comparing an image pixel with tentative page."""

    def create_message(self, request: dict) -> dict:
        from PIL import Image

        text = request["messages"][0]["content"][1]["text"]
        match = re.search(r"Tentative page = (\d+)", text)
        if not match:
            raise AssertionError("prompt thiếu tentative page")
        tentative_page = int(match.group(1))
        encoded = request["messages"][0]["content"][0]["source"]["data"]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            actual_page_marker = image.getpixel((0, 0))[0]

        call_index = len(self.requests)
        self.requests.append(request)
        input_schema = request["tools"][0]["input_schema"]
        payload = {
            "trang_khop_du_kien": actual_page_marker == tentative_page
            and call_index not in self.mismatch_call_indexes
        }
        for key, schema in input_schema["properties"].items():
            if key == "trang_khop_du_kien":
                continue
            payload[key] = {
                "value": _blank_from_value_schema(schema["properties"]["value"]),
                "flags": [],
            }
        return make_tool_response(payload)


schema = load_schema()

# ---- Scope and slicing ----
check("Task 3b có đúng 31 parent IDs", len(TASK3B_IDS) == 31, TASK3B_IDS)
check("Task 3b IDs không trùng", len(set(TASK3B_IDS)) == 31)
for page, expected_ids in TASK3B_PAGE_SCOPE.items():
    page_slice = build_page_slice(schema, page)
    check(
        f"slice trang {page} đúng thứ tự IDs",
        [question["id"] for question in page_slice] == list(expected_ids),
        [question["id"] for question in page_slice],
    )

page1 = build_page_slice(schema, 1)
q5 = next(question for question in page1 if question["id"] == "Q5")
check(
    "Q5 chỉ có 3 checkbox Task 3b",
    [component["id"] for component in q5["components"]]
    == list(Q5_SELECT_COMPONENTS),
    q5,
)
check(
    "Q5 loại Q5_lop_cao_nhat text",
    "Q5_lop_cao_nhat" not in json.dumps(q5, ensure_ascii=False),
)
q6 = next(question for question in page1 if question["id"] == "Q6")
check(
    "Q6 slice không lộ subfield text",
    "Q6_tuoi_ket_hon" not in json.dumps(q6, ensure_ascii=False),
)
expect_error("page ngoài 1..7 bị từ chối", Exception, lambda: build_page_slice(schema, 8))

# ---- Dynamic tool schema and prompt ----
tool = build_tool_definition(page1)
tool_schema = tool["input_schema"]
check("tool schema bật strict output", tool.get("strict") is True, tool)


def collect_schema_keys(value):
    keys = []
    if isinstance(value, dict):
        keys.extend(value)
        for child in value.values():
            keys.extend(collect_schema_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(collect_schema_keys(child))
    return keys


all_tools = [
    build_tool_definition(build_page_slice(schema, page_number))
    for page_number in TASK3B_PAGE_SCOPE
]
schema_keys = collect_schema_keys([item["input_schema"] for item in all_tools])
check("mọi page tool đều bật strict", all(item.get("strict") is True for item in all_tools))
check("strict schema không dùng uniqueItems unsupported", "uniqueItems" not in schema_keys)
check("strict schema không dùng minItems > 1", "minItems" not in schema_keys)
check(
    "tool schema required đủ page bool + 8 IDs",
    tool_schema["required"] == ["trang_khop_du_kien", *TASK3B_PAGE_SCOPE[1]],
    tool_schema["required"],
)
check(
    "mọi question property required value+flags",
    all(
        tool_schema["properties"][question_id]["required"] == ["value", "flags"]
        for question_id in TASK3B_PAGE_SCOPE[1]
    ),
)
check(
    "Q5 tool schema dùng boolean cho 3 components",
    all(
        definition["type"] == "boolean"
        for definition in tool_schema["properties"]["Q5"]["properties"]["value"]
        ["properties"].values()
    ),
)
page4 = build_page_slice(schema, 4)
q17_schema = build_tool_definition(page4)["input_schema"]["properties"]["Q17"]
check(
    "Q17 tool schema có rows + khong_ai_co",
    q17_schema["properties"]["value"]["required"] == ["rows", "khong_ai_co"],
)
prompt = build_user_prompt(2, build_page_slice(schema, 2))
for required_phrase in (
    "Tick, X, khoanh tròn, gạch chéo",
    '"ko"/"không"',
    "gạch huỷ",
    "multi_mark_on_single_select",
    "depends_on",
    "exclusive",
    "Q10",
    "Q30",
    "needs_review",
):
    check(
        f"prompt chứa rule {required_phrase}",
        required_phrase in prompt,
        required_phrase,
    )

image_for_request = TMP_ROOT / "request.png"
make_image(image_for_request)
request = build_api_request(
    image_path=image_for_request,
    page_number=1,
    page_slice=page1,
    model="claude-test",
)
check(
    "request ép đúng một tool call",
    request["tool_choice"]
    == {
        "type": "tool",
        "name": "submit_mc_page",
        "disable_parallel_tool_use": True,
    },
)
check("request gửi 1 ảnh base64", request["messages"][0]["content"][0]["source"]["type"] == "base64")


class FakeHTTPResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b'{"content": []}'


http_attempts = []
sleep_delays = []
original_urlopen = mc_extraction.urllib.request.urlopen
original_sleep = mc_extraction.time.sleep


def fake_urlopen(request, timeout):
    http_attempts.append((request, timeout))
    if len(http_attempts) == 1:
        raise urllib.error.HTTPError(
            request.full_url,
            529,
            "overloaded",
            {"Retry-After": "0"},
            io.BytesIO(b'{"error":{"type":"overloaded_error"}}'),
        )
    return FakeHTTPResponse()


try:
    mc_extraction.urllib.request.urlopen = fake_urlopen
    mc_extraction.time.sleep = sleep_delays.append
    retry_response = AnthropicHTTPClient(
        api_key="fake-test-key", retries=1
    ).create_message({"model": "claude-test"})
finally:
    mc_extraction.urllib.request.urlopen = original_urlopen
    mc_extraction.time.sleep = original_sleep

check("HTTP 529 được retry", len(http_attempts) == 2, len(http_attempts))
check("HTTP retry tôn trọng Retry-After", sleep_delays == [0.0], sleep_delays)
check("HTTP retry trả response kế tiếp", retry_response == {"content": []}, retry_response)


def always_overloaded(request, timeout):
    raise urllib.error.HTTPError(
        request.full_url,
        529,
        "overloaded",
        {},
        io.BytesIO(b'{"error":{"type":"overloaded_error"}}'),
    )


exhausted_error = None
try:
    mc_extraction.urllib.request.urlopen = always_overloaded
    AnthropicHTTPClient(api_key="fake-test-key", retries=0).create_message(
        {"model": "claude-test"}
    )
except AnthropicAPIError as exc:
    exhausted_error = exc
finally:
    mc_extraction.urllib.request.urlopen = original_urlopen
check(
    "HTTP service lỗi sau hết retry được phân loại batch-fatal",
    exhausted_error is not None and exhausted_error.batch_fatal,
    exhausted_error,
)

# ---- Validation semantics: null, [], flags, Q5/Q17 ----
payload1 = blank_payload(page1)
payload1["Q5"]["flags"] = ["multi_mark_on_single_select"]
answers1, matches1, invalid1 = validate_page_payload(payload1, page1)
check("single blank giữ null", answers1["Q3"]["value"] is None, answers1["Q3"])
check("multi blank giữ [] khác null", answers1["Q7"]["value"] == [], answers1["Q7"])
check("Q5 bool giữ nguyên", answers1["Q5"]["value"] == dict.fromkeys(Q5_SELECT_COMPONENTS, False))
check(
    "Q5 tự bỏ multi_mark flag không có nghĩa",
    "multi_mark_on_single_select" not in answers1["Q5"]["flags"],
    answers1["Q5"],
)
check("payload hợp lệ không invalid codes", matches1 and invalid1 == {}, invalid1)

q3 = next(question for question in page1 if question["id"] == "Q3")
q3_code = q3["options"][0]["code"]
case_payload = blank_payload(page1)
case_payload["Q3"]["value"] = q3_code.upper()
case_answers, _, case_invalid = validate_page_payload(case_payload, page1)
check(
    "enum casing drift được canonicalize về code schema",
    case_answers["Q3"]["value"] == q3_code and case_invalid == {},
    (case_answers["Q3"], case_invalid),
)

page2 = build_page_slice(schema, 2)
payload2 = blank_payload(page2)
payload2["Q10"] = {"value": ["buon_ban", "nong_dan"], "flags": []}
answers2, _, _ = validate_page_payload(payload2, page2)
check(
    "single multi-mark canonical theo schema order",
    answers2["Q10"]["value"] == ["nong_dan", "buon_ban"],
    answers2["Q10"],
)
check(
    "single array tự thêm multi_mark flag",
    "multi_mark_on_single_select" in answers2["Q10"]["flags"],
    answers2["Q10"],
)
payload2_scalar = blank_payload(page2)
payload2_scalar["Q10"] = {
    "value": "nong_dan",
    "flags": ["multi_mark_on_single_select"],
}
answers2_scalar, _, _ = validate_page_payload(payload2_scalar, page2)
check(
    "single scalar tự bỏ multi_mark flag mâu thuẫn",
    "multi_mark_on_single_select" not in answers2_scalar["Q10"]["flags"],
    answers2_scalar["Q10"],
)
payload2_fake_code_flag = blank_payload(page2)
payload2_fake_code_flag["Q10"]["flags"] = ["self_consistency_mismatch"]
expect_error(
    "model không được tự khai code-owned flags",
    ModelOutputError,
    lambda: validate_page_payload(payload2_fake_code_flag, page2),
)

payload4 = blank_payload(page4)
payload4["Q17"]["value"] = {
    "rows": {
        "dien_thoai": ["vo", "chong"],
        "may_tinh": [],
        "may_tinh_bang": [],
    },
    "khong_ai_co": True,
}
payload4["Q17"]["flags"] = ["multi_mark_on_single_select"]
answers4, _, invalid4 = validate_page_payload(payload4, page4)
check(
    "Q17 canonical row order",
    answers4["Q17"]["value"]["rows"]["dien_thoai"] == ["chong", "vo"],
    answers4["Q17"],
)
check(
    "Q17 giữ mâu thuẫn exclusive, không tự sửa",
    answers4["Q17"]["value"]["khong_ai_co"] is True
    and answers4["Q17"]["value"]["rows"]["dien_thoai"],
    answers4["Q17"],
)
check("Q17 hợp lệ không invalid", invalid4 == {}, invalid4)
check(
    "Q17 tự bỏ multi_mark flag không có nghĩa",
    "multi_mark_on_single_select" not in answers4["Q17"]["flags"],
    answers4["Q17"],
)

page6 = build_page_slice(schema, 6)
payload6 = blank_payload(page6)
payload6["Q30"] = {
    "value": ["tieu_thu", "san_xuat", "thu_hai"],
    "flags": [],
}
answers6, _, _ = validate_page_payload(payload6, page6)
check(
    "Q30 multi-mark thật canonical đủ 3 codes",
    answers6["Q30"]["value"] == ["san_xuat", "thu_hai", "tieu_thu"],
    answers6["Q30"],
)
check(
    "Q30 multi-mark thật tự gắn flag",
    "multi_mark_on_single_select" in answers6["Q30"]["flags"],
    answers6["Q30"],
)

missing_payload = blank_payload(page2)
del missing_payload["Q11"]
expect_error(
    "thiếu question field là hard error",
    ModelOutputError,
    lambda: validate_page_payload(missing_payload, page2),
)

# ---- Invalid option retry: one recovery, then retained raw + flag ----
bad = blank_payload(page2)
bad["Q10"] = {"value": "code_la", "flags": []}
good = blank_payload(page2)
good["Q10"] = {"value": "nong_dan", "flags": []}
retry_image = TMP_ROOT / "retry.png"
make_image(retry_image)
recover_client = SequenceClient([bad, good])
recovered, recovered_page = extract_page_run(
    client=recover_client,
    image_path=retry_image,
    page_number=2,
    page_slice=page2,
    model="claude-test",
)
check("invalid code retry đúng 1 lần rồi recover", len(recover_client.requests) == 2)
check("retry valid dùng giá trị mới", recovered["Q10"]["value"] == "nong_dan", recovered["Q10"])
check("retry giữ page match", recovered_page is True)
check(
    "retry prompt nêu code lỗi",
    "code_la" in recover_client.requests[1]["messages"][0]["content"][1]["text"],
)

fail_client = SequenceClient([bad, bad])
failed_retry, _ = extract_page_run(
    client=fail_client,
    image_path=retry_image,
    page_number=2,
    page_slice=page2,
    model="claude-test",
)
check("invalid code retry tối đa 1 lần", len(fail_client.requests) == 2)
check("invalid code giữ raw sau retry", failed_retry["Q10"]["value"] == "code_la", failed_retry["Q10"])
check(
    "invalid code gắn flag sau retry",
    "invalid_option_code" in failed_retry["Q10"]["flags"],
    failed_retry["Q10"],
)

# ---- Self-consistency ----
run1 = {"Q11": {"value": ["hoi_phu_nu", "hoi_nong_dan"], "flags": []}}
run2 = {"Q11": {"value": ["hoi_nong_dan", "hoi_phu_nu"], "flags": []}}
merged, debug = merge_self_consistency(run1, run2, ["Q11"])
check("self-consistency array ignore order", debug["Q11"]["match"] is True, debug)
check("match không gắn mismatch flag", merged["Q11"]["flags"] == [], merged)
check("values_equal phân biệt null và []", not values_equal(None, []))

run2_mismatch = {"Q11": {"value": ["hoi_phu_nu"], "flags": ["needs_review"]}}
merged_mismatch, debug_mismatch = merge_self_consistency(run1, run2_mismatch, ["Q11"])
check("mismatch giữ run1 official", merged_mismatch["Q11"]["value"] == run1["Q11"]["value"])
check(
    "mismatch gắn self_consistency_mismatch",
    "self_consistency_mismatch" in merged_mismatch["Q11"]["flags"],
    merged_mismatch,
)
check(
    "review flag ở run2 không bị mất",
    "needs_review" in merged_mismatch["Q11"]["flags"],
    merged_mismatch,
)
run2_invalid = {
    "Q11": {
        "value": ["hoi_phu_nu", "code_la"],
        "flags": ["invalid_option_code"],
    }
}
merged_invalid_run2, _ = merge_self_consistency(run1, run2_invalid, ["Q11"])
check(
    "invalid flag chỉ ở run2 không gắn lên official run1 hợp lệ",
    "invalid_option_code" not in merged_invalid_run2["Q11"]["flags"],
    merged_invalid_run2,
)
check("debug lưu đủ run1/run2/match", debug_mismatch["Q11"] == {"run1": run1["Q11"]["value"], "run2": run2_mismatch["Q11"]["value"], "match": False})

# ---- Full seven-page record: 14 independent calls + page mismatch ----
page_paths: list[dict] = []
record_render_dir = TMP_ROOT / "_render" / "TEST-001"
record_render_dir.mkdir(parents=True)
for page_number in range(1, 8):
    image_path = record_render_dir / f"TEST-001__p{page_number}.png"
    make_image(image_path, marker=page_number)
    page_paths.append(
        {
            "source_file": "mock.pdf",
            "kind": "pdf_page",
            "image_path": str(image_path),
            "tentative_page": page_number,
        }
    )
# Put page 3's image into tentative slot 4.  The content-aware mock reads the
# image marker, so this exercises the page-order plumbing rather than merely
# forcing a boolean by call index.
page_paths[3]["image_path"] = page_paths[2]["image_path"]
assembly = {
    "record_id": "TEST-001",
    "expected_pages": 7,
    "found_pages": 7,
    "pages": page_paths,
    "flags": [],
    "status": "ok",
}
full_client = ContentAwareSchemaClient()
record = extract_record(
    assembly=assembly,
    questionnaire=schema,
    client=full_client,
    model="claude-test",
    image_base_dir=TMP_ROOT,
    extracted_at="2026-07-22T12:00:00+07:00",
)
check("full record gọi đúng 14 lần", len(full_client.requests) == 14, len(full_client.requests))
check("full record đủ 31 answers đúng order", tuple(record["answers"]) == TASK3B_IDS)
check("full record đủ 7 page metadata", list(record["pages"]) == [str(i) for i in range(1, 8)])
check("ảnh sai slot -> page_order_mismatch", record["pages"]["4"]["page_order_mismatch"] is True)
check("trang khác không mismatch", all(not record["pages"][str(i)]["page_order_mismatch"] for i in (1, 2, 3, 5, 6, 7)))
check("debug đủ 31 câu", len(record["_debug"]["self_consistency_runs"]) == 31)
check("output timestamp/model/schema", record["extracted_at"].endswith("+07:00") and record["model"] == "claude-test" and record["schema_version"] == "v1")

missing_last_image_assembly = copy.deepcopy(assembly)
missing_last_image_assembly["pages"][-1]["image_path"] = str(
    record_render_dir / "TEST-001__p7-missing.png"
)
preflight_client = SchemaDrivenClient()
expect_error(
    "preflight page 7 lỗi trước mọi paid call",
    MCExtractionError,
    lambda: extract_record(
        assembly=missing_last_image_assembly,
        questionnaire=schema,
        client=preflight_client,
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)
check("preflight lỗi không gọi API", len(preflight_client.requests) == 0)

malformed_page7_schema = copy.deepcopy(schema)
q33 = next(
    question
    for question in malformed_page7_schema["questions"]
    if question["id"] == "Q33"
)
q33["options"][1]["code"] = q33["options"][0]["code"]
schema_preflight_client = SchemaDrivenClient()
expect_error(
    "preflight option code page 7 lỗi trước mọi paid call",
    MCExtractionError,
    lambda: extract_record(
        assembly=assembly,
        questionnaire=malformed_page7_schema,
        client=schema_preflight_client,
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)
check("preflight schema lỗi không gọi API", len(schema_preflight_client.requests) == 0)

# ---- CLI run isolation and safe IDs ----
assembly_dir = TMP_ROOT / "assembly"
out_dir = TMP_ROOT / "out"
assembly_dir.mkdir()
with (assembly_dir / "TEST-001.json").open("w", encoding="utf-8") as handle:
    json.dump(assembly, handle)
isolation_client = SchemaDrivenClient()
batch_results = run_cli_records(
    record_ids=["TEST-001", "TEST-404"],
    assembly_dir=assembly_dir,
    out_dir=out_dir,
    schema_path=REPO_ROOT / "schema" / "questionnaire_v1.json",
    client=isolation_client,
    model="claude-test",
    image_base_dir=TMP_ROOT,
)
check("CLI cách ly lỗi xử lý đủ 2 records", len(batch_results) == 2, batch_results)
check("CLI record tốt thành công", batch_results[0]["ok"] is True, batch_results[0])
check("CLI record thiếu assembly lỗi nhưng không crash", batch_results[1]["ok"] is False, batch_results[1])
check("CLI ghi success JSON", (out_dir / "TEST-001.json").is_file())
check("CLI ghi error JSON", (out_dir / "TEST-404.json").is_file())
with (out_dir / "TEST-404.json").open(encoding="utf-8") as handle:
    error_json = json.load(handle)
check("error JSON có status=error", error_json.get("status") == "error", error_json)


class BatchFatalClient:
    def __init__(self):
        self.calls = 0

    def create_message(self, request):
        self.calls += 1
        raise AnthropicAPIError(
            "service unavailable after retries",
            status_code=529,
            error_type="overloaded_error",
            batch_fatal=True,
        )


fatal_client = BatchFatalClient()
fatal_out_dir = TMP_ROOT / "fatal-out"
fatal_out_dir.mkdir()
prior_success_path = fatal_out_dir / "TEST-001.json"
prior_success_path.write_text('{"status":"prior-success"}\n', encoding="utf-8")
prior_success = prior_success_path.read_text(encoding="utf-8")
expect_error(
    "CLI dừng batch ngay khi API service lỗi sau retry",
    AnthropicAPIError,
    lambda: run_cli_records(
        record_ids=["TEST-001", "TEST-404"],
        assembly_dir=assembly_dir,
        out_dir=fatal_out_dir,
        schema_path=REPO_ROOT / "schema" / "questionnaire_v1.json",
        client=fatal_client,
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)
check("API service lỗi chỉ gọi một lần", fatal_client.calls == 1, fatal_client.calls)
check(
    "API service lỗi không ghi đè output thành công cũ",
    prior_success_path.read_text(encoding="utf-8") == prior_success,
)

config_client = SchemaDrivenClient()
expect_error(
    "CLI reject max_tokens toàn cục trước record loop",
    MCExtractionError,
    lambda: run_cli_records(
        record_ids=["TEST-001", "TEST-404"],
        assembly_dir=assembly_dir,
        out_dir=TMP_ROOT / "config-out",
        schema_path=REPO_ROOT / "schema" / "questionnaire_v1.json",
        client=config_client,
        model="claude-test",
        image_base_dir=TMP_ROOT,
        max_tokens=0,
    ),
)
check("config lỗi không gọi API", len(config_client.requests) == 0)
expect_error(
    "record_id path traversal bị chặn",
    MCExtractionError,
    lambda: validate_record_id("../evil"),
)
expect_error(
    "CLI không mặc định upload toàn manifest khi thiếu selection",
    MCExtractionError,
    lambda: resolve_record_ids(None, REPO_ROOT / "data" / "manifest.csv"),
)
expect_error(
    "API endpoint khác Anthropic bị chặn để tránh lộ key/ảnh",
    AnthropicAPIError,
    lambda: AnthropicHTTPClient(
        api_key="fake-test-key", api_url="https://attacker.invalid/v1/messages"
    ),
)
check(
    "HTTP auth/permission/model lỗi được phân loại batch-fatal",
    all(
        AnthropicAPIError("fatal", status_code=status).batch_fatal
        for status in (401, 403, 404)
    ),
)
check(
    "HTTP 400 image-specific vẫn được cách ly theo record",
    not mc_extraction._is_shared_request_configuration_error(
        "invalid_request_error", "image exceeds maximum dimensions"
    ),
)
check(
    "HTTP 400 tool schema lỗi được phân loại batch-global",
    mc_extraction._is_shared_request_configuration_error(
        "invalid_request_error", "tools.0.input_schema is invalid"
    ),
)
outside_image = Path(tempfile.gettempdir()).resolve().parent / "outside.png"
unsafe_assembly = copy.deepcopy(assembly)
unsafe_assembly["pages"][0]["image_path"] = str(outside_image)
expect_error(
    "assembly image ngoài allowed root bị chặn trước khi upload",
    MCExtractionError,
    lambda: extract_record(
        assembly=unsafe_assembly,
        questionnaire=schema,
        client=SchemaDrivenClient(),
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)
other_render_dir = TMP_ROOT / "_render" / "OTHER-001"
other_render_dir.mkdir(parents=True)
other_record_image = other_render_dir / "OTHER-001__p1.png"
make_image(other_record_image, marker=1)
cross_record_assembly = copy.deepcopy(assembly)
cross_record_assembly["pages"][0]["image_path"] = str(other_record_image)
expect_error(
    "assembly không được upload ảnh của record khác cùng workspace",
    MCExtractionError,
    lambda: extract_record(
        assembly=cross_record_assembly,
        questionnaire=schema,
        client=SchemaDrivenClient(),
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)
extra_page_assembly = copy.deepcopy(assembly)
extra_page_assembly["pages"].append(
    {
        "source_file": "mock.pdf",
        "kind": "pdf_page",
        "image_path": str(page_paths[0]["image_path"]),
        "tentative_page": 8,
    }
)
expect_error(
    "assembly page ngoài 1..7 không bị bỏ qua âm thầm",
    MCExtractionError,
    lambda: extract_record(
        assembly=extra_page_assembly,
        questionnaire=schema,
        client=SchemaDrivenClient(),
        model="claude-test",
        image_base_dir=TMP_ROOT,
    ),
)

# ---- Ground-truth comparator normalizes Q5/Q17 and required flags ----
with (REPO_ROOT / "data" / "ground_truth" / "LCA-LP-001.json").open(
    encoding="utf-8"
) as handle:
    ground_truth = json.load(handle)
oracle_extracted = {"record_id": "LCA-LP-001", "answers": {}}
for question_id in COMPARATOR_TASK3B_FIELDS:
    raw_ground_answer = ground_truth["answers"][question_id]
    if question_id == "Q5":
        expected_value = {
            "Q5_khong_di_hoc": False,
            "Q5_khong_tieng_pho_thong": False,
            "Q5_trung_cap_dh": True,
        }
    elif question_id == "Q17":
        expected_value = {
            "rows": {
                "dien_thoai": ["chong", "vo"],
                "may_tinh": [],
                "may_tinh_bang": [],
            },
            "khong_ai_co": False,
        }
    else:
        expected_value = raw_ground_answer["value"]
    required_flags = [
        flag
        for flag in raw_ground_answer.get("flags", [])
        if flag == "multi_mark_on_single_select"
    ]
    oracle_extracted["answers"][question_id] = {
        "value": expected_value,
        "flags": required_flags,
    }
oracle_results = compare_documents(
    ground_truth, oracle_extracted, COMPARATOR_TASK3B_FIELDS
)
check(
    "comparator normalize Q5/Q17 đạt 31/31 oracle",
    len(oracle_results) == 31 and all(result.matches for result in oracle_results),
    [result.question_id for result in oracle_results if not result.matches],
)
oracle_without_q10_flag = copy.deepcopy(oracle_extracted)
oracle_without_q10_flag["answers"]["Q10"]["flags"] = []
flag_results = compare_documents(
    ground_truth, oracle_without_q10_flag, COMPARATOR_TASK3B_FIELDS
)
failed_fields = [result.question_id for result in flag_results if not result.matches]
check(
    "comparator bắt thiếu multi_mark flag Q10",
    failed_fields == ["Q10"],
    failed_fields,
)

redacted_extracted = copy.deepcopy(oracle_extracted)
redacted_extracted["answers"]["Q3"]["value"] = "PII-SHOULD-NOT-PRINT"
redacted_results = compare_documents(ground_truth, redacted_extracted, ["Q3"])
redacted_output = io.StringIO()
with contextlib.redirect_stdout(redacted_output):
    print_report(redacted_results)
check(
    "comparator che expected/actual mặc định",
    "PII-SHOULD-NOT-PRINT" not in redacted_output.getvalue()
    and "<redacted" in redacted_output.getvalue(),
    redacted_output.getvalue(),
)
shown_output = io.StringIO()
with contextlib.redirect_stdout(shown_output):
    print_report(redacted_results, show_values=True)
check(
    "comparator chỉ hiện value khi opt-in",
    "PII-SHOULD-NOT-PRINT" in shown_output.getvalue(),
    shown_output.getvalue(),
)


def main() -> int:
    failed = [result for result in RESULTS if not result[1]]
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if not ok and detail is not None:
            line += f"  -> {detail}"
        print(line)
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} pass")
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
