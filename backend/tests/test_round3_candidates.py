"""候选组合与身份稳定性：只验证真实入口行为，不使用企业答案。"""
from copy import deepcopy
from app.connectivity_pipeline import candidate_checks, structured_candidate_pool, _reference
from app.connectivity_engine import validate_refs
from test_connectivity_conditions_20261017 import row, run_with, doc


def test_stable_unique_ids_survive_multiple_candidate_sources_and_reordering():
    rows=[row(1,'环保投入费用化','60'),row(2,'环保投入资本化','40'),row(3,'环保投入合计','110'),
          row(4,'环保投入费用化','60'),row(5,'环保投入资本化','40')]
    one=candidate_checks(rows,'2025',run=run_with(rows))
    two=candidate_checks(list(reversed(rows)),'2025',run=run_with(rows))
    assert len(one)>1
    assert len({c.check_id for c in one})==len(one)
    def keyed(checks):
        return {(c.rule_id,tuple(sorted((m.role,m.occurrence_id) for m in c.members))):c.check_id for c in checks}
    assert keyed(one)==keyed(two)


def test_bounded_pool_retains_different_caliber_as_narrative_not_equality():
    rows=[]
    for index in range(1,9):
        r=row(index,'环保投入（资本性）' if index%2 else '环保投入（费用性）','100')
        r.document_id='AR' if index%2 else 'ESG'
        rows.append(r)
    pool=structured_candidate_pool(rows,'2025',limit=3)
    assert len(pool)==3
    assert all(p['rule_id']=='NAR-001' and p['status']=='unverified_candidate' for p in pool)
    assert all(m['occurrence_id'] in {r.occurrence_id for r in rows} for p in pool for m in p['members'])


def test_generated_reference_does_not_quote_synthetic_row_prefix():
    r=row(1,'环保投入','100')
    r.context='单位：万元，环保投入 | 100 | 万元。'
    r.row_header='环保投入 | 环保投入 | 100 | 万元'
    ref=_reference(r)
    assert validate_refs([ref],{r.occurrence_id:r})
    assert ref.quote in r.context


def test_numbers_from_one_narrative_sentence_are_not_multi_location_disclosure():
    """宝钢年报PDF11/12实际写法：一句话里的产量、同比、指数不是同一指标的多个披露位置。"""
    sentence='2025年，我国粗钢产量9.61亿吨，同比下降4.4%；钢材价格指数93.2，同比下跌9.1%。'
    rows=[row(index, '国粗钢产量', value, context=sentence) for index, value in
          enumerate(('9.61','4.4','93.2','9.1'), 1)]
    for item in rows:
        item.unit='%'
        item.table_id=''
        item.row_header=sentence
    found=candidate_checks(rows,'2025',run=run_with(rows))
    assert not [check for check in found if check.rule_id=='OCC-001']


def test_same_indicator_disclosed_twice_in_one_document_still_forms_candidate():
    """不能因为去掉同句噪声就丢掉真正的同报告多位置披露。"""
    rows=[row(1,'环保投入合计','100'),row(2,'环保投入合计','100')]
    found=candidate_checks(rows,'2025',run=run_with(rows))
    assert [check for check in found if check.rule_id=='OCC-001']
