"""决赛反例均为测试构造，不代表真实供应商输出。"""
from backend.app.evidence_fitness import enforce_output_boundaries, CURRENT_ENTITY, NORMATIVE_BASIS
from backend.app.schemas import AgentClaim


def test_normal_explanation_cannot_use_standard_to_prove_entity_fact():
    output = {"claims": [], "normal_explanations": [{"text": "公司已经回收欠款", "evidence_ids": ["STANDARD"], "support_status": "supported"}]}
    failures = enforce_output_boundaries(output, {"STANDARD": NORMATIVE_BASIS})
    assert failures[0]["claim_group"] == "normal_explanations"
    assert output["normal_explanations"][0]["support_status"] == "unverified_hypothesis"


def test_legal_id_does_not_prove_semantic_support():
    output = {"claims": [{"text": "该企业已经回收全部欠款", "evidence_ids": ["ENTITY"], "support_status": "supported"}]}
    assert enforce_output_boundaries(output, {"ENTITY": CURRENT_ENTITY}) == []
    assert output["claims"][0]["semantic_support_status"] == "not_verified"
    assert AgentClaim.model_validate(output["claims"][0]).semantic_support_status == "not_verified"


def test_old_claim_without_semantic_flag_stays_unverified():
    assert AgentClaim(text="旧记录", evidence_ids=["E"]).semantic_support_status == "not_verified"


def test_foreign_id_is_not_treated_as_current_entity_evidence():
    output = {"claims": [{"text": "公司事实", "evidence_ids": ["FOREIGN"], "support_status": "supported"}]}
    assert enforce_output_boundaries(output, {"ENTITY": CURRENT_ENTITY})
    assert output["claims"][0]["support_status"] == "unverified_hypothesis"
