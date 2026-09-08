"""独立发布证据重算与外置版本绑定的反向契约测试。

覆盖整改项 F02、F03 要求的“篡改拒绝矩阵”：

1. 读取器必须从磁盘原件重算文件哈希、调用 ID 和事实闸门结论；
2. 记录里的自报字段（verified、true、完成数）不能代替重算结果；
3. 缺角色、缺尝试哈希、缓存回放、备用子运行、调用数不一致都要阻断；
4. 人工评分只能来自独立台账，且至少两名真人、分数非空、带签名哈希；
5. 外置绑定必须位于工作区之外，内容被改、指向文件漂移、HEAD 漂移、
   工作区脏或未获真人批准时都不得判定为 verified；
6. 发布门禁在没有 verified 绑定时必须保持 false。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from backend.app.release_evidence import (
    AUTOMATED_IDENTITIES,
    BINDING_PENDING_APPROVAL,
    BINDING_VERIFIED,
    build_b3_evidence_from_disk,
    build_release_binding,
    compute_approval_signature,
    human_score_row_digest,
    verify_release_binding,
)
from backend.app.release_gate import SIGNOFF_APPROVED, VALID, evaluate_release_ready
from backend.app.schemas import AgentOutput, AgentStep, ModelCheck, RuleResult, RunResponse

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "RUN-TEST-EVIDENCE-0001"
COMMIT = "a" * 40
MANIFEST_HASH = "b" * 64


def _output(role: str, run_id: str) -> AgentOutput:
    """构造一条只引用本次证据编号、不含强阈值与因果断言的合规输出。"""

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


def _step(role: str, run_id: str, *, offset: int = 1) -> AgentStep:
    """一个角色一次真实调用；哈希按角色派生，便于重算校验。"""

    input_hash = hashlib.sha256(f"input-{role}-{offset}".encode()).hexdigest()
    response_hash = hashlib.sha256(f"response-{role}-{offset}".encode()).hexdigest()
    return AgentStep(
        role=role,  # type: ignore[arg-type]
        status="completed",
        detail="已完成结构化输出并通过校验。",
        model_id="deepseek-v4-flash",
        prompt_version="agent_prompt_v3",
        input_sha256=input_hash,
        response_sha256=response_hash,
        duration_ms=1200,
        input_tokens=1000,
        output_tokens=200,
        provider_call_performed=True,
        provider_call_count=1,
        model_attempt_history=[
            {
                "attempt": offset,
                "input_sha256": input_hash,
                "response_sha256": response_hash,
                "validation_passed": True,
            }
        ],
        output=_output(role, run_id),
    )


def _run(run_id: str = RUN_ID, *, roles: tuple[str, ...] = ("challenge", "counter", "review"), **overrides: Any) -> RunResponse:
    """默认构造一份“看起来完整”的运行记录；测试用 overrides 逐项破坏它。"""

    steps = [_step(role, run_id) for role in roles]
    from backend.app.provider_calls import derive_provider_call_ids

    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": "candidate",
        "context": {"environment": "production", "provider": "deepseek_direct"},
        "source_validation": {"status": "passed"},
        "sources": [],
        "rule_results": [
            RuleResult(
                rule_id="R1",  # type: ignore[arg-type]
                status="candidate",
                source_validation={"status": "passed"},
                metrics={"revenue_growth": 10.0, "receivable_growth": 25.0, "growth_gap": 15.0},
                risk_card={"rule_id": "R1", "threshold_pct": 15.0},
                evidence_ids=["PROC-R1-2025", "EV-REV-2025"],
            )
        ],
        "model_check": ModelCheck(status="model_success", model_id="deepseek-v4-flash", detail="三角色完成", provider_call_count=3, execution_mode="external_live"),
        "run_completeness": "complete_full_analysis",
        "execution_mode": "external_live",
        "model_id": "deepseek-v4-flash",
        "prompt_version": "agent_prompt_v3",
        "provider_call_count": 3,
        "provider_call_ids": derive_provider_call_ids(steps, run_id),
        "cache_hit": False,
        "agent_steps": steps,
    }
    payload.update(overrides)
    return RunResponse(**payload)


def _write_run(workspace: Path, run: RunResponse) -> Path:
    """把运行原件写到 <workspace>/backend/runtime/runs/<run_id>.json。"""

    target = workspace / "backend" / "runtime" / "runs" / f"{run.run_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"run": run.model_dump(mode="json")}, ensure_ascii=False), encoding="utf-8")
    return target


def _evidence(workspace: Path, run_id: str = RUN_ID, **kwargs: Any) -> dict[str, Any]:
    return build_b3_evidence_from_disk(run_id, workspace_root=workspace, **kwargs)


def test_reader_recomputes_hash_and_call_ids(tmp_path: Path) -> None:
    """正常记录应重算出与原件一致的哈希、调用 ID 和事实闸门结论。"""

    run = _run()
    path = _write_run(tmp_path, run)
    result = _evidence(tmp_path, expected_model_id="deepseek-v4-flash")
    assert result["status"] == "loaded"
    evidence = result["evidence"]
    assert evidence["result_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert evidence["provider_call_ids"] == run.provider_call_ids
    assert evidence["provider_calls"] == 3
    assert evidence["posthoc_validation_status"] == "passed"
    # 人工评分没有独立台账时必须为 False，不能因为记录完整就推导为已完成。
    assert evidence["human_scores_completed"] is False


def test_reader_rejects_missing_and_duplicate_records(tmp_path: Path) -> None:
    """找不到原件或同一编号有多份原件时不得猜测证据。"""

    assert _evidence(tmp_path)["status"] == "blocked"
    _write_run(tmp_path, _run())
    duplicate = tmp_path / "backend" / "runtime" / "ns-a" / "runs" / f"{RUN_ID}.json"
    duplicate.parent.mkdir(parents=True, exist_ok=True)
    duplicate.write_text((tmp_path / "backend" / "runtime" / "runs" / f"{RUN_ID}.json").read_text(encoding="utf-8"), encoding="utf-8")
    assert "多份原件" in _evidence(tmp_path)["reason"]


@pytest.mark.parametrize("bad_run_id", ["../escape", "RUN-", "not-a-run", "RUN-A"])
def test_reader_rejects_malformed_run_id(tmp_path: Path, bad_run_id: str) -> None:
    """运行编号先过格式校验，避免把外部输入当路径片段拼接。"""

    assert _evidence(tmp_path, bad_run_id)["status"] == "blocked"


@pytest.mark.parametrize(
    "roles",
    [
        ("challenge", "counter"),
        ("challenge", "counter", "counter"),
    ],
    ids=["缺角色", "重复角色"],
)
def test_reader_requires_exact_three_roles(tmp_path: Path, roles: tuple[str, ...]) -> None:
    """角色集合必须正好是 challenge/counter/review；数量凑够也不行。"""

    _write_run(tmp_path, _run(roles=roles))  # type: ignore[arg-type]
    result = _evidence(tmp_path)
    assert result["status"] == "blocked"
    assert "角色集合" in result["reason"]


def test_reader_rejects_skipped_role(tmp_path: Path) -> None:
    """三个角色都在但其中一步被跳过时，不能算完整链。"""

    run = _run()
    run.agent_steps[2].status = "skipped"
    _write_run(tmp_path, run)
    result = _evidence(tmp_path)
    assert result["status"] == "blocked"
    assert "未完成" in result["reason"]


def test_reader_rejects_self_declared_call_ids(tmp_path: Path) -> None:
    """记录里写三个像样的调用 ID，但重算对不上时必须阻断。"""

    run = _run(provider_call_ids=["CALL-" + "1" * 32, "CALL-" + "2" * 32, "CALL-" + "3" * 32])
    _write_run(tmp_path, run)
    result = _evidence(tmp_path)
    assert result["status"] == "blocked"
    assert "调用 ID" in result["reason"]


def test_reader_rejects_attempt_without_response_hash(tmp_path: Path) -> None:
    """某次尝试缺响应哈希时不能重算出调用 ID，也不能沿用记录里的旧 ID。"""

    run = _run()
    run.agent_steps[1].model_attempt_history[0]["response_sha256"] = None
    _write_run(tmp_path, run)
    assert "调用 ID" in _evidence(tmp_path)["reason"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("cache_hit", True),
        ("execution_mode", "cached_replay"),
        ("parent_run_id", "RUN-PARENT-0000000001"),
        ("provider_call_count", 2),
        ("model_id", "other-model"),
    ],
    ids=["缓存回放", "非实时模式", "备用子运行", "调用数不符", "模型不符"],
)
def test_reader_rejects_non_fresh_runs(tmp_path: Path, field: str, value: Any) -> None:
    """缓存、备用、数量不符与模型漂移都不能算新鲜完整链。"""

    overrides: dict[str, Any] = {field: value}
    if field == "provider_call_count":
        overrides["model_check"] = ModelCheck(status="model_success", model_id="deepseek-v4-flash", detail="调用数不一致", provider_call_count=2, execution_mode="external_live")
    _write_run(tmp_path, _run(**overrides))
    assert _evidence(tmp_path, expected_model_id="deepseek-v4-flash")["status"] == "blocked"


def test_reader_reports_fact_language_guard_failure(tmp_path: Path) -> None:
    """落盘输出把外部因果解释写成受字段证据支持时，重算必须复现闸门失败。"""

    run = _run()
    # 闸门规则：normal_explanations 标为 supported 且含外部因果词，但证据 ID 里没有
    # RAG-/SUP- 来源时，属于“用财务字段支持外部因果解释”，必须整步判失败。
    explanation = run.agent_steps[0].output.normal_explanations[0]
    explanation.support_status = "supported"
    explanation.text = "主要因信用政策放宽导致应收账款增长。"
    explanation.evidence_ids = ["EV-REV-2025"]
    _write_run(tmp_path, run)
    result = _evidence(tmp_path)
    assert result["status"] == "loaded"
    assert result["evidence"]["posthoc_validation_status"] == "failed"
    assert "外部因果解释" in str(result["evidence"]["posthoc_validation_error"])


def _ledger(path: Path, rows: list[dict[str, Any]]) -> Path:
    """写一份人工评分台账；每行代表一名真人的独立评分。"""

    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")
    return path


def _write_rubric(workspace: Path) -> Path:
    """在临时工作区放一份测试用评分标准，模拟“已由真人冻结”。"""

    rubric_dir = workspace / "backend" / "release_records" / "human_scores" / "rubrics"
    rubric_dir.mkdir(parents=True, exist_ok=True)
    (rubric_dir / "TEST-RUBRIC-V1.json").write_text(
        json.dumps(
            {
                "schema_version": "human_score_rubric_v1",
                "rubric_version": "TEST-RUBRIC-V1",
                "required_dimensions": ["相关性", "依据", "可执行性"],
                "score_min": 1,
                "score_max": 5,
                "status": "frozen",
                "frozen_by": "测试夹具甲",
                "frozen_at": "2026-09-08T10:00:00+08:00",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return rubric_dir


def _score_row(record_id: str, scorer: str, *, scores: Any = None, signature: str | None = None) -> dict[str, Any]:
    """按写入端同一摘要规范签好一行评分；signature 传入坏值用于制造反例。"""

    row: dict[str, Any] = {
        "schema_version": "human_score_record_v1",
        "record_id": record_id,
        "run_id": RUN_ID,
        "scorer": scorer,
        "rubric_version": "TEST-RUBRIC-V1",
        "scores": {"相关性": 4, "依据": 4, "可执行性": 3} if scores is None else scores,
        "scored_at": "2026-09-08T11:00:00+08:00",
        "signed_payload_sha256": "",
    }
    row["signed_payload_sha256"] = human_score_row_digest(row) if signature is None else signature
    return row


def test_human_scores_require_two_signed_real_scorers(tmp_path: Path) -> None:
    """两名真人、摘要可重算且维度齐全时才算完成，并只从台账推导。"""

    _write_run(tmp_path, _run())
    _write_rubric(tmp_path)
    ledger = _ledger(tmp_path / "scores.jsonl", [_score_row("SCORE-1", "张三"), _score_row("SCORE-2", "李四")])
    result = _evidence(tmp_path, human_score_ledger_path=ledger)
    assert result["evidence"]["human_scores_completed"] is True
    assert result["evidence"]["human_score_record_ids"] == ["SCORE-1", "SCORE-2"]


@pytest.mark.parametrize(
    "rows,label",
    [
        ([_score_row("SCORE-1", "张三")], "只有一名评分者"),
        ([_score_row("SCORE-1", "张三"), _score_row("SCORE-2", "张三")], "同一人重复评分"),
        ([_score_row("SCORE-1", "张三"), _score_row("SCORE-2", "AI")], "自动化身份"),
        ([_score_row("SCORE-1", "张三"), _score_row("SCORE-2", "李四", scores={})], "分数为空"),
        ([_score_row("SCORE-1", "张三"), _score_row("SCORE-2", "李四", signature="")], "缺签名哈希"),
        ([_score_row("SCORE-1", "张三"), _score_row("SCORE-1", "李四")], "记录 ID 重复"),
    ],
    ids=["单人", "同人重复", "AI署名", "空分数", "无签名", "重复ID"],
)
def test_human_score_ledger_rejections(tmp_path: Path, rows: list[dict[str, Any]], label: str) -> None:
    """台账不合格时 human_scores_completed 必须为 False，并给出原因。"""

    _write_run(tmp_path, _run())
    _write_rubric(tmp_path)
    ledger = _ledger(tmp_path / "scores.jsonl", rows)
    result = _evidence(tmp_path, human_score_ledger_path=ledger)
    assert result["evidence"]["human_scores_completed"] is False
    assert result["reason"], label


def _binding_inputs(workspace: Path) -> tuple[Path, Path]:
    """准备一个仓库内文件与一份运行原件，返回（工作区, 外置锚点路径）。"""

    tracked = workspace / "release_record.json"
    tracked.write_text('{"release_id": "R-1"}', encoding="utf-8")
    _write_run(workspace, _run())
    outside = workspace.parent / "outside-bindings" / "binding.json"
    return tracked, outside


def test_binding_must_live_outside_workspace(tmp_path: Path) -> None:
    """锚点放在工作区内等于自证，直接拒绝生成。"""

    tracked, _ = _binding_inputs(tmp_path)
    inside = tmp_path / "binding.json"
    with pytest.raises(ValueError, match="工作区之外"):
        build_release_binding(
            workspace_root=tmp_path,
            release_id="R-1",
            git_head=COMMIT,
            tracked_files=[str(tracked.relative_to(tmp_path))],
            run_ids=[RUN_ID],
            binding_path=inside,
        )


def _make_binding(workspace: Path, *, approver: str = "", approved_at: str = "") -> Path:
    """生成一份最小锚点；本文件的用例只测漂移与篡改，必需清单由收紧用例单独覆盖。"""

    tracked, outside = _binding_inputs(workspace)
    build_release_binding(
        workspace_root=workspace,
        release_id="R-1",
        git_head=COMMIT,
        tracked_files=[str(tracked.relative_to(workspace))],
        run_ids=[RUN_ID],
        binding_path=outside,
        approver=approver,
        approved_at=approved_at,
        required_files=(),
    )
    return outside


def _verify(workspace: Path, outside: Path, *, head: str | None = COMMIT, dirty: bool | None = False) -> dict[str, Any]:
    """本文件统一的绑定复验入口：必需清单置空，只测漂移、HEAD 与批准状态。"""

    return verify_release_binding(
        outside, workspace_root=workspace, git_head=head, worktree_dirty=dirty, required_files=()
    )


def test_binding_stays_pending_until_a_real_person_approves(tmp_path: Path) -> None:
    """未签锚点只能是待签状态；补上真人签名摘要后才算通过。"""

    outside = _make_binding(tmp_path, approver="张三", approved_at="2026-09-08T12:00:00+08:00")
    pending = _verify(tmp_path, outside)
    assert pending["status"] == BINDING_PENDING_APPROVAL
    payload = json.loads(outside.read_text(encoding="utf-8"))
    payload["human_approval"]["signature_sha256"] = compute_approval_signature(
        payload["human_approval"]["content_sha256"], approver="张三", approved_at="2026-09-08T12:00:00+08:00"
    )
    outside.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert _verify(tmp_path, outside)["status"] == BINDING_VERIFIED


def test_binding_rejects_late_edit_of_approver(tmp_path: Path) -> None:
    """锚点生成后再偷偷改批准人，内容自校验必须先失败。"""

    outside = _make_binding(tmp_path, approver="张三", approved_at="2026-09-08T12:00:00+08:00")
    payload = json.loads(outside.read_text(encoding="utf-8"))
    payload["human_approval"]["approver"] = "李四"
    outside.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    report = _verify(tmp_path, outside)
    assert report["status"] == "blocked"
    assert "疑似被改写" in report["reason"]


@pytest.mark.parametrize(
    "tamper",
    ["repo_file", "run_record", "content", "head", "dirty", "missing"],
    ids=["仓库文件漂移", "运行原件漂移", "锚点被改", "HEAD漂移", "工作区脏", "锚点缺失"],
)
def test_binding_rejects_drift_and_tampering(tmp_path: Path, tamper: str) -> None:
    """绑定指向的内容一旦变化，就必须报漂移而不是继续放行。"""

    outside = _make_binding(tmp_path, approver="张三", approved_at="2026-09-08T12:00:00+08:00")
    payload = json.loads(outside.read_text(encoding="utf-8"))
    payload["human_approval"]["signature_sha256"] = compute_approval_signature(
        payload["human_approval"]["content_sha256"], approver="张三", approved_at="2026-09-08T12:00:00+08:00"
    )
    outside.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    dirty = False
    head = COMMIT
    if tamper == "repo_file":
        (tmp_path / "release_record.json").write_text('{"release_id": "TAMPERED"}', encoding="utf-8")
    elif tamper == "run_record":
        record = tmp_path / "backend" / "runtime" / "runs" / f"{RUN_ID}.json"
        record.write_text(record.read_text(encoding="utf-8") + " ", encoding="utf-8")
    elif tamper == "content":
        broken = json.loads(outside.read_text(encoding="utf-8"))
        broken["repo_files"]["release_record.json"] = "0" * 64
        outside.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
    elif tamper == "head":
        head = "d" * 40
    elif tamper == "dirty":
        dirty = True
    elif tamper == "missing":
        outside.unlink()
    report = _verify(tmp_path, outside, head=head, dirty=dirty)
    assert report["status"] != BINDING_VERIFIED
    assert report["reason"]


def test_release_ready_requires_verified_binding() -> None:
    """技术条件齐备但缺外置绑定时，发布门禁仍必须为 false。"""

    release_data = {
        "release_status": "release_candidate",
        "model": {"model_id": "deepseek-v4-flash"},
        "demo": {"materialized_source_head": COMMIT, "manifest_sha256": MANIFEST_HASH, "case_count": 15},
        "evaluation": {"evaluation_id": "EVAL-X", "human_scoring_status": "completed"},
    }
    evaluation_data = {
        "evaluation_id": "EVAL-X",
        "pointer_status": "valid",
        "model_id": "deepseek-v4-flash",
        "raw_records_status": "completed",
        "human_scoring_status": "completed",
    }
    kwargs: dict[str, Any] = {
        "git_head": COMMIT,
        "worktree_dirty": False,
        "human_final_approval": True,
        "deployment_commit": COMMIT,
        "release_evidence_head": COMMIT,
        "manifest_sha256": MANIFEST_HASH,
        "expected_model_id": "deepseek-v4-flash",
        "signoff_status": SIGNOFF_APPROVED,
        "b3_evidence": {
            "run_id": "RUN-B3-FRESH-0001",
            "run_record_status": "verified",
            "environment": "production",
            "external_live": True,
            "provider": "deepseek_direct",
            "model_id": "deepseek-v4-flash",
            "source_commit": COMMIT,
            "deployment_commit": COMMIT,
            "manifest_sha256": MANIFEST_HASH,
            "manifest_hash_verified": True,
            "result_hash_verified": True,
            "result_sha256": "e" * 64,
            "result_status": "complete",
            "analysis_status": "complete_full_analysis",
            "completed_roles": 3,
            "role_statuses": {"challenge": "completed", "counter": "completed", "review": "completed"},
            "provider_calls": 3,
            "provider_call_ids": ["CALL-1", "CALL-2", "CALL-3"],
            "posthoc_validation_status": "passed",
            "human_scores_completed": True,
            "human_score_record_ids": ["SCORE-1", "SCORE-2"],
        },
    }
    assert evaluate_release_ready(release_data, evaluation_data, **kwargs) == (False, "外置版本绑定未通过：缺少绑定记录")
    pending = evaluate_release_ready(
        release_data, evaluation_data, **{**kwargs, "release_binding": {"status": BINDING_PENDING_APPROVAL, "reason": "缺少真人批准"}}
    )
    assert pending[0] is False and "真人批准" in pending[1]
    blocked = evaluate_release_ready(
        release_data, evaluation_data, **{**kwargs, "release_binding": {"status": "blocked", "reason": "锚点被改写"}}
    )
    assert blocked[0] is False and "锚点被改写" in blocked[1]
    assert evaluate_release_ready(release_data, evaluation_data, **{**kwargs, "release_binding": {"status": BINDING_VERIFIED}}) == (True, VALID)


def test_inline_self_declared_evidence_is_no_longer_read() -> None:
    """发布记录里内联的“已验证”字典不能再被门禁当作证据。"""

    from backend.app.main import _load_fresh_b3_evidence

    state = {
        "release_readiness": {
            "fresh_production_b3_evidence": {"run_record_status": "verified", "human_scores_completed": True},
            "fresh_production_b3_evidence_path": "backend/release_records/current_release.json",
        }
    }
    evidence, reason = _load_fresh_b3_evidence(state)
    assert evidence is None
    assert reason and "fresh_production_b3_run_id" in reason


def test_current_release_record_still_blocks_release() -> None:
    """当前真实发布记录必须保持阻断，且原因指向未闭合的人工与绑定门禁。"""

    release = json.loads((REPO_ROOT / "backend" / "release_records" / "current_release.json").read_text(encoding="utf-8"))
    readiness = release["release_readiness"]
    assert readiness["competition_release_ready"] is False
    # 不允许登记任何“自报完成”的 B3 运行编号或绑定结论。
    assert "fresh_production_b3_run_id" not in readiness
    assert "release_binding" not in readiness
    # 人工评分台账已接线，但必须真的是空的待填状态；接线不等于完成。
    assert str(readiness.get("human_score_ledger_status") or "").startswith("empty")
    ledger_relative = str(readiness.get("human_score_ledger_path") or "")
    assert ledger_relative, "台账路径应已登记，供真人评分后直接可用"
    ledger = REPO_ROOT / ledger_relative
    rows = [line for line in (ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else []) if line.strip()]
    assert rows == [], "AI 不得预先写入任何人工评分行"
    # 评分标准同样只能由真人冻结：目录里出现任何自动化署名的标准都算越界。
    rubric_dir = REPO_ROOT / "backend/release_records/human_scores/rubrics"
    for spec_path in sorted(rubric_dir.glob("*.json")) if rubric_dir.is_dir() else []:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        assert str(spec.get("frozen_by") or "").strip().lower() not in AUTOMATED_IDENTITIES, spec_path.name
