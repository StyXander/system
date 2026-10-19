"""定向补证与专业规则依据检索：先按关系生成具体 query，再做支持/反证两路召回。

旧实现把同一事项的宽泛关键词反复复用，命中多但难以把条件升级。
本模块把“公司 + 报告对 + 成员指标 + 同义词 + 缺口条件 + 期间”拼成可去重
的检索单元，并把每次命中、被用于升级的引文和错误引用率单独记录。
"""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Iterable

from .connectivity_engine import validate_refs
from .connectivity_extraction import PARSER_CACHE_VERSION
from .connectivity_rules import direct_metric
from .connectivity_schemas import DisclosureOccurrence

RULE_BASIS_PATH = Path(__file__).with_name("connectivity_rule_basis.json")
RETRIEVAL_VERSION = "connectivity_directed_retrieval_v1"
KNOWLEDGE_VERSION = "connectivity_rule_basis_v1"

#: 别名只用于召回；取水与耗水、研发费用与研发投入等差异仍由原文定义确认。
#: 别名表不参与“同口径”判定，也不把研发费用自动并入研发投入。
METRIC_SYNONYMS = {
    "研发投入": ["研发支出", "研发投入金额", "研发投入合计", "研究开发投入"],
    "研发投入金额": ["研发投入", "研发支出", "研发投入合计"],
    "研发人员数量": ["研发人员", "研发人员人数", "研发人员数量"],
    "研发人员数量占比": ["研发人员比例", "研发人员占比"],
    "研发投入占营业收入比例": ["研发投入比例", "研发投入占营业收入比重"],
    "环保投入": ["环境保护投入", "环保资金投入", "环保投入合计"],
    "环保资本化项目投入": ["环保资本化", "资本化环保投入"],
    "环保费用化投入": ["环保费用化", "费用化环保投入"],
    "综合能源消耗": ["综合能耗", "能源消耗总量", "综合能源消费量"],
    "直接能源消耗": ["直接能耗"],
    "营业收入": ["营业总收入", "主营业务收入"],
    "温室气体排放总量": ["温室气体排放量", "碳排放总量"],
    "排放强度": ["单位产量排放强度", "碳排放强度"],
    "用水": ["用水量", "取水量", "耗水量"],
    "总用水量": ["用水总量", "总取水量"],
}

CONDITION_TERMS = {
    # 每个缺口只补与条件直接相关的词，避免所有关系共用“范围/定义”这类宽泛词。
    "主体": ["公司全称", "报告主体", "合并范围", "母公司"],
    "期间": ["报告期间", "本期", "上期", "年度列"],
    "定义": ["是指", "包括", "定义为", "统计口径"],
    "范围": ["统计范围", "合并报表范围", "母公司", "组织边界"],
    "单位": ["单位：元", "单位：万元", "人民币", "亿元"],
    "组成完整": ["合计", "分项", "构成", "其他"],
    "互不重叠": ["其中", "不重复", "互斥", "不包括"],
    "公式": ["分母", "占比", "强度", "除以"],
}

COUNTER_TERMS = {
    # 反证检索必须和指标名一起出现；只搜“反证/例外”会得到大量无关段落。
    "主体": ["母公司", "不同主体", "子公司", "合并范围"],
    "期间": ["重述", "更正", "上期", "本期", "不同年度"],
    "定义": ["不包括", "仅包括", "定义不同", "口径不同"],
    "范围": ["未纳入", "不包括", "母公司", "组织边界", "例外"],
    "单位": ["千元", "万元", "亿元", "换算", "脚注"],
    "组成完整": ["其他", "未列示", "分项不全", "合计不等"],
    "互不重叠": ["重复", "包含", "重叠", "已计入"],
    "公式": ["分母不同", "非营业收入", "调整", "不可比"],
}


