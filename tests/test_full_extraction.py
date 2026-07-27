from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from survey_pipeline.full_extraction import (  # noqa: E402
    MCExtractionError,
    answer_schema,
    build_tool,
    extract_record,
    merge_runs,
    page_questions,
)


class FakeVLMClient:
    def __init__(self):
        self.calls = 0

    def create_message(self, request):
        self.calls += 1
        tool = request["tools"][0]
        question_ids = [key for key in tool["input_schema"]["properties"] if key not in {"page_matches", "page_note"}]
        payload = {"page_matches": True, "page_note": None}
        for question_id in question_ids:
            payload[question_id] = {"value": "synthetic", "confidence": "high", "flags": [], "note": None}
        return {"content": [{"type": "tool_use", "name": tool["name"], "input": payload}]}


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

    from PIL import Image

    generic_schema = {
        "schema_version": "1.0.0",
        "title": "Unrelated synthetic form",
        "total_pages": 1,
        "questions": [{"id": "field_alpha", "page": 1, "text": "Any text field", "type": "text"}],
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        image_path = root / "page.png"
        Image.new("RGB", (10, 10), "white").save(image_path)
        assembly = {"record_id": "GENERIC-001", "pages": [{"tentative_page": 1, "image_path": "page.png"}]}

        single_client = FakeVLMClient()
        record = extract_record(
            assembly=assembly, questionnaire=generic_schema, client=single_client,
            model="fake-model", image_base_dir=root, double_read=False,
        )
        assert single_client.calls == 1
        assert record["answers"]["field_alpha"]["value"] == "synthetic"

        double_client = FakeVLMClient()
        extract_record(
            assembly=assembly, questionnaire=generic_schema, client=double_client,
            model="fake-model", image_base_dir=root, double_read=True,
        )
        assert double_client.calls == 2

        invalid_schema = {key: value for key, value in generic_schema.items() if key != "total_pages"}
        try:
            extract_record(
                assembly=assembly, questionnaire=invalid_schema, client=FakeVLMClient(),
                model="fake-model", image_base_dir=root,
            )
        except MCExtractionError:
            pass
        else:
            raise AssertionError("total_pages must come from the project schema")
    print("OK: full extraction schema/tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
