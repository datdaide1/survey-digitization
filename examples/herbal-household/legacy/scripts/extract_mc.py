#!/usr/bin/env python3
"""Task 3b — extract single/multi-select marks with Claude Vision.

Examples:
  python scripts/extract_mc.py --record-id LCA-LP-001
  python scripts/extract_mc.py --all --manifest data/manifest.csv

Each page is sent twice in independent Messages API calls.  Tests inject a mock
client; live execution requires ``ANTHROPIC_API_KEY``.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).parent))
from lib.mc_extraction import (  # noqa: E402
    AnthropicAPIError,
    AnthropicHTTPClient,
    MCExtractionError,
    TASK3B_PAGE_SCOPE,
    build_page_slice,
    build_tool_definition,
    extract_record,
    load_json,
    now_bangkok_iso,
    validate_record_id,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _safe_output_path(out_dir: str | Path, record_id: str) -> Path:
    record_id = validate_record_id(record_id)
    root = Path(out_dir).resolve()
    candidate = (root / f"{record_id}.json").resolve()
    if candidate.parent != root:
        raise MCExtractionError(f"Output path thoát thư mục đích: {candidate}")
    return candidate


def _read_manifest_ids(manifest_path: str | Path) -> list[str]:
    path = Path(manifest_path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: list[str] = []
    for line_number, row in enumerate(rows, start=2):
        record_id = row.get("record_id") or ""
        try:
            validate_record_id(record_id)
        except MCExtractionError as exc:
            raise MCExtractionError(
                f"{path}:{line_number}: record_id không hợp lệ"
            ) from exc
        if record_id not in result:
            result.append(record_id)
    return result


def resolve_record_ids(
    requested_ids: Iterable[str] | None,
    manifest_path: str | Path,
    *,
    process_all: bool = False,
) -> list[str]:
    if requested_ids:
        result: list[str] = []
        for record_id in requested_ids:
            validate_record_id(record_id)
            if record_id not in result:
                result.append(record_id)
        return result
    if process_all:
        return _read_manifest_ids(manifest_path)
    raise MCExtractionError(
        "Phải truyền --record-id. Batch toàn manifest chỉ chạy khi chủ động thêm --all "
        "(ít nhất 14 API calls/phiếu; tối đa 28 nếu cả hai run đều retry code sai)."
    )


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _error_record(
    record_id: str, schema_version: str | None, model: str, error: Exception
) -> dict[str, Any]:
    return {
        "record_id": record_id,
        "schema_version": schema_version,
        "extracted_at": now_bangkok_iso(),
        "model": model,
        "status": "error",
        "answers": {},
        "pages": {},
        "error": {"type": type(error).__name__, "message": str(error)},
    }


def run(
    *,
    record_ids: Iterable[str],
    assembly_dir: str | Path,
    out_dir: str | Path,
    schema_path: str | Path,
    client: Any,
    model: str,
    image_base_dir: str | Path,
    allowed_image_roots: Iterable[str | Path] | None = None,
    max_tokens: int = 4096,
) -> list[dict[str, Any]]:
    """Process records independently and write one success/error JSON per record."""

    questionnaire = load_json(schema_path)
    schema_version = questionnaire.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version:
        raise MCExtractionError("questionnaire.schema_version không hợp lệ")
    if not isinstance(model, str) or not model.strip():
        raise MCExtractionError("Tên model Claude không được rỗng")
    if max_tokens <= 0:
        raise MCExtractionError("max_tokens phải > 0")
    # Questionnaire/request configuration is shared by the entire batch. Fail
    # once, before touching any prior per-record output, if it cannot generate
    # every strict page tool schema.
    for page_number in TASK3B_PAGE_SCOPE:
        build_tool_definition(build_page_slice(questionnaire, page_number))
    assembly_root = Path(assembly_dir).resolve()
    normalized_allowed_roots = (
        list(allowed_image_roots) if allowed_image_roots is not None else None
    )
    results: list[dict[str, Any]] = []

    for requested_id in record_ids:
        record_id = validate_record_id(requested_id)
        out_path = _safe_output_path(out_dir, record_id)
        assembly_path = (assembly_root / f"{record_id}.json").resolve()
        try:
            if assembly_path.parent != assembly_root:
                raise MCExtractionError(
                    f"Assembly path thoát thư mục nguồn: {assembly_path}"
                )
            assembly = load_json(assembly_path)
            if assembly.get("record_id") != record_id:
                raise MCExtractionError(
                    f"record_id trong assembly {assembly.get('record_id')!r} "
                    f"không khớp tên yêu cầu {record_id!r}"
                )
            output = extract_record(
                assembly=assembly,
                questionnaire=questionnaire,
                client=client,
                model=model,
                image_base_dir=image_base_dir,
                allowed_image_roots=normalized_allowed_roots,
                max_tokens=max_tokens,
            )
            _atomic_write_json(out_path, output)
            results.append({"record_id": record_id, "ok": True, "output": output})
        except Exception as exc:  # isolation per record, matching ingest.py convention
            if isinstance(exc, AnthropicAPIError) and exc.batch_fatal:
                # Credentials, permissions, billing, or a missing model cannot
                # recover on the next record; abort instead of producing a full
                # manifest of doomed API calls/error files.
                raise
            error_output = _error_record(
                record_id,
                schema_version if isinstance(schema_version, str) else None,
                model,
                exc,
            )
            _atomic_write_json(out_path, error_output)
            results.append(
                {"record_id": record_id, "ok": False, "output": error_output, "error": exc}
            )
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--record-id",
        action="append",
        dest="record_ids",
        help="Chỉ xử lý record này; có thể truyền nhiều lần.",
    )
    selection.add_argument(
        "--all",
        action="store_true",
        help=(
            "Chủ động xử lý toàn manifest (14–28 API calls/phiếu; "
            "pilot thuộc Task 7)."
        ),
    )
    parser.add_argument("--manifest", default="data/manifest.csv")
    parser.add_argument("--assembly-dir", default="output/assembly")
    parser.add_argument("--out-dir", default="output/extract_mc")
    parser.add_argument("--schema", default="schema/questionnaire_v1.json")
    parser.add_argument(
        "--model",
        default=os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        help="Claude model ID (mặc định đọc ANTHROPIC_MODEL nếu có).",
    )
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parent.parent
    try:
        record_ids = resolve_record_ids(
            args.record_ids, args.manifest, process_all=args.all
        )
        if not record_ids:
            raise MCExtractionError("Không có record nào để xử lý")
        client = AnthropicHTTPClient(timeout=args.timeout)
        results = run(
            record_ids=record_ids,
            assembly_dir=args.assembly_dir,
            out_dir=args.out_dir,
            schema_path=args.schema,
            client=client,
            model=args.model,
            image_base_dir=repo_root,
            allowed_image_roots=[
                Path(args.assembly_dir).resolve(),
                repo_root / "data" / "raw" / "khao-sat",
            ],
            max_tokens=args.max_tokens,
        )
    except (OSError, ValueError, MCExtractionError) as exc:
        print(f"ERROR cấu hình: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    ok_count = 0
    for result in results:
        if result["ok"]:
            ok_count += 1
            output = result["output"]
            mismatched_pages = [
                page
                for page, metadata in output["pages"].items()
                if metadata["page_order_mismatch"]
            ]
            review_answers = [
                question_id
                for question_id, answer in output["answers"].items()
                if answer["flags"]
            ]
            print(
                f"OK {result['record_id']}: answers={len(output['answers'])}/31 "
                f"review_answers={review_answers} page_mismatch={mismatched_pages}"
            )
        else:
            error = result["output"]["error"]
            print(
                f"!! {result['record_id']}: {error['type']}: {error['message']}",
                file=sys.stderr,
            )

    print(f"\n{ok_count}/{len(results)} phiếu trích xuất thành công. Chi tiết: {args.out_dir}/")
    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
