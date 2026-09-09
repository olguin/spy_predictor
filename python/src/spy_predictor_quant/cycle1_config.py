"""Fail-closed preregistration loader for CYCLE-ASYMMETRY-001."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from spy_predictor_quant.market_archive import content_hash


EXPECTED_INSTRUMENTS = ("SPY", "QQQ")
EXPECTED_MODELS = (
    "unconditional-history",
    "valuation-only",
    "direction-only",
    "fixed-cycle-score",
    "regularized-cycle",
)
FORBIDDEN_SOURCE_IDS = {"BAA", "BAMLC0A0CM", "BAMLH0A0HYM2"}
EXPECTED_FEATURES = {
    "valuation": ("real-price-trend-deviation",),
    "stress": (
        "bank-prime-minus-treasury-credit-spread",
        "realized-volatility-3m",
        "drawdown-from-trailing-high-12m",
    ),
    "direction": (
        "momentum-6m",
        "momentum-12m",
        "price-versus-moving-average-10m",
        "bank-prime-minus-treasury-credit-spread-change-3m",
        "industrial-production-growth-6m",
    ),
}
PLACEHOLDER_TEXT = {"tbd", "todo", "null", "placeholder", "fixme"}


@dataclass(frozen=True)
class Cycle1Plan:
    raw: dict[str, Any]
    config_hash: str
    instruments: tuple[str, ...]
    model_ids: tuple[str, ...]
    hypothesis_count: int


def load_cycle1_plan(path: Path, *, schema_path: Path | None = None) -> Cycle1Plan:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Cycle 1 preregistration must be a JSON object")
    schema_file = schema_path or _default_schema_path(path, payload.get("schemaVersion"))
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        detail = "; ".join(
            f"{_json_path(error.absolute_path)}: {error.message}" for error in errors
        )
        raise ValueError(f"Invalid Cycle 1 preregistration: {detail}")

    _reject_placeholders(payload)
    _validate_semantics(payload)
    models = tuple(model["id"] for model in payload["models"]["perInstrument"])
    instruments = tuple(payload["instruments"])
    return Cycle1Plan(
        raw=payload,
        config_hash=content_hash(payload),
        instruments=instruments,
        model_ids=models,
        hypothesis_count=(len(payload["evaluationLedger"]) if "evaluationLedger" in payload
                          else len(instruments) * len(models)),
    )


def assert_candidate_evaluation_allowed(plan: Cycle1Plan) -> None:
    """Recheck the immutable scientific budget at the evaluation boundary."""
    _validate_semantics(plan.raw)
    if plan.raw["schemaVersion"] == "cycle1-preregistration-v5":
        raise RuntimeError(
            "Cycle 1 v5 is proposed-synthetic-only: simulation design, whole-procedure "
            "power approval, and a qualified dataset are required; real evaluation is blocked."
        )
    if plan.hypothesis_count != 10:
        raise ValueError("Candidate evaluation requires exactly ten hypotheses")
    if plan.raw["schemaVersion"] == "cycle1-preregistration-v4":
        raise RuntimeError(
            "Cycle 1 v4 is suspended for pre-evaluation repair: cash publication "
            "coverage, selection feasibility, and the evaluation contract are unresolved. "
            "Use npm run cycle1:preflight for the metadata-only audit."
        )


def _default_schema_path(config_path: Path, version: str | None = None) -> Path:
    filenames = {
        "cycle1-preregistration-v4": "cycle1-config-v4.schema.json",
        "cycle1-preregistration-v5": "cycle1-config-v5-draft.schema.json",
    }
    if version not in filenames:
        raise ValueError(f"Unsupported Cycle 1 preregistration version {version}")
    for parent in config_path.resolve().parents:
        candidate = parent / "schemas" / filenames[version]
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Cannot locate schemas/cycle1-config.schema.json")


def _reject_placeholders(value: Any, path: str = "$") -> None:
    if value is None:
        raise ValueError(f"Cycle 1 preregistration contains null at {path}")
    if isinstance(value, str):
        normalized = value.strip().lower()
        if not normalized or normalized in PLACEHOLDER_TEXT or any(
            token in normalized for token in ("<tbd>", "__tbd__", "to-be-decided")
        ):
            raise ValueError(f"Cycle 1 preregistration contains placeholder text at {path}")
    elif isinstance(value, dict):
        for key, child in value.items():
            _reject_placeholders(child, f"{path}.{key}")
    elif isinstance(value, list):
        if not value:
            raise ValueError(f"Cycle 1 preregistration contains an empty list at {path}")
        for index, child in enumerate(value):
            _reject_placeholders(child, f"{path}[{index}]")


def _validate_semantics(payload: dict[str, Any]) -> None:
    if payload.get("schemaVersion") == "cycle1-preregistration-v5":
        _validate_v5_semantics(payload)
        return
    if payload.get("schemaVersion") != "cycle1-preregistration-v4":
        raise ValueError("Unsupported Cycle 1 preregistration version")
    required_paths = (
        "decisionFrequency.frequency", "decisionFrequency.calendar",
        "decisionFrequency.timezone", "decisionFrequency.snapshotSessionRule",
        "decisionFrequency.snapshotCutoff", "decisionFrequency.recordAvailabilityRule",
        "decisionFrequency.earliestPolicyExecution", "targets.primary.id",
        "targets.primary.startEndpoint", "targets.primary.endEndpoint",
        "targets.primary.equityReturn.method", "targets.primary.cashReturn.formula",
        "targets.primary.inflation.commonDeflatorRule", "targets.secondary.formula",
        "targets.secondary.eventThreshold", "targets.diagnostic.formula",
        "targets.labelAvailabilityRule", "features.missingValuePolicy",
        "features.availability.pointInTimeRule", "features.normalization.percentileMethod",
        "features.normalization.percentileMinimumHistoryMonths",
        "features.dimensionAggregation", "features.cycleScoreAggregation",
        "states.thresholds.cheapValuationMinimum",
        "states.thresholds.expensiveValuationMaximum",
        "states.thresholds.highStressMinimum", "states.thresholds.easyStressMaximum",
        "states.thresholds.positiveDirectionMinimum",
        "states.thresholds.weakDirectionMaximum",
        "states.thresholds.stressChangeMagnitude",
        "states.thresholds.formerlyExpensiveLookbackMonths",
        "partitions.minimumTrainingMonths", "partitions.rollingWindowMonths",
        "partitions.primaryLabelOverlapMonths", "partitions.purgeMonths",
        "partitions.selectionConfirmationEmbargoMonths",
        "partitions.confirmationBoundaryRule",
        "partitions.minimumConfirmationLabeledMonths",
        "partitions.minimumConfirmationCalendarYears",
        "partitions.minimumEffectiveAnnualBlocks",
        "partitions.minimumLabeledMonthsPerHalf", "partitions.bootstrap.method",
        "partitions.bootstrap.blockLengthMonths", "partitions.bootstrap.resamples",
        "partitions.bootstrap.confidenceLevel", "partitions.bootstrap.seed",
        "promotionGates.returnDistribution.primaryMetric",
        "promotionGates.returnDistribution.minimumRelativeImprovement",
        "promotionGates.returnDistribution.minimumAbsoluteImprovement",
        "promotionGates.returnDistribution.maximumRmseDegradation",
        "promotionGates.returnDistribution.bootstrapLowerBoundMustExceed",
        "promotionGates.drawdown.primaryMetric",
        "promotionGates.drawdown.minimumAbsoluteBrierImprovement",
        "promotionGates.drawdown.maximumLogLossDegradation",
        "promotionGates.drawdown.maximumExpectedCalibrationError",
        "promotionGates.drawdown.minimumCalibrationSlope",
        "promotionGates.drawdown.maximumCalibrationSlope",
        "promotionGates.monotonicity.groups",
        "promotionGates.monotonicity.minimumObservationsPerGroup",
        "promotionGates.stability.minimumEvaluableEras",
        "promotionGates.stability.minimumPositiveEraFraction",
        "promotionGates.stability.maximumRelativeLossDegradationAnyEra",
        "promotionGates.stability.maximumSingleBlockBenefitFraction",
        "promotionGates.multipleTesting.method",
        "promotionGates.multipleTesting.familyWiseAlpha",
        "promotionGates.economicPolicy.oneWayTransactionCostBps",
        "promotionGates.economicPolicy.stressCostMultiplier",
        "promotionGates.economicPolicy.maximumAnnualTurnover",
        "promotionGates.economicPolicy.minimumRiskAdjustedTradeoffImprovement",
        "promotionGates.economicPolicy.maximumAnnualizedReturnShortfall",
        "promotionGates.economicPolicy.minimumMaximumDrawdownImprovement",
    )
    for path in required_paths:
        _required(payload, path)
    instruments = tuple(payload["instruments"])
    if instruments != EXPECTED_INSTRUMENTS:
        raise ValueError("Cycle 1 instruments must be exactly SPY and QQQ")
    models = tuple(model["id"] for model in payload["models"]["perInstrument"])
    if models != EXPECTED_MODELS or len(set(models)) != 5:
        raise ValueError("Cycle 1 must contain the five frozen models in frozen order")
    if payload["models"]["hmmIncluded"] is not False:
        raise ValueError("An HMM is not preregistered for Cycle 1")
    if "hmm" in json.dumps(payload["models"], sort_keys=True).lower().replace(
        '"hmmincluded": false', ""
    ):
        raise ValueError("Cycle 1 model definitions may not include an HMM")
    serialized = json.dumps(payload["features"], sort_keys=True)
    present_forbidden = sorted(
        source_id for source_id in FORBIDDEN_SOURCE_IDS if source_id in serialized
    )
    if present_forbidden:
        raise ValueError(
            "Cycle 1 may not archive license-incompatible credit series: "
            + ", ".join(present_forbidden)
        )
    dimensions = payload["features"]["dimensions"]
    if set(dimensions) != set(EXPECTED_FEATURES):
        raise ValueError("Cycle 1 feature dimensions differ from preregistration")
    for dimension, expected_ids in EXPECTED_FEATURES.items():
        features = dimensions[dimension]["features"]
        ids = tuple(feature.get("id") for feature in features)
        if ids != expected_ids:
            raise ValueError(f"Frozen {dimension} features are missing or reordered")
        for feature in features:
            if feature.get("economicSign") not in {-1, 1}:
                raise ValueError(f"Feature {feature.get('id')} needs a frozen economic sign")
            if feature.get("promotionEligible") is not True:
                raise ValueError(f"Core feature {feature.get('id')} must remain promotion eligible")
            if "windowMonths" in feature and feature["windowMonths"] <= 0:
                raise ValueError(f"Feature {feature['id']} window must be positive")
    spread = dimensions["stress"]["features"][0]
    if spread.get("sources") != ["MPRIME", "GS3M"]:
        raise ValueError("Cycle 1 credit spread sources must be exactly MPRIME and GS3M")
    if spread.get("alignment") != "latest-common-observation-month-whose-both-vintages-were-published-by-cutoff" or spread.get("formula") != "MPRIME_t-GS3M_t":
        raise ValueError("Cycle 1 credit spread alignment and formula must remain frozen")
    spread_change = dimensions["direction"]["features"][3]
    if spread_change.get("source") != spread["id"]:
        raise ValueError("Cycle 1 credit-spread change must reference the frozen level")
    if spread_change.get("formula") != "spread_t-spread_t_minus_3_months":
        raise ValueError("Cycle 1 credit-spread change formula must remain frozen")
    stress_diagnostics = dimensions["stress"].get("diagnostics", [])
    if len(stress_diagnostics) != 1 or stress_diagnostics[0].get("id") != "national-financial-conditions-index" or stress_diagnostics[0].get("promotionEligible") is not False:
        raise ValueError("NFCI must remain a single diagnostic-only stress input")
    if set(payload["states"]["rules"]) != {
        "EUPHORIA", "EARLY_RECOVERY", "CRISIS", "CORRECTION", "GREED", "NORMAL"
    }:
        raise ValueError("Every frozen deterministic state rule is required")

    budget = payload["hypothesisBudget"]
    actual = len(instruments) * len(models)
    if budget != {
        "instruments": 2,
        "modelsPerInstrument": 5,
        "primaryEvaluations": 10,
        "optionalHmmEvaluations": 0,
    } or actual != 10:
        raise ValueError("Cycle 1 hypothesis budget must be exactly 2 x 5 = 10")

    targets = payload["targets"]
    if targets["primary"]["horizonMonths"] != 12:
        raise ValueError("The primary horizon must remain twelve months")
    if targets["secondary"]["eventThreshold"] != -0.2:
        raise ValueError("The drawdown event threshold must remain -20 percent")
    if targets["diagnostic"]["promotionEligible"] is not False or targets[
        "diagnostic"
    ]["mayRescuePrimaryFailure"] is not False:
        raise ValueError("The 24-month diagnostic may not affect promotion")

    partitions = payload["partitions"]
    if partitions["purgeMonths"] < targets["primary"]["horizonMonths"]:
        raise ValueError("Purge must cover the complete primary target overlap")
    if partitions["selectionConfirmationEmbargoMonths"] < targets["primary"][
        "horizonMonths"
    ]:
        raise ValueError("Confirmation embargo must cover the primary horizon")
    if partitions["minimumLabeledMonthsPerHalf"] * partitions[
        "confirmationHalves"
    ] > partitions["minimumConfirmationLabeledMonths"]:
        raise ValueError("Confirmation half minima exceed the total confirmation sample")

    gates = payload["promotionGates"]
    required_positive = {
        "minimumCoreFeatureCoveragePercent": gates[
            "minimumCoreFeatureCoveragePercent"
        ],
        "minimumRelativeImprovement": gates["returnDistribution"][
            "minimumRelativeImprovement"
        ],
        "minimumAbsoluteImprovement": gates["returnDistribution"][
            "minimumAbsoluteImprovement"
        ],
        "bootstrapLowerBoundMustExceed": gates["returnDistribution"][
            "bootstrapLowerBoundMustExceed"
        ],
        "minimumAbsoluteBrierImprovement": gates["drawdown"][
            "minimumAbsoluteBrierImprovement"
        ],
        "familyWiseAlpha": gates["multipleTesting"]["familyWiseAlpha"],
        "oneWayTransactionCostBps": gates["economicPolicy"][
            "oneWayTransactionCostBps"
        ],
        "minimumRiskAdjustedTradeoffImprovement": gates["economicPolicy"][
            "minimumRiskAdjustedTradeoffImprovement"
        ],
    }
    for name, value in required_positive.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ValueError(f"Numeric promotion gate {name} must be explicitly positive")
    _reject_zero_numeric_gates(gates)


def _validate_v5_semantics(payload: dict[str, Any]) -> None:
    """Check linked roles and test accounting independently of schema shape."""
    models = payload["models"]["perInstrument"]
    ids = [model["id"] for model in models]
    expected = ["unconditional-history", "volatility-conditioned-history",
                "valuation-only", "direction-only", "position-plus-direction",
                "fixed-cycle-score", "regularized-cycle"]
    if ids != expected:
        raise ValueError("v5 requires seven ordered SPY models")
    ledger = payload["evaluationLedger"]
    expected_entries = [("SPY", model) for model in expected] + [
        ("QQQ", model) for model in [*expected[-2:], expected[0]]
    ]
    if [(row["instrument"], row["modelId"]) for row in ledger] != expected_entries:
        raise ValueError("v5 requires ten explicit ledger entries with conditional QQQ transfer")
    if len({row["entryId"] for row in ledger}) != 10:
        raise ValueError("v5 ledger entry identities must be unique")
    comparison = payload["evaluationContract"]["comparisons"]
    if (comparison["primaryHypotheses"] != expected[-2:]
            or comparison["challengerBaselines"] != expected[:5]
            or comparison["holmFamily"] != "two-SPY-composite-cycle-claims"):
        raise ValueError("v5 requires two composite claims against all five comparators")
    budget = payload["hypothesisBudget"]
    if (budget["totalLedgerEntries"] != 10 or budget["compositePrimaryClaims"] != 2
            or budget["componentTestsPerClaim"] != 10):
        raise ValueError("v5 ledger and comparison budgets disagree")
    if (payload["status"] != "proposed-synthetic-only"
            or payload["execution"]["realCandidateEvaluationAllowed"] is not False
            or payload["execution"]["datasetBuildAllowed"] is not False
            or payload["execution"]["confirmationOpeningAllowed"] is not False):
        raise ValueError("v5 proposal cannot authorize real data or confirmation")
    if payload["targets"]["primary"]["cashReturn"]["seriesId"] != "GS3M":
        raise ValueError("v5 cash proxy must be GS3M")
    if payload["partitions"]["qqqSelectionMetricsAllowed"] is not False:
        raise ValueError("QQQ cannot participate in development")


def _required(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            raise ValueError(f"Cycle 1 preregistration is missing required field {path}")
        value = value[key]
    return value


def _reject_zero_numeric_gates(value: Any, path: str = "promotionGates") -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)) and value == 0:
        raise ValueError(f"Numeric promotion gate {path} may not be a zero placeholder")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_zero_numeric_gates(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_zero_numeric_gates(child, f"{path}[{index}]")


def _json_path(parts: Any) -> str:
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered
