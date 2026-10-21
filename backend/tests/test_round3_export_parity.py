"""第三轮验收：六级统计、逐条AI判定与数字/引文的真实反例。"""
from io import BytesIO
import importlib.util
from pathlib import Path

from docx import Document
import pytest

from app.connectivity_schemas import (AIAnalysis, ConnectivityRun, DisclosureOccurrence, ExtractionExclusion,
    EvidenceRef, RelationshipCheck, RelationshipMember)
from app.connectivity_overview import build_overview

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/verify_round3_outputs.py'
spec = importlib.util.spec_from_file_location('round3_outputs', SCRIPT)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


@pytest.fixture
def saved_run():
    # 每一档均有关系，避免正式零项掩盖“条件试算被计入正式”的缺陷。
    source = DisclosureOccurrence(occurrence_id='O1', document_id='AR', pdf_page=1,
        label='研发投入金额', value='100', unit='万元', context='本期研发投入金额100万元，统计范围待核实。')
    checks = []
    for index, (conclusion, criteria, calculation) in enumerate([
        ('formal_consistent', 'supported', 'consistent'),
        ('assumption_compatible', 'unknown', 'not_comparable'),
        ('limited_support', 'unknown', 'not_comparable'),
        ('insufficient_basis', 'unknown', 'not_comparable'),
        ('insufficient_basis', 'conflicting', 'not_comparable'),
        ('not_applicable', 'unknown', 'not_applicable'),
    ]):
        checks.append(RelationshipCheck(check_id=f'C{index}', rule_id='EQ-001', title=f'合成核对事项{index}',
            operator='equal', members=[RelationshipMember(occurrence_id='O1', role='left')],
            criteria_status=criteria, calculation_status=calculation, conclusion_level=conclusion))
    analyses = [AIAnalysis(check_id=f'C{i}', verdict=verdict, summary='仍需核实指标的统计范围。',
        reasons=['原文尚未明确说明指标的统计范围。'],
        supporting_evidence=[EvidenceRef(occurrence_id='O1', quote='本期研发投入金额100万元')])
        for i, verdict in enumerate(['lean_consistent', 'plausible_explanation', 'potential_conflict'])]
    run = ConnectivityRun(run_id='SYNTHETIC-PARITY', company='合成验收', period='2025',
        dataset_role='synthetic', documents=[], occurrences=[source], checks=checks, ai_analyses=analyses)
    run.overview = build_overview(run)
    return run


def test_six_bands_and_distinct_ai_verdicts_survive_all_exports(saved_run):
    result = verify.verify_exports(saved_run)
    assert result['passed'], result['problems']
    assert result['levels'] == dict.fromkeys(verify.LEVEL_LABELS, 1)
    assert result['ai_count'] == 3


@pytest.mark.parametrize('kind', ['csv', 'docx'])
def test_export_cannot_collapse_explanation_and_conflict_into_consistency(saved_run, monkeypatch, kind):
    original = verify.export_run

    def corrupt(run, format_name):
        payload, mime = original(run, format_name)
        if format_name == kind:
            if kind == 'csv':
                payload = payload.replace('存在合理解释路径'.encode(), '倾向一致'.encode())
            else:
                document = Document(BytesIO(payload))
                for paragraph in document.paragraphs:
                    if paragraph.text == 'AI分析意见：存在合理解释路径':
                        paragraph.text = 'AI分析意见：倾向一致'
                buffer = BytesIO()
                document.save(buffer)
                payload = buffer.getvalue()
        return payload, mime

    monkeypatch.setattr(verify, 'export_run', corrupt)
    result = verify.verify_exports(saved_run)
    assert not result['passed']
    assert any('AI' in error for error in result['problems'])


def test_duplicate_relationship_identity_is_detected_even_when_total_is_unchanged(saved_run):
    saved_run.checks[-1].check_id = saved_run.checks[0].check_id
    result = verify.inspect_run(saved_run)
    assert any('重复 check_id' in error for error in result['problems'])


def test_fabricated_quote_and_unbound_amount_do_not_pass(saved_run):
    saved_run.ai_analyses[0].supporting_evidence[0].quote = '报告从未披露过的原文'
    saved_run.ai_analyses[1].summary = '研发投入金额为987654321万元。'
    result = verify.inspect_run(saved_run)
    assert any('引用不能逐字回溯' in error for error in result['problems'])
    assert any('未绑定数值' in error for error in result['problems'])


def test_pdf_control_character_does_not_crash_word_or_rewrite_json(saved_run):
    # 宝钢真实 PDF 排除条目中存在 XML1.0 非法控制字符；仅净化 Word 展示。
    saved_run.extraction_exclusions = [ExtractionExclusion(occurrence_id='EX1', document_id='AR',
        pdf_page=2, label='原文\x00控制字符', value='100', unit='万元', reason='无法确定年度')]
    before = saved_run.model_dump(mode='json')
    result = verify.verify_exports(saved_run)
    assert result['passed'], result['problems']
    assert saved_run.model_dump(mode='json') == before


def test_equivalent_unit_conversion_is_not_reported_as_invented_number(saved_run):
    # 数字护栏既拒绝编造，也应允许100万元对应1000000元的可复算表达。
    saved_run.ai_analyses[0].summary = '原文金额按单位换算为1000000元，范围仍待核实。'
    result = verify.inspect_run(saved_run)
    assert not result['problems'], result['problems']
