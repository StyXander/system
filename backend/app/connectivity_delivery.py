"""同一保存结果的JSON、CSV与Word导出，保留口径和未决条件。

复用原delivery的字体、标题、表格方法，不另造排版框架。
公众摘要和专业明细共享同一版本事实，角色名称不替代运行证据。
"""
from __future__ import annotations

import csv
from io import BytesIO, StringIO
import json

from docx import Document
from docx.shared import Pt, RGBColor

from .connectivity_schemas import ConnectivityRun, notice_for
from .delivery import _add_heading, _table_rows, _set_run_font

STATUS_LABELS = {"supported": "依据齐备", "unknown": "依据待补", "conflicting": "存在冲突",
    "consistent": "所选关系计算一致", "precision_explained": "可由已知精度解释",
    "adjustment_explained": "有据加性调节后与0相容", "unexplained_difference": "未解释差异",
    "not_comparable": "暂不可比较", "not_executable": "暂不可执行", "not_applicable": "不适用数值计算",
    "unreviewed": "未人工复核", "demo_modified": "演示更正", "read_confirmed": "使用者已阅读"}
AI_LABELS = {"lean_consistent": "倾向一致", "potential_conflict": "存在潜在矛盾", "plausible_explanation": "存在合理解释路径",
             "insufficient_basis": "依据不足但可继续核查", "not_comparable": "当前不可直接比较"}


def export_fingerprint(run: ConnectivityRun) -> list[dict]:
    """同源校验用指纹：check_id、两类状态与正式残差必须与页面渲染一致。"""
    return [{"check_id": c.check_id, "criteria_status": c.criteria_status,
             "calculation_status": c.calculation_status, "residual": c.calculation.get("residual")}
            for c in run.checks]


def verify_export_same_source(run: ConnectivityRun, payload: bytes) -> list[str]:
    """比对导出 JSON 与内存结果的指纹；不一致即视为发布失败，返回差异说明。"""
    exported = json.loads(payload.decode("utf-8"))
    rows = exported.get("checks") or []
    left = export_fingerprint(run)
    if len(rows) != len(left):
        return [f"导出关系数{len(rows)}与结果{len(left)}不一致"]
    problems = []
    for expected, actual in zip(left, rows):
        for key in ("check_id", "criteria_status", "calculation_status"):
            if expected[key] != actual.get(key):
                problems.append(f"{expected['check_id']}的{key}不一致")
        if (expected["residual"] or None) != ((actual.get("calculation") or {}).get("residual") or None):
            problems.append(f"{expected['check_id']}的正式残差与页面不一致")
    if exported.get("ai_analyses", []) != [a.model_dump(mode="json") for a in run.ai_analyses]:
        problems.append("导出AI研判与保存结果不一致")
    for expected, actual in zip(run.checks, rows):
        for field in ("calculation_plan", "scenario_adjustment", "narrative_test"):
            if expected.model_dump(mode="json").get(field) != actual.get(field):
                problems.append(f"{expected.check_id}的{field}与保存结果不一致")
    return problems


def _paragraph(document, text):
    """每段明确设正文宋体小四，避免继承系统默认字体。"""
    run = document.add_paragraph().add_run(str(text))
    _set_run_font(run)
    run.font.size = Pt(12)


def _cell(value):
    text = str(value if value is not None else "")
    # 报告标签与模型文字不作为电子表格公式执行。
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _assert_notice(payload: bytes, notice: str) -> None:
    """导出必须包含当次业务对应的声明常量，否则拒绝生成，不靠调用方自觉。"""
    if notice[:10] not in payload.decode("utf-8", "ignore"):
        raise ValueError("导出缺少当次业务对应的声明，已拒绝生成")


