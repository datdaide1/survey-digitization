# Survey Digitization Pipeline

Turn scanned questionnaires into validated, reviewable records with
schema-guided VLM extraction, then produce reusable statistical outputs—without
committing respondent data or client results.

The pipeline is schema-driven: question IDs, page layouts, privacy declarations,
variable types, and analysis policies live in a project profile rather than in
the engine. The same workflow can support customer research, program evaluation,
field surveys, audits, assessments, and other structured forms.

## What it does

```text
PDFs / images → integrity checks → schema-guided VLM extraction → human review
→ PII removal and flattening → configured statistics → XLSX, DOCX and JSON
```

- Ingests PDFs and images with page-count and file-integrity checks.
- Extracts text, selections, matrices, composite fields, grids, and page notes
  through a strict schema supplied to the configured vision-language model.
- Supports independent reads and sends disagreements to human review.
- Generates a browser review interface from the questionnaire schema.
- Removes fields marked `pii: true` before creating analytical records.
- Produces descriptives, cross-tabs, reliability, association measures,
  non-parametric group comparisons, and multiple-testing correction.

## Quick start

Prerequisites: Python 3.12 and a virtual or Conda environment.

```powershell
python -m pip install -e .
Copy-Item -Recurse examples/basic my-survey
Copy-Item my-survey/manifest.example.csv my-survey/manifest.csv
```

Add source files under `my-survey/data/source`, update the manifest, then run:

```powershell
survey-pipeline --project my-survey/project.json ingest

$env:ANTHROPIC_API_KEY = "your-key"
survey-pipeline --project my-survey/project.json extract

survey-pipeline --project my-survey/project.json validate
survey-pipeline --project my-survey/project.json stats
survey-pipeline --project my-survey/project.json report
```

Use `all` to run the stages in sequence. Extraction sends configured page images
to the selected provider; obtain appropriate data-processing approval first.

## VLM digitization and quality control

Digitization is treated as a traceable data-production process, not a single OCR
call. The questionnaire schema defines which fields exist on each page, their
allowed values, whether they contain PII, and the structured response expected
from the vision-language model.

For every source record, the pipeline:

1. renders and inventories pages while checking expected page counts;
2. sends only the relevant page schema and image to the configured VLM provider;
3. performs independent reads when `double_read` is enabled;
4. merges matching answers and marks disagreements, low confidence, ambiguous
   marks, or page mismatches for review;
5. validates the reviewed record against the same questionnaire contract; and
6. removes schema-declared PII before flattening data for statistics.

The VLM is therefore an extraction component, not an authority. Human review
remains the decision point for uncertain or conflicting observations. Provider
configuration is project-specific, so another backend can be added without
putting client question IDs or survey logic into the reusable engine.

## Project profile

Each survey is self-contained:

```text
project.json             paths, providers, analysis and reporting policy
schema.json              questions, options, layout and PII declarations
data/manifest.csv        anonymous record IDs and source-file references
data/source/             private questionnaire files
work/assembly/           rendered pages and integrity metadata
work/full/               reviewed extraction records
work/stats/              privacy-safe records and analysis.json
work/combined.csv        flattened analytical table
work/reports/            generated XLSX and DOCX reports
```

Paths in `project.json` must be relative to that file and cannot escape the
project directory. The manifest requires `record_id` and `source_path`;
`expected_pages` is optional. Extra manifest columns receive a `meta__` prefix.

## Reusable statistical layer

Declare analytical columns as `continuous`, `ordinal`, `categorical`, or
`binary`. The engine chooses a method from their measurement types:

| Variable pair or goal | Method |
|---|---|
| numeric ↔ numeric | Spearman's rho |
| categorical ↔ categorical | Cramér's V |
| numeric ↔ binary | rank-biserial correlation |
| numeric ↔ 3+ category | eta |
| two independent groups | Mann–Whitney U |
| three or more independent groups | Kruskal–Wallis |
| multi-item scale | Cronbach's alpha |

Each inferential result carries sample size, a small-group warning, an effect
measure, and a p-value where computable. Benjamini–Hochberg correction is the
default for association families. See [Statistical methods](docs/statistical-methods.md)
for formulas, assumptions, configuration, and interpretation boundaries.

## Review interface

Serve the static app, open the local URL in a current Chromium-based browser,
and choose the project folder:

```powershell
python -m http.server 8765 --directory scripts/review_ui
```

The interface reads project paths and questionnaire structure at runtime. It
supports arbitrary page counts, schema-defined options, corrections, and local
saving through the browser file-system API.

## Privacy and publication boundary

This repository publishes implementation knowledge, not client records. Real
source files, extracted records, review work, flattened tables, and generated
reports are ignored by Git. Public examples must be synthetic.

PII removal is schema-controlled, but technical controls cannot replace
governance. Before sharing, review quasi-identifiers, small cells, free text,
provider terms, retention rules, and the risk of combining multiple outputs.
Statistical association must never be presented as causation.

## Development

```powershell
python -m pip install -e .
python -m pytest
```

Tests use synthetic data and cover path isolation, privacy filtering, ingest,
extraction, reporting, statistical formulas, and disclosure flags.

## Repository map

- `survey_pipeline/` — reusable package and command-line workflow.
- `scripts/review_ui/` — local browser review interface.
- `examples/basic/` — synthetic starter profile.
- `examples/herbal-household/` — legacy implementation reference without real
  respondent data or generated client results.
- `docs/` — architecture decisions and statistical methodology.
- `tests/` — synthetic regression tests.

Architecture rationale is in [ADR-0001](docs/adr/0001-project-profiles.md).
