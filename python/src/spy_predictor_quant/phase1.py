"""One-command TARGET-TOURNAMENT-001 completion workflow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spy_predictor_quant.phase1_comparison import build_phase1_comparison
from spy_predictor_quant.phase1_config import load_phase1_plan
from spy_predictor_quant.phase1_dataset import build_phase1_dataset
from spy_predictor_quant.phase1_tournament import run_phase1_tournament


def run(
    *,
    config_path: Path,
    repo_root: Path,
    offline: bool = False,
    dataset_only: bool = False,
    ibkr_manifest_path: Path | None = None,
) -> dict[str, object]:
    plan = load_phase1_plan(config_path)
    dataset_path, dataset = build_phase1_dataset(
        plan,
        repo_root,
        offline=offline,
    )
    result: dict[str, object] = {
        "status": "dataset-ready" if dataset_only else "completed",
        "datasetVersion": dataset["datasetVersion"],
        "datasetIdentityHash": dataset["datasetIdentityHash"],
        "datasetManifest": str(dataset_path),
        "normalizedBars": dataset["normalizedBars"]["records"],
    }
    if dataset_only:
        return result
    comparison_path, comparison = build_phase1_comparison(
        dataset_manifest_path=dataset_path,
        repo_root=repo_root,
        tournament_config=plan.tournament,
        ibkr_manifest_path=ibkr_manifest_path,
        offline=offline,
    )
    report_path, report = run_phase1_tournament(
        plan=plan,
        dataset_manifest_path=dataset_path,
        comparison_path=comparison_path,
        repo_root=repo_root,
    )
    result.update(
        {
            "comparison": str(comparison_path),
            "comparisonHash": comparison["comparisonHash"],
            "crossProviderPassed": {
                instrument: gate["passed"]
                for instrument, gate in comparison["gates"].items()
            },
            "decision": report["decision"],
            "selectedCandidate": report["selectedCandidate"],
            "report": str(report_path),
            "reportHash": report["reportHash"],
            "hypothesesEvaluated": report["hypothesesEvaluated"],
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build/resume the Phase 1 dataset and run the target tournament"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Refuse network access and require every raw page to be pinned",
    )
    parser.add_argument("--dataset-only", action="store_true")
    parser.add_argument("--ibkr-manifest", type=Path)
    args = parser.parse_args()
    try:
        result = run(
            config_path=args.config,
            repo_root=args.repo_root.resolve(),
            offline=args.offline,
            dataset_only=args.dataset_only,
            ibkr_manifest_path=args.ibkr_manifest,
        )
    except Exception as error:
        print(
            json.dumps({"status": "error", "message": str(error)}, indent=2),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
