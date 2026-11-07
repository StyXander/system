"""测试挑战杯 V2.1 严谨科研实验套件：
1. RunRequest 2x2 因子设计与消融条件校验 (no_ontology_gate, experiment_mode)
2. G0–G7 实验组解析与因数设计映射
3. 统一五级核验结论 (5-Class Verdict) 映射规则
4. FCR、精确率、覆盖率与 Macro-F1 计算公式准确性
5. 双盲标注 Cohen's Kappa (κ) 与加权 Kappa 正确性
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.connectivity_schemas import RunRequest
from scripts.run_final_comparison import resolve_groups, EXPERIMENT_GROUPS, FACTORIAL_2X2_GROUPS
from scripts.evaluate_matter_benchmark import (
    normalize_verdict,
    extract_verdict_from_assessment,
    compute_binary_metrics,
    compute_multiclass_metrics,
    VERDICT_CLASSES,
)
from scripts.compute_iaa_metrics import compute_cohens_kappa


class TestFactorialExperimentSchema:
    def test_run_request_allows_no_ontology_gate(self):
        # single_model with no_ontology_gate (G1)
        req_g1 = RunRequest(
            pair_id="CNINFO_000858_T0_20260430",
            mode="single_model",
            ablation="no_ontology_gate",
            experiment_mode="end_to_end",
        )
        assert req_g1.ablation == "no_ontology_gate"
        assert req_g1.experiment_mode == "end_to_end"

        # five_agents with no_ontology_gate (G6)
        req_g6 = RunRequest(
            pair_id="CNINFO_000858_T0_20260430",
            mode="five_agents",
            ablation="no_ontology_gate",
            experiment_mode="fixed_evidence",
        )
        assert req_g6.ablation == "no_ontology_gate"
        assert req_g6.experiment_mode == "fixed_evidence"

    def test_run_request_rejects_invalid_ablation_mode_combinations(self):
        # three_agents should NOT allow no_ontology_gate
        with pytest.raises(ValidationError):
            RunRequest(
                pair_id="CNINFO_000858_T0_20260430",
                mode="three_agents",
                ablation="no_ontology_gate",
            )

        # three_agents should NOT allow no_temporal
        with pytest.raises(ValidationError):
            RunRequest(
                pair_id="CNINFO_000858_T0_20260430",
                mode="three_agents",
                ablation="no_temporal",
            )


class TestGroupResolution:
    def test_factorial_2x2_resolution(self):
        class DummyArgs:
            factor_design = True
            groups = None
            ablations = False
            allow_models = True

        resolved = resolve_groups(DummyArgs())
        assert resolved == ["G1", "G7", "G6", "G3"]

    def test_explicit_groups_parsing(self):
        class DummyArgs:
            factor_design = False
            groups = "G0,G3,G6"
            ablations = False
            allow_models = True

        resolved = resolve_groups(DummyArgs())
        assert resolved == ["G0", "G3", "G6"]

    def test_all_groups_exist(self):
        for gid in ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]:
            assert gid in EXPERIMENT_GROUPS
            assert "mode" in EXPERIMENT_GROUPS[gid]
            assert "ablation" in EXPERIMENT_GROUPS[gid]


class TestVerdictAndEvaluationMetrics:
    def test_verdict_normalization(self):
        assert normalize_verdict("确认一致") == "CONFIRMED_CONSISTENT"
        assert normalize_verdict("consistent") == "CONFIRMED_CONSISTENT"
        assert normalize_verdict("疑似冲突") == "SUSPECTED_CONFLICT"
        assert normalize_verdict("conflicting") == "SUSPECTED_CONFLICT"
        assert normalize_verdict("不可比") == "NOT_COMPARABLE"
        assert normalize_verdict("已解释差异") == "EXPLAINED_DIFFERENCE"
        assert normalize_verdict("待查明") == "INSUFFICIENT_EVIDENCE"

    def test_verdict_extraction_logic(self):
        # 1. Not comparable
        v1 = extract_verdict_from_assessment({"amount_comparability": "not_comparable", "relation_support": "supported"})
        assert v1 == "NOT_COMPARABLE"

        # 2. Conflicting with explanation -> EXPLAINED_DIFFERENCE
        v2 = extract_verdict_from_assessment(
            {"relation_support": "conflicting"},
            explanations=[{"status": "supported_as_reported", "supporting_evidence_ids": ["E2"], "summary": "附注已说明子公司范围差异"}],
        )
        assert v2 == "EXPLAINED_DIFFERENCE"

        # 3. Conflicting without explanation -> SUSPECTED_CONFLICT
        v3 = extract_verdict_from_assessment(
            {"relation_support": "conflicting"},
            explanations=[],
        )
        assert v3 == "SUSPECTED_CONFLICT"

        # 4. Supported & comparable -> CONFIRMED_CONSISTENT
        v4 = extract_verdict_from_assessment(
            {"relation_support": "supported", "amount_comparability": "comparable", "numeric_consistency": "consistent", "supporting_evidence_ids": ["E1"]},
        )
        assert v4 == "CONFIRMED_CONSISTENT"

    def test_binary_fcr_and_precision(self):
        y_true = ["CONFIRMED_CONSISTENT", "SUSPECTED_CONFLICT", "NOT_COMPARABLE", "CONFIRMED_CONSISTENT"]
        # System confirmed 3 cases, but one of them was actually a SUSPECTED_CONFLICT (false confirmation)
        y_pred = ["CONFIRMED_CONSISTENT", "CONFIRMED_CONSISTENT", "NOT_COMPARABLE", "CONFIRMED_CONSISTENT"]

        metrics = compute_binary_metrics(y_true, y_pred, {"CONFIRMED_CONSISTENT"})
        assert metrics["n_total"] == 4
        assert metrics["n_confirm"] == 3
        assert metrics["n_true_confirm"] == 2
        assert metrics["n_false_confirm"] == 1
        assert metrics["fcr"] == round(1 / 3, 4)
        assert metrics["precision"] == round(2 / 3, 4)
        assert metrics["recall"] == 1.0
        assert metrics["coverage"] == 0.75

    def test_multiclass_metrics_perfect_case(self):
        y_true = VERDICT_CLASSES
        y_pred = list(VERDICT_CLASSES)
        m = compute_multiclass_metrics(y_true, y_pred)
        assert m["accuracy"] == 1.0
        assert m["macro_f1"] == 1.0


class TestCohenKappaIAA:
    def test_perfect_agreement(self):
        rater_a = ["CONFIRMED_CONSISTENT", "SUSPECTED_CONFLICT", "NOT_COMPARABLE"]
        rater_b = ["CONFIRMED_CONSISTENT", "SUSPECTED_CONFLICT", "NOT_COMPARABLE"]
        res = compute_cohens_kappa(rater_a, rater_b, VERDICT_CLASSES)
        assert res["percent_agreement"] == 1.0
        assert res["cohens_kappa"] == 1.0
        assert res["weighted_kappa"] is None
        assert res["interpretation"] == "Almost Perfect"

    def test_partial_agreement(self):
        rater_a = ["CONFIRMED_CONSISTENT", "CONFIRMED_CONSISTENT", "SUSPECTED_CONFLICT", "INSUFFICIENT_EVIDENCE"]
        rater_b = ["CONFIRMED_CONSISTENT", "NOT_COMPARABLE", "SUSPECTED_CONFLICT", "INSUFFICIENT_EVIDENCE"]
        res = compute_cohens_kappa(rater_a, rater_b, VERDICT_CLASSES)
        assert res["percent_agreement"] == 0.75
        assert res["cohens_kappa"] > 0.5
