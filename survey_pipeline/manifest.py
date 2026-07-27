"""Manifest contract: record_id, source_path and optional metadata columns."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_manifest(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    seen: set[str] = set()
    for index, row in enumerate(rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        source_path = (row.get("source_path") or "").strip()
        if not record_id or not source_path:
            raise ValueError(f"Manifest row {index} requires record_id and source_path")
        if record_id in seen:
            raise ValueError(f"Duplicate record_id in manifest: {record_id}")
        seen.add(record_id)
        row["record_id"] = record_id
        row["source_path"] = source_path
    return rows


def by_record_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["record_id"]: row for row in rows}
