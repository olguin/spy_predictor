"""Cycle workbench with explicit evidence provenance and illustrative rules.

Scores are handcrafted fixtures or derived from validated input metrics. Higher
scores mean more supportive conditions, except stress (higher means more risk).
No fitted probability of profit or order interface exists.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from html import escape
import json
import math
from pathlib import Path
from typing import Iterable

VERSION = "cycle-workbench-inputs-v2"
COMPONENTS = ("growth", "credit", "psychology", "stress", "quality", "valuation", "timing")
MARKET_COMPONENTS = COMPONENTS[:4]
SCENARIOS = ("recovery", "expensive-rally", "stressed-selloff", "cheap-deteriorating", "conflicting", "missing-data")
NOTICE = "SYNTHETIC_ONLY; INDEPENDENT_ILLUSTRATIVE_RULES; PREDICTIVE_VALUE_UNVALIDATED"


def _instant(value: datetime | str) -> datetime:
    result = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(result, datetime) or result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Use an explicit timezone-aware datetime cutoff/publication time")
    return result.astimezone(timezone.utc)


@dataclass(frozen=True)
class ComponentObservation:
    component: str
    score: float | None
    observed_at: datetime
    published_at: datetime
    first_seen_at: datetime
    source: str
    revision: str
    max_age_days: int = 45
    evidence: str = "SYNTHETIC"
    raw_metric: str | None = None
    raw_value: float | None = None
    raw_unit: str | None = None
    transform: str | None = None
    provenance_hash: str | None = None

    def __post_init__(self) -> None:
        if self.component not in COMPONENTS:
            raise ValueError(f"Unknown component: {self.component}")
        if self.score is not None and (isinstance(self.score, bool) or not math.isfinite(self.score) or not -1 <= self.score <= 1):
            raise ValueError("Component scores must be finite in [-1, 1]")
        if not isinstance(self.max_age_days, int) or isinstance(self.max_age_days, bool) or self.max_age_days < 0:
            raise ValueError("max_age_days must be a nonnegative integer")
        for name in ("observed_at", "published_at", "first_seen_at"):
            object.__setattr__(self, name, _instant(getattr(self, name)))
        if self.observed_at > self.published_at or self.published_at > self.first_seen_at:
            raise ValueError("Expected observation <= publication <= first_seen")
        if not self.revision:
            raise ValueError("A source revision identity is required")
        if self.evidence == "SYNTHETIC":
            if not self.source.startswith("synthetic://"):
                raise ValueError("Synthetic evidence requires a synthetic source identity")
        elif self.evidence in {"RECONSTRUCTED_RESEARCH", "OBSERVED_AS_OF"}:
            if not (self.source.startswith(("https://", "http://")) and self.raw_metric
                    and self.raw_unit and self.transform and self.provenance_hash
                    and len(self.provenance_hash) == 64
                    and all(c in '0123456789abcdef' for c in self.provenance_hash)):
                raise ValueError("Non-synthetic scores require a source metric, transformation and verified provenance")
        else:
            raise ValueError("Unknown evidence tier")


@dataclass(frozen=True)
class AssessmentRules:
    supportive: float = 0.25
    severe_stress: float = 0.75
    adverse_timing: float = -0.25
    quality_failure: float = -0.75

    def __post_init__(self) -> None:
        if not (0 < self.supportive < self.severe_stress <= 1):
            raise ValueError("Require 0 < supportive < severe_stress <= 1")
        if not (-1 <= self.quality_failure < self.adverse_timing < 0):
            raise ValueError("Require -1 <= quality_failure < adverse_timing < 0")


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def select_components(observations: Iterable[ComponentObservation], *, as_of: datetime | str) -> dict:
    """Select most recent observed period and latest vintage actually seen by cutoff.

    Freshness measures age of the observation, so a new revision cannot rejuvenate
    old economic evidence. max_age_days is an explicit per-component fixture SLA.
    Future observations/revisions do not enter report identity or selected values.
    """
    cutoff = _instant(as_of)
    eligible: dict[str, list[ComponentObservation]] = {key: [] for key in COMPONENTS}
    for item in observations:
        if max(item.observed_at, item.published_at, item.first_seen_at) <= cutoff:
            eligible[item.component].append(item)
    result = {}
    for key in COMPONENTS:
        rows = eligible[key]
        if not rows:
            result[key] = {"status": "MISSING", "score": None, "reason": "NO_ADMISSIBLE_OBSERVATION"}
            continue
        latest_key = max((r.observed_at, r.published_at, r.first_seen_at) for r in rows)
        tied = [r for r in rows if (r.observed_at, r.published_at, r.first_seen_at) == latest_key]
        if any(r != tied[0] for r in tied[1:]):
            raise ValueError(f"Ambiguous same-time revisions for {key}")
        selected = tied[0]
        detail = asdict(selected)
        for name in ("observed_at", "published_at", "first_seen_at"):
            detail[name] = detail[name].isoformat()
        age = (cutoff - selected.observed_at).total_seconds() / 86400
        detail.update(status="MISSING" if selected.score is None else "FRESH" if age <= selected.max_age_days else "STALE", age_days=age)
        if selected.score is None:
            detail["reason"] = "LATEST_ADMISSIBLE_REVISION_IS_MISSING"
        detail["snapshot_hash"] = _digest(detail)
        result[key] = detail
    return result


def assess(observations: Iterable[ComponentObservation], *, as_of: datetime | str,
           symbol: str = "DEMO", rules: AssessmentRules = AssessmentRules(),
           input_metadata: dict | None = None) -> dict:
    """Return a traceable market context and conditional instrument assessment."""
    if not symbol.strip():
        raise ValueError("symbol is a display identity and must be nonempty")
    components = select_components(observations, as_of=as_of)
    missing = [key for key, value in components.items() if value["status"] != "FRESH"]
    score = {key: value["score"] for key, value in components.items()}
    market_missing = [key for key in MARKET_COMPONENTS if key in missing]
    market_reasons: list[str] = []
    if market_missing:
        market = "INSUFFICIENT_EVIDENCE"
        market_reasons = [f"{key.upper()}_{components[key]['status']}" for key in market_missing]
    elif score["stress"] >= rules.severe_stress:
        market = "DEFENSIVE"
        market_reasons = ["SEVERE_CURRENT_STRESS"]
    elif all(score[key] >= rules.supportive for key in ("growth", "credit", "psychology")) and score["stress"] < rules.supportive:
        market = "SUPPORTIVE"
        market_reasons = ["GROWTH_CREDIT_PSYCHOLOGY_SUPPORTIVE", "CURRENT_STRESS_CONTAINED"]
    else:
        market = "MIXED"
        market_reasons = ["MARKET_COMPONENTS_DO_NOT_ALIGN"]

    reasons: list[str] = []
    counterevidence = []
    for key in COMPONENTS:
        if key in missing:
            continue
        adverse = score[key] >= rules.supportive if key == "stress" else score[key] < 0
        if adverse:
            counterevidence.append(f"{key.upper()}_ADVERSE")
    if missing:
        action = "INSUFFICIENT_EVIDENCE"
        reasons = [f"{key.upper()}_{components[key]['status']}" for key in missing]
        next_step = "Obtain admissible, fresh required components before an investment assessment."
    elif market == "DEFENSIVE" or score["quality"] <= rules.quality_failure:
        action = "DEFENSIVE_REVIEW"
        reasons = (["SEVERE_CURRENT_STRESS"] if market == "DEFENSIVE" else []) + (["QUALITY_THESIS_FAILURE"] if score["quality"] <= rules.quality_failure else [])
        next_step = "Review concentration and thesis failure; reassess after stress and quality improve."
    elif score["quality"] >= rules.supportive and score["valuation"] >= rules.supportive and (score["timing"] <= rules.adverse_timing or market != "SUPPORTIVE"):
        action = "WAIT_FOR_CONFIRMATION"
        reasons = ["QUALITY_AND_VALUE_INTERESTING"] + (["ADVERSE_TIMING"] if score["timing"] <= rules.adverse_timing else []) + (["MIXED_MARKET_CONTEXT"] if market != "SUPPORTIVE" else [])
        next_step = "Watch timing and market confirmation; reassess immediately if quality deteriorates."
    elif market == "SUPPORTIVE" and all(score[key] >= rules.supportive for key in ("quality", "valuation", "timing")):
        action = "CANDIDATE_FOR_RESEARCH"
        reasons = ["QUALITY_VALUE_TIMING_ALIGN", "SUPPORTIVE_MARKET_CONTEXT"]
        next_step = "Research the thesis and staged-entry scenarios; no position size is established."
    else:
        action = "NEUTRAL"
        reasons = ["NO_COMPLETE_QUALIFYING_SETUP"]
        next_step = "Keep on review; identify which quality, valuation, timing or context condition would change."
    evidence_tiers = sorted({value["evidence"] for value in components.values() if "evidence" in value})
    notice = ("; ".join(evidence_tiers) if evidence_tiers else "NO_ADMISSIBLE_EVIDENCE") + "; INDEPENDENT_ILLUSTRATIVE_RULES; PREDICTIVE_VALUE_UNVALIDATED"
    report = {
        "version": VERSION, "notice": notice, "as_of": _instant(as_of).isoformat(),
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "symbol": symbol, "coverage": "VALIDATED_INPUT_METRICS" if input_metadata is not None else "HANDCRAFTED_COMPONENT_INPUTS",
        "input_metadata": input_metadata,
        "evidence_tiers": evidence_tiers,
        "rules": asdict(rules), "components": components,
        "market": {"posture": market, "reasons": market_reasons},
        "instrument": {"action": action, "reasons": reasons, "counterevidence": counterevidence, "next_step": next_step},
        "evidence_quality": {"fresh_components": len(COMPONENTS)-len(missing), "required_components": len(COMPONENTS), "unavailable": missing,
                             "meaning": "Data completeness only; not a probability of profit."},
        "reassessment": {"next_review": (_instant(as_of) + timedelta(days=7)).isoformat(),
                         "triggers": ["New admissible component observation", "Timing or valuation crosses the displayed rule", "Quality deterioration or severe stress"]},
    }
    report["report_hash"] = _digest(report)
    return report


def synthetic_fixture(name: str = "recovery") -> tuple[ComponentObservation, ...]:
    """Fixed handcrafted scores, independent of cutoff and all market archives."""
    cases = {
        "recovery": (.6, .4, .3, .1, .7, .6, .5),
        "expensive-rally": (.6, .4, .8, .1, .7, -.8, .8),
        "stressed-selloff": (-.8, -.7, -.9, .95, .4, .7, -.9),
        "cheap-deteriorating": (.6, .4, .3, .1, .7, .8, -.8),
        "conflicting": (-.4, .5, -.4, .4, .7, .6, .5),
        "missing-data": (.6, .4, .3, .1, .7, .6, .5),
    }
    if name not in cases:
        raise ValueError(f"Unknown synthetic fixture: {name}")
    observed = datetime(2026, 8, 1, tzinfo=timezone.utc)
    published = datetime(2026, 8, 3, 16, tzinfo=timezone.utc)
    return tuple(ComponentObservation(key, value, observed, published, published,
                 f"synthetic://{VERSION}/{name}/{key}", "initial", 120 if key in {"quality", "valuation"} else 45)
                 for key, value in zip(COMPONENTS, cases[name]) if not (name == "missing-data" and key in {"valuation", "psychology"}))


def render_html(report: dict) -> str:
    """Standalone escaped report; no external scripts or remote assets."""
    rows = []
    for key, item in report["components"].items():
        metric = item.get("raw_metric") or "handcrafted score"
        raw = f"{item.get('raw_value')} {item.get('raw_unit') or ''}" if item.get("raw_metric") else "—"
        values = [key, item["status"], item["score"], metric, raw, item.get("transform") or "—", item.get("observed_at", "—"), item.get("published_at", "—"), item.get("source", "—")]
        rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>")
    instrument = report["instrument"]
    evidence_description = ("Scores derived from manifest-validated metrics. Validation checks structure, hashes, units and availability; it does not establish predictive value."
                            if report.get("input_metadata") is not None else "Handcrafted component scores; no source metric calculation.")
    metadata_html = ("<details><summary>Input provenance and validation</summary><pre>" + escape(json.dumps(report["input_metadata"], indent=2, sort_keys=True)) + "</pre></details>"
                     if report.get("input_metadata") is not None else "")
    return """<!doctype html><html lang="en"><meta charset="utf-8"><title>Cycle Workbench</title>
