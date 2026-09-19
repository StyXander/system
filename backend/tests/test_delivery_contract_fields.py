"""契约字段进 Word 备忘录的验收测试（W05 补齐 + 轨 C 点名的运行来源同步）。

覆盖三份 fixture 与两条独立轴：
- run_contract_mock.json            完整成功态（闸门 passed → E2 / P2 / retain / external_live）
- run_contract_mock_degraded.json   闸门未通过态（passed=false → E3 / P2 不变 / 仍 external_live）

这里最重要的不是"降级卡有没有文案"，而是双轴性质必须被钉住：
数字闸门只决定证据闭合状态，绝不参与审计关注优先级定级。
若将来有人把闸门结果接进优先级，本文件的 P2 断言会先失败。

统一 AI 声明在此按字面量断言，而不是复用被模块导入的常量——逐字性需要独立锚点。
"""

from pathlib import Path
from typing import Any

import pytest
from docx import Document

from backend.app.delivery import build_report
from backend.app.schemas import (
    ExecutionBadge,
    HumanReviewRequest,
    RunResponse,
    StoredRunResponse,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def _load(name: str) -> dict[str, Any]:
    import json

    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _stored(raw: dict[str, Any]) -> StoredRunResponse:
    """把裸 RunResponse 载荷包装成报告读取形态，人工处置留自动化水印。"""
    return StoredRunResponse(
        run=RunResponse.model_validate(raw),
        human_review=HumanReviewRequest(
            status="暂缓",
            note="契约字段验收测试，不构成人工专业结论。",
            reviewer="自动化测试",
            reviewer_type="automation",
            export_approved=True,
        ),
    )


def _report_text(tmp_path: Path, raw: dict[str, Any]) -> str:
    path = build_report(tmp_path, _stored(raw))
    document = Document(path)
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            chunks.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(chunks)


def test_both_contract_fixtures_round_trip_as_run_response() -> None:
    """两份载荷都必须能过 RunResponse，防止 fixture 与 schema 漂移。"""
    for name in ("run_contract_mock.json", "run_contract_mock_degraded.json"):
        run = RunResponse.model_validate(_load(name))
        assert run.planning_priority is not None, name
        assert run.evidence_state is not None, name
        assert run.disposition is not None, name
        assert run.execution_badge is not None, name
        assert run.numeric_gate_summary is not None, name


def test_report_carries_priority_evidence_disposition_and_source_rows(tmp_path: Path) -> None:
    """完整态：四行独立状态 + 运行来源必须同时在场，且逐字用已签标签。"""
    text = _report_text(tmp_path, _load("run_contract_mock.json"))
    for probe in (
        "审计关注优先级",
        "P2 优先核查",
        "证据闭合状态",
        "E2 部分闭合",
        "处置",
        "建议保留（retain）",
        "金额重要性",
        "运行来源",
        "本次真实模型运行",
        "本次真实调用 3 次",
        AI_NOTICE,
    ):
        assert probe in text, probe


def test_gate_rejected_report_is_truthful_and_keeps_priority_unchanged(tmp_path: Path) -> None:
    """降级态：如实说明真实调用已完成、指出未通过数字，且优先级不得被闸门拉低。"""
    raw = _load("run_contract_mock_degraded.json")
    assert raw["run_completeness"] == "incomplete_numeric_claims"

    text = _report_text(tmp_path, raw)
    for probe in (
        "数字可追溯闸门说明",
        "真实模型调用已完成 3 次",
        "1 个关键财务数字未通过可追溯闸门",
        "故不发布为完整结果",
        "41,813,685.32",
        "确定性计算结果仍可查看",
        "E3 未闭合",
        "P2 优先核查",
        "本次真实模型运行",
        AI_NOTICE,
    ):
        assert probe in text, probe

    # 闸门结果不得进入优先级：降级态仍是 P2，只有证据闭合状态变化。
    run = RunResponse.model_validate(raw)
    assert run.planning_priority.grade == "P2"
    assert run.evidence_state.state == "E3"
    assert run.numeric_gate_summary.passed is False


def test_report_renders_complete_state_as_closed(tmp_path: Path) -> None:
    """完整态不得出现降级说明段，防止两个状态共用同一段措辞。"""
    text = _report_text(tmp_path, _load("run_contract_mock.json"))
    assert "数字可追溯闸门说明" not in text
    assert "E3" not in text


@pytest.mark.parametrize(
    ("mode", "label", "calls"),
    [
        ("external_live", "本次真实模型运行", 3),
        ("cache_replay", "已验证历史结果回放", 0),
        ("deterministic_backup", "确定性备用链", 0),
    ],
)
def test_execution_source_badge_never_collapses_across_three_states(
    tmp_path: Path, mode: str, label: str, calls: int
) -> None:
    """三态在报告中必须各说各话：把同一载荷只换徽标，断言互不冒充。"""
    raw = _load("run_contract_mock.json")
    raw["execution_badge"] = {"mode": mode, "label": label, "provider_call_count": calls}
    text = _report_text(tmp_path / mode, raw)

    assert label in text
    assert "运行来源" in text
    # 另外两种标签不得同时出现，否则等于三态混淆。
    others = {"本次真实模型运行", "已验证历史结果回放", "确定性备用链"} - {label}
    for other in others:
        assert other not in text, (mode, other)


def test_missing_badge_is_reported_as_not_provided(tmp_path: Path) -> None:
    """徽标缺失时如实写未提供，不得由报告端推断本次是否调用过模型。"""
    raw = _load("run_contract_mock.json")
    raw["execution_badge"] = None
    text = _report_text(tmp_path, raw)
    assert "运行来源" in text
    assert "未提供" in text
    assert "本次真实模型运行" not in text


def test_badge_model_keeps_provider_call_count_field() -> None:
    """ExecutionBadge 必须保留本次真实调用数，供页面与报告同源引用。"""
    badge = ExecutionBadge(mode="external_live", label="本次真实模型运行", provider_call_count=3)
    assert badge.provider_call_count == 3


def test_report_uses_songti_body_and_heiti_headings(tmp_path: Path) -> None:
    """用户口径：正文宋体小四(12pt)、标题黑体三号(16pt)。

    表格因密度用五号(10.5pt)，是对"正文小四"的登记例外，不在此断言。
    """
    from docx.shared import Pt as _Pt

    raw = _load("run_contract_mock.json")
    path = build_report(tmp_path, _stored(raw))
    document = Document(path)

    normal = document.styles["Normal"]
    assert normal.font.name == "宋体"
    assert normal.font.size == _Pt(12)

    title_run = document.paragraphs[0].runs[0]
    assert title_run.font.name == "黑体"
    assert title_run.font.size == _Pt(16)

    headings = [p for p in document.paragraphs if p.style.name.startswith("Heading")]
    assert headings, "报告应至少有一个标题段"
    first = headings[0].runs[0]
    assert first.font.name == "黑体"
    assert first.font.size == _Pt(16)
