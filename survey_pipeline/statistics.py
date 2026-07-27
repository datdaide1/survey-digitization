"""Reusable, privacy-aware statistical summaries for digitized datasets.

The functions in this module operate on tabular data and explicit variable
metadata. They contain no questionnaire IDs, client labels, or domain rules.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from math import sqrt
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import stats

VariableKind = Literal["continuous", "ordinal", "categorical", "binary"]
VALID_KINDS = {"continuous", "ordinal", "categorical", "binary"}


def _native(value: Any) -> Any:
    return value.item() if isinstance(value, np.generic) else value


@dataclass(frozen=True)
class StatisticalPolicy:
    """Rules that make analytical limitations explicit and reproducible."""

    alpha: float = 0.05
    min_pair_n: int = 20
    min_group_n: int = 5
    suppress_below_n: int = 0
    percent_denominator: Literal["all", "valid"] = "valid"
    multiple_testing: Literal["benjamini-hochberg", "none"] = "benjamini-hochberg"


@dataclass(frozen=True)
class AssociationResult:
    variable_a: str
    variable_b: str
    method: str
    effect: float | None
    p_value: float | None
    adjusted_p_value: float | None
    n: int
    min_group_n: int | None
    caution: str | None


def frequency_table(series: pd.Series, policy: StatisticalPolicy | None = None) -> list[dict[str, Any]]:
    """Return counts and percentages while retaining missingness information."""
    policy = policy or StatisticalPolicy()
    valid = series.dropna()
    denominator = len(series) if policy.percent_denominator == "all" else len(valid)
    rows: list[dict[str, Any]] = []
    for value, count in valid.value_counts(dropna=False).items():
        suppressed = 0 < count < policy.suppress_below_n
        rows.append({
            "value": _native(value),
            "count": None if suppressed else int(count),
            "percent": None if suppressed or denominator == 0 else float(count / denominator),
            "suppressed": suppressed,
            "valid_n": int(len(valid)),
            "missing_n": int(series.isna().sum()),
            "denominator_n": int(denominator),
        })
    return rows


def descriptive_summary(series: pd.Series) -> dict[str, Any]:
    """Summarize a numeric variable without silently coercing invalid values."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    n = len(numeric)
    if n == 0:
        return {key: None for key in ("n", "mean", "std", "min", "q1", "median", "q3", "max")}
    return {
        "n": int(n),
        "mean": float(numeric.mean()),
        "std": float(numeric.std(ddof=1)) if n > 1 else None,
        "min": float(numeric.min()),
        "q1": float(numeric.quantile(0.25)),
        "median": float(numeric.median()),
        "q3": float(numeric.quantile(0.75)),
        "max": float(numeric.max()),
    }


def crosstab(
    outcome: pd.Series, group: pd.Series, policy: StatisticalPolicy | None = None
) -> list[dict[str, Any]]:
    """Return group-wise counts and column percentages for two categorical variables."""
    policy = policy or StatisticalPolicy()
    paired = pd.DataFrame({"outcome": outcome, "group": group}).dropna()
    rows: list[dict[str, Any]] = []
    for group_value, subset in paired.groupby("group", observed=True):
        for item in frequency_table(subset["outcome"], policy):
            rows.append({"group": group_value, **item})
    return rows


def cronbach_alpha(items: pd.DataFrame) -> dict[str, Any]:
    """Compute Cronbach's alpha using complete cases across two or more items."""
    numeric = items.apply(pd.to_numeric, errors="coerce").dropna()
    n, k = numeric.shape
    if n < 2 or k < 2:
        return {"alpha": None, "n": int(n), "items": int(k), "reason": "insufficient_data"}
    total_variance = numeric.sum(axis=1).var(ddof=1)
    if total_variance <= 0 or np.isnan(total_variance):
        return {"alpha": None, "n": int(n), "items": int(k), "reason": "zero_total_variance"}
    alpha = (k / (k - 1)) * (1 - numeric.var(axis=0, ddof=1).sum() / total_variance)
    return {"alpha": float(alpha), "n": int(n), "items": int(k), "reason": None}


