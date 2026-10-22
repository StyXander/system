"""第三轮真实无关补证复现及指标锚点回归；全部离线。"""
import json

import pytest

from app.connectivity_extraction import PARSER_CACHE_VERSION
from app.connectivity_retrieval import _local_line_context, _score_line, retrieve_targeted_pages
from app.connectivity_schemas import ReportDocument
from test_connectivity_hybrid import bridge_run


def query(anchor, *conditions, kind="support"):
    return {"query_id": "Q-FOCUS", "kind": kind, "terms": [anchor, *conditions]}


@pytest.mark.parametrize("text,terms", [
    ("其他长期职工福利，是指除短期薪酬、离职后福利、辞退福利之外所有的职工薪酬，包括长期带薪",
     ["总用水量", "是指", "包括", "定义为", "统计口径"]),
    ("约定2025 年内公司在财务公司每日存款余额最高不超过人民币550 亿元，2025 年内贷款和授信每日余额",
     ["耗水强度", "单位：元", "单位：万元", "人民币", "亿元"]),
    ("最高不超过人民币100 亿元。", ["取水强度", "单位：元", "单位：万元", "人民币", "亿元"]),
])
def test_observed_unrelated_supplements_no_longer_match_two_generic_terms(text, terms):
    # 首批真实SUP原文：旧逻辑只看总命中数，会把两个通词当指标证据。
    legacy_hits = sum(term.replace(" ", "") in text.replace(" ", "") for term in terms)
    assert legacy_hits >= 2
    assert _score_line(text, [query(terms[0], *terms[1:])]) == (0, 0, [])


def test_metric_definition_support_and_explicit_counter_both_retrieved():
    support = query("研发投入", "是指", "包括")
    counter = query("研发投入", "不包括", "口径不同", kind="counter")
    assert _score_line("研发投入是指本期研究开发活动支出，包括费用化与资本化部分。", [support])[0] > 0
    assert _score_line("研发投入不包括联营企业资本化支出，统计口径不同。", [counter])[1] > 0
    assert _score_line("本期不包括联营企业，统计口径不同。", [counter]) == (0, 0, [])
    assert _score_line("研发投入156000万元。", [support, counter]) == (0, 0, [])


def test_alias_recalls_split_metric_but_not_unrelated_expense():
    q = query('研发投入', '不包括', kind='counter')
    assert _score_line('注：不包括联营企业。', [q], '研发支出\n注：不包括联营企业。')[1] > 0
    assert _score_line('研发费用不包括其他费用。', [q]) == (0, 0, [])


def test_tool_hit_survives_context_selection_and_packing():
    from app.connectivity_intelligence import targeted_context, pack_role_context
    from app.connectivity_schemas import DisclosureOccurrence
    run = bridge_run()
    run.occurrences.append(DisclosureOccurrence(occurrence_id='HIT',
        document_id=run.occurrences[0].document_id, pdf_page=90, label='注',
        context='统计口径不包括联营企业。', quality='text_only'))
    event = dict(kind='agent_tool_result', check_id=run.checks[0].check_id,
                 delivered_evidence_ids=['HIT'])
    run.intelligence_trace.append(event)
    rows, tasks = targeted_context(run, run.checks)
    packed = pack_role_context(dict(occurrences=rows,
        candidate_checks=[c.model_dump() for c in run.checks], collaboration_history=[event]))
    assert 'HIT' in {r['occurrence_id'] for r in packed['occurrences']}
    assert any('联营企业' in b['text'] for b in packed['evidence_blocks'])


@pytest.mark.parametrize("anchor", ["", "该指标", "本指标", "合计", "其他", "一", "GDP", "全国研发投入"])
def test_generic_or_macro_anchor_cannot_create_business_evidence(anchor):
    text = f"{anchor}是指相关统计范围，包括企业项目。"
    assert _score_line(text, [query(anchor, "是指", "包括")]) == (0, 0, [])


def test_macro_line_does_not_become_company_metric_evidence():
    assert _score_line("全国环保投入统计范围包括各省企业。", [query("环保投入", "统计范围", "包括")]) == (0, 0, [])


def test_only_short_local_context_can_anchor_split_footnote():
    note = "注：不包括联营企业资本化支出。"
    q = query("研发投入", "不包括", kind="counter")
    assert _score_line(note, [q], "研发投入总额\n" + note)[1] > 0
    assert _score_line(note, [q], "研发投入总额\n" + "其他章节\n" * 8 + note) == (0, 0, [])
    assert _score_line(note, [q], "研发投入总额" + "其他说明" * 160 + note) == (0, 0, [])


def test_missing_column_metadata_does_not_join_unlocated_or_other_column_text():
    lines = [{"text": "研发投入", "bbox": [10, 10, 100, 20]},
             {"text": "注：不包括联营企业。", "bbox": [300, 10, 500, 20]}]
    assert _local_line_context(lines, 1) == lines[1]["text"]
    assert _local_line_context([{"text": "研发投入"}, {"text": "注：不包括联营企业。"}], 1) == "注：不包括联营企业。"
    lines[1]["bbox"] = [10, 21, 200, 31]
    assert "研发投入" in _local_line_context(lines, 1)


def test_cached_same_column_footnote_retained_and_other_column_anchor_rejected(tmp_path):
    run = bridge_run()
    doc_id = run.occurrences[0].document_id
    doc = ReportDocument(document_id=doc_id, case_id="SYN", company_id="SYN", company="合成企业",
        report_type="AR", period="2025", file_sha256="a" * 64, source_url="https://example.invalid/synthetic")
    run.documents = [doc]
    lines = [
        {"text": "环保投入", "side": 0, "bbox": [10, 10, 220, 20]},
        {"text": "注：统计范围不包括联营企业。", "side": 0, "bbox": [10, 21, 220, 31]},
        {"text": "其他长期职工福利，是指相关职工薪酬，包括长期带薪缺勤。", "side": 1, "bbox": [300, 10, 550, 20]},
    ]
    directory = tmp_path / "backend/runtime/connectivity/extraction"
    directory.mkdir(parents=True)
    cache = directory / f"{doc.file_sha256}-{PARSER_CACHE_VERSION}.json"
    cache.write_text(json.dumps([{"page": 70, "width": 595, "height": 842, "lines": lines}]), encoding="utf-8")
    tasks = retrieve_targeted_pages(tmp_path, run, run.checks)
    added = [row for row in run.occurrences if "-SUP-" in row.occurrence_id]
    assert any(row.label.startswith("注：统计范围") for row in added)
    assert not any("长期职工福利" in row.context for row in added)
    assert tasks[0]["counter_hits"] > 0
    assert all(row.quality == "text_only" and row.value is None for row in added)