def knowledge_enabled() -> bool:
    """显式环境变量关闭规则依据，用于开/关知识消融；默认开启。"""
    return os.getenv("CONNECTIVITY_DISABLE_KNOWLEDGE", "0").lower() not in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def load_rule_basis(path: str | None = None) -> dict:
    """读取规则依据索引；文件缺失时返回空表，不让整次运行失败。"""
    target = Path(path) if path else RULE_BASIS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": KNOWLEDGE_VERSION, "rules": [], "load_error": "规则依据索引不可读"}
    rules = [item for item in data.get("rules", []) if item.get("basis_id") and item.get("statement")]
    data["rules"] = rules
    return data


def _check_text(check) -> str:
    conditions = " ".join(item.name for item in check.conditions if item.status != "supported")
    return " ".join([check.rule_id, check.title, check.topic, check.mapping_type, conditions])


def rule_basis_for(check, limit: int = 4, enabled: bool | None = None) -> list[dict]:
    """按规则适用条件和关系文本排序；检索命中不等于当前业务当然适用。

    返回的 verification_status 决定 UI 能否显示具体条款；unverified 条目
    只能提示“应检查什么”，不能写成准则原文或条号。
    """
    if enabled is None:
        enabled = knowledge_enabled()
    if not enabled:
        return []
    words = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Z]{2,}-\d{3}", _check_text(check)))
    hits = []
    for rule in load_rule_basis().get("rules", []):
        matched = []
        score = 0
        if check.rule_id in (rule.get("applicability") or []):
            score += 4
            matched.append(check.rule_id)
        for condition in rule.get("conditions") or []:
            if condition in _check_text(check):
                score += 2
                matched.append(condition)
        for word in words:
            if word in rule.get("statement", "") or word in rule.get("internal_name", ""):
                score += 1
                matched.append(word)
        if score <= 0:
            continue
        source = rule.get("source") or {}
        hits.append({
            "basis_id": rule.get("basis_id"), "internal_name": rule.get("internal_name"),
            "statement": rule.get("statement"), "source": source,
            "applicability": rule.get("applicability") or [], "conditions": rule.get("conditions") or [],
            "counterexample": rule.get("counterexample", ""),
            "verification_status": rule.get("verification_status", "unverified"),
            "verified_at": rule.get("verified_at", ""), "note": rule.get("note", ""),
            "matched_terms": list(dict.fromkeys(matched))[:8], "score": score,
            "retrieval_id": "RUL-" + hashlib.sha256(
                f"{check.check_id}|{rule.get('basis_id')}".encode()).hexdigest()[:10].upper(),
            "applicability_note": "检索命中仅表示条目相关；须由原文和本条关系条件确认适用",
        })
    hits.sort(key=lambda item: (-item["score"], item["basis_id"]))
    return hits[:limit]


def _clean_label(label: str) -> str:
    """去掉行次、括号和单位后缀，保留可读指标名。"""
    text = re.sub(r"^[（(]?[一二三四五六七八九十\d]+[）)、.．]\s*", "", str(label or ""))
    text = re.sub(r"[（(](?:元|万元|亿元|人|%|％)[）)]$", "", text)
    text = re.sub(r"\s+", "", text)
    return text[:40]


def metric_names(check, run) -> list[str]:
    """成员指标名、受控直接指标与同义词；别名只用于召回。"""
    names = []
    for member in check.members:
        row = next((item for item in run.occurrences if item.occurrence_id == member.occurrence_id), None)
        if row is None:
            continue
        label = _clean_label(row.label)
        if label:
            names.append(label)
        direct = direct_metric(row.label)
        if direct:
            names.append(direct)
    for name in list(names):
        names.extend(METRIC_SYNONYMS.get(name, []))
    if not names:
        names.append(_clean_label(check.title.split("·")[0]) or check.title[:30])
    return list(dict.fromkeys(name for name in names if name))[:8]


