"""A02/A03 返工的负向契约：评分台账必须整行重算，绑定必须真正绑定到文件与运行。

对应 2026-09-08 独立验收报告：

- A02 评分读取器只核对签名哈希的格式，从不重算行内容，也没有按冻结评分标准检查
  必填维度、合法区间和有限数值；
- A03 外置绑定允许空文件表与空运行表，也允许把调用方传入的“预期版本”写成运行事实。

本文件里的人名、分数与评分标准一律是合成测试夹具，不代表任何真实评分者，也不写入
真实人工台账；发布锚点只在临时目录生成。
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from backend.app.provider_calls import derive_provider_call_ids
from backend.app.release_evidence import (
    BINDING_SCHEMA_VERSION,
    BINDING_VERIFIED,
    REQUIRED_REPO_FILES,
    WORKSPACE_ROOT,
    build_b3_evidence_from_disk,
    build_release_binding,
    canonical_sha256,
    compute_approval_signature,
    human_score_row_digest,
    load_human_score_record_ids,
    verify_release_binding,
)
from backend.app.schemas import AgentOutput, AgentStep, ModelCheck, RuleResult, RunResponse

RUN_ID = "RUN-TEST-HARDEN-0001"
OTHER_RUN_ID = "RUN-TEST-HARDEN-0002"
COMMIT = "a" * 40
DEPLOY_COMMIT = "d" * 40
MANIFEST_HASH = "b" * 64
DIMENSIONS = ["相关性", "依据充分性", "可执行性"]
RUBRIC_VERSION = "TEST-RUBRIC-V1"
LEDGER_NAME = "scores.jsonl"
RUBRIC_RELATIVE = "backend/release_records/human_scores/rubrics"


# ---------------------------------------------------------------- 运行原件夹具


def _output(role: str, run_id: str) -> AgentOutput:
    """一条只引用本次编号、不含强阈值与因果断言的合规输出。"""

    return AgentOutput(
        schema_version="agent_output_v2",
        run_id=run_id,
        role=role,  # type: ignore[arg-type]
        rule_id="R1",  # type: ignore[arg-type]
        status="candidate",
        analysis_conclusion="risk_candidate",
        claims=[{"text": "程序计算的增速差与应收变动有本次字段证据支持，构成待核查候选。", "evidence_ids": ["PROC-R1-2025", "EV-REV-2025"], "support_status": "supported"}],
        normal_explanations=[{"text": "待验证假设：信用政策变化可能解释该变化，需向管理层确认。", "evidence_ids": ["EV-REV-2025"], "support_status": "unverified_hypothesis"}],
        reason_for_status="证据仅支持形成待核查事项，不足以判断企业已发生错报。",
        data_gaps=["缺少账龄明细"],
        requested_materials=["应收账款账龄表"],
    )


def _step(role: str, run_id: str) -> AgentStep:
    """一个角色一次真实调用，带可重算的输入/响应哈希。"""

    input_hash = hashlib.sha256(f"harden-input-{role}".encode()).hexdigest()
    response_hash = hashlib.sha256(f"harden-response-{role}".encode()).hexdigest()
    return AgentStep(
        role=role,  # type: ignore[arg-type]
        status="completed",
        detail="已完成结构化输出并通过校验。",
        model_id="deepseek-v4-flash",
        prompt_version="agent_prompt_v3",
        input_sha256=input_hash,
        response_sha256=response_hash,
        duration_ms=1000,
        input_tokens=1000,
        output_tokens=200,
        provider_call_performed=True,
        provider_call_count=1,
        model_attempt_history=[{"attempt": 1, "input_sha256": input_hash, "response_sha256": response_hash, "validation_passed": True}],
        output=_output(role, run_id),
    )


def _run(run_id: str = RUN_ID, *, with_versions: bool = False) -> RunResponse:
    """构造一份除版本字段外尽量完整的运行原件。"""

    steps = [_step(role, run_id) for role in ("challenge", "counter", "review")]
    context: dict[str, Any] = {"environment": "production", "provider": "deepseek_direct"}
    if with_versions:
        context.update({"source_commit": COMMIT, "deployment_commit": DEPLOY_COMMIT, "manifest_sha256": MANIFEST_HASH})
    return RunResponse(
        run_id=run_id,
        status="candidate",
        context=context,
        source_validation={"status": "passed"},
        sources=[],
        rule_results=[
            RuleResult(
                rule_id="R1",  # type: ignore[arg-type]
                status="candidate",
                source_validation={"status": "passed"},
                metrics={"revenue_growth": 10.0, "receivable_growth": 25.0, "growth_gap": 15.0},
                risk_card={"rule_id": "R1", "threshold_pct": 15.0},
                evidence_ids=["PROC-R1-2025", "EV-REV-2025"],
            )
        ],
        model_check=ModelCheck(status="model_success", model_id="deepseek-v4-flash", detail="三角色完成", provider_call_count=3, execution_mode="external_live"),
        run_completeness="complete_full_analysis",
        execution_mode="external_live",
        model_id="deepseek-v4-flash",
        prompt_version="agent_prompt_v3",
        provider_call_count=3,
        provider_call_ids=derive_provider_call_ids(steps, run_id),
        cache_hit=False,
        agent_steps=steps,
    )


def _write_run(workspace: Path, run: RunResponse) -> Path:
    """把运行原件写到 <workspace>/backend/runtime/runs/<run_id>.json。"""

    target = workspace / "backend" / "runtime" / "runs" / f"{run.run_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"run": run.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
    return target


# ---------------------------------------------------------------- 评分夹具


def _write_rubric(workspace: Path, *, status: str = "frozen", rubric_version: str = RUBRIC_VERSION, **overrides: Any) -> Path:
    """在临时工作区放一份测试用评分标准，模拟“已由真人冻结”。"""

    rubric_dir = workspace / RUBRIC_RELATIVE
    rubric_dir.mkdir(parents=True, exist_ok=True)
    spec: dict[str, Any] = {
        "schema_version": "human_score_rubric_v1",
        "rubric_version": rubric_version,
        "required_dimensions": DIMENSIONS,
        "score_min": 1,
        "score_max": 5,
        "status": status,
        "frozen_by": "测试夹具甲",
        "frozen_at": "2026-09-08T10:00:00+08:00",
    }
    spec.update(overrides)
    (rubric_dir / f"{rubric_version}.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return rubric_dir


def _row(record_id: str, scorer: str, *, scores: Any = None, rubric_version: str = RUBRIC_VERSION, run_id: str = RUN_ID) -> dict[str, Any]:
    """按写入端同一摘要规范签好一行评分，供测试逐项破坏。"""

    row: dict[str, Any] = {
        "schema_version": "human_score_record_v1",
        "record_id": record_id,
        "run_id": run_id,
        "scorer": scorer,
        "rubric_version": rubric_version,
        "scores": {"相关性": 4, "依据充分性": 3, "可执行性": 4} if scores is None else scores,
        "note": "合成夹具，非真人评分。",
        "scored_at": "2026-09-08T11:00:00+08:00",
        "signed_payload_sha256": "",
    }
    row["signed_payload_sha256"] = human_score_row_digest(row)
    return row


def _read(tmp_path: Path, rows: list[dict[str, Any]], rubric_dir: Path | None = None) -> tuple[list[str], str | None]:
    ledger = tmp_path / LEDGER_NAME
    ledger.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    return load_human_score_record_ids(ledger, RUN_ID, rubric_dir=rubric_dir or tmp_path / "no-rubrics")


# ---------------------------------------------------------------- A02 评分重算


def test_digest_uses_writer_empty_digest_convention() -> None:
    """写入端约定是“摘要位先置空再规范哈希”，读取端必须用同一规范重算。"""

    row = _row("SCORE-1", "测试夹具甲")
    assert row["signed_payload_sha256"] == human_score_row_digest({**row, "signed_payload_sha256": ""})


def test_valid_fixture_rows_are_accepted(tmp_path: Path) -> None:
    """夹具本身必须先是合法的，否则后面的反例不成立。"""

    rubric_dir = _write_rubric(tmp_path)
    ids, error = _read(tmp_path, [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")], rubric_dir)
    assert error is None, error
    assert ids == ["SCORE-1", "SCORE-2"]


def test_tampered_score_with_old_digest_is_rejected(tmp_path: Path) -> None:
    """A02 主案：改分不改摘要，读取端必须发现而不是继续接受。"""

    rubric_dir = _write_rubric(tmp_path)
    rows = [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")]
    rows[0]["scores"]["相关性"] = 999
    ids, error = _read(tmp_path, rows, rubric_dir)
    assert ids == []
    assert error and "摘要" in error


@pytest.mark.parametrize(
    "overrides",
    [
        {"scores": {"相关性": 4, "依据充分性": 3}},
        {"scores": {"相关性": 4, "依据充分性": 3, "可执行性": 4, "额外": 4}},
        {"scores": {"相关性": 0, "依据充分性": 3, "可执行性": 4}},
        {"scores": {"相关性": 6, "依据充分性": 3, "可执行性": 4}},
        {"scores": {"相关性": float("nan"), "依据充分性": 3, "可执行性": 4}},
        {"scores": {"相关性": float("inf"), "依据充分性": 3, "可执行性": 4}},
        {"scores": {"相关性": True, "依据充分性": 3, "可执行性": 4}},
        {"scores": {"相关性": "4", "依据充分性": 3, "可执行性": 4}},
        {"rubric_version": "NOT-FROZEN-RUBRIC"},
        {"rubric_version": ""},
    ],
    ids=["缺必填维度", "多出不评维度", "低于下限", "越上界", "NaN", "Infinity", "布尔分数", "字符串分数", "未冻结标准版本", "缺标准版本"],
)
def test_score_row_rejections(tmp_path: Path, overrides: dict[str, Any]) -> None:
    """行自身摘要必须先是自洽的，拒绝只能来自冻结标准的维度、区间与有限性规则。

    如果先签名再改内容，摘要检查会先挡下来，这条用例就变成对摘要检查的重复测试，
    规则本身反而没有覆盖——那正是 A02 被漏掉的原因。
    """

    rubric_dir = _write_rubric(tmp_path)
    bad = _row("SCORE-1", "测试夹具甲", **overrides)
    ledger_rows = [bad, _row("SCORE-2", "测试夹具乙")]
    ledger = tmp_path / LEDGER_NAME
    ledger.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in ledger_rows) + "\n", encoding="utf-8")
    # 先确认坏行是自洽的：摘要检查不能成为拒绝理由。
    assert human_score_row_digest(bad) == bad["signed_payload_sha256"]
    ids, error = load_human_score_record_ids(ledger, RUN_ID, rubric_dir=rubric_dir)
    assert ids == []
    assert error and "摘要" not in error, f"拒绝原因应来自评分规则而不是摘要：{error}"


def test_score_rows_cannot_be_reused_for_another_run(tmp_path: Path) -> None:
    """两名真人对运行 A 的评分，不能当成运行 B 的人工评分。"""

    rubric_dir = _write_rubric(tmp_path)
    ledger = tmp_path / LEDGER_NAME
    ledger.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")]) + "\n",
        encoding="utf-8",
    )
    assert load_human_score_record_ids(ledger, RUN_ID, rubric_dir=rubric_dir)[0] == ["SCORE-1", "SCORE-2"]
    ids, error = load_human_score_record_ids(ledger, "RUN-TEST-OTHER-0001", rubric_dir=rubric_dir)
    assert ids == [] and error


def test_non_finite_values_survive_json_parsing() -> None:
    """NaN 与 Infinity 会被 json 解析成浮点数，因此必须用有限性判断挡下。"""

    assert math.isnan(json.loads('{"v": NaN}')['v'])
    assert math.isinf(json.loads('{"v": Infinity}')['v'])


def test_missing_rubric_directory_blocks_human_scores(tmp_path: Path) -> None:
    """没有任何真人冻结标准时，即使两行摘要自洽也不得判人工评分完成。"""

    ids, error = _read(tmp_path, [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")])
    assert ids == [] and error and "评分标准" in error


def test_unfrozen_rubric_file_is_not_accepted(tmp_path: Path) -> None:
    """标准文件存在但状态不是已冻结时同样失败关闭。"""

    rubric_dir = _write_rubric(tmp_path, status="draft")
    ids, error = _read(tmp_path, [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")], rubric_dir)
    assert ids == [] and error


def test_rubric_version_path_cannot_escape(tmp_path: Path) -> None:
    """评分标准版本参与文件名拼接，必须先过格式校验。"""

    _write_rubric(tmp_path)
    escaping = tmp_path / ".." / ".." / "evil.json"
    row = _row("SCORE-1", "测试夹具甲", rubric_version="../../evil")
    ids, error = _read(tmp_path, [row, _row("SCORE-2", "测试夹具乙")])
    assert ids == [] and error
    assert not escaping.exists()


def test_evidence_reader_discovers_rubric_directory(tmp_path: Path) -> None:
    """B3 证据读取器必须把评分标准目录一并接上，而不是只接台账。"""

    _write_run(tmp_path, _run())
    _write_rubric(tmp_path)
    ledger = tmp_path / LEDGER_NAME
    ledger.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in [_row("SCORE-1", "测试夹具甲"), _row("SCORE-2", "测试夹具乙")]) + "\n",
        encoding="utf-8",
    )
    loaded = build_b3_evidence_from_disk(RUN_ID, workspace_root=tmp_path, human_score_ledger_path=ledger)
    assert loaded["status"] == "loaded", loaded.get("reason")
    assert loaded["evidence"]["human_scores_completed"] is True, "同一工作区下的冻结标准应被自动发现"
    stripped = build_b3_evidence_from_disk(
        RUN_ID, workspace_root=tmp_path, human_score_ledger_path=ledger, human_rubric_dir=tmp_path / "empty-dir"
    )
    assert stripped["evidence"]["human_scores_completed"] is False
    assert "评分标准" in stripped["reason"]


# ------------------------------------------------- A03 版本期望不得补作运行事实


def test_expected_versions_are_not_recorded_as_run_facts(tmp_path: Path) -> None:
    """运行原件没登记版本时，调用方期望值不能补写成运行事实。"""

    _write_run(tmp_path, _run())
    result = build_b3_evidence_from_disk(
        RUN_ID,
        workspace_root=tmp_path,
        expected_source_commit=COMMIT,
        expected_deployment_commit=DEPLOY_COMMIT,
        expected_manifest_sha256=MANIFEST_HASH,
    )
    assert result["status"] == "blocked"
    assert "版本" in result["reason"]


def test_versions_come_from_the_original_record(tmp_path: Path) -> None:
    """原件确实登记了版本时，证据取原件值并与期望比对通过。"""

    _write_run(tmp_path, _run(with_versions=True))
    result = build_b3_evidence_from_disk(
        RUN_ID,
        workspace_root=tmp_path,
        expected_source_commit=COMMIT,
        expected_deployment_commit=DEPLOY_COMMIT,
        expected_manifest_sha256=MANIFEST_HASH,
    )
    assert result["status"] == "loaded", result.get("reason")
    evidence = result["evidence"]
    assert evidence["source_commit"] == COMMIT
    assert evidence["deployment_commit"] == DEPLOY_COMMIT
    assert evidence["manifest_sha256"] == MANIFEST_HASH.lower()
    assert evidence["manifest_hash_verified"] is True


def test_stale_run_with_new_commit_is_rejected(tmp_path: Path) -> None:
    """旧运行配新提交：原件登记的是旧 commit，期望值不同时必须阻断。"""

    _write_run(tmp_path, _run(with_versions=True))
    result = build_b3_evidence_from_disk(RUN_ID, workspace_root=tmp_path, expected_source_commit="e" * 40)
    assert result["status"] == "blocked"
    assert "commit" in result["reason"]


def test_manifest_hash_verified_is_false_without_original_evidence(tmp_path: Path) -> None:
    """不传期望值时读取器仍可给出证据，但必须如实标成未核验而不是 true。"""

    _write_run(tmp_path, _run())
    result = build_b3_evidence_from_disk(RUN_ID, workspace_root=tmp_path)
    assert result["status"] == "loaded"
    assert result["evidence"]["manifest_hash_verified"] is False
    assert result["evidence"]["source_commit"] == ""


# ---------------------------------------------------------------- A03 绑定收紧


def _repo_with_required_files(workspace: Path) -> Path:
    """按必需清单铺一个临时工作区，返回锚点路径（锚点必须落在树外）。"""

    for relative in REQUIRED_REPO_FILES:
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"placeholder": "测试夹具"}, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_run(workspace, _run())
    return workspace.parent / "outside-bindings" / "binding.json"


def _build(workspace: Path, anchor: Path, *, ledger: Path | None = None, sign: bool = True) -> Path:
    """生成锚点并可由“测试夹具”补上批准摘要；仅测试，不代替真人签字。"""

    build_release_binding(
        workspace_root=workspace,
        release_id="TEST-ONLY",
        git_head=COMMIT,
        tracked_files=list(REQUIRED_REPO_FILES),
        run_ids=[RUN_ID],
        binding_path=anchor,
        approver="测试夹具甲" if sign else "",
        approved_at="2026-09-08T12:00:00+08:00" if sign else "",
        human_score_ledger_path=ledger,
    )
    if sign:
        payload = json.loads(anchor.read_text(encoding="utf-8"))
        approval = payload["human_approval"]
        approval["signature_sha256"] = compute_approval_signature(
            approval["content_sha256"], approver=approval["approver"], approved_at=approval["approved_at"]
        )
        anchor.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return anchor


def test_binding_rejects_empty_file_and_run_tables(tmp_path: Path) -> None:
    """A03 主案：空清单没有待检项，不能作为发布绑定。"""

    workspace = tmp_path / "repo"
    workspace.mkdir()
    with pytest.raises(ValueError, match="不能为空"):
        build_release_binding(
            workspace_root=workspace,
            release_id="TEST-ONLY",
            git_head=COMMIT,
            tracked_files=[],
            run_ids=[],
            binding_path=tmp_path / "empty.json",
        )


def test_binding_requires_the_mandatory_release_files(tmp_path: Path) -> None:
    """只绑一个文件不构成发布绑定：必需清单缺项必须拒绝生成。"""

    workspace = tmp_path / "repo"
    (workspace / "release_record.json").parent.mkdir(parents=True, exist_ok=True)
    (workspace / "release_record.json").write_text('{"release_id": "R-1"}', encoding="utf-8")
    _write_run(workspace, _run())
    with pytest.raises(ValueError, match="必需文件"):
        build_release_binding(
            workspace_root=workspace,
            release_id="TEST-ONLY",
            git_head=COMMIT,
            tracked_files=["release_record.json"],
            run_ids=[RUN_ID],
            binding_path=tmp_path / "partial.json",
        )


def test_hand_crafted_empty_binding_is_blocked(tmp_path: Path) -> None:
    """手写一份结构合法但内容清空的锚点，校验端必须挡住而不是循环空转。"""

    workspace = tmp_path / "repo"
    workspace.mkdir()
    anchor = tmp_path / "hand-crafted.json"
    payload = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "release_id": "TEST-ONLY",
        "git_head": COMMIT,
        "repo_files": {},
        "run_records": {},
        "human_score_ledger": {},
        "human_approval": {"approver": "", "approved_at": "", "content_sha256": "", "signature_sha256": ""},
    }
    payload["human_approval"]["content_sha256"] = canonical_sha256(payload)
    anchor.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = verify_release_binding(anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False)
    assert report["status"] == "blocked"
    assert report["reason"]


def _sha(path: Path) -> str:
    """测试内使用的文件哈希，便于手写锚点与重算结果对上。"""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_v2_anchor_with_empty_declared_required_is_still_blocked(tmp_path: Path) -> None:
    """锚点自己声明“无必需文件”不能成为绕过必需清单的口子。"""

    workspace = tmp_path / "repo"
    arbitrary = workspace / "anything.json"
    arbitrary.parent.mkdir(parents=True, exist_ok=True)
    arbitrary.write_text('{"x": 1}', encoding="utf-8")
    _write_run(workspace, _run())
    anchor = tmp_path / "selfwaived.json"
    payload = {
        "schema_version": BINDING_SCHEMA_VERSION,
        "release_id": "TEST-ONLY",
        "git_head": COMMIT,
        "required_repo_files": [],
        "repo_files": {"anything.json": _sha(arbitrary)},
        "run_records": {},
        "human_score_ledger": {},
        "human_approval": {"approver": "", "approved_at": "", "content_sha256": "", "signature_sha256": ""},
    }
    payload["human_approval"]["content_sha256"] = canonical_sha256(payload)
    anchor.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = verify_release_binding(anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False)
    assert report["status"] == "blocked"
    assert "必需文件" in report["reason"] or "运行清单为空" in report["reason"]


def test_binding_must_cover_the_run_the_gate_selects(tmp_path: Path) -> None:
    """锚点绑运行 A、门禁选用运行 B 时必须阻断。"""

    workspace = tmp_path / "repo"
    anchor = _repo_with_required_files(workspace)
    _build(workspace, anchor)
    assert verify_release_binding(
        anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False, expected_run_ids=[RUN_ID]
    )["status"] == BINDING_VERIFIED
    _write_run(workspace, _run(run_id=OTHER_RUN_ID))
    mismatched = verify_release_binding(
        anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False, expected_run_ids=[OTHER_RUN_ID]
    )
    assert mismatched["status"] == "blocked"
    assert "运行" in mismatched["reason"]


def test_binding_tracks_human_ledger_edits(tmp_path: Path) -> None:
    """锚点生成后再改人工台账，必须报漂移而不是继续放行。"""

    workspace = tmp_path / "repo"
    anchor = _repo_with_required_files(workspace)
    ledger = workspace / LEDGER_NAME
    ledger.write_text(json.dumps(_row("SCORE-1", "测试夹具甲"), ensure_ascii=False) + "\n", encoding="utf-8")
    _build(workspace, anchor, ledger=ledger)
    assert verify_release_binding(
        anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False, expected_run_ids=[RUN_ID]
    )["status"] == BINDING_VERIFIED
    ledger.write_text(ledger.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    after = verify_release_binding(
        anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False, expected_run_ids=[RUN_ID]
    )
    assert after["status"] == "blocked"
    assert "台账" in after["reason"]


def test_v1_anchor_is_no_longer_supported(tmp_path: Path) -> None:
    """旧版锚点缺少必需清单与交叉绑定，新校验必须拒绝而不是继续放行。"""

    workspace = tmp_path / "repo"
    workspace.mkdir()
    anchor = tmp_path / "v1.json"
    payload = {
        "schema_version": "audittrace_release_binding_v1",
        "release_id": "RELEASE-CANDIDATE-20260828-V1",
        "git_head": COMMIT,
        "repo_files": {},
        "run_records": {},
        "human_approval": {"approver": "", "approved_at": "", "content_sha256": "", "signature_sha256": ""},
    }
    payload["human_approval"]["content_sha256"] = canonical_sha256(payload)
    anchor.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = verify_release_binding(anchor, workspace_root=workspace, git_head=COMMIT, worktree_dirty=False)
    assert report["status"] == "blocked"
    assert "版本" in report["reason"]


def test_any_v1_anchor_on_disk_is_rejected() -> None:
    """规则性检查：本机若还留着 v1 锚点，收紧后的校验必须拒绝而不是放行。"""

    anchor_dir = WORKSPACE_ROOT.parent / "audittrace-release-bindings"
    checked = 0
    for path in sorted(anchor_dir.glob("*.json")) if anchor_dir.is_dir() else []:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "audittrace_release_binding_v1":
            continue
        checked += 1
        report = verify_release_binding(path, workspace_root=WORKSPACE_ROOT)
        assert report["status"] == "blocked", path.name
    assert checked <= 3, "本机锚点数量异常，先人工确认再改测试"
