"""财务穿透层专项测试：正例与反例都要能挡住“把可能说成已确认”。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.financial_impact import accounting_mapping, impact_analysis, impact_graph, impact_verifier
from backend.app.financial_impact.financial_linker import Index, Unit, filter_unit, rrf, search, search_counter
from backend.app.financial_impact.financial_notes import _header_row, _semantics, parse_notes
from backend.app.financial_impact.models import (Amount, AmountNature, FinancialItem, ImpactRelation,
                                                 RelationGrade, Stage, SustainabilityEvent)
from backend.app.financial_impact.sustainability_events import build_event, collect_candidates
from backend.app.financial_impact.textutil import detect_stage, project_name, strip_leading_verbs, to_amounts

ROOT = Path(__file__).resolve().parents[2]


class Doc:
    company = "测试企业"
    company_id = "000001"
    period = "2025"
    document_id = "DOC"
    file_sha256 = "hash"
    report_type = "ESG"


def page(number: int, text: str) -> dict:
    return {"page": number, "text": text, "blocks_detail": [{"text": text, "bbox": [10, 20, 500, 60]}], "tables": []}


def event(**kwargs) -> SustainabilityEvent:
    base = dict(event_id="EV-T", company="测试企业", project_name="羧甲基纤维素改造项目", period="2025",
                stage=Stage.EXECUTING, amount_nature=AmountNature.INVESTMENT_INCURRED,
                document_id="DOC", report_type="ESG", pdf_page=10, quote="本期投入1亿元", scope="合并",
                amounts=[Amount(raw="1", value="1", unit="亿元", dimension="money", normalized="100000000",
                                nature=AmountNature.INVESTMENT_INCURRED)])
    base.update(kwargs)
    return SustainabilityEvent(**base)


def item(**kwargs) -> FinancialItem:
    base = dict(item_id="FI-T", company="测试企业", table_title="在建工程·羧甲基纤维素改造项目",
                row_header="羧甲基纤维素改造项目", column_header="本期增加金额",
                value_semantics=AmountNature.PERIOD_INCREASE, raw_value="100,000,000.00",
                value="100000000", unit="元", normalized="100000000", period="2025", scope="合并",
                document_id="DOC", pdf_page=154, quote="羧甲基纤维素改造项目 | 100,000,000.00",
                page_verified=True)
    base.update(kwargs)
    return FinancialItem(**base)


def treatment(status="supported"):
    treatments, _ = accounting_mapping.map_events([event()])
    value = treatments[0]
    value.status = status
    return value


SUPPORT = [{"filter_ok": True, "quote": "羧甲基纤维素改造项目 本期增加", "pdf_page": 154}]


# ---------- 任务2：事项抽取 ----------

def test_承诺不得写成已发生支出():
    text = "公司计划在未来三年投资5亿元建设绿色工厂项目。"
    events = collect_candidates([page(3, text)], Doc())
    assert events, "应识别出计划类事项"
    assert events[0].stage == Stage.PLANNED
    assert events[0].amount_nature == AmountNature.PLANNED_INVESTMENT
    assert events[0].stage != Stage.SETTLED


def test_项目名只取原文明确写出的名称():
    assert project_name("实施《绿色低碳改造项目》，投入1亿元。") == "绿色低碳改造项目"
    assert project_name("本期营业成本为294亿元。") == ""
    assert strip_leading_verbs("配套建设成品酒包装及智能仓储配送一体化项目") == "成品酒包装及智能仓储配送一体化项目"


def test_阶段识别区分在建与已建成():
    assert detect_stage("项目已开工建设") == Stage.EXECUTING
    assert detect_stage("项目已建成投产") == Stage.COMPLETED
    assert detect_stage("拟投资建设") == Stage.PLANNED


def test_缺少项目名时列入缺失字段():
    built = build_event(Doc(), page(8, "本期环保投入1.8亿元。"), "本期环保投入1.8亿元。")
    assert "project_name" in built.missing_fields
    assert built.page_verified is True


def test_非环境事项不得混入():
    events = collect_candidates([page(9, "公司2025年现金分红总额为10亿元，每10股派发现金红利3元。")], Doc())
    assert events == []


# ---------- 任务3：附注解析 ----------

def test_金额语义按列名判定而不是按数值猜():
    assert _semantics("预算数") == AmountNature.BUDGET
    assert _semantics("期末余额") == AmountNature.CLOSING_BALANCE
    assert _semantics("本期增加金额") == AmountNature.PERIOD_INCREASE
    assert _semantics("本期转入固定资产金额") == AmountNature.TRANSFER_OUT
    assert _semantics("工程累计投入占预算比例") == AmountNature.NONE


def test_表头必须含语义列():
    rows = [["项目", "2025年金额", "2024年金额"], ["营业收入", "100", "90"]]
    assert _header_row(rows) is None
    rows = [["项目名称", "预算数", "期初余额", "本期增加金额", "期末余额"],
            ["某项目", "100", "20", "30", "50"]]
    assert _header_row(rows) == 0


def test_附注保留行列语义与坐标():
    pages = [{
        "page": 154, "text": "单位：元 在建工程",
        "blocks_detail": [{"text": "在建工程", "bbox": [70, 60, 120, 80]}],
        "tables": [{"bbox": [60, 90, 500, 200],
                    "data": [["项目名称", "预算数", "本期增加金额", "期末余额"],
                             ["绿色改造项目", "1,000,000.00", "200,000.00", "800,000.00"]],
                    "cells": [[None, None, None, None], [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]]]}],
    }]
    items, receipt = parse_notes(pages, Doc())
    assert receipt["items"] == 3
    budget = next(value for value in items if value.value_semantics == AmountNature.BUDGET)
    assert budget.row_header == "绿色改造项目"
    assert budget.table_title == "在建工程"
    assert budget.bbox == [5.0, 6.0, 7.0, 8.0]
    assert budget.normalized == "1000000.00"


# ---------- 任务5：混合检索 ----------

def make_index():
    units = [
        Unit("ESG#1#0", "ESG", "ESG", 1, "配套建设成品酒包装及智能仓储配送一体化项目，冷却水回用率90%"),
        Unit("AR#102#0", "AR", "AR", 102, "成品酒包装及智能仓储配送一体化项目预算数8596655000元"),
        Unit("AR#200#0", "AR", "AR", 200, "2023年另一基地包装项目本期增加金额1000000元"),
        Unit("AR#201#0", "AR", "AR", 201, "污水处理厂本期增加金额200000元"),
    ]
    return Index(units)


def test_同一项目的不同名称可通过别名召回():
    found = search(event(project_name="包装及智能仓储配送一体化项目", aliases=["成品酒包装及智能仓储配送一体化项目"]),
                   [treatment()], make_index())
    assert any(candidate["pdf_page"] == 102 for candidate in found["candidates"])
    assert found["receipt"]["note"].startswith("相似度只决定核查顺序")


def test_年度错配被过滤():
    target = Unit("AR#200#0", "AR", "AR", 200, "成品酒包装及智能仓储配送一体化项目2023年本期增加")
    ok, reasons = filter_unit(event(), target)
    assert ok is False
    assert any("期间不匹配" in reason for reason in reasons)


def test_合并范围错配被过滤():
    target = Unit("AR#300#0", "AR", "AR", 300, "母公司报表 羧甲基纤维素改造项目期末余额")
    ok, reasons = filter_unit(event(), target)
    assert ok is False
    assert any("范围不匹配" in reason for reason in reasons)


def test_同名不同主体被过滤():
    target = Unit("AR#301#0", "AR", "AR", 301, "某某分公司羧甲基纤维素改造项目本期增加")
    ok, reasons = filter_unit(event(subject="梅山基地"), target)
    assert ok is False
    assert any("主体不匹配" in reason for reason in reasons)


def test_无向量模型时明确降级():
    found = search(event(), [treatment()], make_index(), allow_vector=True)
    assert found["receipt"]["vector"]["status"] in {"degraded_no_vector", "vector_enabled"}
    if found["receipt"]["vector"]["status"] == "degraded_no_vector":
        assert "未安装" in found["receipt"]["vector"]["reason"] or "不可用" in found["receipt"]["vector"]["reason"]


def test_rrf按名次融合而不是分数相加():
    fused = rrf([(1, 99.0), (2, 1.0)], [(2, 0.9), (3, 0.8)])
    order = [index for index, _score in fused]
    assert order[0] == 2
    assert order[1] in {1, 3}


def test_反证必须与项目同句且带否定():
    index = Index([
        Unit("AR#1#0", "AR", "AR", 1, "羧甲基纤维素改造项目尚未开工，不存在本期投入"),
        Unit("AR#2#0", "AR", "AR", 2, "其他项目尚未完工，与本公司羧甲基纤维素改造项目无关"),
    ])
    counter = search_counter(event(), index)
    assert counter and counter[0]["pdf_page"] == 1
    assert all("羧甲基纤维素改造项目" in entry["quote"] for entry in counter)


# ---------- 任务8：九项条件与等级 ----------

def test_九项条件全部成立才是A级():
    relation = impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT)
    assert relation.grade == RelationGrade.A
    assert {check.key for check in relation.conditions} == {
        "identity", "period", "scope", "accounting_conditions", "comparability",
        "cross_reference", "evidence", "no_counter_evidence", "reconciliation"}


def test_预算数不能与已发生投入勾稽():
    relation = impact_verifier.build_relation(
        event(), item(value_semantics=AmountNature.BUDGET, column_header="预算数"), treatment(), support=SUPPORT)
    assert relation.grade != RelationGrade.A
    comparability = next(check for check in relation.conditions if check.key == "comparability")
    assert comparability.status == "false"


def test_期末余额不得当作当期投入():
    relation = impact_verifier.build_relation(
        event(), item(value_semantics=AmountNature.CLOSING_BALANCE, column_header="期末余额"), treatment(),
        support=SUPPORT)
    assert relation.numeric_reconciliation["status"] == "not_comparable"
    assert relation.grade != RelationGrade.A


def test_期间不一致判为不兼容():
    relation = impact_verifier.build_relation(event(), item(period="2023"), treatment(), support=SUPPORT)
    assert relation.grade == RelationGrade.INCOMPATIBLE
    period = next(check for check in relation.conditions if check.key == "period")
    assert period.status == "false"


def test_合并范围不一致判为不兼容():
    relation = impact_verifier.build_relation(event(), item(scope="母公司"), treatment(), support=SUPPORT)
    assert relation.grade == RelationGrade.INCOMPATIBLE


def test_项目名不同判为不兼容():
    relation = impact_verifier.build_relation(
        event(), item(table_title="在建工程·污水处理厂", row_header="污水处理厂项目",
                      quote="污水处理厂项目 | 100,000,000.00"), treatment(), support=SUPPORT)
    assert relation.grade == RelationGrade.INCOMPATIBLE
    identity = next(check for check in relation.conditions if check.key == "identity")
    assert identity.status == "false"


def test_汇总行不能当作同名项目():
    relation = impact_verifier.build_relation(
        event(), item(row_header="合计", quote="合计 | 100,000,000.00"), treatment(), support=SUPPORT)
    identity = next(check for check in relation.conditions if check.key == "identity")
    assert identity.status == "unknown"
    assert relation.grade != RelationGrade.A


def test_会计前提未验证不能给A():
    relation = impact_verifier.build_relation(event(), item(), treatment(status="hypothesis"), support=SUPPORT)
    assert relation.grade in {RelationGrade.B, RelationGrade.C}
    assert relation.grade != RelationGrade.A


def test_存在反证即降为冲突并保留原等级():
    counter = [{"quote": "羧甲基纤维素改造项目尚未开工", "pdf_page": 20}]
    relation = impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT, counter=counter)
    assert relation.grade == RelationGrade.CONTRADICTED
    assert relation.counter


def test_反证推翻后等级变化写入历史():
    previous = ImpactRelation(relation_id="IR-1", event_id="EV-T", grade=RelationGrade.B, conditions=[])
    relation = impact_verifier.build_relation(
        event(), item(), treatment(), support=SUPPORT,
        counter=[{"quote": "项目未实施", "pdf_page": 21}], previous=previous)
    assert relation.history and relation.history[-1]["from"] == "B"


def test_找不到财务项目只记D不推断披露不实():
    relation = impact_verifier.build_relation(event(), None, treatment(), support=SUPPORT)
    assert relation.grade in {RelationGrade.C, RelationGrade.D}
    assert "不推断企业未披露" in relation.explanation or "待补证" in relation.explanation


def test_无任何候选证据时为D():
    relation = impact_verifier.build_relation(event(), None, treatment(), support=[])
    assert relation.grade == RelationGrade.D


def test_等级不是概率():
    assert "不代表模型正确概率" in impact_verifier.GRADE_MEANING
    assert "不构成审计结论" in impact_verifier.GRADE_MEANING


def test_金额勾稽仅在性质可比时执行():
    result = impact_verifier.reconcile(event(), item(value_semantics=AmountNature.BUDGET))
    assert result["status"] == "not_comparable"
    result = impact_verifier.reconcile(event(), item())
    assert result["status"] == "reconciled"


def test_金额差异记为difference而不是错报():
    result = impact_verifier.reconcile(event(amounts=[Amount(raw="2", value="2", unit="亿元", dimension="money",
                                                             normalized="200000000",
                                                             nature=AmountNature.INVESTMENT_INCURRED)]), item())
    assert result["status"] == "difference"
    assert "差异不等于错报" in result["note"]


# ---------- 任务6：图谱 ----------

def test_图谱路径按顺序扩展且不跨层():
    relations = [impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT)]
    graph = impact_graph.build([event()], [item()], [treatment()], relations)
    types = {node["type"] for node in graph["nodes"]}
    assert {"sustainability_event", "business_project", "accounting_treatment", "financial_item"} <= types
    for path in graph["paths"]:
        assert path["edges"][0] == "describes"
        assert "supported_by" in path["edges"] or "accounting_path" in path["edges"]


def test_未验证路径不会升级为已验证():
    relation = impact_verifier.build_relation(event(), item(), treatment(status="hypothesis"), support=SUPPORT)
    graph = impact_graph.build([event()], [item()], [treatment()], [relation])
    path_edges = [edge for edge in graph["edges"]
                  if edge["type"] in {"supported_by", "contradicted_by", "unresolved"}
                  and edge["source"].startswith("EV-T:")]
    assert path_edges and all(not edge["verified"] for edge in path_edges)


# ---------- 任务9：当期与预期影响 ----------

def test_预期影响三类分开():
    planned = event(event_id="EV-P", stage=Stage.PLANNED,
                    amount_nature=AmountNature.BUDGET,
                    amounts=[Amount(raw="5", value="5", unit="亿元", dimension="money",
                                    normalized="500000000", nature=AmountNature.BUDGET)])
    qualitative = event(event_id="EV-Q", stage=Stage.STRATEGY, amount_nature=AmountNature.NONE, amounts=[])
    analysis = impact_analysis.build([planned, qualitative], [], [], [])
    kinds = {entry["kind"] for entry in analysis["expected"]}
    assert "disclosed_quantified" in kinds
    assert "qualitative_only" in kinds
    assert "净利润" in analysis["note"]


def test_只有实物绩效时不代算金额():
    performance = event(event_id="EV-E", stage=Stage.PLANNED, amount_nature=AmountNature.PERFORMANCE,
                        amounts=[Amount(raw="25.85", value="25.85", unit="万吨标准煤", dimension="energy",
                                        normalized="258500", nature=AmountNature.PERFORMANCE)],
                        performance=[Amount(raw="25.85", value="25.85", unit="万吨标准煤", dimension="energy",
                                            normalized="258500", nature=AmountNature.PERFORMANCE)])
    analysis = impact_analysis.build([performance], [], [], [])
    entry = analysis["expected"][0]
    assert entry["kind"] == "scenario_trial"
    assert entry["amount"]["value"] == ""
    assert "用户输入假设" in entry["note"]


def test_当期影响只收AB级且阶段在实施之后():
    relations = [impact_verifier.build_relation(event(), item(), treatment(), support=SUPPORT)]
    analysis = impact_analysis.build([event()], relations, [treatment()], [item()])
    assert analysis["current"] and analysis["current"][0]["grade"] == "A"
    planned = event(event_id="EV-P2", stage=Stage.PLANNED)
    analysis = impact_analysis.build([planned], [ImpactRelation(relation_id="IR-X", event_id="EV-P2",
                                                               grade=RelationGrade.A, conditions=[])], [], [])
    assert analysis["current"] == []


# ---------- 规则库 ----------

def test_规则库有来源且未核验的标pending():
    rules = accounting_mapping.load_rules()
    assert len(rules) >= 10
    for rule in rules:
        assert rule.basis and rule.basis[0].get("title")
        assert rule.basis[0].get("issuer")
    assert any(rule.verification == "pending_human_review" for rule in rules)


def test_规则库不伪造条文号():
    raw = json.loads((ROOT / "backend/app/financial_impact/accounting_rules.json").read_text(encoding="utf-8"))
    for rule in raw["rules"]:
        for basis in rule["basis"]:
            assert "第" not in str(basis.get("locator", "")) or "条" not in str(basis.get("locator", ""))