def _query_id(check_id: str, kind: str, terms: Iterable[str]) -> str:
    seed = f"{check_id}|{kind}|{'|'.join(terms)}"
    return "Q-" + hashlib.sha256(seed.encode()).hexdigest()[:10].upper()


def build_query_plan(run, checks: list) -> dict:
    """为每个缺口生成指标级 query；相同 query 只检索一次并记录共享关系。

    共享只发生在指标名与缺口条件都相同的 query 上；不会把 13 条不同关系
    合并成一条事项级宽泛词。查询文本用于展示，terms 用于逐词命中。
    """
    registry: dict[str, dict] = {}
    per_check = {}
    for check in checks:
        names = metric_names(check, run)
        selected = {}
        missing = [item.name for item in check.conditions if item.status != "supported"]
        # 成员很多时只取前四个指标名，避免 query 变成一条宽泛长句。
        for name in names[:4]:
            for condition in missing:
                support_terms = [name, *CONDITION_TERMS.get(condition, [condition])]
                counter_terms = [name, *COUNTER_TERMS.get(condition, ["反证", "例外"])]
                for kind, terms in (("support", support_terms), ("counter", counter_terms)):
                    key = "|".join(terms)
                    query_id = _query_id(check.check_id, kind, terms)
                    if key not in registry:
                        registry[key] = {"query_id": query_id, "kind": kind, "terms": terms,
                                         "text": f"{run.company} {run.period} " + " ".join(terms),
                                         "condition": condition, "check_ids": [check.check_id],
                                         "specificity": "metric_condition"}
                    elif check.check_id not in registry[key]["check_ids"]:
                        registry[key]["check_ids"].append(check.check_id)
                    selected[registry[key]["query_id"]] = registry[key]
            if not missing:
                terms = [name, "定义", "范围", "本期"]
                key = "|".join(terms)
                query_id = _query_id(check.check_id, "support", terms)
                if key not in registry:
                    registry[key] = {"query_id": query_id, "kind": "support", "terms": terms,
                                     "text": f"{run.company} {run.period} " + " ".join(terms),
                                     "condition": "补充核验", "check_ids": [check.check_id],
                                     "specificity": "metric_context"}
                elif check.check_id not in registry[key]["check_ids"]:
                    registry[key]["check_ids"].append(check.check_id)
                selected[registry[key]["query_id"]] = registry[key]
        per_check[check.check_id] = {
            "check_id": check.check_id, "metrics": names, "missing_conditions": missing,
            "query_ids": list(selected),
            "queries": list(selected.values()),
        }
    shared = [item for item in registry.values() if len(item["check_ids"]) > 1]
    return {"schema_version": RETRIEVAL_VERSION, "check_plans": per_check,
            "queries": list(registry.values()), "query_count": len(registry),
            "shared_query_count": len(shared), "shared_queries": shared[:20],
            "dedupe_note": "按指标名+缺口条件去重；共享 query 仍保留指标名，不退化为事项级宽泛词"}


def _cached_pages(root: Path, run) -> dict[str, list[dict]]:
    """读取已解析页缓存；没有缓存时只用本次 occurrence，不联网。"""
    cached = {}
    for document in run.documents:
        path = root / "backend/runtime/connectivity/extraction" / f"{document.file_sha256}-{PARSER_CACHE_VERSION}.json"
        if path.is_file():
            try:
                cached[document.document_id] = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
    return cached


def _score_line(text: str, queries: list[dict]) -> tuple[int, int, list[str]]:
    """支持与反证分开计分；query 的指标名和条件词都必须至少命中一个。

    只命中一个通用条件词（例如只出现“范围”）不足以召回，防止 13 条关系
    反复拿到同一段宽泛文本；命中两个以上词才计入分数。
    """
    compact = re.sub(r"\s+", "", text)
    support = counter = 0
    hit_ids = []
    for query in queries:
        terms = [term for term in query["terms"] if term]
        if not terms:
            continue
        hits = sum(1 for term in terms if re.sub(r"\s+", "", term) in compact)
        if hits < 2 and len(terms) > 1:
            continue
        weight = hits * (2 if query["kind"] == "support" else 3)
        if query["kind"] == "support":
            support += weight
        else:
            counter += weight
        if hits:
            hit_ids.append(query["query_id"])
    return support, counter, hit_ids


