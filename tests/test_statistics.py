from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from survey_pipeline.statistics import (
    StatisticalPolicy,
    analyze_dataset,
    benjamini_hochberg,
    compare_groups,
    cronbach_alpha,
    frequency_table,
)


def test_frequency_denominator_and_suppression_are_explicit():
    series = pd.Series(["a", "a", "b", None])
    rows = frequency_table(
        series, StatisticalPolicy(percent_denominator="all", suppress_below_n=2)
    )
    assert rows[0]["count"] == 2 and rows[0]["percent"] == 0.5
    assert rows[1]["count"] is None and rows[1]["suppressed"] is True
    assert rows[0]["missing_n"] == 1 and rows[0]["denominator_n"] == 4


def test_reliability_matches_known_perfect_scale():
    result = cronbach_alpha(pd.DataFrame({"a": [1, 2, 3], "b": [1, 2, 3]}))
    assert result["n"] == 3 and result["items"] == 2
    assert result["alpha"] is not None and result["alpha"] > 0.9


def test_benjamini_hochberg_is_monotonic_in_rank_order():
    adjusted = benjamini_hochberg([0.01, 0.04, None, 0.03])
    assert adjusted[2] is None
    assert adjusted[0] <= adjusted[3] <= adjusted[1]
    assert all(value is None or 0 <= value <= 1 for value in adjusted)


def test_group_comparison_and_full_analysis_are_generic():
    frame = pd.DataFrame({
        "score": [1, 2, 3, 8, 9, 10],
        "segment": ["a", "a", "a", "b", "b", "b"],
        "flag": [0, 0, 1, 1, 1, 1],
        "item_1": [1, 2, 3, 4, 5, 6],
        "item_2": [2, 3, 4, 5, 6, 7],
    })
    comparison = compare_groups(frame["score"], frame["segment"], StatisticalPolicy(min_group_n=2))
    assert comparison["method"] == "mann_whitney_u"
    assert math.isfinite(comparison["statistic"])

    result = analyze_dataset(
        frame,
        variable_types={"score": "continuous", "segment": "categorical", "flag": "binary"},
        scales={"generic_scale": ["item_1", "item_2"]},
        comparisons=[{"outcome": "score", "group": "segment"}],
        policy=StatisticalPolicy(min_pair_n=2, min_group_n=2),
    )
    methods = {item["method"] for item in result["associations"]}
    assert {"rank_biserial", "cramers_v"}.issubset(methods)
    assert result["reliability"]["generic_scale"]["alpha"] is not None
    assert result["group_comparisons"][0]["method"] == "mann_whitney_u"


def main() -> int:
    test_frequency_denominator_and_suppression_are_explicit()
    test_reliability_matches_known_perfect_scale()
    test_benjamini_hochberg_is_monotonic_in_rank_order()
    test_group_comparison_and_full_analysis_are_generic()
    print("OK: generic statistics tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
