# Survey Digitization Pipeline

A reusable, schema-driven pipeline for turning scanned questionnaires into
reviewable records, privacy-safe analysis tables and client-ready reports.

The engine does not know a client's question IDs, locations or statistical
buckets. Each survey is a self-contained project profile:

```text
project.json
schema.json
data/
  manifest.csv
  source/
work/
  assembly/   rendered pages and integrity metadata
  full/       complete extraction, including declared PII
  stats/      privacy-safe records
  combined.csv
  reports/
```

## Capabilities

- PDF/image ingest and page integrity checks.
- Structured VLM extraction for text, single/multi select, composite fields,
  matrices, device grids, subfields and per-page notes.
- Two independent reads per page; disagreements become review flags.
- Browser review UI generated from the questionnaire schema.
- PII removal driven by `pii: true` declarations in the schema.
- Generic flattening and frequency reports for any questionnaire.
- Optional project plugins for domain-specific derived metrics and narrative.

## Quick start

Copy the basic example to a private working directory and rename
`manifest.example.csv` to `manifest.csv`. Put source files under the configured
source directory; source data and generated work products are ignored by Git.

```powershell
$python = "E:\anaconda3\envs\survey-digitizer\python.exe"
& $python scripts/survey.py --project path\to\project.json ingest

$env:ANTHROPIC_API_KEY = "..."
& $python scripts/survey.py --project path\to\project.json extract

& $python scripts/survey.py --project path\to\project.json stats
& $python scripts/survey.py --project path\to\project.json report
```

`all` runs the four stages in order. Live extraction sends the configured page
images to the selected provider; obtain the necessary data-processing approval
before using respondent data.

## Project contract

`project.json` owns paths and operational settings. `schema.json` owns the
questionnaire structure. The minimum manifest columns are:

| Column | Meaning |
|---|---|
| `record_id` | Stable anonymous record identifier |
| `source_path` | Path relative to the configured source directory |
| `expected_pages` | Optional; defaults to `schema.total_pages` |

All additional manifest columns are carried into the analysis table with a
`meta__` prefix.

## Review UI

Serve `scripts/review_ui` over HTTP, open it in Chrome/Edge, then select a folder
containing `project.json`:

```powershell
& "E:\anaconda3\envs\survey-digitizer\python.exe" -m http.server 8765 --directory scripts/review_ui
```

The UI reads the schema, manifest, assembly and extraction paths from the project
profile. It supports arbitrary page counts and schema-defined grid extra options.

## Examples and legacy compatibility

- `examples/basic/` is a small, client-neutral starter project.
- `examples/herbal-household/` preserves the original questionnaire and bespoke
  analytics as a legacy example. It is not imported by the generic engine.

Real survey data, extracted records and reports are never committed. See
[ADR-0001](docs/adr/0001-project-profiles.md) for the architecture decision.
