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
    contract_only: bool = False,
    dataset_builder: DatasetBuilder = build_cycle1_dataset,
) -> dict[str, Any]:
    """Validate frozen authorities and build only an explicitly requested dataset."""
    plan: Cycle1Plan = load_cycle1_plan(config_path)
    audit: Cycle1SourceAudit = load_cycle1_source_audit(
        source_audit_path,
        plan=plan,
    )
    from spy_predictor_quant.cycle1_power_gate import read_terminal_decision
    terminal = read_terminal_decision(repo_root)
    if terminal is not None and not contract_only and plan.raw['schemaVersion'] == 'cycle1-preregistration-v5':
        raise RuntimeError('Cycle 1 power audit is stopped: INSUFFICIENT_EVIDENCE; real evaluation is blocked.')

    if contract_only:
        if dataset_only:
            raise ValueError("--contract-only and --dataset-only are mutually exclusive")
        if plan.raw["schemaVersion"] != "cycle1-preregistration-v5":
            raise ValueError("Contract review requires the v5 proposal")
        from spy_predictor_quant.market_archive import content_hash, file_sha256
        from spy_predictor_quant.cycle1_simulation_design import load_design

        authority_root = config_path.resolve().parent.parent
        design = load_design(
            authority_root / plan.raw["evaluationContract"]["powerAudit"]["designPath"],
            repo_root=authority_root,
        )

        report = {
            "status": "VALID_PROPOSAL_BLOCKED_FOR_REAL_DATA",
            "preregistrationHash": plan.config_hash,
            "sourceAuditHash": audit.audit_hash,
            "simulationDesignHash": design["designHash"],
            "ledgerHash": content_hash(plan.raw["evaluationLedger"]),
            "ledgerEntries": plan.hypothesis_count,
            "compositePrimaryClaims": plan.raw["hypothesisBudget"]["compositePrimaryClaims"],
            "implementationHashes": {
                name: file_sha256(Path(__file__).with_name(name))
                for name in ("cycle1.py", "cycle1_config.py", "cycle1_source_audit.py")
            },
            "blockingReasons": ["FULL_PROCEDURE_AUDIT_NOT_IMPLEMENTED", "POWER_AUDIT_NOT_RUN",
                                "INDEPENDENT_ARCHIVE_RESTORE_NOT_VERIFIED",
                                "V5_DATASET_NOT_QUALIFIED"],
            "candidateMetricsComputed": False,
            "confirmationMetricsOpened": False,
            "syntheticMetricsComputed": False,
        }
        if terminal is not None:
            report['terminalPowerDecision'] = terminal
            report['status'] = 'STOPPED_INSUFFICIENT_EVIDENCE'
        return {**report, "reportHash": content_hash(report)}

    if plan.raw["schemaVersion"] == "cycle1-preregistration-v5":
        assert_candidate_evaluation_allowed(plan)

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
    parser.add_argument("--contract-only", action="store_true",
                        help="Validate the v5 proposal without reading market data or fitting models")
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
            contract_only=args.contract_only,
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
