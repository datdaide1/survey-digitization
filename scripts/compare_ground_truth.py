#!/usr/bin/env python3
"""Compare extracted survey answers with their human-authored ground truth.

Examples:
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" scripts/compare_ground_truth.py LCA-LP-001 --fields task3b
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" scripts/compare_ground_truth.py LCA-LP-001 --fields Q3,Q4,Q17
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" scripts/compare_ground_truth.py LCA-LP-001 --fields all

Values are redacted from differences by default because ``--fields all`` can
include PII.  Use ``--show-values`` only in an access-controlled terminal.

Exit codes follow the usual comparison-tool convention:
  0  every selected field matches
  1  one or more selected fields differ
  2  invalid arguments, unsafe paths, or unreadable/invalid input data
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# The parent IDs in docs/implement-plan-03b-mc-extraction.md section 2.1.
TASK3B_FIELDS: tuple[str, ...] = (
    "CONSENT_1",
    "CONSENT_2",
    "Q3",
    "Q4",
    "Q5",
    "Q6",
    "Q7",
    "Q8",
    "Q10",
    "Q11",
    "Q12",
    "Q13",
    "Q16a",
    "Q17",
    "Q18",
    "Q19",
    "Q20",
    "Q21a",
    "Q21b",
    "Q22a",
    "Q22b",
    "Q23",
    "Q24",
    "Q25",
    "Q26",
    "Q27a",
    "Q28",
    "Q29a",
    "Q29b",
    "Q30",
    "Q33",
)

Q5_SELECT_COMPONENTS: tuple[str, ...] = (
    "Q5_khong_di_hoc",
    "Q5_khong_tieng_pho_thong",
    "Q5_trung_cap_dh",
)

# Only extraction-owned flags are oracle requirements here.  In particular,
# conflicting_answer belongs to Task 6 and must not make a Task 3B comparison fail.
REQUIRED_GROUND_TRUTH_FLAGS = frozenset({"multi_mark_on_single_select"})

SAFE_RECORD_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SAFE_FIELD_ID = re.compile(r"^[A-Za-z0-9_]+$")
_MISSING = object()


class ComparisonInputError(ValueError):
    """The comparison could not run because an input or its shape is invalid."""


@dataclass(frozen=True)
class FieldComparison:
    """Comparison result for one parent question ID."""

    question_id: str
    expected_value: Any = _MISSING
    actual_value: Any = _MISSING
    required_flags: tuple[str, ...] = ()
    actual_flags: tuple[str, ...] = ()
    value_matches: bool = False
    flags_match: bool = False
    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def matches(self) -> bool:
        return self.value_matches and self.flags_match and not self.errors


def _strict_json_constant(value: str) -> None:
    """Reject NaN/Infinity, which Python accepts but JSON does not."""

    raise ValueError(f"hằng số JSON không hợp lệ: {value}")


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object and report a useful, path-aware error."""

    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle, parse_constant=_strict_json_constant)
    except FileNotFoundError as exc:
        raise ComparisonInputError(f"không tìm thấy file: {path}") from exc
    except OSError as exc:
        raise ComparisonInputError(f"không đọc được {path}: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise ComparisonInputError(f"JSON không hợp lệ trong {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise ComparisonInputError(f"root JSON phải là object: {path}")
    return value


def _answers(document: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    answers = document.get("answers")
    if not isinstance(answers, dict):
        raise ComparisonInputError(f"{label}.answers phải là object")
    if not all(isinstance(question_id, str) for question_id in answers):
        raise ComparisonInputError(f"mọi key trong {label}.answers phải là string")
    return answers


def _deduplicate(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(values))


def resolve_fields(
    specification: str,
    ground_truth_answers: Mapping[str, Any],
    extracted_answers: Mapping[str, Any],
) -> list[str]:
    """Resolve ``task3b``, ``all``, or an explicit comma-separated ID list."""

    requested = specification.strip()
    keyword = requested.casefold()
    if keyword == "task3b":
        return list(TASK3B_FIELDS)
    if keyword == "all":
        # Use the union so a field missing from either document cannot disappear
        # silently.  Ground-truth order is stable and easiest for humans to scan.
        fields = list(ground_truth_answers)
        fields.extend(qid for qid in extracted_answers if qid not in ground_truth_answers)
        if not fields:
            raise ComparisonInputError("không có field nào để so sánh")
        return fields

    fields = [part.strip() for part in requested.split(",")]
    if not fields or any(not item for item in fields):
        raise ComparisonInputError(
            "--fields phải là task3b, all, hoặc danh sách ID cách nhau bằng dấu phẩy"
        )
    invalid = [item for item in fields if not SAFE_FIELD_ID.fullmatch(item)]
    if invalid:
        raise ComparisonInputError(f"field ID không hợp lệ: {', '.join(invalid)}")
    return _deduplicate(fields)


def _ground_truth_flags(raw_answer: Mapping[str, Any], question_id: str) -> tuple[str, ...]:
    raw_flags = raw_answer.get("flags", [])
    if not isinstance(raw_flags, list) or not all(isinstance(flag, str) for flag in raw_flags):
        raise ComparisonInputError(f"ground_truth.answers.{question_id}.flags phải là array[string]")
    return tuple(sorted(set(raw_flags) & REQUIRED_GROUND_TRUTH_FLAGS))


def _unwrap_ground_truth_value(value: Any, path: str) -> Any:
    if not isinstance(value, dict) or "value" not in value:
        raise ComparisonInputError(f"{path} phải là object có key 'value'")
    return value["value"]


def _normalize_q5(raw_answer: Mapping[str, Any]) -> dict[str, bool]:
    """Convert old Q5.components ground truth to Task 3B's parent value object."""

    if "value" in raw_answer:
        source = raw_answer["value"]
        if not isinstance(source, dict):
            raise ComparisonInputError("ground_truth.answers.Q5.value phải là object")
        values = {component: source.get(component, _MISSING) for component in Q5_SELECT_COMPONENTS}
    else:
        components = raw_answer.get("components")
        if not isinstance(components, dict):
            raise ComparisonInputError("ground_truth.answers.Q5.components phải là object")
        values = {
            component: _unwrap_ground_truth_value(
                components.get(component), f"ground_truth.answers.Q5.components.{component}"
            )
            for component in Q5_SELECT_COMPONENTS
        }

    missing = [component for component, value in values.items() if value is _MISSING]
    if missing:
        raise ComparisonInputError(f"ground_truth.answers.Q5 thiếu component: {', '.join(missing)}")
    non_boolean = [component for component, value in values.items() if not isinstance(value, bool)]
    if non_boolean:
        raise ComparisonInputError(
            "ground_truth.answers.Q5 component phải là boolean: " + ", ".join(non_boolean)
        )
    return values  # type: ignore[return-value]


def _normalize_q17(raw_answer: Mapping[str, Any]) -> dict[str, Any]:
    """Convert old Q17 row wrappers to Task 3B's nested value object."""

    source = raw_answer.get("value", raw_answer)
    if not isinstance(source, dict):
        raise ComparisonInputError("ground_truth.answers.Q17 phải là object")

    rows = source.get("rows")
    if not isinstance(rows, dict):
        raise ComparisonInputError("ground_truth.answers.Q17.rows phải là object")

    normalized_rows: dict[str, list[Any]] = {}
    for row_code, row_value in rows.items():
        if not isinstance(row_code, str):
            raise ComparisonInputError("ground_truth.answers.Q17.rows có row code không phải string")
        if isinstance(row_value, dict):
            row_value = _unwrap_ground_truth_value(
                row_value, f"ground_truth.answers.Q17.rows.{row_code}"
            )
        if not isinstance(row_value, list):
            raise ComparisonInputError(
                f"ground_truth.answers.Q17.rows.{row_code} phải là array"
            )
        normalized_rows[row_code] = row_value

    khong_ai_co = source.get("khong_ai_co", _MISSING)
    if not isinstance(khong_ai_co, bool):
        raise ComparisonInputError("ground_truth.answers.Q17.khong_ai_co phải là boolean")
    return {"rows": normalized_rows, "khong_ai_co": khong_ai_co}


def normalize_ground_truth_answer(question_id: str, raw_answer: Any) -> tuple[Any, tuple[str, ...]]:
    """Return the Task-output value plus extraction-owned required flags."""

    if not isinstance(raw_answer, dict):
        raise ComparisonInputError(f"ground_truth.answers.{question_id} phải là object")

    required_flags = _ground_truth_flags(raw_answer, question_id)
    if question_id == "Q5":
        value = _normalize_q5(raw_answer)
    elif question_id == "Q17":
        value = _normalize_q17(raw_answer)
    elif "value" in raw_answer:
        value = raw_answer["value"]
    else:
        raise ComparisonInputError(f"ground_truth.answers.{question_id} thiếu key 'value'")
    return value, required_flags


def normalize_extracted_answer(question_id: str, raw_answer: Any) -> tuple[Any, tuple[str, ...]]:
    """Validate the parent-answer contract ``{value, flags}``."""

    if not isinstance(raw_answer, dict):
        raise ComparisonInputError(f"extracted.answers.{question_id} phải là object")
    if "value" not in raw_answer:
        raise ComparisonInputError(f"extracted.answers.{question_id} thiếu key 'value'")
    if "flags" not in raw_answer:
        raise ComparisonInputError(f"extracted.answers.{question_id} thiếu key 'flags'")
    flags = raw_answer["flags"]
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ComparisonInputError(f"extracted.answers.{question_id}.flags phải là array[string]")
    return raw_answer["value"], tuple(flags)


def _canonical_json(value: Any) -> tuple[Any, ...]:
    """Canonicalize JSON, treating every array as an unordered multiset recursively."""

    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, (int, float)):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    if isinstance(value, list):
        items = [_canonical_json(item) for item in value]
        return ("array", tuple(sorted(items, key=repr)))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            return ("invalid-object-key", repr(value))
        return (
            "object",
            tuple((key, _canonical_json(value[key])) for key in sorted(value)),
        )
    return ("non-json", type(value).__name__, repr(value))


def values_equal(expected: Any, actual: Any) -> bool:
    """Compare JSON values with recursively order-insensitive arrays."""

    return _canonical_json(expected) == _canonical_json(actual)


def compare_documents(
    ground_truth: Mapping[str, Any],
    extracted: Mapping[str, Any],
    fields_to_compare: Sequence[str],
) -> list[FieldComparison]:
    ground_answers = _answers(ground_truth, "ground_truth")
    extracted_answers = _answers(extracted, "extracted")
    results: list[FieldComparison] = []

    for question_id in fields_to_compare:
        errors: list[str] = []
        expected_value: Any = _MISSING
        actual_value: Any = _MISSING
        required_flags: tuple[str, ...] = ()
        actual_flags: tuple[str, ...] = ()

        raw_ground = ground_answers.get(question_id, _MISSING)
        if raw_ground is _MISSING:
            errors.append("thiếu trong ground truth")
        else:
            try:
                expected_value, required_flags = normalize_ground_truth_answer(
                    question_id, raw_ground
                )
            except ComparisonInputError as exc:
                errors.append(str(exc))

        raw_extracted = extracted_answers.get(question_id, _MISSING)
        if raw_extracted is _MISSING:
            errors.append("thiếu trong extracted output")
        else:
            try:
                actual_value, actual_flags = normalize_extracted_answer(
                    question_id, raw_extracted
                )
            except ComparisonInputError as exc:
                errors.append(str(exc))

        value_matches = (
            expected_value is not _MISSING
            and actual_value is not _MISSING
            and values_equal(expected_value, actual_value)
        )
        flags_match = not errors and set(required_flags).issubset(actual_flags)
        results.append(
            FieldComparison(
                question_id=question_id,
                expected_value=expected_value,
                actual_value=actual_value,
                required_flags=required_flags,
                actual_flags=actual_flags,
                value_matches=value_matches,
                flags_match=flags_match,
                errors=tuple(errors),
            )
        )
    return results


def _print_table(rows: Sequence[Sequence[str]]) -> None:
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    for row_index, row in enumerate(rows):
        print("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)))
        if row_index == 0:
            print("  ".join("-" * width for width in widths))


def _json_display(value: Any) -> str:
    if value is _MISSING:
        return "<missing>"
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def print_report(
    results: Sequence[FieldComparison], *, show_values: bool = False
) -> None:
    rows: list[list[str]] = [["Field", "Value", "Required flags", "Result"]]
    for result in results:
        if result.errors:
            value_status = "ERROR"
        else:
            value_status = "MATCH" if result.value_matches else "DIFF"
        if not result.required_flags:
            flag_status = "-"
        else:
            missing_flags = sorted(set(result.required_flags) - set(result.actual_flags))
            flag_status = "MATCH" if not missing_flags else "MISSING: " + ",".join(missing_flags)
        rows.append(
            [
                result.question_id,
                value_status,
                flag_status,
                "PASS" if result.matches else "FAIL",
            ]
        )
    _print_table(rows)

    failures = [result for result in results if not result.matches]
    if failures:
        print("\nDifferences:")
        for result in failures:
            print(f"- {result.question_id}")
            for error in result.errors:
                print(f"    error: {error}")
            if show_values and not result.value_matches and not result.errors:
                print(f"    expected: {_json_display(result.expected_value)}")
                print(f"    actual:   {_json_display(result.actual_value)}")
            elif not result.value_matches and not result.errors:
                print("    values: <redacted; use --show-values in a controlled terminal>")
            missing_flags = sorted(set(result.required_flags) - set(result.actual_flags))
            if missing_flags:
                print(f"    missing required flags: {', '.join(missing_flags)}")
                print(f"    actual flags: {_json_display(list(result.actual_flags))}")

    matched = sum(result.matches for result in results)
    print(f"\nSummary: {matched}/{len(results)} fields matched.")


def _validate_record_id(record_id: str) -> str:
    if not SAFE_RECORD_ID.fullmatch(record_id):
        raise ComparisonInputError(
            "record_id không hợp lệ (chỉ cho phép chữ ASCII, số, '_' và '-')"
        )
    return record_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record_id", help="Mã phiếu, ví dụ LCA-LP-001")
    parser.add_argument(
        "--fields",
        default="task3b",
        help="task3b (31 câu), all, hoặc danh sách ID cách nhau bằng dấu phẩy",
    )
    parser.add_argument(
        "--extracted-dir",
        "--extract-dir",
        dest="extracted_dir",
        default="output/extract_mc",
        help="Thư mục chứa JSON trích xuất (mặc định: output/extract_mc)",
    )
    parser.add_argument(
        "--ground-truth-dir",
        default="data/ground_truth",
        help="Thư mục chứa JSON ground truth (mặc định: data/ground_truth)",
    )
    parser.add_argument(
        "--show-values",
        action="store_true",
        help="Hiện expected/actual (có thể chứa PII; mặc định được che).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        record_id = _validate_record_id(args.record_id)
        extracted_path = Path(args.extracted_dir) / f"{record_id}.json"
        ground_truth_path = Path(args.ground_truth_dir) / f"{record_id}.json"
        extracted = load_json(extracted_path)
        ground_truth = load_json(ground_truth_path)

        for label, document in (("extracted", extracted), ("ground truth", ground_truth)):
            embedded_record_id = document.get("record_id")
            if embedded_record_id is not None and embedded_record_id != record_id:
                raise ComparisonInputError(
                    f"{label} record_id là {embedded_record_id!r}, mong đợi {record_id!r}"
                )

        ground_answers = _answers(ground_truth, "ground_truth")
        extracted_answers = _answers(extracted, "extracted")
        selected_fields = resolve_fields(args.fields, ground_answers, extracted_answers)
        results = compare_documents(ground_truth, extracted, selected_fields)
        print(f"Record: {record_id}")
        print(f"Extracted: {extracted_path}")
        print(f"Ground truth: {ground_truth_path}\n")
        print_report(results, show_values=args.show_values)
        return 0 if all(result.matches for result in results) else 1
    except ComparisonInputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
