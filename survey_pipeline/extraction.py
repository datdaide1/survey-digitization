"""Run full schema-driven extraction for a configured project."""

from __future__ import annotations

import json
import os
from typing import Any

from .config import ProjectConfig
from .manifest import load_manifest


def run_extraction(config: ProjectConfig, schema: dict[str, Any], client=None) -> list[dict[str, Any]]:
    from .full_extraction import AnthropicClient, extract_record

    provider = str(config.extraction.get("provider") or "anthropic")
    if provider != "anthropic":
        raise ValueError(f"Unsupported extraction provider: {provider}")
    model = str(config.extraction.get("model") or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-5-20250929")
    max_tokens = int(config.extraction.get("max_tokens") or 8192)
    client = client or AnthropicClient()
    config.paths.full.mkdir(parents=True, exist_ok=True)
    results = []
    for row in load_manifest(config.paths.manifest):
        record_id = row["record_id"]
        assembly_path = config.paths.assembly / f"{record_id}.json"
        assembly = json.loads(assembly_path.read_text(encoding="utf-8"))
        record = extract_record(
            assembly=assembly,
            questionnaire=schema,
            client=client,
            model=model,
            image_base_dir=config.paths.root,
            allowed_image_roots=[config.paths.assembly, config.paths.source],
            max_tokens=max_tokens,
        )
        (config.paths.full / f"{record_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        results.append(record)
    return results
