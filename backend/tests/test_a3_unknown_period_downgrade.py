"""A3 time evidence: fail closed on unsupported years without discarding other verified work."""
from types import SimpleNamespace as NS

from backend.app.connectivity_matters import suppress_unsupported_temporal_fields


def make_result():
    return NS(
        events=[
            NS(occurred_period="2025", evidence_ids=["ME-1"]),
            NS(occurred_period="2025", evidence_ids=["ME-2"]),
        ],
        commitments=[NS(baseline_year="2023", target_year="2026",
                        status="not_due", evidence_ids=["ME-3"])],
    )


def test_a3_unsupported_year_is_blank_and_audited():
    result=make_result()
    trusted={
        "ME-1": NS(quote="2025年12月项目竣工，完成验收"),
        "ME-2": NS(quote="本报告年度披露零碳项目进度，未披露具体投产日期"),
        "ME-3": NS(quote="计划在2026年建设，并提及2024年基准水平"),
    }
    changes=suppress_unsupported_temporal_fields(result,trusted)
    assert result.events[0].occurred_period == "2025"
    assert result.events[1].occurred_period == ""
    assert result.commitments[0].baseline_year == ""
    assert result.commitments[0].target_year == "2026"
    assert result.commitments[0].status == "needs_review"
    assert len(changes)==2
    assert all(x["accepted_value"] == "" for x in changes)
    assert {x["field_path"] for x in changes} == {
        "events.1.occurred_period", "commitments.0.baseline_year"
    }


def test_missing_citation_remains_unverified_not_forged():
    result=NS(events=[NS(occurred_period="2025",evidence_ids=["NONEXISTENT"])],commitments=[])
    issues=suppress_unsupported_temporal_fields(result,{})
    assert result.events[0].evidence_ids == ["NONEXISTENT"]
    assert result.events[0].occurred_period == ""
    assert issues[0]["code"] == "EVENT_PERIOD_UNSUPPORTED_DOWNGRADED"
    # The unchanged integration validator rejects missing IDs afterwards.
