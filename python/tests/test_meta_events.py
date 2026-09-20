from copy import deepcopy

import pytest

from spy_predictor_quant.meta_events import cluster_news, reaction_feature, verified_exposure_paths
from spy_predictor_quant.meta_forecast import build_structured_forecast, load_policy
from test_meta_forecast import packet, report


def news(**changes):
    return {"kind": "news", "symbols": ["SPY"], "text": "Company updates its fiscal quarter guidance",
            "published_at": "2026-09-14T14:00:00Z", "retrieved_at": "2026-09-14T14:01:00Z", **changes}


def test_syndication_is_one_event_and_source_independence_is_not_inferred():
    evidence = {"a": news(), "b": news(published_at="2026-09-14T14:00:01Z"),
                "c": news(symbols=["QQQ"]), "d": news(retrieved_at=None)}
    result = cluster_news(evidence, "2026-09-14T15:00:00Z")
    assert len(result["clusters"]) == 2
    assert result["clusters"][0]["evidence_ids"] == ["a", "b"]
    assert result["clusters"][0]["independent_source_count"] is None
    assert result["excluded"] == [{"evidence_id": "d", "reason": "UNKNOWN_OR_INELIGIBLE_AVAILABILITY"}]


def test_one_event_cannot_add_two_role_votes():
    data = packet()
    data["event_context"] = {"clusters": [{"event_id": "shared-event", "evidence_ids": ["news-evidence", "geopolitical-evidence"]}]}
    row = build_structured_forecast(data, report(), load_policy())["symbols"]["SPY"]["horizons"][0]
    assert row["context_signal"]["accepted_roles"] == 4
    assert any(item["status"] == "CORRELATED_DUPLICATE" for item in row["context_signal"]["evidence_family_coverage"])


def test_expired_or_unverified_exposure_is_unknown():
    edge = {"from": "CUSTOMER", "to": "SPY", "status": "VERIFIED", "evidence_ids": ["a"],
            "valid_from": "2026-09-14T14:00:00Z", "valid_until": "2026-09-15T00:00:00Z",
            "available_at": "2026-09-14T14:01:00Z", "confidence": .8}
    assert verified_exposure_paths([edge], "CUSTOMER", "SPY", "2026-09-14T15:00:00Z", {"a": news()})["status"] == "VERIFIED_PATH"
    assert verified_exposure_paths([edge], "CUSTOMER", "SPY", "2026-09-15T15:00:00Z", {"a": news()})["status"] == "UNKNOWN_EXPOSURE"
    assert verified_exposure_paths([{**edge, "status": "INFERRED"}], "CUSTOMER", "SPY", "2026-09-14T15:00:00Z", {"a": news()})["status"] == "UNKNOWN_EXPOSURE"


def test_event_reaction_cannot_predict_an_earlier_origin():
    before = {"timestamp": "2026-09-14T14:00:00Z", "available_at": "2026-09-14T14:00:01Z", "price": 100}
    after = {"timestamp": "2026-09-14T15:00:00Z", "available_at": "2026-09-14T15:00:01Z", "price": 103}
    benchmark_after = {**after, "price": 101}
    result = reaction_feature(before, after, before, benchmark_after, "2026-09-14T15:01:00Z")
    assert result["market_adjusted_return"] == pytest.approx(.02)
    assert result["priced_in_degree"] == "UNKNOWN"
    with pytest.raises(ValueError, match="before the prediction origin"):
        reaction_feature(before, after, before, benchmark_after, "2026-09-14T14:59:00Z")