def _cramers_v(a: pd.Series, b: pd.Series) -> tuple[float | None, float | None, int | None]:
    table = pd.crosstab(a, b)
    if min(table.shape) < 2:
        return None, None, None
    chi2, p_value, _, _ = stats.chi2_contingency(table, correction=False)
    n = int(table.to_numpy().sum())
    denominator = n * (min(table.shape) - 1)
    effect = sqrt(chi2 / denominator) if denominator else None
    min_group = int(min(table.sum(axis=0).min(), table.sum(axis=1).min()))
    return effect, float(p_value), min_group


def _association(
    a: pd.Series, b: pd.Series, kind_a: VariableKind, kind_b: VariableKind
) -> tuple[str, float | None, float | None, int | None]:
    numeric = {"continuous", "ordinal"}
    if kind_a in numeric and kind_b in numeric:
        result = stats.spearmanr(pd.to_numeric(a), pd.to_numeric(b))
        effect = None if np.isnan(result.statistic) else float(result.statistic)
        p_value = None if np.isnan(result.pvalue) else float(result.pvalue)
        return "spearman_rho", effect, p_value, None
    if kind_a not in numeric and kind_b not in numeric:
        effect, p_value, min_group = _cramers_v(a, b)
        return "cramers_v", effect, p_value, min_group

    x, g = (a, b) if kind_a in numeric else (b, a)
    x = pd.to_numeric(x)
    levels = sorted(g.unique(), key=str)
    groups = [x[g == level].to_numpy() for level in levels]
    min_group = min((len(values) for values in groups), default=0)
    if len(groups) == 2:
        result = stats.mannwhitneyu(groups[0], groups[1], alternative="two-sided")
        denominator = len(groups[0]) * len(groups[1])
        effect = 1 - 2 * float(result.statistic) / denominator if denominator else None
        return "rank_biserial", effect, float(result.pvalue), min_group
    if len(groups) < 2:
        return "eta", None, None, min_group
    grand_mean = x.mean()
    total = float(((x - grand_mean) ** 2).sum())
    between = sum(len(values) * (values.mean() - grand_mean) ** 2 for values in groups)
    effect = sqrt(float(between / total)) if total > 0 else None
    result = stats.kruskal(*groups)
    return "eta", effect, float(result.pvalue), min_group


def benjamini_hochberg(p_values: list[float | None]) -> list[float | None]:
    """Control false discovery rate for a family of simultaneous tests."""
    valid = [(index, value) for index, value in enumerate(p_values) if value is not None]
    ordered = sorted(valid, key=lambda item: item[1])
    adjusted: list[float | None] = [None] * len(p_values)
    running = 1.0
    total = len(ordered)
    for rank_index in range(total - 1, -1, -1):
        original_index, value = ordered[rank_index]
        rank = rank_index + 1
        running = min(running, value * total / rank)
        adjusted[original_index] = min(1.0, running)
    return adjusted


def association_matrix(
    frame: pd.DataFrame,
    variable_types: dict[str, VariableKind],
    policy: StatisticalPolicy | None = None,
) -> list[AssociationResult]:
    """Select the association measure from the declared types for every pair."""
    policy = policy or StatisticalPolicy()
    raw: list[dict[str, Any]] = []
    for variable_a, variable_b in combinations(variable_types, 2):
        paired = frame[[variable_a, variable_b]].dropna()
        n = len(paired)
        if n < 2:
            method, effect, p_value, min_group = "not_computable", None, None, None
        else:
            method, effect, p_value, min_group = _association(
                paired[variable_a], paired[variable_b], variable_types[variable_a], variable_types[variable_b]
            )
        caution = None
        if n < policy.min_pair_n:
            caution = "low_pair_n"
        elif min_group is not None and min_group < policy.min_group_n:
            caution = "small_group"
        raw.append({
            "variable_a": variable_a, "variable_b": variable_b, "method": method,
            "effect": effect, "p_value": p_value, "n": n,
            "min_group_n": min_group, "caution": caution,
        })
    adjusted = (
        benjamini_hochberg([row["p_value"] for row in raw])
        if policy.multiple_testing == "benjamini-hochberg"
        else [row["p_value"] for row in raw]
    )
    return [AssociationResult(adjusted_p_value=adjusted[index], **row) for index, row in enumerate(raw)]


