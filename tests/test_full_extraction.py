from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lib.full_extraction import answer_schema, build_tool, merge_runs, page_questions  # noqa: E402


def main() -> int:
    questionnaire = json.loads((ROOT / "schema" / "questionnaire_v1.json").read_text(encoding="utf-8"))
    expected = [q["id"] for q in questionnaire["questions"] if not q.get("per_page")]
    actual = [q["id"] for page in range(1, 8) for q in page_questions(questionnaire, page)]
    assert actual == expected
    for page in range(1, 8):
        tool = build_tool(questionnaire, page)
        assert tool["strict"] is True
        assert set(tool["input_schema"]["properties"]) == set(tool["input_schema"]["required"])
    by_id = {q["id"]: q for q in questionnaire["questions"]}
    assert "components" in answer_schema(by_id["Q5"])["properties"]
    assert "derived_subfield" in answer_schema(by_id["Q9"])["properties"]
    assert "rows" in answer_schema(by_id["Q14"])["properties"]
    base = {"value": "nu", "confidence": "cao", "flags": [], "note": None}
    merged, matches, note = merge_runs(
        {"Q3": base, "page_matches": True, "page_note": None},
        {"Q3": {**base, "value": "nam"}, "page_matches": True, "page_note": None},
        ["Q3"],
    )
    assert merged["Q3"]["needs_review"] is True
    assert merged["Q3"]["confidence"] == "thap"
    assert matches is True and note is None
    print("OK: full extraction schema/tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