<style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 16px;color:#202735}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ccc;padding:8px;text-align:left}code{overflow-wrap:anywhere}.notice{background:#fff0cc;padding:12px}</style><body>""" + f"""
<h1>Cycle Workbench · {escape(report['symbol'])}</h1><p class="notice">{escape(report['notice'])}</p>
<p>Cutoff: {escape(report['as_of'])}. {escape(evidence_description)}</p>{metadata_html}
<h2>Market: {escape(report['market']['posture'])}</h2><p>{escape('; '.join(report['market']['reasons']))}</p>
<h2>Instrument: {escape(instrument['action'])}</h2><p>{escape('; '.join(instrument['reasons']))}</p>
<p>{escape(instrument['next_step'])}</p><p>Counterevidence: {escape('; '.join(instrument['counterevidence']) or 'None under these illustrative rules.')}</p>
<table><thead><tr><th>Component</th><th>Status</th><th>Score</th><th>Raw metric</th><th>Raw value</th><th>Transformation</th><th>Observed</th><th>Published</th><th>Source</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p>Fresh components: {report['evidence_quality']['fresh_components']}/{report['evidence_quality']['required_components']}. Data completeness is not probability of profit.</p>
<p>Next review: {escape(report['reassessment']['next_review'])}. Triggers: {escape('; '.join(report['reassessment']['triggers']))}</p>
<p>Illustrative rules: <code>{escape(json.dumps(report['rules'], sort_keys=True))}</code></p>
<p>Report identity: <code>{escape(report['report_hash'])}</code></p></body></html>"""


def export_report(report: dict, directory: str | Path, *, input_audit: dict | None = None) -> dict[str, str]:
    if report.get("report_hash") != _digest({key: value for key, value in report.items() if key != "report_hash"}):
        raise ValueError("Report identity does not match its contents")
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    # Hash-qualified names preserve earlier scenarios in the same export folder.
    stem = report["report_hash"]
    json_path = destination / f"{stem}.json"
    html_path = destination / f"{stem}.html"
    for path, content in ((json_path, json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"),
                          (html_path, render_html(report))):
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError("Refusing to overwrite a different report under the same identity")
        else:
            path.write_text(content, encoding="utf-8")
    paths = {"json": str(json_path), "html": str(html_path)}
    if input_audit is not None:
        # Keep full-file lineage separately: appending future records changes
        # source bytes but must not change an earlier selected assessment.
        audit_path = destination / f"{stem}.input-audit.{_digest(input_audit)[:16]}.json"
        content = json.dumps(input_audit, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if audit_path.exists() and audit_path.read_text(encoding="utf-8") != content:
            raise ValueError("Input audit identity collision")
        if not audit_path.exists():
            audit_path.write_text(content, encoding="utf-8")
        paths["input_audit"] = str(audit_path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=("market", "instrument", "compare", "validate-inputs"))
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--fixture", choices=SCENARIOS)
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--input-root", type=Path, help="Dedicated allowed directory for manifest/snapshot files")
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO timestamp")
    parser.add_argument("--symbol", help="Must match the manifest's instrument identity when using raw inputs")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.view != "validate-inputs" and args.output is None:
        parser.error("--output is required for reports")
    if args.manifest is not None:
        if args.input_root is None:
            parser.error("--manifest requires an explicit --input-root")
        if args.view == "compare":
            parser.error("Manifest input currently supports one instrument; compare is for synthetic scenarios")
        from spy_predictor_quant.cycle_workbench_inputs import load_workbench_inputs
        loaded = load_workbench_inputs(args.manifest, as_of=args.as_of, allowed_root=args.input_root)
        symbol = loaded.metadata['symbol']
        if args.symbol is not None and args.symbol != symbol:
            parser.error("--symbol does not match the manifest instrument")
        if args.view == 'validate-inputs':
            print(json.dumps({'status': 'INPUT_CONTRACT_VALID', 'metadata': loaded.metadata, 'audit': loaded.audit}))
            return
        report = assess(loaded.observations, as_of=args.as_of, symbol=symbol, input_metadata=loaded.metadata)
        print(json.dumps({'symbol': symbol, 'market': report['market']['posture'],
                          'action': report['instrument']['action'],
                          **export_report(report, args.output, input_audit=loaded.audit)}))
        return
    if args.view == "validate-inputs" or args.input_root is not None:
        parser.error("Input validation requires --manifest and --input-root")
    cases = SCENARIOS if args.view == "compare" else (args.fixture or 'recovery',)
    for case in cases:
        report = assess(synthetic_fixture(case), as_of=args.as_of, symbol=f"{args.symbol or 'DEMO'}:{case}")
        print(json.dumps({"scenario": case, "market": report["market"]["posture"], "action": report["instrument"]["action"], **export_report(report, args.output)}))


if __name__ == "__main__":
    main()