def export_run(run: ConnectivityRun, format_name: str, include_personal: bool = True) -> tuple[bytes, str]:
    notice = notice_for(run.task_kind)
    if format_name == "json":
        body = run.model_dump(mode="json")
        body["ai_generated_content_notice"] = notice
        if not include_personal:
            body["personal_observation_count"] = len(run.professional_notes)
            body["professional_notes"] = []
        payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        _assert_notice(payload, notice)
        return payload, "application/json"
    sources = {o.occurrence_id: o for o in run.occurrences}
    if format_name == "csv":
        stream = StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["行类型", "运行", "版本", "核对项", "规则", "事项", "角色或条件", "原值或状态", "单位", "文件", "PDF顺序页", "原文或说明", "算式", "差额", "口径", "计算", "复核"])
        for check in run.checks:
            base = [run.run_id, run.result_revision, check.check_id, check.rule_id, check.title]
            tail = [check.calculation.get("expression", ""), check.calculation.get("residual") or "", check.criteria_status, check.calculation_status, check.review_status]
            gate = check.calculation.get("gate") or {}
            note = "；".join(check.unresolved)
            if gate:
                note = f"{gate.get('conclusion', '暂不能直接比较')}：缺少{'、'.join(gate.get('missing') or [])}；{note}"
            writer.writerow([_cell(v) for v in ["relation", *base, "", "", "", "", "", note, *tail]])
            for member in check.members:
                o = sources[member.occurrence_id]
                writer.writerow([_cell(v) for v in ["member", *base, member.role, o.value, o.unit, o.document_id, o.pdf_page, o.context, *tail]])
            for condition in check.conditions:
                writer.writerow([_cell(v) for v in ["condition", *base, condition.name, condition.status, "", "", "", condition.reason + "；" + "；".join(ref.quote for ref in condition.evidence), *tail]])
            for index, position in enumerate(check.calculation.get("positions") or [], start=1):
                writer.writerow([_cell(v) for v in ["position", *base, f"第{index}处比较", position.get("residual", ""), "",
                    "", "", f"是否精度相容：{position.get('precision_compatible')}", *tail]])
            for item in (check.calculation.get("adjustment") or {}).get("applied", []):
                writer.writerow([_cell(v) for v in ["adjustment", *base, item["effect_id"], f"{item['sign']}{item['amount']}", item["unit"], "", "", item["label"] + "；" + item["note"], *tail]])
            for item in (check.calculation.get("adjustment") or {}).get("rejected", []):
                writer.writerow([_cell(v) for v in ["adjustment_rejected", *base, item.get("adjustment_id", ""), "已拒绝", "", "", "", item["reason"], *tail]])
            if check.hypothetical:
                writer.writerow([_cell(v) for v in ["hypothetical_only", *base, "假设试算", "非正式结论", check.hypothetical.get("normalized_unit", ""), "", "",
                    check.hypothetical.get("expression", "") + "；残差" + str(check.hypothetical.get("residual")), check.hypothetical.get("expression", ""), check.hypothetical.get("residual") or "", "假设", "不进入已衔接统计", ""]])
            if check.explanation:
                writer.writerow([_cell(v) for v in ["explanation", *base, "", "", "", "", "", check.explanation, *tail]])
            if check.related_checks:
                writer.writerow([_cell(v) for v in ["related_checks", *base, "", "", "", "", "", ";".join(check.related_checks), *tail]])
            for kind, value in [("calculation_plan", check.calculation_plan.model_dump() if check.calculation_plan else None),
                                ("scenario_adjustment", check.scenario_adjustment), ("narrative_test", check.narrative_test)]:
                if value:
                    writer.writerow([_cell(v) for v in [kind, *base, "", "", "", "", "", json.dumps(value, ensure_ascii=False), *tail]])
            for opinion in (a for a in run.ai_analyses if a.check_id == check.check_id):
                writer.writerow([_cell(v) for v in ["ai_analysis", *base, opinion.status, AI_LABELS[opinion.verdict], "", "", "",
                    json.dumps(opinion.model_dump(), ensure_ascii=False), *tail]])
        for exclusion in run.extraction_exclusions:
            writer.writerow([_cell(v) for v in ["excluded_occurrence", run.run_id, run.result_revision, "", "", "", "",
                exclusion.value, exclusion.unit, exclusion.document_id, exclusion.pdf_page, exclusion.label + "；" + exclusion.reason]])
        for record in run.version_records:
            writer.writerow([_cell(v) for v in ["version_record", run.run_id, run.result_revision, "", "", "", record.version_role,
                record.value or "未登记数值", record.unit, record.document_id, "", record.label + "；" + record.effective_relation]])
        for change in run.version_changes:
            writer.writerow([_cell(v) for v in ["version_change_only", run.run_id, run.result_revision, "", "", "", change.label,
                change.display_change, change.unit, change.from_version_id, "", change.note]])
        if include_personal:
            for note in run.professional_notes:
                writer.writerow([_cell(v) for v in ["personal_observation", run.run_id, run.result_revision, note.check_id,
                    "", "", note.actor, "个人观察，非系统结论", "", "", "", note.observation + "；理由：" + note.reason]])
        elif run.professional_notes:
            writer.writerow(["personal_observation_count", run.run_id, run.result_revision, "", "", "", "", f"存在{len(run.professional_notes)}条个人观察", "", "", "", "公共导出不含个人观察正文", "", "", "", "", ""])
        for review in run.reviews:
            writer.writerow([_cell(v) for v in ["review_event", run.run_id, run.result_revision, review.check_id,
                "", "", review.actor, review.action, "", "", "", json.dumps(review.model_dump(), ensure_ascii=False)]])
        writer.writerow(["notice", notice])
        payload = stream.getvalue().encode("utf-8-sig")
        _assert_notice(payload, notice)
        return payload, "text/csv; charset=utf-8"
    if format_name != "docx":
        raise ValueError("不支持的报告格式")
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "宋体"
    normal.font.size = Pt(12)
    title = document.add_paragraph(style="Title").add_run("年度报告与可持续发展报告关联核对")
    _set_run_font(title, "黑体")
    title.font.size = Pt(16)
    title.font.color.rgb = RGBColor(0, 0, 0)
    _paragraph(document, f"{run.company} · {run.period} · {run.run_id} · 结果版本{run.result_revision}")
    _paragraph(document, notice)
    _add_heading(document, "阅读摘要", 2)
    _paragraph(document, f"本次从登记报告中发现{len(run.occurrences)}处候选及上下文，形成{len(run.checks)}项关系记录、{len(run.findings)}项待查问题。数字相符不替代定义与范围依据。")
    overview = run.overview or {}
    if overview:
        _add_heading(document, "结果概览（各带分母，状态可重叠）", 3)
        for key in ("confirmable", "unconfirmable", "unexplained"):
            item = overview.get(key) or {}
            _paragraph(document, f"{item.get('label', key)}：{item.get('value')} / {item.get('denominator')}。")
        not_found = overview.get("not_found") or {}
        _paragraph(document, f"{not_found.get('label', '未定位或提取失败的位置')}：{not_found.get('value')}，{not_found.get('denominator_label', '')}。")
        _paragraph(document, overview.get("note", ""))
    _table_rows(document, [("实际运行方式", run.execution_mode), ("模型状态", run.model_status), ("发现方式", run.discovery_mode),
        ("资料身份", run.dataset_role), ("耗时毫秒", run.duration_ms), ("父运行", run.parent_run_id or "无")])
    _add_heading(document, "本次文件与实际搜索覆盖", 2)
    for doc in run.documents:
        _table_rows(document, [("文件", doc.document_id), ("公司和期间", f"{doc.company} {doc.period}"),
            ("报告所属期间", doc.report_period or doc.period), ("指标所属期间", doc.metric_period or "未登记，按各披露行年度列归属"),
            ("来源类别", doc.source_kind), ("版本", doc.version), ("公开出处", doc.source_url), ("编制依据登记", doc.compilation_basis)])
    for coverage in run.coverage:
        _paragraph(document, f"{coverage.document_id}：共{coverage.total_pages}页，解析{coverage.parsed_pages}页，搜索{len(coverage.searched_pages)}页；失败页：{json.dumps(coverage.failed_pages, ensure_ascii=False)}。仅说明实际处理范围。")
    if run.extraction_exclusions:
        _add_heading(document, "已提取但未计入的位置", 2)
        _paragraph(document, f"共{len(run.extraction_exclusions)}处未进入候选，原因逐条登记；这些位置不作为“没有披露”的证据。")
        for exclusion in run.extraction_exclusions:
            _paragraph(document, f"{exclusion.document_id} PDF顺序页{exclusion.pdf_page} · {exclusion.label} · {exclusion.value} {exclusion.unit} · {exclusion.reason}")
    for check in run.checks:
        _add_heading(document, check.title, 2)
        _table_rows(document, [("核对项及规则", f"{check.check_id} / {check.rule_id}"),
            ("口径状态", STATUS_LABELS.get(check.criteria_status, check.criteria_status)),
            ("计算状态", STATUS_LABELS.get(check.calculation_status, check.calculation_status)),
            ("复核状态", STATUS_LABELS.get(check.review_status, check.review_status))])
        for opinion in (a for a in run.ai_analyses if a.check_id == check.check_id):
            _add_heading(document, "AI分析意见：" + AI_LABELS[opinion.verdict], 3)
            _paragraph(document, "仅供核查参考；" + ("输入已变化，需重新分析" if opinion.status == "needs_refresh" else "与本次保存结果绑定"))
            _paragraph(document, "使用者处理：" + {"unreviewed": "未复核", "accepted": "已采纳为核查参考", "rejected": "已驳回"}[opinion.review_status])
            _paragraph(document, opinion.summary)
            for title, values in [("判断依据", opinion.reasons), ("假设", opinion.assumptions),
                                  ("其他解释", opinion.alternative_explanations), ("下一步", opinion.next_actions),
                                  ("分析质量说明", opinion.quality_reasons)]:
                if values:
                    _paragraph(document, title + "：" + "；".join(values))
            for kind, refs in [("支持原文", opinion.supporting_evidence), ("相反证据", opinion.counter_evidence)]:
                for ref in refs:
                    row = sources.get(ref.occurrence_id)
                    _paragraph(document, f"{kind} {ref.occurrence_id} / PDF {row.pdf_page if row else '?'}：{ref.quote}")
        if check.calculation_plan:
            _paragraph(document, "计算方案：" + check.calculation_plan.reason + "；假设：" + "；".join(check.calculation_plan.assumptions))
        if check.scenario_adjustment:
            _add_heading(document, "条件调节试算（不覆盖正式差额）", 3)
            _paragraph(document, json.dumps(check.scenario_adjustment, ensure_ascii=False))
        if check.narrative_test:
            _paragraph(document, "文字与数值方向核对：" + json.dumps(check.narrative_test, ensure_ascii=False))
        for condition in check.conditions:
            _paragraph(document, f"{condition.name}：{STATUS_LABELS.get(condition.status, condition.status)}；{condition.reason}")
            for ref in condition.evidence:
                _paragraph(document, f"依据 {ref.occurrence_id}：{ref.quote}")
        for member in check.members:
            row = sources[member.occurrence_id]
            _table_rows(document, [("成员与角色", f"{row.occurrence_id} / {member.role}"), ("原标签", row.label),
                ("原值与单位", f"{row.value if row.value is not None else '未提取数值'} {row.unit}"),
                ("位置", f"{row.document_id} PDF顺序页{row.pdf_page}；列头{row.column_header}；年度{row.year or '未归属'}（{row.year_status}）")])
            _paragraph(document, "原文上下文：" + row.context)
        gate = check.calculation.get("gate") or {}
        if gate:
            _paragraph(document, f"正式结论：{gate.get('conclusion', '暂不能直接比较')}；缺少：{'、'.join(gate.get('missing') or [])}；{gate.get('needed', '')}")
        _paragraph(document, "正式计算记录：" + json.dumps(check.calculation, ensure_ascii=False))
        if check.hypothetical:
            _add_heading(document, "假设试算（非正式结论，不进入已衔接统计）", 3)
            _paragraph(document, "假设：" + "；".join(check.hypothetical.get("assumptions") or []))
            _paragraph(document, f"试算算式：{check.hypothetical.get('expression', '')}；试算差额：{check.hypothetical.get('residual')} {check.hypothetical.get('normalized_unit', '')}")
        adjustment = check.calculation.get("adjustment") or {}
        if adjustment:
            _add_heading(document, "差异解释的加性调节与残差", 3)
            for item in adjustment.get("applied", []):
                _paragraph(document, f"调节 {item['adjustment_id']}（效果{item['effect_id']}）：{item['sign']}{item['amount']} {item['unit']}；{item['label']}。{item['note']}")
            for item in adjustment.get("rejected", []):
                _paragraph(document, f"已拒绝的调节 {item.get('adjustment_id')}：{item['reason']}")
            if adjustment.get("applied"):
                interval = adjustment.get("remaining_interval") or {}
                _paragraph(document, f"剩余残差：{adjustment.get('remaining_residual')}；区间[{interval.get('low')}, {interval.get('high')}]；是否含0：{interval.get('contains_zero')}。{adjustment.get('note', '')}")
        _paragraph(document, "解释：" + (check.explanation or "本次尚未找到充分解释"))
        _paragraph(document, "关联的解释或分组记录：" + ("；".join(check.related_checks) or "暂无"))
        _paragraph(document, "未决条件：" + ("；".join(check.unresolved) or "当前选定关系无额外未决条件"))
    if run.version_records or run.version_changes:
        _add_heading(document, "企业披露版本与版本变化（不进入正式跨报告差额）", 2)
        for record in run.version_records:
            _paragraph(document, f"{record.document_id} · {record.version_role} · {record.disclosure_date or '披露日期未登记'} · 指标期间{record.metric_period or '未登记'} · {record.effective_relation} · 来源{record.source_kind}")
        for change in run.version_changes:
            _paragraph(document, f"{change.label}：{change.from_version_id} → {change.to_version_id}，显示变化{change.display_change} {change.unit}。{change.note}")
    _add_heading(document, "具体问题与后续资料用途", 2)
    for finding in run.findings:
        _table_rows(document, [("关联核对项", finding.check_id), ("已知事实", finding.known_facts), ("待查问题", finding.question),
            ("可进一步了解的说明或资料", finding.requested_material), ("用途", finding.purpose)])
    _add_heading(document, "使用者个人观察", 2)
    if not include_personal:
        _paragraph(document, f"公共导出不含个人观察正文；本次记录存在{len(run.professional_notes)}条个人观察，仅本人视图可展开。")
    for note in (run.professional_notes if include_personal else []):
        _paragraph(document, f"{note.check_id} / {note.actor} / {note.created_at}：{note.observation}；理由：{note.reason}。本项为个人观察，不改变系统计算结论。")
    _add_heading(document, "角色、调用及修订记录", 2)
    _paragraph(document, json.dumps(run.agent_steps, ensure_ascii=False))
    _paragraph(document, json.dumps(run.provider_calls, ensure_ascii=False))
    for review in run.reviews:
        _paragraph(document, json.dumps(review.model_dump(), ensure_ascii=False))
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
