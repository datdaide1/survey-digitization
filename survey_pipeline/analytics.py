"""Build privacy-safe records and a generic analysis table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .flatten import flatten_record
from .manifest import by_record_id, load_manifest
from .privacy import to_analysis_record


def run_analysis(config: ProjectConfig, schema: dict[str, Any]):
    import pandas as pd

    manifest = by_record_id(load_manifest(config.paths.manifest))
    config.paths.stats.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(config.paths.full.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record_id = str(record.get("record_id") or path.stem)
        if record_id not in manifest:
            raise ValueError(f"Record {record_id} is not present in the manifest")
        safe_record = to_analysis_record(record, schema)
        (config.paths.stats / f"{record_id}.json").write_text(
            json.dumps(safe_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        rows.append(flatten_record(record, schema, manifest=manifest[record_id]))
    frame = pd.DataFrame(rows)
    config.paths.combined.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(config.paths.combined, index=False, encoding="utf-8-sig")
    return frame
