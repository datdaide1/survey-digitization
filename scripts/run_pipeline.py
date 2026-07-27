#!/usr/bin/env python3
"""Run the survey pipeline end-to-end without manual data-entry steps."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--skip-extraction", action="store_true", help="Reuse output/full; useful only for report rebuilds")
    parser.add_argument("--record-id", action="append", dest="record_ids")
    args = parser.parse_args()
    python = sys.executable
    commands: list[list[str]] = []
    if not args.skip_ingest:
        commands.append([python, "scripts/ingest.py"])
    if not args.skip_extraction:
        command = [python, "scripts/extract_full.py"]
        for record_id in args.record_ids or []:
            command += ["--record-id", record_id]
        commands.append(command)
    commands += [
        [python, "scripts/validate_schema.py", "schema/questionnaire_v1.json"],
        [python, "scripts/validate_record.py", "schema/questionnaire_v1.json", "output/full/*.json"],
        [python, "scripts/build_stats_layer.py"],
        [python, "scripts/build_client_report.py"],
    ]
    for command in commands:
        print("\n==>", " ".join(command))
        completed = subprocess.run(command, cwd=Path(__file__).resolve().parent.parent)
        if completed.returncode:
            return completed.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