def retrieve_targeted_pages(root: Path, run, checks: list, round_number: int = 1, per_check: int = 8) -> list[dict]:
    """按定向 query 搜索已解析页并补充文字证据；命中/未命中都留记录。

    缓存只读登记哈希对应的解析结果，不接受模型传入路径或联网地址；
    新增片段标记为 text_only，不猜数值、单位或年度归属。
    """
    if round_number not in (1, 2):
        return []
    plan = build_query_plan(run, checks)
    cached = _cached_pages(root, run)
    existing = {row.occurrence_id: row for row in run.occurrences}
    tasks = []
    for check in checks:
        item = plan["check_plans"].get(check.check_id) or {}
        queries = item.get("queries") or []
        if not queries:
            continue
        member_pages = {row.document_id: row.pdf_page for row in run.occurrences
                        if row.occurrence_id in {member.occurrence_id for member in check.members}}
        ranked, scanned, failed = [], {}, []
        seen_text = set()
        for document_id, pages in cached.items():
            scanned[document_id] = []
            for page in pages:
                if page.get("error"):
                    failed.append({"document_id": document_id, "page": page.get("page"), "reason": page["error"]})
                    continue
                scanned[document_id].append(page.get("page"))
                lines = page.get("lines", [])
                for index, line in enumerate(lines):
                    support, counter, hit_ids = _score_line(line.get("text", ""), queries)
                    if not (support or counter):
                        continue
                    context = "\n".join(row["text"] for row in lines[max(0, index - 2):index + 3]
                                        if row.get("side") == line.get("side"))
                    key = (document_id, page.get("page"), re.sub(r"\s+", "", context))
                    if key in seen_text:
                        continue
                    if any(row.document_id == document_id and row.pdf_page == page.get("page")
                           and context in row.context for row in run.occurrences):
                        continue
                    seen_text.add(key)
                    nearby = page.get("page") == member_pages.get(document_id)
                    ranked.append(((counter > 0, support + counter, nearby), DisclosureOccurrence(
                        occurrence_id=f"{document_id}-{page.get('page')}-SUP-{index}",
                        document_id=document_id, pdf_page=max(1, int(page.get("page") or 1)),
                        bbox=line.get("bbox", []), page_width=page.get("width", 0), page_height=page.get("height", 0),
                        label=line.get("text", "")[:180], row_header=line.get("text", ""), context=context,
                        quality="text_only", quality_reason="按具体关系定向补查的原文；未绑定数值字段",
                        topic=check.topic)))
        # 也把现有 occurrence 中命中 query 的片段计入任务，避免误以为只搜索了缓存页。
        existing_hits = []
        for row in run.occurrences:
            support, counter, hit_ids = _score_line(row.context, queries)
            if support or counter:
                existing_hits.append(row.occurrence_id)
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        added, counter_added = [], 0
        for score, occurrence in ranked:
            if len(added) >= per_check:
                break
            if occurrence.occurrence_id in existing:
                continue
            run.occurrences.append(occurrence)
            existing[occurrence.occurrence_id] = occurrence
            added.append(occurrence.occurrence_id)
            if score[0]:
                counter_added += 1
        tasks.append({
            "check_id": check.check_id, "round": round_number, "version": RETRIEVAL_VERSION,
            "queries": queries, "query_ids": item.get("query_ids", []),
            "query_count": len(queries), "dedupe": plan["shared_query_count"],
            "support_hits": len(added), "counter_hits": counter_added,
            "existing_hits": existing_hits[:20], "new_evidence_ids": added,
            "scanned_pages": scanned, "failed_pages": failed,
            "coverage_note": "只搜索登记版本已解析文字；未命中不等于企业未披露",
        })
    return tasks