def compare_groups(
    outcome: pd.Series, group: pd.Series, policy: StatisticalPolicy | None = None
) -> dict[str, Any]:
    """Use Mann-Whitney U for two groups and Kruskal-Wallis for three or more."""
    policy = policy or StatisticalPolicy()
    paired = pd.DataFrame({"outcome": pd.to_numeric(outcome, errors="coerce"), "group": group}).dropna()
    samples = [(name, values["outcome"].to_numpy()) for name, values in paired.groupby("group", observed=True)]
    details = [{"group": name, "n": len(values), "median": float(np.median(values))} for name, values in samples]
    if len(samples) == 2 and all(len(values) > 0 for _, values in samples):
        result = stats.mannwhitneyu(samples[0][1], samples[1][1], alternative="two-sided")
        method = "mann_whitney_u"
    elif len(samples) >= 3 and all(len(values) > 0 for _, values in samples):
        result = stats.kruskal(*(values for _, values in samples))
        method = "kruskal_wallis"
    else:
        return {"method": "not_computable", "statistic": None, "p_value": None, "groups": details, "caution": "insufficient_groups"}
    caution = "small_group" if any(item["n"] < policy.min_group_n for item in details) else None
    return {"method": method, "statistic": float(result.statistic), "p_value": float(result.pvalue), "groups": details, "caution": caution}


def analyze_dataset(
    frame: pd.DataFrame,
    variable_types: dict[str, VariableKind],
    scales: dict[str, list[str]] | None = None,
    comparisons: list[dict[str, str]] | None = None,
    policy: StatisticalPolicy | None = None,
) -> dict[str, Any]:
    """Run a configured, client-neutral analysis and return serializable tables."""
    policy = policy or StatisticalPolicy()
    invalid_kinds = {column: kind for column, kind in variable_types.items() if kind not in VALID_KINDS}
    if invalid_kinds:
        values = ", ".join(f"{column}={kind}" for column, kind in sorted(invalid_kinds.items()))
        raise ValueError(f"Unsupported variable types: {values}")
    missing = sorted(set(variable_types) - set(frame.columns))
    if missing:
        raise ValueError(f"Configured analysis columns are missing: {', '.join(missing)}")
    frequencies = {
        column: frequency_table(frame[column], policy)
        for column, kind in variable_types.items() if kind in {"categorical", "binary", "ordinal"}
    }
    descriptives = {
        column: descriptive_summary(frame[column])
        for column, kind in variable_types.items() if kind in {"continuous", "ordinal"}
    }
    reliability = {}
    for name, columns in (scales or {}).items():
        absent = sorted(set(columns) - set(frame.columns))
        reliability[name] = (
            {"alpha": None, "n": 0, "items": len(columns), "reason": f"missing_columns:{','.join(absent)}"}
            if absent else cronbach_alpha(frame[columns])
        )
    group_tests = []
    for spec in comparisons or []:
        outcome, group = spec["outcome"], spec["group"]
        absent = sorted({outcome, group} - set(frame.columns))
        if absent:
            raise ValueError(f"Configured comparison columns are missing: {', '.join(absent)}")
        result = compare_groups(frame[outcome], frame[group], policy)
        group_tests.append({"outcome": outcome, "group": group, **result})
    return {
        "policy": asdict(policy),
        "frequencies": frequencies,
        "descriptives": descriptives,
        "associations": [asdict(result) for result in association_matrix(frame, variable_types, policy)],
        "reliability": reliability,
        "group_comparisons": group_tests,
    }
