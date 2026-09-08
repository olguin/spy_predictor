"""Safe command-line entry point for CYCLE-ASYMMETRY-001."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from spy_predictor_quant.cycle1_config import (
    Cycle1Plan,
    assert_candidate_evaluation_allowed,
    load_cycle1_plan,
)
from spy_predictor_quant.cycle1_dataset import build_cycle1_dataset
from spy_predictor_quant.cycle1_source_audit import (
    Cycle1SourceAudit,
    load_cycle1_source_audit,
)


DatasetBuilder = Callable[..., tuple[Path, dict[str, Any]]]


def run(
    *,
    config_path: Path,
    source_audit_path: Path,
    repo_root: Path,
    offline: bool = False,
    dataset_only: bool = False,
    dataset_builder: DatasetBuilder = build_cycle1_dataset,
) -> dict[str, Any]:
    """Validate frozen authorities and build only an explicitly requested dataset."""
    plan: Cycle1Plan = load_cycle1_plan(config_path)
    audit: Cycle1SourceAudit = load_cycle1_source_audit(
        source_audit_path,
        plan=plan,
    )

    if not dataset_only:
        assert_candidate_evaluation_allowed(plan)
        raise RuntimeError(
            "Cycle 1 candidate evaluation is not implemented. "
            "Use --dataset-only to acquire or verify the immutable monthly dataset."
        )

    manifest_path, manifest = dataset_builder(
        plan=plan,
        audit=audit,
        repo_root=repo_root,
        offline=offline,
    )
    return {
        "status": "dataset-ready",
        "mode": "offline" if offline else "online",
        "datasetVersion": manifest["datasetVersion"],
        "datasetIdentityHash": manifest["datasetIdentityHash"],
        "datasetManifest": str(manifest_path),
        "preregistrationHash": plan.config_hash,
        "sourceAuditHash": audit.audit_hash,
        "hypothesesEvaluated": 0,
        "tracks": [
            {
                "trackId": track["trackId"],
                "role": track["role"],
                "instrument": track["instrument"],
                "manifestPath": track["manifestPath"],
                "datasetIdentityHash": track["datasetIdentityHash"],
            }
            for track in manifest["tracks"]
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate Cycle 1 authorities and build/resume its immutable monthly dataset"
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-audit", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Refuse network access and require every raw resource to be pinned",
    )
    parser.add_argument(
        "--dataset-only",
        action="store_true",
        help="Build or verify the dataset without evaluating any candidate",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run(
            config_path=args.config,
            source_audit_path=args.source_audit,
            repo_root=args.repo_root.resolve(),
            offline=args.offline,
            dataset_only=args.dataset_only,
        )
    except Exception as error:
        print(
            json.dumps(
                {"status": "error", "message": str(error)},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
