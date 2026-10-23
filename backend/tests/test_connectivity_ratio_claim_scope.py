"""真实运行发现的混合句误拒绝：比例与金额可以在同句中分别使用。"""
from types import SimpleNamespace as N
from backend.app.connectivity_claims import _column_claims

def check(text):
    row=N(occurrence_id='R', value='1.11', label='研发投入占营业收入比例',
          column_header='2025年', row_header='研发投入占营业收入比例', unit='%', year='2025')
    rel=N(check_id='C', members=[N(occurrence_id='R')])
    return _column_claims(rel,text,[row],[])

def test_ratio_and_separate_money_in_one_sentence_are_not_confused():
    claims=check('ESG 1.11%以4.49亿元除以营业收入复算，范围仍待确认。')
    assert claims and all(c['support_status']=='supported' for c in claims)

def test_ratio_explicitly_written_as_money_is_still_rejected():
    assert check('研发投入为1.11亿元。')[0]['support_status']=='contradicted'

def test_ratio_explicitly_written_as_headcount_is_still_rejected():
    assert check('人数为1.11。')[0]['support_status']=='contradicted'
