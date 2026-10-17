"""混合核验：定向材料、受限计算建议、条件调节与独立AI意见。

所有数值从本次披露取回。这里不调用模型、不修改正式计算状态，
也不把逐字引文验证等同于专业含义已被验证。
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
import re

from .connectivity_engine import normalized, number, text_number, validate_refs
from .connectivity_schemas import AIAnalysis, ConnectivityRun, RelationshipCheck

METRIC_GUIDANCE = [
    {"metric": "研发投入", "aliases": ["研发支出", "研发投入金额"], "dimension": "money",
     "distinguish": ["研发费用", "资本化研发支出", "费用化研发支出"], "hint": "费用化与资本化组成须看原文，不默认研发费用等于投入"},
    {"metric": "研发人员数量", "aliases": ["研发人员人数"], "dimension": "count",
     "distinguish": ["期末人数", "年度平均人数"], "hint": "区分期末、平均及外包人员范围"},
    {"metric": "环保投入", "aliases": ["环境保护投入", "环保相关投入"], "dimension": "money",
     "distinguish": ["环保费用", "环保治理投入", "环保设备投资"], "hint": "同名也需看资本性/费用性与覆盖边界；其中项不重复加总"},
    {"metric": "用水", "aliases": ["总用水量", "总取水量", "耗水量"], "dimension": "volume",
     "distinguish": ["取水", "耗水", "循环用水"], "hint": "别名只用于召回，取水和耗水不是等价定义"},
    {"metric": "排放强度", "aliases": ["单位产品温室气体排放", "碳排放强度"], "dimension": "ratio",
     "distinguish": ["收入强度", "吨产品强度", "Scope 1", "Scope 2"], "hint": "先识别分子范围和产量/收入分母，不能用总排放变化替代强度"},
    {"metric": "能源强度", "aliases": ["能耗强度", "单位产品能耗"], "dimension": "ratio",
     "distinguish": ["综合能源消耗", "产量", "营业收入"], "hint": "核实折标系数、分母及组织范围"},
]

GAP_KEYWORDS = {
    "主体": ["报告主体", "股份有限公司", "母公司", "集团"],
    "期间": ["报告期间", "报告时间", "本期", "上年", "年度"],
    "定义": ["定义", "是指", "包括", "不包括", "统计口径"],
    "范围": ["统计范围", "组织边界", "合并范围", "子公司", "重点", "范围", "设备", "治理", "资本化", "费用化"],
    "单位": ["单位", "人民币", "亿元", "万元", "吨", "立方米"],
    "组成完整": ["合计", "构成", "组成", "资本化", "费用化", "其中"],
    "互不重叠": ["其中", "包含", "重复", "不包括", "分项"],
    "公式": ["公式", "分母", "强度", "产量", "营业收入", "占"],
}


def analysis_fingerprint(check: RelationshipCheck) -> str:
    fields = {"members", "conditions", "calculation", "hypothetical", "adjustments", "scenario_adjustment",
              "mapping_type", "mapping_reason", "narrative_test", "explanation", "explanation_evidence"}
    content = json.dumps(check.model_dump(include=fields), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def refresh_analysis_status(run: ConnectivityRun) -> None:
    checks = {c.check_id: c for c in run.checks}
    for opinion in run.ai_analyses:
        check = checks.get(opinion.check_id)
        opinion.status = "current" if check and opinion.input_fingerprint == analysis_fingerprint(check) else "needs_refresh"


def targeted_context(run: ConnectivityRun, checks: list[RelationshipCheck], limit: int = 160) -> tuple[list[dict], list[dict]]:
    """先保证成员及已引用材料，再按每项实际缺口检索；记录预算裁剪。"""
    found = {o.occurrence_id: o for o in run.occurrences}
    selected = {}
    tasks = []
    for check in checks:
        refs = check.relationship_evidence + check.explanation_evidence + [r for c in check.conditions for r in c.evidence]
        refs += [r for p in check.adjustment_proposals for r in p.evidence]
        bound = [p.occurrence_id for p in check.adjustment_proposals]
        if check.narrative_claim:
            bound += [check.narrative_claim.current_id, check.narrative_claim.previous_id]
            refs += check.narrative_claim.evidence
        for ref_id in [m.occurrence_id for m in check.members] + bound + [r.occurrence_id for r in refs]:
            if ref_id in found:
                selected.setdefault(ref_id, found[ref_id])
    essential_count = len(selected)
    # 即使成员很多也显式记录未进入本批的关系，不声称模型已审阅。
    selected = dict(list(selected.items())[:limit])
    for check in checks:
        members = [found[m.occurrence_id] for m in check.members if m.occurrence_id in found]
        missing = [c.name for c in check.conditions if c.status != "supported"]
        words = list(dict.fromkeys([w for name in missing for w in GAP_KEYWORDS.get(name, [])] +
                                  ["资本化", "费用化", "重述", "调整", "同比", "下降", "增加"]))
        docs = {m.document_id for m in members}
        ranked = []
        for row in run.occurrences:
            if row.document_id not in docs:
                continue
            hits = sum(word in row.context for word in words)
            if not hits:
                continue
            distance = min((abs(row.pdf_page - m.pdf_page) for m in members if m.document_id == row.document_id), default=999)
            topical = row.topic == check.topic or row.topic == "basis"
            ranked.append(((topical, distance <= 1, hits, -distance), row))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        retrieved = [row for _, row in ranked[:12]]
        for row in retrieved:
            if len(selected) < limit:
                selected.setdefault(row.occurrence_id, row)
        tasks.append({"check_id": check.check_id, "missing_conditions": missing, "keywords": words,
                      "retrieved_ids": [r.occurrence_id for r in retrieved],
                      "sent_ids": [r.occurrence_id for r in retrieved if r.occurrence_id in selected],
                      "member_ids": [m.occurrence_id for m in check.members],
                      "searched_occurrences": sum(o.document_id in docs for o in run.occurrences),
                      "coverage_note": "检索当前已提取材料，不代表未召回的PDF正文不存在相关披露",
                      "essential_budget_exceeded": essential_count > limit})
    return [r.model_dump() for r in selected.values()], tasks


def _same_cell(a, b) -> bool:
    if a.document_id != b.document_id or a.pdf_page != b.pdf_page or len(a.bbox) != 4 or len(b.bbox) != 4:
        return False
    overlap = max(0, min(a.bbox[2], b.bbox[2])-max(a.bbox[0], b.bbox[0])) * max(0, min(a.bbox[3], b.bbox[3])-max(a.bbox[1], b.bbox[1]))
    area = min(max(0, a.bbox[2]-a.bbox[0])*max(0, a.bbox[3]-a.bbox[1]),
               max(0, b.bbox[2]-b.bbox[0])*max(0, b.bbox[3]-b.bbox[1]))
    return area > 0 and overlap / area > .7


def enrich_calculation(check: RelationshipCheck, rows: list) -> RelationshipCheck:
    """刷新模型计算建议的可执行身份与条件调节，不改变正式结果。"""
    if check.calculation_plan:
        check.calculation_plan.status = ("formal" if check.calculation_status in {"consistent", "precision_explained", "adjustment_explained", "unexplained_difference"}
                                         else "trial" if check.hypothetical else "rejected")
    check.scenario_adjustment = None
    check.narrative_test = None
    found = {r.occurrence_id: r for r in rows}
    base = check.hypothetical or check.calculation
    if check.adjustment_proposals and base.get("residual") is not None and check.operator in {"equal", "sum"}:
        inputs = base.get("inputs") or check.calculation.get("inputs", [])
        dimension = next((i.get("dimension") for i in inputs), None)
        members = [found[m.occurrence_id] for m in check.members if m.occurrence_id in found]
        periods = {r.year for r in members if r.year}
        currencies = {r.currency for r in members if r.currency}
        applied, rejected, seen = [], [], list(members)
        total = Decimal(0)
        for proposal in check.adjustment_proposals:
            row = found.get(proposal.occurrence_id)
            problem = ""
            try:
                if row is None or row.value is None:
                    raise ValueError("调节数值未定位")
                if not validate_refs(proposal.evidence, found) or not any(ref.occurrence_id == row.occurrence_id for ref in proposal.evidence):
                    raise ValueError("调节额缺少本行逐字原文")
                quoted_numbers = [number(n) for ref in proposal.evidence if ref.occurrence_id == row.occurrence_id
                                  for n in re.findall(r"\d[\d,，]*(?:\.\d+)?", ref.quote)]
                if number(row.value) not in quoted_numbers:
                    raise ValueError("所引原句未包含调节额")
                amount, actual_dimension, _ = normalized(row)
                if amount < 0 or actual_dimension != dimension:
                    raise ValueError("调节金额或量纲不适用")
                if row.year and periods and row.year not in periods:
                    raise ValueError("调节项指标期间不同")
                if len(periods) > 1:
                    raise ValueError("基础关系包含不同期间，不能作同年范围桥接")
                if row.currency and currencies and row.currency not in currencies:
                    raise ValueError("调节项币种不同")
                if any(row.occurrence_id == old.occurrence_id or _same_cell(row, old) for old in seen):
                    raise ValueError("调节项重复使用已计入的数值或物理单元格")
                contribution = amount if proposal.sign == "+" else -amount
                total += contribution
                seen.append(row)
                applied.append({**proposal.model_dump(), "amount": text_number(contribution),
                                "unit": base.get("normalized_unit", ""), "source_value": row.value,
                                "source_unit": row.unit, "source_period": row.year})
            except (ValueError, ArithmeticError) as error:
                problem = str(error)
            if problem:
                rejected.append({"occurrence_id": proposal.occurrence_id, "reason": problem})
        residual = number(base["residual"]) - total
        check.scenario_adjustment = {"hypothetical": True, "original_residual": base["residual"],
            "applied": applied, "rejected": rejected, "contribution": text_number(total),
            "remaining_residual": text_number(residual), "unit": base.get("normalized_unit", ""),
            "assumptions": list(dict.fromkeys(["仅为候选范围桥接；未确认分类覆盖完整且互不重叠"] +
                [f"待核实：{c.name}（{c.reason}）" for c in check.conditions if c.status != "supported"] +
                [a for p in check.adjustment_proposals for a in p.assumptions])),
            "note": "原始候选差额减去有符号调节贡献；试算闭合不证明业务解释成立，不改正式计算状态"}
    claim = check.narrative_claim
    if claim:
        try:
            current, previous = found[claim.current_id], found[claim.previous_id]
            if not validate_refs(claim.evidence, found):
                raise ValueError("文字主张缺少有效原文")
            a, da, _ = normalized(current)
            b, db, _ = normalized(previous)
            if da != db or da == "unknown":
                raise ValueError("趋势数据量纲不同")
            if current.currency != previous.currency:
                raise ValueError("趋势数据币种不同")
            if not current.year or not previous.year or int(current.year) - int(previous.year) != 1:
                raise ValueError("同比需要明确的连续两期指标年度")
            actual = "increase" if a > b else "decrease" if a < b else "stable"
            check.narrative_test = {"current": text_number(a), "previous": text_number(b), "dimension": da,
                "direction": actual, "claimed_direction": claim.direction, "direction_matches": actual == claim.direction,
                "change_percent": text_number((a-b)/abs(b)*100) if b else None,
                "basis_status": "conflicting" if current.scope and previous.scope and current.scope != previous.scope else "needs_review",
                "note": "这里只检验所绑定数值方向，指标语义、强度分母及叙述限定语由AI结合原文研判"}
        except (KeyError, ValueError, ArithmeticError) as error:
            check.narrative_test = {"status": "not_executable", "reason": str(error)}
        if check.calculation_plan and check.narrative_test.get("status") != "not_executable":
            check.calculation_plan.status = "trial"
    return check


def integrate_analyses(run: ConnectivityRun, analyses: list[AIAnalysis], allowed_ids: set[str], role: str, prompt_version: str) -> dict:
    checks = {c.check_id: c for c in run.checks}
    sources = {o.occurrence_id: o for o in run.occurrences}
    accepted, rejected = [], []
    seen = set()
    for item in analyses:
        check = checks.get(item.check_id)
        refs = item.supporting_evidence + item.counter_evidence
        reason = ""
        if not check or item.check_id in seen:
            reason = "意见未绑定本次唯一核对项"
        elif not refs or any(r.occurrence_id not in allowed_ids for r in refs) or not validate_refs(refs, sources):
            reason = "意见所引原文缺失、越界或无法逐字核实"
        elif not any(r.occurrence_id in {m.occurrence_id for m in check.members} for r in refs):
            reason = "意见没有引用本关系成员；需补充该指标的直接依据"
        elif not any(len(r.strip()) >= 8 for r in item.reasons):
            reason = "意见缺少针对该关系的具体理由"
        if reason:
            rejected.append({"check_id": item.check_id, "reason": reason})
            continue
        seen.add(item.check_id)
        text = item.summary + " ".join(item.reasons + item.assumptions + item.alternative_explanations + item.next_actions)
        sourced = " ".join(sources[r.occurrence_id].context for r in refs)
        computed = json.dumps({"calculation": check.calculation, "hypothetical": check.hypothetical,
                               "scenario": check.scenario_adjustment, "narrative": check.narrative_test}, ensure_ascii=False)
        numbers = {n.replace(",", "").replace("，", "") for n in re.findall(r"\d[\d,，]*(?:\.\d+)?", sourced + computed)}
        if any(n.replace(",", "").replace("，", "") not in numbers for n in re.findall(r"\d[\d,，]*(?:\.\d+)?", text)):
            rejected.append({"check_id": item.check_id, "reason": "意见含非引用原文或本项计算中的数值"})
            continue
        if re.search(r"认定舞弊|存在重大错报|保证真实|建议买入|不存在风险", text):
            rejected.append({"check_id": item.check_id, "reason": "意见越过关联核查用途"})
            continue
        if item.verdict == "lean_consistent" and check.criteria_status == "conflicting":
            rejected.append({"check_id": item.check_id, "reason": "明确口径冲突仍存在，不能输出倾向一致"})
            continue
        item.producer_role = role
        item.prompt_version = prompt_version
        item.input_fingerprint = analysis_fingerprint(check)
        item.status = "current"
        item.review_status = "unreviewed"
        item.calculation_plan_ids = [check.calculation_plan.plan_id] if check.calculation_plan else []
        # 质量是可解释的系统标签，不使用模型自报概率。
        item.analysis_quality = "low" if not item.next_actions and check.criteria_status != "supported" else "medium"
        item.quality_reasons = ["原文引用已逐字核验；业务含义为AI意见，未经独立专业确认"]
        if check.criteria_status != "supported":
            item.quality_reasons.append("尚有比较前提或冲突待解决")
        run.ai_analyses = [a for a in run.ai_analyses if a.check_id != item.check_id] + [item]
        accepted.append(item.check_id)
    return {"accepted_analysis_ids": accepted, "analysis_rejections": rejected}