class DisclosureLike:
    """旧版兼容占位；新代码请直接使用 DisclosureOccurrence。"""

    def __init__(self, **values):
        self.__dict__.update(values)

    def model_dump(self):
        return dict(self.__dict__)
def retrieval_effect(before_checks: list, after_checks: list, occurrences: list,
                     new_evidence_ids: set[str] | None = None) -> dict:
    """统计检索前后真正升级的条件、引文复核数和错误引用率。

    分母是“本次新变为 supported 的条件所带引文”，不是所有历史引文；
    这样能区分“检索命中很多”与“真正让条件升级且引用可回查”。
    """
    before = {check.check_id: {item.name: item.status for item in check.conditions} for check in before_checks}
    after = {check.check_id: {item.name: item.status for item in check.conditions} for check in after_checks}
    found = {row.occurrence_id: row for row in occurrences}
    upgraded_checks, upgraded_conditions = [], []
    citations = invalid = used_new = 0
    for check in after_checks:
        prior = before.get(check.check_id, {})
        changes = []
        for condition in check.conditions:
            if prior.get(condition.name) == "supported" or condition.status != "supported":
                continue
            changes.append(condition.name)
            if condition.evidence:
                citations += len(condition.evidence)
                if not validate_refs(condition.evidence, found):
                    invalid += len(condition.evidence)
                used_new += sum(1 for ref in condition.evidence
                                if new_evidence_ids and ref.occurrence_id in new_evidence_ids)
        if changes:
            upgraded_checks.append(check.check_id)
            upgraded_conditions.extend({"check_id": check.check_id, "condition": name} for name in changes)
    return {
        "version": RETRIEVAL_VERSION,
        "checks_with_upgraded_conditions": len(upgraded_checks),
        "upgraded_conditions": upgraded_conditions,
        "supported_conditions_before": sum(1 for values in before.values() for value in values.values() if value == "supported"),
        "supported_conditions_after": sum(1 for values in after.values() for value in values.values() if value == "supported"),
        "new_evidence_used_in_upgrades": used_new,
        "citations_checked": citations,
        "invalid_citations": invalid,
        "erroneous_citation_rate": (invalid / citations) if citations else 0.0,
        "note": "升级只表示原文条件由 unknown/conflicting 变为 supported；不等于专业结论成立",
    }


def rule_basis_payload(check, store: dict | None = None) -> dict:
    """给模型和导出侧的统一规则依据结构；未核验项不得写成准则原文。"""
    hits = rule_basis_for(check)
    payload = {
        "basis_version": KNOWLEDGE_VERSION,
        "enabled": knowledge_enabled(),
        "hits": hits,
        "boundary": "规则依据只约束应检查什么，不证明企业披露正确；未核验条目不得引用具体条款。",
    }
    if store is not None:
        store.setdefault("rule_basis", []).append({"check_id": check.check_id, **payload})
    return payload


def knowledge_ablation(check) -> dict:
    """同一关系开/关规则依据的消融记录；只比较检索命中，不冒充模型质量差异。"""
    on = rule_basis_for(check, limit=10, enabled=True)
    off = rule_basis_for(check, limit=10, enabled=False)
    return {
        "check_id": check.check_id,
        "enabled_hit_count": len(on), "disabled_hit_count": len(off),
        "enabled_basis_ids": [hit["basis_id"] for hit in on],
        "verified_hit_count": sum(1 for hit in on if hit.get("verification_status", "").startswith("verified")),
        "unverified_hit_count": sum(1 for hit in on if not hit.get("verification_status", "").startswith("verified")),
        "boundary": "这是检索消融，不是模型效果实验；是否改变判断须由开启/关闭两次真实运行对照",
    }
