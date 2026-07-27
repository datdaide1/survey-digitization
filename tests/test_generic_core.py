from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from survey_pipeline.config import ProjectConfigError, load_project
from survey_pipeline.analytics import run_analysis
from survey_pipeline.ingest import run_ingest
from survey_pipeline.flatten import flatten_record
from survey_pipeline.privacy import to_analysis_record
from survey_pipeline.reporting import build_reports
from survey_pipeline.schema import load_schema

EXAMPLE = ROOT / "examples" / "basic"


def test_project_paths_are_scoped():
    project = load_project(EXAMPLE / "project.json")
    assert project.paths.schema == (EXAMPLE / "schema.json").resolve()
    raw = json.loads((EXAMPLE / "project.json").read_text(encoding="utf-8"))
    raw["paths"]["schema"] = "../outside.json"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "project.json"
        path.write_text(json.dumps(raw), encoding="utf-8")
        try:
            load_project(path)
        except ProjectConfigError:
            pass
        else:
            raise AssertionError("path traversal must be rejected")


def test_flatten_and_privacy_follow_schema():
    schema = load_schema(EXAMPLE / "schema.json")
    record = {
        "record_id": "DEMO-001",
        "source_images": ["private.png"],
        "answers": {
            "respondent_name": {"value": "Private Person"},
            "satisfaction": {"value": "high"},
            "channels": {"value": ["web", "phone"]},
            "comment": {"value": "ok"},
        },
    }
    row = flatten_record(record, schema, manifest={"record_id": "DEMO-001", "group": "pilot"})
    assert "respondent_name" not in row
    assert row["channels__web"] == 1
    assert row["channels__office"] == 0
    assert row["meta__group"] == "pilot"
    safe = to_analysis_record(record, schema)
    assert "respondent_name" not in safe["answers"]
    assert "source_images" not in safe


def test_synthetic_analysis_and_reports():
    schema = load_schema(EXAMPLE / "schema.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
        project_raw = json.loads((EXAMPLE / "project.json").read_text(encoding="utf-8"))
        (root / "project.json").write_text(json.dumps(project_raw), encoding="utf-8")
        (root / "manifest.csv").write_text("record_id,source_path,group\nDEMO-001,demo.pdf,pilot\n", encoding="utf-8")
        full = root / "work" / "full"
        full.mkdir(parents=True)
        record = {
            "record_id": "DEMO-001",
            "answers": {
                "respondent_name": {"value": "Private Person"},
                "satisfaction": {"value": "high"},
                "channels": {"value": ["web"]},
                "comment": {"value": "fine"},
            },
        }
        (full / "DEMO-001.json").write_text(json.dumps(record), encoding="utf-8")
        project = load_project(root / "project.json")
        frame = run_analysis(project, schema)
        assert len(frame) == 1 and "respondent_name" not in frame.columns
        xlsx, docx = build_reports(project)
        assert xlsx.is_file() and docx.is_file()


def test_synthetic_ingest_uses_project_relative_paths():
    from PIL import Image

    schema = load_schema(EXAMPLE / "schema.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
        project_raw = json.loads((EXAMPLE / "project.json").read_text(encoding="utf-8"))
        (root / "project.json").write_text(json.dumps(project_raw), encoding="utf-8")
        (root / "manifest.csv").write_text("record_id,source_path\nDEMO-001,demo.png\n", encoding="utf-8")
        source = root / "data" / "source"
        source.mkdir(parents=True)
        Image.new("RGB", (20, 20), "white").save(source / "demo.png")
        project = load_project(root / "project.json")
        result = run_ingest(project, schema)[0]
        assert result["status"] == "ok"
        assert not Path(result["pages"][0]["image_path"]).is_absolute()


def main() -> int:
    test_project_paths_are_scoped()
    test_flatten_and_privacy_follow_schema()
    test_synthetic_analysis_and_reports()
    test_synthetic_ingest_uses_project_relative_paths()
    print("OK: generic core tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
