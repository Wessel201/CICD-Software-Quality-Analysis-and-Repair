import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from analyzer import Analyzer
from main import SqsWorker
from repairman import Repairman


def _build_worker_harness(max_repair_cycles: int) -> SqsWorker:
    # Bypass cloud-dependent __init__; this harness only uses local helper methods.
    worker = object.__new__(SqsWorker)
    worker.max_repair_cycles = max(1, int(max_repair_cycles))
    return worker


def _copy_input_file(input_file: Path) -> tuple[Path, Path, Path]:
    workspace = Path(tempfile.mkdtemp(prefix="worker_local_"))
    source_dir = workspace / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    target_file = source_dir / input_file.name
    shutil.copy2(input_file, target_file)
    return workspace, source_dir, target_file


def _count_findings(findings: list[dict[str, Any]]) -> int:
    return len(findings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run worker analysis/repair flow locally for a single file.")
    parser.add_argument("file", help="Path to the source file to analyze/repair.")
    parser.add_argument("--repair", action="store_true", help="Enable LLM repair attempts.")
    parser.add_argument(
        "--cycles",
        type=int,
        default=1,
        help="Maximum repair cycles to run when --repair is enabled (default: 1).",
    )
    parser.add_argument(
        "--in-place",
        "--in_place",
        dest="in_place",
        action="store_true",
        help="Write repaired output back to the original file path.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output JSON path. Use '-' for stdout (default).",
    )
    args = parser.parse_args()

    input_file = Path(args.file).expanduser().resolve()
    if not input_file.exists() or not input_file.is_file():
        raise SystemExit(f"Input file does not exist: {input_file}")

    workspace, source_dir, working_file = _copy_input_file(input_file)
    try:
        worker = _build_worker_harness(max_repair_cycles=args.cycles)
        repairman = Repairman()

        before_raw = Analyzer(str(source_dir)).run_all()
        before_findings = worker._normalize_findings(before_raw, source_dir)

        applied_fixes = 0
        llm_unavailable = False
        repair_skipped_reason: str | None = None
        after_findings = before_findings

        if args.repair:
            llm_client = worker._build_llm_client()
            if llm_client is None:
                repair_skipped_reason = "OPENAI_API_KEY not configured"
            else:
                repair_targets = worker._findings_to_repair_targets(before_findings)
                cycles = max(1, int(args.cycles))

                for _ in range(cycles):
                    applied_count, aborted_due_to_llm_unavailable = worker._apply_repairs_for_findings(
                        source_dir=source_dir,
                        findings=repair_targets,
                        repairman=repairman,
                        llm_client=llm_client,
                        job_id="local-file-run",
                    )
                    applied_fixes += applied_count

                    after_raw = Analyzer(str(source_dir)).run_all()
                    after_findings = worker._normalize_findings(after_raw, source_dir)

                    if aborted_due_to_llm_unavailable:
                        llm_unavailable = True
                        repair_skipped_reason = "LLM provider unavailable or quota exhausted"
                        break
                    if not after_findings:
                        break

                    repair_targets = worker._findings_to_repair_targets(after_findings)

        before_total = _count_findings(before_findings)
        after_total = _count_findings(after_findings)
        reduction_pct = 0.0
        if before_total > 0:
            reduction_pct = round(((before_total - after_total) / before_total) * 100, 2)

        if args.in_place and args.repair:
            shutil.copy2(working_file, input_file)

        payload = {
            "file": str(input_file),
            "working_file": str(working_file),
            "repair_enabled": bool(args.repair),
            "llm_unavailable": llm_unavailable,
            "repair_skipped_reason": repair_skipped_reason,
            "applied_fixes": applied_fixes,
            "summary": {
                "before_total": before_total,
                "after_total": after_total,
                "reduction_pct": reduction_pct,
            },
            "before": before_findings,
            "after": after_findings,
        }

        if args.output == "-":
            print(json.dumps(payload, indent=2))
        else:
            output_path = Path(args.output).expanduser().resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Wrote results to {output_path}")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
