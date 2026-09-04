"""发布门禁可靠性与版本绑定反向契约测试。

严格验证《AI-2：评委复现与发布门禁可靠性计划》Phase 4 的门禁约束：
1. 工作区 dirty 或 HEAD 不一致时发布必须为 false；
2. manifest、评估记录、部署提交必须可核验；
3. current_evaluation 模型必须一致，旧模型只能保留在历史/superseded 区域；
4. 受签文件变动后签字回归 stale_requires_reapproval；
5. 新鲜 B3 必须硬绑定真实 run_id、调用次数、多角色和事实闸门，禁止布尔假冒；
6. 缺少最终真人批准时发布绝对为 false。
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from backend.app.release_gate import SIGNOFF_APPROVED, VALID, evaluate_b3_eligibility, evaluate_release_ready
from backend.app.signoff import SIGNOFF_STALE_STATUS, load_signoff_status

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_JSON = REPO_ROOT / "backend" / "release_records" / "current_release.json"
EVALUATION_JSON = REPO_ROOT / "backend" / "release_records" / "current_evaluation.json"
MANIFEST_JSON = REPO_ROOT / "backend" / "competition_demo_cases.json"
STATUS_JSON = REPO_ROOT / "PROJECT_STATUS.json"


def _valid_b3_evidence(**overrides: object) -> dict:
    """一份绑定齐备、应判合格的 B3 证据；调用方可覆盖任意字段构造反例。"""
    evidence = {
        "run_id": "RUN-B3-FRESH-0001",
        "run_record_status": "verified",
        "environment": "production",
        "external_live": True,
        "provider": "deepseek_direct",
        "model_id": "deepseek-v4-flash",
        "source_commit": "b" * 40,
        "deployment_commit": "b" * 40,
        "manifest_sha256": "c" * 64,
        "manifest_hash_verified": True,
        "result_hash_verified": True,
        "completed_roles": 3,
        "role_statuses": {"challenge": "completed", "counter": "completed", "review": "completed"},
        "provider_calls": 3,
        "provider_call_ids": ["CALL-1", "CALL-2", "CALL-3"],
        "result_sha256": "a" * 64,
        "result_status": "complete",
        "analysis_status": "complete_full_analysis",
        "posthoc_validation_status": "passed",
        "human_scores_completed": True,
        "human_score_record_ids": ["SCORE-1", "SCORE-2"],
    }
    evidence.update(overrides)
    return evidence


def _canonical_json_sha256(data: dict) -> str:
    serialized = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def test_dirty_workspace_and_head_mismatch_blocks_release_ready() -> None:
    """工作区 dirty 或 HEAD 未冻结时，competition_release_ready 绝不能为 true。"""
    assert RELEASE_JSON.is_file(), "缺少 current_release.json"
    release_data = json.loads(RELEASE_JSON.read_text(encoding="utf-8"))

    # 发布就绪门禁硬断言必须为 false
    assert release_data["release_readiness"]["competition_release_ready"] is False
    assert "尚未取得" in release_data["release_readiness"]["reason"]

    # 检查 Git HEAD 与发布记录中绑定的 HEAD
    git_head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    materialized_head = release_data.get("demo", {}).get("materialized_source_head")

    # 若 HEAD 不一致或工作区存在未冻结变更，发布门禁绝对不能开
    status_proc = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    is_dirty = bool(status_proc.stdout.strip())

    if is_dirty or git_head != materialized_head:
        assert release_data["release_readiness"]["competition_release_ready"] is False


def test_release_manifest_and_evaluation_pointers_are_traceable() -> None:
    """发布快照所引用的案例清单和评估指针必须在磁盘上可查且哈希自洽。"""
    release_data = json.loads(RELEASE_JSON.read_text(encoding="utf-8"))

    # 案例清单核验
    manifest_path = REPO_ROOT / release_data["demo"]["case_manifest"]
    assert manifest_path.is_file(), f"引用的案例清单缺失: {manifest_path}"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    actual_manifest_sha = _canonical_json_sha256(manifest_data)
    expected_manifest_sha = release_data["demo"]["manifest_sha256"]
    assert actual_manifest_sha == expected_manifest_sha, "Manifest 哈希与 release 快照不符"
    assert len(manifest_data.get("cases", [])) == 15, "演示案例数应为 15 案"

    # 评估指针核验
    eval_pointer_path = REPO_ROOT / release_data["evaluation"]["pointer"]
    assert eval_pointer_path.is_file(), f"引用的评估指针缺失: {eval_pointer_path}"
    eval_data = json.loads(eval_pointer_path.read_text(encoding="utf-8"))
    assert eval_data["evaluation_id"] == "EVAL-20260828-RELEASE-CANDIDATE-V1"


def test_current_evaluation_model_consistency() -> None:
    """当前评估记录必须绑定当前目标模型 deepseek-v4-flash，旧模型不得作为当前活跃口径。"""
    eval_data = json.loads(EVALUATION_JSON.read_text(encoding="utf-8"))

    assert eval_data["model_id"] == "deepseek-v4-flash"
    assert eval_data["status"] == "pending_human_scoring_and_fresh_model_runs"
    assert eval_data["human_scoring_status"] == "pending"
    assert eval_data["raw_records_status"] == "initialized_no_model_runs"

    # 检查 dashboard 路径与原始记录路径
    dashboard_path = REPO_ROOT / eval_data["dashboard_path"]
    raw_records_path = REPO_ROOT / eval_data["raw_records_path"]
    assert dashboard_path.is_file(), "当前 dashboard 文件不存在"
    assert raw_records_path.is_file(), "当前 raw_records 文件不存在"

    # 校验 dashboard sha256
    dashboard_bytes = dashboard_path.read_bytes()
    assert hashlib.sha256(dashboard_bytes).hexdigest() == eval_data["dashboard_sha256"]


def test_rule_change_invalidates_signoff_to_stale() -> None:
    """规则变更后，未重新批准的签字必须判定为 stale_requires_reapproval。"""
    current_signoff = load_signoff_status()
    assert current_signoff["signoff_status"] == SIGNOFF_STALE_STATUS
    assert "重新确认" in current_signoff["reason"]


def test_b3_evaluation_cannot_be_faked_by_boolean_flag() -> None:
    """有效 B3 不能仅凭 model_success=true，必须具有真实调用、三角色闭环和事实语言闸门。"""
    status_data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    b3_record = status_data.get("controlled_evaluation", {}).get("B3", {})

    # 历史 RUN-V7-00ED00962F34 经事实闸门复核失败，必须明确记为 failed
    assert b3_record.get("execution_status") == "failed_posthoc_deterministic_fact_guard"
    assert b3_record.get("formal_comparison_eligible") is False
    assert b3_record.get("human_score") is None

    # 判据来自生产模块，不在测试内自定义，避免测试自证
    fake_b3 = {"run_id": "MOCK-001", "model_success": True, "completed_roles": 1, "provider_calls": 0}
    valid, reason = evaluate_b3_eligibility(fake_b3)
    assert not valid
    assert "缺少有效真实 run_id" in reason

    # 历史失败 run 即使字段齐备也必须被生产判据拒绝
    hist_b3 = dict(_valid_b3_evidence(run_id="RUN-V7-00ED00962F34"))
    valid, reason = evaluate_b3_eligibility(hist_b3)
    assert not valid
    assert "已被事后事实闸门复核否定" in reason

    # 事后事实闸门有错误时同样拒绝
    posthoc = _valid_b3_evidence(posthoc_validation_error="模型把未达到的R1强阈值写成已达到")
    valid, reason = evaluate_b3_eligibility(posthoc)
    assert not valid
    assert "未通过事后事实闸门" in reason


def test_b3_requires_all_six_bindings() -> None:
    """计划要求绑定六项：环境、模型、commit、调用数、结果哈希缺一即不合格。"""
    assert evaluate_b3_eligibility(_valid_b3_evidence())[0] is True

    for field, broken in [
        ("环境", {"environment": "local_debug"}),
        ("模型", {"model_id": ""}),
        ("commit", {"source_commit": "be0a8d4"}),
        ("调用数", {"provider_calls": 2}),
        ("结果哈希", {"result_sha256": ""}),
        ("角色闭环", {"completed_roles": 2}),
        ("真人评分", {"human_scores_completed": False}),
    ]:
        valid, reason = evaluate_b3_eligibility(_valid_b3_evidence(**broken))
        assert valid is False, f"{field} 绑定缺失却判为合格"
        assert reason and reason != VALID


def test_release_ready_stays_false_without_human_approval() -> None:
    """技术条件全部满足时，缺真人最终批准仍必须不合格；显式批准才可能为真。"""
    commit = "f" * 40
    manifest = "e" * 64
    release_data = {
        "release_status": "release_candidate",
        "model": {"model_id": "deepseek-v4-flash"},
        "demo": {"materialized_source_head": commit, "manifest_sha256": manifest, "case_count": 15},
        "evaluation": {"evaluation_id": "EVAL-X", "human_scoring_status": "completed"},
    }
    evaluation_data = {
        "evaluation_id": "EVAL-X",
        "pointer_status": "valid",
        "model_id": "deepseek-v4-flash",
        "raw_records_status": "completed",
        "human_scoring_status": "completed",
    }
    b3 = _valid_b3_evidence(
        source_commit=commit,
        deployment_commit=commit,
        manifest_sha256=manifest,
    )
    kwargs = {
        "git_head": commit,
        "worktree_dirty": False,
        "human_final_approval": False,
        "deployment_commit": commit,
        "release_evidence_head": commit,
        "manifest_sha256": manifest,
        "expected_model_id": "deepseek-v4-flash",
        "signoff_status": SIGNOFF_APPROVED,
        "b3_evidence": b3,
    }

    valid, reason = evaluate_release_ready(release_data, evaluation_data, **kwargs)
    assert valid is False and "缺少真人最终发布批准" in reason

    dirty = evaluate_release_ready(release_data, evaluation_data, **{**kwargs, "worktree_dirty": True})
    assert dirty[0] is False and "未提交" in dirty[1]

    drifted_head = evaluate_release_ready(release_data, evaluation_data, **{**kwargs, "git_head": "a" * 40})
    assert drifted_head[0] is False and "materialized_source_head" in drifted_head[1]

    split_pointer = evaluate_release_ready(release_data, {**evaluation_data, "evaluation_id": "EVAL-OTHER"}, **kwargs)
    assert split_pointer[0] is False and "evaluation_id" in split_pointer[1]

    approved = evaluate_release_ready(
        release_data, evaluation_data, **{**kwargs, "human_final_approval": True}
    )
    assert approved == (True, VALID)


def test_release_ready_rejects_boolean_without_verified_b3_evidence() -> None:
    """旧的 fresh_production_b3_completed 布尔值不能代替真实 B3 证据。"""
    commit = "f" * 40
    manifest = "e" * 64
    release_data = {
        "release_status": "release_candidate",
        "model": {"model_id": "deepseek-v4-flash"},
        "demo": {"materialized_source_head": commit, "manifest_sha256": manifest, "case_count": 15},
        "evaluation": {"evaluation_id": "EVAL-X", "human_scoring_status": "completed"},
        "release_readiness": {"fresh_production_b3_completed": True},
    }
    evaluation_data = {
        "evaluation_id": "EVAL-X",
        "pointer_status": "valid",
        "model_id": "deepseek-v4-flash",
        "raw_records_status": "completed",
        "human_scoring_status": "completed",
    }
    valid, reason = evaluate_release_ready(
        release_data,
        evaluation_data,
        git_head=commit,
        worktree_dirty=False,
        human_final_approval=True,
        deployment_commit=commit,
        release_evidence_head=commit,
        manifest_sha256=manifest,
        expected_model_id="deepseek-v4-flash",
        signoff_status=SIGNOFF_APPROVED,
        b3_evidence=None,
    )
    assert valid is False
    assert "新鲜生产 B3 不合格" in reason


def test_missing_human_approval_strictly_keeps_release_false() -> None:
    """缺少真人最终审批时，即使技术条件具备，发布状态仍必须保持为 false。"""
    release_data = json.loads(RELEASE_JSON.read_text(encoding="utf-8"))
    eval_data = json.loads(EVALUATION_JSON.read_text(encoding="utf-8"))

    # 人工评分与最终批准未完成
    assert release_data["evaluation"]["human_scoring_status"] == "pending"
    assert eval_data["human_scoring_status"] == "pending"

    # 发布就绪状态必须绝对为 false
    assert release_data["release_readiness"]["competition_release_ready"] is False
