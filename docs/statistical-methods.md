# Statistical methods after digitization

This guide describes the reusable analytical layer. It is independent of any
questionnaire, sector, geography, or client dataset. Inputs are privacy-safe,
flattened records plus an explicit declaration of each variable's measurement
type.

## Analysis contract

Declare columns under `analysis.variable_types` in `project.json`:

```json
{
  "analysis": {
    "variable_types": {
      "outcome_score": "continuous",
      "ordered_rating": "ordinal",
      "segment": "categorical",
      "used_service": "binary"
    },
    "scales": {
      "experience_scale": ["item_1", "item_2", "item_3"]
    },
    "comparisons": [
      {"outcome": "outcome_score", "group": "segment"}
    ],
    "policy": {
      "alpha": 0.05,
      "min_pair_n": 20,
      "min_group_n": 5,
      "suppress_below_n": 5,
      "percent_denominator": "valid",
      "multiple_testing": "benjamini-hochberg"
    }
  }
}
```

Only configured columns enter inferential analysis. This prevents accidental
testing of identifiers, free text, timestamps, or technical metadata.

## Descriptive statistics

For categorical, binary, and ordinal variables, the pipeline reports frequency
`n`, percentage, valid observations, missing observations, and the denominator.
The denominator can be all records or only valid responses. For numeric and
ordinal variables it reports:

- arithmetic mean: `x̄ = Σxᵢ / n`;
- sample standard deviation: `s = √[Σ(xᵢ − x̄)² / (n − 1)]`;
- minimum, first quartile, median, third quartile, and maximum.

Small-cell suppression hides both count and percentage when `0 < n` is below
`suppress_below_n`. Suppression reduces disclosure risk but does not replace a
formal privacy review, especially when tables can be combined.

## Cross-tabulation

A cross-tab counts each outcome level within each group and calculates column
percentages. It answers questions such as “how is the response distributed
inside each segment?” It does not by itself establish a meaningful difference;
sample size, missingness, effect size, and study design still matter.

## Reliability of a scale

Cronbach's alpha is available for two or more numeric items intended to measure
one construct:

`α = k/(k − 1) × [1 − Σ Var(itemᵢ) / Var(total score)]`

The implementation uses complete cases and returns the number of respondents
and items. Alpha is not proof of unidimensionality or validity. A high value can
also result from redundant items; item wording and construct design must be
reviewed before creating a composite score.

## Pairwise association

The method is selected from the declared measurement types:

| Pair | Method | Effect range | Interpretation |
|---|---|---:|---|
| numeric ↔ numeric | Spearman's rho | −1 to 1 | monotonic association and direction |
| categorical ↔ categorical | Cramér's V | 0 to 1 | strength without direction |
| numeric ↔ binary | rank-biserial correlation | −1 to 1 | group separation and direction |
| numeric ↔ 3+ category | eta | 0 to 1 | share of variation aligned with groups |

Each result includes pairwise `n`, p-value when computable, and the smallest
group size where relevant. A pair is flagged when `n < min_pair_n` or a group is
smaller than `min_group_n`. These thresholds are quality warnings, not universal
scientific laws; set them before reviewing results.

When many pairs are tested, the default Benjamini–Hochberg procedure controls
the expected false discovery rate. For sorted p-values `p(i)`, the initial
adjustment is `p(i) × m / i`, followed by a monotonic correction and a cap at 1.
Report the adjusted p-value, effect size, and uncertainty together. Statistical
significance alone does not imply practical importance.

## Group comparison

- Exactly two independent groups: two-sided Mann–Whitney U.
- Three or more independent groups: Kruskal–Wallis H.

Both tests compare distributions using ranks and avoid a normality assumption.
They still require independent observations and a defensible sampling design.
The output includes each group's `n` and median. A significant omnibus
Kruskal–Wallis result does not identify which groups differ; a pre-specified
post-hoc procedure is needed for that question.

## Interpretation boundaries

- Association is not causation. Cross-sectional survey data cannot establish
  that one variable changed another.
- Missingness can bias estimates. Always inspect valid and missing counts.
- Very small or sparse groups can create unstable, extreme effects.
- Measurement error from extraction and human review propagates into analysis.
- Exploratory factor analysis and clustering are deliberately not run by
  default. They require adequate sample size, suitable variables, diagnostics,
  stability checks, and a question-specific interpretation plan.
- Client data and generated results belong outside the public repository. The
  public layer contains algorithms, configuration contracts, synthetic examples,
  and tests only.

## Outputs

The `stats` stage writes privacy-safe records, the flattened table, and
`work/stats/analysis.json` when variable types are configured. The `report`
stage adds Descriptives, Associations, Reliability, Group Tests, and Methodology
worksheets to the spreadsheet, plus a concise methodological note to the document.
