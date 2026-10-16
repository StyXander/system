"""解释及分组只能补充关系，不能吞掉原始第三处差异。"""
from app.connectivity_pipeline import integrate_proposals
from app.connectivity_schemas import ConnectivityRun
from app.connectivity_engine import calculate
from test_connectivity_engine import relationship


def test_narrative_and_subset_group_keep_complete_numeric_relation():
    rows, original = relationship("OCC-001", ["100", "100", "105"], ["occurrence"]*3)
    original = calculate(original, rows)
    run = ConnectivityRun(run_id="SYN", company="合成企业", period="2025", documents=[], occurrences=rows, checks=[original])
    fields = {"rule_id", "title", "topic", "members", "conditions", "relationship_evidence", "explanation", "explanation_evidence"}
    proposal = original.model_dump(include=fields)
    proposal["rule_id"] = "NAR-001"
    proposal["explanation"] = "合成叙述补充，不消除差额"
    proposal["explanation_evidence"] = proposal["relationship_evidence"]
    result = integrate_proposals(run, {"checks": [proposal], "notes": []}, {r.occurrence_id for r in rows}, "A2")
    assert len(result["accepted_check_ids"]) == 1
    assert len(run.checks) == 2
    preserved = next(c for c in run.checks if c.check_id == original.check_id)
    assert preserved.calculation == original.calculation
    assert preserved.calculation_status == "unexplained_difference"
    assert len(preserved.members) == 3
    proposal["rule_id"] = "OCC-001"
    proposal["members"] = proposal["members"][:2]
    result = integrate_proposals(run, {"checks": [proposal], "notes": []}, {r.occurrence_id for r in rows}, "A2")
    assert len(run.checks) == 3
    preserved = next(c for c in run.checks if c.check_id == original.check_id)
    assert len(preserved.members) == 3
    assert preserved.calculation["residual"] != "0"
    assert result["accepted_check_ids"][0] in preserved.related_checks
