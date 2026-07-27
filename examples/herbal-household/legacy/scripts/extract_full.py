#!/usr/bin/env python3
"""Extract every survey field from rendered pages with a vision model."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from survey_pipeline.full_extraction import AnthropicClient, extract_record  # noqa: E402


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(manifest: str, assembly_dir: str, schema: str, out_dir: str, model: str, max_tokens: int, record_ids: list[str] | None = None, client=None) -> int:
    import csv
    questionnaire = load_json(schema)
    with open(manifest, encoding="utf-8-sig", newline="") as handle:
        ids = [row["record_id"].strip() for row in csv.DictReader(handle)]
    if record_ids:
        unknown = sorted(set(record_ids) - set(ids))
        if unknown:
            raise ValueError(f"record_id không có trong manifest: {unknown}")
        ids = record_ids
    client = client or AnthropicClient()
    failures = 0
    for record_id in ids:
        try:
            assembly = load_json(Path(assembly_dir) / f"{record_id}.json")
            result = extract_record(
                assembly=assembly, questionnaire=questionnaire, client=client,
                model=model, image_base_dir=".", allowed_image_roots=[assembly_dir],
                max_tokens=max_tokens,
            )
            _write(Path(out_dir) / f"{record_id}.json", result)
            print(f"OK {record_id}: {len(result['answers'])} mục")
        except Exception as exc:
            failures += 1
            print(f"ERROR {record_id}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/manifest.csv")
    parser.add_argument("--assembly-dir", default="output/assembly")
    parser.add_argument("--schema", default="schema/questionnaire_v1.json")
    parser.add_argument("--out-dir", default="output/full")
    parser.add_argument("--model", default=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"))
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--record-id", action="append", dest="record_ids")
    args = parser.parse_args()
    return run(args.manifest, args.assembly_dir, args.schema, args.out_dir, args.model, args.max_tokens, args.record_ids)


if __name__ == "__main__":
    raise SystemExit(main())
