"""混合核验：定向材料、受限计算建议、条件调节与独立AI意见。

所有数值从本次披露取回。这里不调用模型、不修改正式计算状态，
也不把逐字引文验证等同于专业含义已被验证。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re

from .connectivity_engine import normalized, number, text_number, validate_refs
from .connectivity_claims import (apply_hypothesis_updates, build_claim_ledger, build_next_evidence,
    hypothesis_ledger, should_reject_analysis, verify_narrative_magnitude)
from .connectivity_retrieval import build_query_plan, rule_basis_for
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

#: 批次、字段或校验回执属于内部处理信息；模型若把它写成结论，不能当作业务分析保存。
PROCESSING_NOTE = re.compile(r"occurrence_id|check_id|CHECK-\d|PENDING|本批occurrences|不在本批|超出本批|未进入本批|validation_feedback")
ACTION_MATERIAL = re.compile(r"脚注|附注|表头|统计范围|合并范围|定义|上期|本期|分母|组成|分项|页码|原文|口径|单位|币种|报告")
ACTION_VERB = re.compile(r"补|核对|核查|核实|查证|查|获取|对照|确认|复核|抽取|比较")


def _specific_action(text: str) -> bool:
    """下一步必须说清补什么材料、补哪里；只有“建议关注”不算。"""
    value = str(text or "").strip()
    return len(value) >= 8 and bool(ACTION_MATERIAL.search(value)) and bool(ACTION_VERB.search(value))


def analysis_fingerprint(check: RelationshipCheck) -> str:
    fields = {"members", "conditions", "calculation", "hypothetical", "adjustments", "scenario_adjustment",
              "mapping_type", "mapping_reason", "narrative_test", "narrative_claim", "hypotheses",
              "relationship_evidence", "relationship_basis", "explanation", "explanation_evidence"}
    content = json.dumps(check.model_dump(include=fields), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def refresh_analysis_status(run: ConnectivityRun, prompt_version: str | None = None) -> None:
    checks = {c.check_id: c for c in run.checks}
    for opinion in run.ai_analyses:
        check = checks.get(opinion.check_id)
        version_current = prompt_version is None or opinion.prompt_version == prompt_version
        opinion.status = "current" if check and version_current and opinion.input_fingerprint == analysis_fingerprint(check) else "needs_refresh"


def pack_role_context(payload: dict, char_budget: int = 62000) -> dict:
    """压缩重复原文与服务端计算回显，保留成员身份、关键引文和实际覆盖记录。"""
    result = dict(payload)
    checks = payload.get('candidate_checks', [])
    essential = set()
    check_ids = {c['check_id'] for c in checks}
    for event in payload.get('collaboration_history', []):
        if event.get('check_id') in check_ids:
            essential.update(event.get('delivered_evidence_ids', []))
    for check in checks:
        essential.update(m['occurrence_id'] for m in check.get('members', []))
        refs = check.get('relationship_evidence', []) + check.get('explanation_evidence', [])
        refs += [r for c in check.get('conditions', []) for r in c.get('evidence', [])]
        refs += [r for p in check.get('adjustment_proposals', []) for r in p.get('evidence', [])]
        refs += [r for h in check.get('hypotheses', []) for r in h.get('supporting_evidence', []) + h.get('counter_evidence', [])]
        essential.update(r['occurrence_id'] for r in refs)
    for record in payload.get('hypothesis_ledger', []):
        essential.update(record.get('supporting_ids', []))
        essential.update(record.get('counter_ids', []))
    pool = payload.get('structured_candidate_pool', [])
    for candidate in pool[:8]:
        essential.update(member['occurrence_id'] for member in candidate.get('members', []))
    rows = payload.get('occurrences', [])
    ordered = sorted(enumerate(rows), key=lambda pair: (pair[1]['occurrence_id'] not in essential, pair[0]))
    selected = [row for _, row in ordered if row['occurrence_id'] in essential]
    selected.extend(row for _, row in ordered if row['occurrence_id'] not in essential)
    selected = selected[:max(80, sum(r['occurrence_id'] in essential for r in rows))]
    # 状态和派生数值在calculated_results中只传一遍，不再随每条候选重复全量字典。
    proposal_fields = {'check_id', 'rule_id', 'title', 'topic', 'operator', 'members', 'conditions',
                       'relationship_evidence', 'relationship_basis', 'explanation', 'explanation_evidence',
                       'mapping_type', 'mapping_reason', 'calculation_plan', 'adjustment_proposals', 'hypotheses', 'narrative_claim'}
    result['candidate_checks'] = [{k:v for k,v in check.items() if k in proposal_fields} for check in checks]
    numeric_fields = {'expression','left','right','residual','normalized_unit','residual_interval',
                      'precision_compatible','denominator_check','adjustment','positions'}
    compact_results = []
    for row in result.get('calculated_results', []):
        compact = dict(row)
        compact['calculation'] = {k:v for k,v in row.get('calculation',{}).items() if k in numeric_fields}
        compact_results.append(compact)
    result['calculated_results'] = compact_results
    result['retrieval_tasks'] = [{k:v for k,v in task.items() if k in
        {'check_id','missing_conditions','keywords','sent_ids','essential_budget_exceeded'}} for task in result.get('retrieval_tasks',[])]
    result['program_hints'] = [{k:v for k,v in hint.items() if k in
        {'check_id','difference','priority','priority_reason'}} for hint in result.get('program_hints',[])]
    def excerpt(text, label, width):
        index = text.find(label) if label else -1
        start = max(0, index-width//3) if index >= 0 else 0
        return text[start:start+width]
    for width in (900, 550, 320):
        blocks, packed = {}, []
        for row in selected:
            key = (row.get('document_id'), row.get('pdf_page'), row.get('context', ''))
            if key not in blocks:
                blocks[key] = {'block_id': f'B{len(blocks)+1}', 'document_id': row.get('document_id'),
                    'pdf_page': row.get('pdf_page'), 'text': excerpt(row.get('context',''), row.get('label',''), width)}
            fields = {k:row[k] for k in ('occurrence_id','document_id','pdf_page','bbox','label','value','unit','year','year_status',
                      'currency','currency_status','currency_source_id','currency_source_quote',
                      'unit_status','unit_source','unit_source_quote','scope','scope_level','scope_source_id','scope_source_quote',
                      'report_boundary','report_boundary_source_id','report_boundary_source_quote','table_scope',
                      'column_header','full_table_header','header_path','table_id','row_index','column_index','row_role',
                      'column_role','row_parent_label','metric_id','metric_identity','display_precision','rounding_method',
                      'definition','quality') if k in row and (row[k] not in ('',[]) or k=='value')}
            fields['context'] = row.get('row_header') or excerpt(row.get('context',''), row.get('label',''), min(width,220))
            fields['context_ref'] = blocks[key]['block_id']
            if row.get('footnote_scope'):
                fields['footnote_scope'] = row['footnote_scope'][:min(width,420)]
            packed.append(fields)
        result.update(occurrences=packed, evidence_blocks=list(blocks.values()), actual_context_count=len(packed))
        if len(json.dumps(result,ensure_ascii=False)) <= char_budget:
            break
    # 优先移除非必要补充片段；成员与条件引文不为满足预算而静默消失。
    while len(json.dumps(result,ensure_ascii=False)) > char_budget:
        removable = next((i for i in range(len(result['occurrences'])-1,-1,-1)
                          if result['occurrences'][i]['occurrence_id'] not in essential), None)
        if removable is None:
            break
        result['occurrences'].pop(removable)
        used = {r['context_ref'] for r in result['occurrences']}
        result['evidence_blocks'] = [b for b in result['evidence_blocks'] if b['block_id'] in used]
    ids = {r['occurrence_id'] for r in result['occurrences']}
    result['actual_context_count'] = len(ids)
    result['context_packing'] = {'input_occurrences': len(rows), 'sent_occurrences': len(ids),
        'omitted_occurrences': len(rows)-len(ids), 'char_budget': char_budget,
        'note': '完整原文留在结果中；模型只读取本批压缩片段与逐字引文'}
    if 'structured_candidate_pool' in payload:
        result['structured_candidate_pool'] = [candidate for candidate in pool
            if all(member['occurrence_id'] in ids for member in candidate.get('members', []))]
        result['context_packing']['candidate_pool_input_count'] = len(pool)
        result['context_packing']['candidate_pool_sent_count'] = len(result['structured_candidate_pool'])
        result['context_packing']['candidate_pool_omitted_count'] = len(pool) - len(result['structured_candidate_pool'])
    for task in result.get('retrieval_tasks', []):
        task['sent_ids'] = [oid for oid in task.get('sent_ids', []) if oid in ids]
    result['context_packing']['actual_chars'] = len(json.dumps(result,ensure_ascii=False))
    result['context_packing']['essential_budget_exceeded'] = result['context_packing']['actual_chars'] > char_budget
    return result


def targeted_context(run: ConnectivityRun, checks: list[RelationshipCheck], limit: int = 160) -> tuple[list[dict], list[dict]]:
    """先保证成员及已引用材料，再按每项实际缺口检索；记录预算裁剪。

    2026-10-19 起 query 由 directed retrieval 计划生成，同一缺口不再反复使用
    事项级宽泛词；排序同时要求指标名命中，避免只靠“资本化/范围”等通用词召回。
    """
    found = {o.occurrence_id: o for o in run.occurrences}
    plan = build_query_plan(run, checks)
    selected = {}
    tasks = []
    for check in checks:
        refs = check.relationship_evidence + check.explanation_evidence + [r for c in check.conditions for r in c.evidence]
        refs += [r for p in check.adjustment_proposals for r in p.evidence]
        refs += [r for h in check.hypotheses for r in h.supporting_evidence + h.counter_evidence]
        bound = [p.occurrence_id for p in check.adjustment_proposals]
        if check.narrative_claim:
            bound += [check.narrative_claim.current_id, check.narrative_claim.previous_id]
            refs += check.narrative_claim.evidence
        for ref_id in [m.occurrence_id for m in check.members] + bound + [r.occurrence_id for r in refs]:
            if ref_id in found:
                selected.setdefault(ref_id, found[ref_id])
    check_ids = {c.check_id for c in checks}
    for event in run.intelligence_trace:
        if event.get('kind') == 'agent_tool_result' and event.get('check_id') in check_ids:
            for oid in event.get('delivered_evidence_ids', []):
                if oid in found:
                    selected.setdefault(oid, found[oid])
    essential_count = len(selected)
    # 模型可能新增调节项或反证，必须能看到同主题、同指标词根的邻近原文；
    # 否则它只能在未见过的 ADJ 上编造 ID。该召回只扩上下文，不自动成为关系成员。
    for check in checks:
        member_labels = [found[m.occurrence_id].label for m in check.members if m.occurrence_id in found]
        member_docs = {found[m.occurrence_id].document_id for m in check.members if m.occurrence_id in found}
        roots = {label[:2] for label in member_labels if len(label) >= 2}
        for row in run.occurrences:
            if len(selected) >= limit:
                break
            if row.document_id not in member_docs or not roots:
                continue
            if any(root in (row.label or "") for root in roots):
                selected.setdefault(row.occurrence_id, row)
    # 即使成员很多也显式记录未进入本批的关系，不声称模型已审阅。
    selected = dict(list(selected.items())[:limit])
    for check in checks:
        members = [found[m.occurrence_id] for m in check.members if m.occurrence_id in found]
        missing = [c.name for c in check.conditions if c.status != "supported"]
        plan_item = plan["check_plans"].get(check.check_id, {})
        plan_queries = plan_item.get("queries", [])
        metric_terms = plan_item.get("metrics", [])
        words = list(dict.fromkeys([term for query in plan_queries for term in query["terms"]] +
                                  [q for h in check.hypotheses for q in h.retrieval_queries]))
        if not words:
            words = [w for name in missing for w in GAP_KEYWORDS.get(name, [])]
        words = words[:32]
        docs = {m.document_id for m in members}
        ranked = []
        for row in run.occurrences:
            if row.document_id not in docs:
                continue
            hits = sum(word in row.context for word in words)
            specific = sum(term in row.context for term in metric_terms)
            if not hits and not specific:
                continue
            distance = min((abs(row.pdf_page - m.pdf_page) for m in members if m.document_id == row.document_id), default=999)
            topical = row.topic == check.topic or row.topic == "basis"
            ranked.append(((topical, distance <= 1, specific, hits, -distance), row))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        retrieved = [row for _, row in ranked[:12]]
        for row in retrieved:
            if len(selected) < limit:
                selected.setdefault(row.occurrence_id, row)
        tasks.append({"check_id": check.check_id, "missing_conditions": missing, "keywords": words,
                      "queries": plan_queries, "query_ids": plan_item.get("query_ids", []),
                      "query_count": len(plan_queries), "query_dedupe": plan.get("shared_query_count", 0),
                      "metric_terms": metric_terms,
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
        adjustment_ids = {a['occurrence_id'] for a in applied}
        refuted = [h for h in check.hypotheses if h.status == 'refuted' and
                   any(r.occurrence_id in adjustment_ids for r in h.supporting_evidence)]
        if refuted:
            check.scenario_adjustment.update(assumption_status='refuted',
                note='相关调节假设已有反证；仅保留原假设下的算术记录，不再作为有效差异解释')
    claim = check.narrative_claim
    if claim:
        try:
            if not validate_refs(claim.evidence, found):
                raise ValueError("文字主张缺少有效原文")
            current, previous = found[claim.current_id], found[claim.previous_id]
            test = verify_narrative_magnitude(check, claim, rows)
            if current.scope and previous.scope and current.scope != previous.scope:
                test["basis_status"] = "conflicting"
            else:
                test["basis_status"] = "needs_review"
            # 兼容旧字段名，同时保留幅度、精度与目标/结果区分。
            test.setdefault("change_percent", test.get("actual_change_percent"))
            check.narrative_test = test
        except (KeyError, ValueError, ArithmeticError) as error:
            check.narrative_test = {"status": "not_executable", "reason": str(error)}
        if check.calculation_plan and check.narrative_test.get("status") != "not_executable":
            check.calculation_plan.status = "trial"
    return check


def grounded_numbers(check: RelationshipCheck, rows: list, refs: list) -> set[Decimal]:
    """数值按数值身份比较，允许真实单位换算及本项程序派生值，不按字符串写法卡住意见。"""
    values = {Decimal(0)}
    numeric = re.compile(r"[-−+]?\d[\d,，]*(?:\.\d+)?")
    cited = {ref.occurrence_id for ref in refs}
    for row in rows:
        if row.occurrence_id not in cited:
            continue
        for token in numeric.findall(row.context):
            try:
                values.add(number(token))
            except ValueError:
                pass
        if row.year:
            values.add(number(row.year))
        if row.value is not None:
            try:
                value, dimension, _ = normalized(row)
                values.add(value)
                # 金额显示可以在元、万元、百万元和亿元之间等值换算。
                if dimension == "money":
                    values.update(value / Decimal(scale) for scale in (1, 10000, 1000000, 100000000))
                elif dimension == "ratio":
                    values.add(value * 100)
            except (ValueError, ArithmeticError):
                pass
    numeric_keys = {"left", "right", "residual", "original_residual", "remaining_residual", "contribution",
                    "current", "previous", "change_percent", "low", "high", "amount", "value", "normalized_value"}
    def collect(value, key=""):
        if isinstance(value, dict):
            for name, child in value.items():
                collect(child, name)
        elif isinstance(value, list):
            for child in value:
                collect(child, key)
        elif key in numeric_keys and value is not None and not isinstance(value, bool):
            try:
                v = number(str(value))
                values.update((v, abs(v)))
                if key in {"residual", "original_residual", "remaining_residual", "contribution", "amount"}:
                    unit = check.calculation.get("normalized_unit", "")
                    if unit == "元":
                        values.update(v / Decimal(scale) for scale in (10000, 1000000, 100000000))
            except ValueError:
                pass
    for data in (check.calculation, check.hypothetical, check.scenario_adjustment, check.narrative_test):
        collect(data)
    left, right = check.calculation.get("left"), check.calculation.get("right")
    if left is not None and right is not None:
        a, b = number(str(left)), number(str(right))
        if max(abs(a), abs(b)):
            values.add(abs(a-b) / max(abs(a), abs(b)) * 100)
    return values


def unsupported_numbers(text: str, allowed: set[Decimal]) -> list[str]:
    """Scope和角色编号是术语；金额、年份与比例断言仍需有来源或程序结果。"""
    cleaned = re.sub(r"\b(?:Scope\s*[123]|A[123])\b", "", text, flags=re.I)
    missing = []
    for token in re.findall(r"[-−+]?\d[\d,，]*(?:\.\d+)?", cleaned):
        try:
            value = number(token)
            places = value.as_tuple().exponent
            matches = value in allowed or (isinstance(places, int) and -6 <= places < 0 and
                any(v.quantize(Decimal(1).scaleb(places), rounding=ROUND_HALF_UP) == value for v in allowed))
            if not matches:
                missing.append(token)
        except ValueError:
            missing.append(token)
    return missing


def merge_hypotheses(previous: list, incoming: list, check_id: str = "") -> tuple[list, list[dict]]:
    """同ID沿用解释身份和历史反证，后续角色不能用一次覆盖抹掉先前的撤回。"""
    known = {hypothesis.hypothesis_id: hypothesis.model_copy(deep=True) for hypothesis in previous}
    notices = []
    for candidate in incoming:
        old = known.get(candidate.hypothesis_id)
        if old is None:
            if len(known) < 3:
                known[candidate.hypothesis_id] = candidate.model_copy(deep=True)
            else:
                notices.append({"check_id": check_id, "field": "hypotheses", "reason": "竞争解释台账已满，保留既有解释及反证；请先处理已有解释"})
            continue
        merged = candidate.model_copy(deep=True)
        if merged.explanation != old.explanation:
            merged.explanation = old.explanation
            notices.append({"check_id": check_id, "field": "hypotheses", "reason": "同一假设ID沿用原解释；不同解释应使用新ID，历史反证仍保留"})
        for field in ("supporting_evidence", "counter_evidence"):
            unique = {(ref.occurrence_id, ref.quote): ref for ref in getattr(old, field)}
            for ref in getattr(merged, field):
                unique.setdefault((ref.occurrence_id, ref.quote), ref)
            setattr(merged, field, list(unique.values())[:6])
        for field, limit in (("reasons", 4), ("assumptions", 5), ("retrieval_queries", 3)):
            setattr(merged, field, list(dict.fromkeys(getattr(old, field) + getattr(merged, field)))[:limit])
        if old.status == "refuted" and old.counter_evidence:
            merged.status = "refuted"
        known[merged.hypothesis_id] = merged
    return list(known.values()), notices


def integrate_analyses(run: ConnectivityRun, analyses: list[AIAnalysis], allowed_ids: set[str], role: str, prompt_version: str,
                       model: str = "") -> dict:
    checks = {c.check_id: c for c in run.checks}
    sources = {o.occurrence_id: o for o in run.occurrences}
    accepted, rejected = [], []
    seen = set()
    for incoming in analyses:
        item = incoming.model_copy(deep=True)
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
        # claim 账本先于数字门禁：列义矛盾（如把0.66%变动比例当年度值）必须直接拒绝。
        pre_ledger = build_claim_ledger(check, item, run.occurrences, role=role, model=model)
        reject_claim, claim_reason = should_reject_analysis(pre_ledger)
        if reject_claim:
            run.intelligence_trace.append({"kind": "claim_ledger", "role": role,
                                           "check_id": item.check_id, "rejected": True,
                                           "reason": claim_reason, **pre_ledger})
            rejected.append({"check_id": item.check_id, "field": "claim", "reason": claim_reason})
            continue
        allowed = grounded_numbers(check, run.occurrences, refs)
        for derived in pre_ledger.get("derived_checks", []):
            if derived.get("matches") and derived.get("computed") is not None:
                try:
                    allowed.add(Decimal(derived["computed"]))
                except (ValueError, ArithmeticError):
                    pass
        def valid(text, field):
            # 模型偶尔把批次或字段诊断当成业务结论回传；内部标识不能进入AI意见。
            if PROCESSING_NOTE.search(text):
                rejected.append({"check_id": item.check_id, "field": field, "reason": "该条回传了系统字段或批次诊断，已移除，需用原文含义重述"})
                return False
            # 已逐个验证操作数来源和结果的算式不再按孤立数字重判；其余文本照常过闸。
            numeric_text = text
            for derived in pre_ledger.get("derived_checks", []):
                if derived.get("matches") and derived.get("inputs_grounded"):
                    numeric_text = numeric_text.replace(derived["raw"], "")
            if unsupported_numbers(numeric_text, allowed) or re.search(r"认定舞弊|存在重大错报|保证真实|建议买入|不存在风险", text):
                rejected.append({"check_id": item.check_id, "field": field, "reason": "该断言含非来源/程序数值或超出关联核查用途，已单独移除"})
                return False
            return True
        # 无效的建议或备选解释不会抹掉同一关系中有效的分析。
        for field in ("reasons", "assumptions", "alternative_explanations", "next_actions"):
            setattr(item, field, [text for text in getattr(item, field) if valid(text, field)])
        item.next_actions = [text for text in item.next_actions if _specific_action(text)]
        program_actions = False
        if not item.next_actions and check.criteria_status != "supported":
            item.next_actions = [action["action"] for action in build_next_evidence(check, rule_basis_for(check))][:4]
            program_actions = bool(item.next_actions)
        if not item.reasons:
            # 理由全部被移除时登记原因，让同轮的补全调用知道该项仍需重述。
            rejected.append({"check_id": item.check_id, "reason": "意见的理由全部被移除，未形成可用业务分析"})
            continue
        if not valid(item.summary, "summary"):
            item.summary = item.reasons[0]
        if item.priority and (len(item.priority_reason.strip()) < 8 or not valid(item.priority_reason, "priority_reason")):
            item.priority = None
            item.priority_reason = ""
        hypotheses = []
        for hypothesis in item.hypotheses:
            hrefs = hypothesis.supporting_evidence + hypothesis.counter_evidence
            if hrefs and (any(r.occurrence_id not in allowed_ids for r in hrefs) or not validate_refs(hrefs, sources)):
                rejected.append({"check_id": item.check_id, "field": "hypotheses", "reason": "竞争解释含无效引用，已保留其他有效意见"})
                continue
            hallowed = grounded_numbers(check, run.occurrences, refs + hrefs)
            texts = [hypothesis.explanation, *hypothesis.reasons, *hypothesis.assumptions]
            if any(unsupported_numbers(t, hallowed) for t in texts):
                rejected.append({"check_id": item.check_id, "field": "hypotheses", "reason": "竞争解释含无来源数字，已单独移除"})
                continue
            if hypothesis.status == "refuted" and not hypothesis.counter_evidence:
                hypothesis.status = "open"
            if hypothesis.status == "refuted" and not hypothesis.reasons:
                hypothesis.reasons = item.reasons[:4]
            hypotheses.append(hypothesis)
        item.hypotheses = hypotheses
        if item.verdict == "lean_consistent" and check.criteria_status == "conflicting" and not (item.assumptions or item.counter_evidence):
            rejected.append({"check_id": item.check_id, "reason": "明确口径冲突仍存在，不能输出倾向一致"})
            continue
        hard_block = check.operator != 'narrative' and check.calculation_status == 'not_executable'
        contradicts = bool(re.search(r'成员绑定错误|成员误绑|量纲不一致|量纲不同|角色不完整|不能作为.{0,12}(?:核对|金额|比较)依据', item.summary + '；'.join(item.reasons)))
        if item.verdict == 'lean_consistent' and (hard_block or contradicts):
            rejected.append({'check_id': item.check_id, 'field': 'verdict',
                             'reason': '当前绑定存在数值执行/量纲/成员限制，或正文已否定可比性；请针对当前成员返回不可比或依据不足，保留解释而非判另一组数字一致'})
            continue
        item.producer_role = role
        item.prompt_version = prompt_version
        item.producer_model = model
        if item.hypotheses:
            before_status = {hypothesis.hypothesis_id: hypothesis.status for hypothesis in check.hypotheses}
            check.hypotheses, merge_notices = merge_hypotheses(check.hypotheses, item.hypotheses, check.check_id)
            rejected.extend(merge_notices)
            enrich_calculation(check, run.occurrences)
            updates = apply_hypothesis_updates(check, run.occurrences)
            updated_ids = {update["hypothesis_id"] for update in updates}
            for hypothesis in check.hypotheses:
                before = before_status.get(hypothesis.hypothesis_id)
                if before and before != hypothesis.status and hypothesis.hypothesis_id not in updated_ids:
                    updates.append({"check_id": check.check_id, "hypothesis_id": hypothesis.hypothesis_id,
                                    "before": before, "after": hypothesis.status,
                                    "reason": "本轮AI依据已定位引文更新竞争解释，语义判断未独立核验",
                                    "counter_ids": [ref.occurrence_id for ref in hypothesis.counter_evidence],
                                    "semantic_status": "ai_assessed_not_independently_verified"})
            incoming_ids = {hypothesis.hypothesis_id for hypothesis in item.hypotheses}
            item.hypotheses = [hypothesis.model_copy(deep=True) for hypothesis in check.hypotheses if hypothesis.hypothesis_id in incoming_ids]
            if updates:
                run.intelligence_trace.append({"kind": "hypothesis_update", "role": role,
                                               "check_id": check.check_id, "updates": updates})
            run.intelligence_trace.append({"kind": "hypothesis_ledger", "role": role,
                                           "check_id": check.check_id,
                                           "hypotheses": hypothesis_ledger(check)})
            if item.hypotheses and all(hypothesis.status == "refuted" for hypothesis in item.hypotheses) and item.verdict in {"lean_consistent", "plausible_explanation"}:
                rejected.append({"check_id": item.check_id, "field": "verdict",
                                 "reason": "本意见依赖的解释已记录为撤回且历史反证仍在；请根据反证更新意见，或提出独立新解释并给出依据"})
                continue
        ledger = build_claim_ledger(check, item, run.occurrences, role=role, model=model)
        run.intelligence_trace.append({"kind": "claim_ledger", "role": role,
                                       "check_id": check.check_id, **ledger})
        item.input_fingerprint = analysis_fingerprint(check)
        item.status = "current"
        item.review_status = "unreviewed"
        item.calculation_plan_ids = [check.calculation_plan.plan_id] if check.calculation_plan else []
        # 质量是可解释的论证完整度，不是正确概率；claim 支持状态单独保存在账本。
        complete_argument = len(item.reasons) >= 2 and len({sources[r.occurrence_id].document_id for r in refs}) >= 2
        claim_supported = ledger.get("support_status") == "supported"
        item.analysis_quality = "high" if (complete_argument and claim_supported and
                                           (item.counter_evidence or item.assumptions)) else "medium"
        if hard_block:
            item.analysis_quality = 'low'
        if not item.next_actions and check.criteria_status != "supported":
            item.analysis_quality = "low"
        item.quality_reasons = ["引用已逐字定位；质量标签只表示论证完整度，不是正确概率",
                                f"claim账本：{ledger.get('support_status')}；支持{ledger.get('support_summary', {}).get('supported', 0)}条，"
                                f"反驳{ledger.get('support_summary', {}).get('contradicted', 0)}条，"
                                f"依据不足{ledger.get('support_summary', {}).get('insufficient_basis', 0)}条"]
        if program_actions:
            item.quality_reasons.append("下一步补证由程序按未决条件生成，需人工确认是否执行")
        if hard_block:
            item.quality_reasons.append('当前数值关系不能执行；本意见仅分析限制与后续路径，不能视作一致性证据')
        if check.criteria_status != "supported":
            item.quality_reasons.append("尚有比较前提或冲突待解决")
        previous = next((a for a in run.ai_analyses if a.check_id == item.check_id), None)
        if previous:
            run.analysis_history.append({"check_id": item.check_id, "previous": previous.model_dump(),
                                         "reason": item.revision_note or "基于本次补证和复算重新研判"})
        run.ai_analyses = [a for a in run.ai_analyses if a.check_id != item.check_id] + [item]
        accepted.append(item.check_id)
    return {"accepted_analysis_ids": accepted, "analysis_rejections": rejected}
