from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from survey_pipeline.full_extraction import answer_schema, build_tool, merge_runs, page_questions  # noqa: E402


def main() -> int:
    questionnaire = json.loads((ROOT / "examples" / "basic" / "schema.json").read_text(encoding="utf-8"))
    expected = [q["id"] for q in questionnaire["questions"] if not q.get("per_page")]
    actual = [q["id"] for page in range(1, questionnaire["total_pages"] + 1) for q in page_questions(questionnaire, page)]
    assert actual == expected
    for page in range(1, 2):
        tool = build_tool(questionnaire, page)
        assert tool["strict"] is True
        assert set(tool["input_schema"]["properties"]) == set(tool["input_schema"]["required"])
    by_id = {q["id"]: q for q in questionnaire["questions"]}
    base = {"value": "high", "confidence": "high", "flags": [], "note": None}
    merged, matches, note = merge_runs(
        {"satisfaction": base, "page_matches": True, "page_note": None},
        {"satisfaction": {**base, "value": "low"}, "page_matches": True, "page_note": None},
        ["satisfaction"],
    )
    assert merged["satisfaction"]["needs_review"] is True
    assert merged["satisfaction"]["confidence"] == "low"
    assert matches is True and note is None
    print("OK: full extraction schema/tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
