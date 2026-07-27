"""Generic manifest-driven file assembly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ProjectConfig
from .manifest import load_manifest


def run_ingest(config: ProjectConfig, schema: dict[str, Any]) -> list[dict[str, Any]]:
    from .assembly import build_assembly

    config.paths.assembly.mkdir(parents=True, exist_ok=True)
    render_root = config.paths.assembly / "_render"
    default_pages = int(schema.get("total_pages") or 1)
    results = []
    for row in load_manifest(config.paths.manifest):
        source = (config.paths.source / row["source_path"]).resolve()
        if not source.is_relative_to(config.paths.source.resolve()):
            raise ValueError(f"source_path escapes source directory: {row['source_path']}")
        expected = int(row.get("expected_pages") or default_pages)
        result = build_assembly(row["record_id"], source, expected, render_root / row["record_id"])
        for page in result.get("pages", []):
            image = Path(page["image_path"]).resolve()
            page["image_path"] = image.relative_to(config.paths.root).as_posix()
        target = config.paths.assembly / f"{row['record_id']}.json"
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(result)
    return results
