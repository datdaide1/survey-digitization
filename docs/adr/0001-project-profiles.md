# ADR-0001: Generic core with project profiles

**Status:** Accepted
**Date:** 2026-07-27

## Context

The first implementation mixed reusable pipeline mechanics with one client's
question IDs, locations, statistical buckets and report narrative. A reusable
repository must accept different questionnaires without modifying engine code.

## Decision

The system is split into:

1. A schema-driven core for ingest, extraction, validation, review, privacy and
   table generation.
2. A `project.json` profile containing paths, provider settings and output policy.
3. Optional domain plugins for derived metrics or bespoke narrative reports.
4. Self-contained examples; no real respondent data is committed.

## Consequences

- New surveys are added through a profile and schema.
- The old herbal-household questionnaire remains an example, not a core contract.
- Generic reports work for every schema; bespoke reports require an explicit plugin.
- Legacy scripts remain temporarily as compatibility adapters during migration.
