"""Project configuration and safe path resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProjectConfigError(ValueError):
    pass


def _safe_path(root: Path, value: str, field: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ProjectConfigError(f"{field} must be a non-empty relative path")
    candidate = (root / value).resolve()
    if not candidate.is_relative_to(root):
        raise ProjectConfigError(f"{field} escapes the project directory: {value}")
    return candidate


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    schema: Path
    manifest: Path
    source: Path
    assembly: Path
    full: Path
    review: Path
    stats: Path
    combined: Path
    reports: Path


@dataclass(frozen=True)
class ProjectConfig:
    path: Path
    project_id: str
    title: str
    locale: str
    paths: ProjectPaths
    extraction: dict[str, Any]
    analysis: dict[str, Any]
    reporting: dict[str, Any]
    review: dict[str, Any]


def load_project(path: str | Path) -> ProjectConfig:
    config_path = Path(path).resolve()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProjectConfigError(f"Cannot read project config {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ProjectConfigError("Project config root must be an object")
    root = config_path.parent
    project_id = raw.get("project_id")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ProjectConfigError("project_id must be a non-empty string")
    values = raw.get("paths", {})
    if not isinstance(values, dict):
        raise ProjectConfigError("paths must be an object")
    defaults = {
        "schema": "schema.json", "manifest": "data/manifest.csv",
        "source": "data/source", "assembly": "work/assembly",
        "full": "work/full", "review": "work/review",
        "stats": "work/stats", "combined": "work/combined.csv",
        "reports": "work/reports",
    }
    resolved = {key: _safe_path(root, values.get(key, default), f"paths.{key}") for key, default in defaults.items()}
    return ProjectConfig(
        path=config_path,
        project_id=project_id,
        title=str(raw.get("title") or project_id),
        locale=str(raw.get("locale") or "en"),
        paths=ProjectPaths(root=root, **resolved),
        extraction=dict(raw.get("extraction") or {}),
        analysis=dict(raw.get("analysis") or {}),
        reporting=dict(raw.get("reporting") or {}),
        review=dict(raw.get("review") or {}),
    )
