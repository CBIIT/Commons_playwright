"""
run_suite.py
Batch runner — finds all TC Excel files in TestCases/ and runs each one via test_runner.

Usage:
    python -m tests.run_suite
    python -m tests.run_suite --filter phs001437
    python -m tests.run_suite --dir TestCases/
    python -m tests.run_suite --fail-fast

Output: prints per-TC results and a summary table at the end.
        Writes a timestamped CSV report to Reports/ (created if absent).
"""
import argparse
import csv
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Allow running from repo root: python -m tests.run_suite
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_runner import run_test_from_excel


def find_tc_files(tc_dir: str, name_filter: str = "", limit: int = 0) -> list[str]:
    """Return sorted list of TC Excel paths in tc_dir, optionally filtered and limited."""
    tc_dir = Path(tc_dir)
    files = sorted(tc_dir.glob("TC*.xlsx"))
    if name_filter:
        files = [f for f in files if name_filter.lower() in f.name.lower()]
    if limit > 0:
        files = files[:limit]
    return [str(f) for f in files]


def _run_one(tc_path: str, index: int, total: int) -> dict:
    tc_name = Path(tc_path).stem
    print(f"\n[run_suite] [{index}/{total}] {tc_name}")
    t0 = time.time()
    try:
        result = run_test_from_excel(tc_path)
        elapsed = round(time.time() - t0, 1)
        status = "PASS" if result["passed"] else "FAIL"
        return {
            "tc":      tc_name,
            "status":  status,
            "elapsed": elapsed,
            "tabs":    result.get("tabs", {}),
            "errors":  result.get("errors", []),
        }
    except Exception as e:
        elapsed = round(time.time() - t0, 1)
        tb = traceback.format_exc()
        print(f"[run_suite] ERROR in {tc_name}:\n{tb}")
        return {
            "tc":      tc_name,
            "status":  "ERROR",
            "elapsed": elapsed,
            "tabs":    {},
            "errors":  [str(e)],
        }


def run_suite(tc_dir: str, name_filter: str = "", fail_fast: bool = False,
              limit: int = 0, workers: int = 1) -> list[dict]:
    tc_files = find_tc_files(tc_dir, name_filter, limit)
    if not tc_files:
        filter_note = f" matching '{name_filter}'" if name_filter else ""
        print(f"[run_suite] No TC Excel files found in '{tc_dir}'{filter_note}.")
        return []

    print(f"\n{'='*70}")
    print(f"[run_suite] Suite: {len(tc_files)} test case(s)  |  workers={workers}")
    if name_filter:
        print(f"[run_suite] Filter: '{name_filter}'")
    print(f"{'='*70}\n")

    results_map = {}  # index → result, to preserve order

    if workers <= 1:
        for i, tc_path in enumerate(tc_files, 1):
            r = _run_one(tc_path, i, len(tc_files))
            results_map[i] = r
            if fail_fast and r["status"] != "PASS":
                print("[run_suite] --fail-fast: stopping after first failure.")
                break
    else:
        futures = {}
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for i, tc_path in enumerate(tc_files, 1):
                f = executor.submit(_run_one, tc_path, i, len(tc_files))
                futures[f] = i
            for f in as_completed(futures):
                i = futures[f]
                results_map[i] = f.result()

    results = [results_map[i] for i in sorted(results_map)]
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errors = sum(1 for r in results if r["status"] == "ERROR")

    _print_summary(results, passed, failed, errors)
    _write_report(results)
    return results


def _print_summary(results: list[dict], passed: int, failed: int, errors: int):
    total = len(results)
    print(f"\n{'='*70}")
    print(f"[run_suite] SUITE SUMMARY  {passed} PASS / {failed} FAIL / {errors} ERROR  (total {total})")
    print(f"{'='*70}")
    col_w = max((len(r["tc"]) for r in results), default=40)
    print(f"  {'TC':<{col_w}}  {'Status':<7}  {'Time':>6}  Tabs")
    print(f"  {'-'*col_w}  {'-'*7}  {'-'*6}  ----")
    for r in results:
        tab_summary = "  ".join(
            f"{tab}: {'✓' if v.get('passed') else '✗'}"
            for tab, v in r["tabs"].items()
        )
        print(f"  {r['tc']:<{col_w}}  {r['status']:<7}  {r['elapsed']:>5}s  {tab_summary}")
        for err in r.get("errors", []):
            print(f"  {'':>{col_w}}           ERROR: {err[:80]}")
    print(f"{'='*70}\n")


def _write_report(results: list[dict]):
    report_dir = Path(__file__).parent.parent / "Reports"
    report_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = report_dir / f"suite_run_{ts}.csv"

    with open(report_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["TC", "Status", "Elapsed(s)", "Tab", "TabStatus", "UI_Count", "DB_Count", "Errors"])
        for r in results:
            if r["tabs"]:
                for tab, tv in r["tabs"].items():
                    writer.writerow([
                        r["tc"],
                        r["status"],
                        r["elapsed"],
                        tab,
                        "PASS" if tv.get("passed") else "FAIL",
                        tv.get("ui_count", ""),
                        tv.get("db_count", ""),
                        "; ".join(r["errors"] + tv.get("mismatches", [])),
                    ])
            else:
                writer.writerow([r["tc"], r["status"], r["elapsed"], "", "", "", "", "; ".join(r["errors"])])

    print(f"[run_suite] Report written: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Playwright TC suite runner")
    parser.add_argument("--dir",       default="TestCases", help="Directory containing TC Excel files")
    parser.add_argument("--filter",    default="",          help="Substring filter on TC file names")
    parser.add_argument("--fail-fast", action="store_true", help="Stop after first failure")
    parser.add_argument("--limit",     type=int, default=0, help="Max number of TCs to run (0 = all)")
    parser.add_argument("--workers",   type=int, default=1, help="Parallel browser workers (default 1)")
    args = parser.parse_args()

    tc_dir = args.dir
    if not os.path.isabs(tc_dir):
        tc_dir = str(Path(__file__).parent.parent / tc_dir)

    run_suite(tc_dir=tc_dir, name_filter=args.filter, fail_fast=args.fail_fast,
              limit=args.limit, workers=args.workers)
