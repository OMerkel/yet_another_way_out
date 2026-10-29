"""Report and enforce statement, line, function, and branch coverage."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import TypedDict, cast

from coverage import Coverage

MINIMUM_COVERAGE = 95.0


class _Summary(TypedDict):
    percent_statements_covered: float
    covered_lines: int
    missing_lines: int
    covered_branches: int
    missing_branches: int
    num_statements: int


class _FunctionSummary(TypedDict):
    num_statements: int


class _FunctionReport(TypedDict):
    executed_lines: list[int]
    summary: _FunctionSummary


class _FileReport(TypedDict):
    functions: dict[str, _FunctionReport]


class _CoverageReport(TypedDict):
    totals: _Summary
    files: dict[str, _FileReport]


def _read_report(data_file: Path) -> _CoverageReport:
    coverage = Coverage(data_file=str(data_file))
    coverage.load()
    with tempfile.TemporaryDirectory() as temporary_directory:
        report_path = Path(temporary_directory) / "coverage.json"
        coverage.json_report(outfile=str(report_path))
        report_value: object = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    return cast(_CoverageReport, report_value)


def _coverage_percent(covered: int, total: int) -> float:
    return 100.0 if total == 0 else covered / total * 100


def _metrics(report: _CoverageReport) -> dict[str, float]:
    totals = report["totals"]
    line_total = totals["covered_lines"] + totals["missing_lines"]
    branch_total = totals["covered_branches"] + totals["missing_branches"]
    functions = [
        function
        for file_report in report["files"].values()
        for name, function in file_report["functions"].items()
        if name and function["summary"]["num_statements"] > 0
    ]
    covered_functions = sum(
        bool(function["executed_lines"]) for function in functions
    )
    function_percent = _coverage_percent(covered_functions, len(functions))
    statement_percent = totals["percent_statements_covered"]
    return {
        "Statement": statement_percent,
        "Line": _coverage_percent(totals["covered_lines"], line_total),
        "Function": function_percent,
        "Branch": _coverage_percent(totals["covered_branches"], branch_total),
    }


def main() -> int:
    """Print every coverage dimension and fail at or below 95 percent."""

    data_file = Path(".coverage")
    if not data_file.exists():
        print("No coverage data; run `uv run pytest` first.", file=sys.stderr)
        return 2

    metrics = _metrics(_read_report(data_file))
    for metric, percentage in metrics.items():
        print(f"{metric} coverage: {percentage:.2f}%")
    failing = [
        metric
        for metric, percentage in metrics.items()
        if percentage <= MINIMUM_COVERAGE
    ]
    if failing:
        print(
            "Coverage must be greater than 95% for: " + ", ".join(failing),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
