"""Command line interface for a configured survey project."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analytics import run_analysis
from .config import load_project
from .extraction import run_extraction
from .ingest import run_ingest
from .reporting import build_reports
from .schema import load_schema
from .validation import validate_records, validate_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="survey-pipeline")
    parser.add_argument("--project", required=True, help="Path to project.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest")
    sub.add_parser("extract")
    sub.add_parser("validate")
    sub.add_parser("stats")
    sub.add_parser("report")
    sub.add_parser("all")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_project(args.project)
    schema = load_schema(config.paths.schema)
    schema_errors = validate_schema(schema)
    if schema_errors:
        for error in schema_errors:
            print(f"schema error: {error}")
        return 1
    if args.command in {"ingest", "all"}:
        results = run_ingest(config, schema)
        print(f"ingest: {len(results)} records")
    if args.command in {"extract", "all"}:
        results = run_extraction(config, schema)
        print(f"extract: {len(results)} records")
    if args.command in {"validate", "all"}:
        failures = validate_records(schema, config.paths.full)
        for filename, errors in failures.items():
            for error in errors:
                print(f"{filename}: {error}")
        if failures:
            return 1
        print("validate: ok")
    if args.command in {"stats", "all"}:
        frame = run_analysis(config, schema)
        print(f"stats: {len(frame)} records, {len(frame.columns)} columns")
    if args.command in {"report", "all"}:
        paths = build_reports(config)
        print("report:", ", ".join(str(path) for path in paths))
    return 0
