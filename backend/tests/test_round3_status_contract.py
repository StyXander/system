"""第三轮状态和多格式同源回归；合成数据仅验证显示合同。"""
from io import BytesIO
import csv
from docx import Document
from app.connectivity_schemas import ConnectivityRun, RelationshipCheck
from app.connectivity_overview import build_overview
from app.connectivity_delivery import export_run

def status_run():
    rows = []
    for key, conclusion, criteria, calculation in [
        ('F', 'formal_consistent', 'supported', 'consistent'),
        ('T', 'assumption_compatible', 'unknown', 'not_comparable'),
        ('L', 'limited_support', 'unknown', 'not_comparable'),
        ('I', 'insufficient_basis', 'unknown', 'not_comparable'),
        ('C', 'unexplained_difference', 'conflicting', 'not_comparable'),
        ('N', 'not_assessed', 'unknown', 'not_applicable')]:
        check = RelationshipCheck(check_id=key, rule_id='EQ-001' if key!='N' else 'NAR-001',
            title=key, topic='environment', operator='equal' if key!='N' else 'narrative', members=[],
            conclusion_level=conclusion, criteria_status=criteria, calculation_status=calculation)
        if key=='F': check.calculation={'residual':'0'}
        if key in {'T','I'}: check.hypothetical={'residual':'0'}
        rows.append(check)
    return ConnectivityRun(run_id='SYN-ROUND3-STATUS', company='合成合同测试', period='2025', documents=[], checks=rows)

def test_summary_aliases_are_projection_not_second_classifier():
    view=build_overview(status_run())
    assert {k:v['value'] for k,v in view['program_levels'].items()}==dict.fromkeys(
        ['formal','conditional','limited','insufficient','conflict','not_applicable'],1)
    assert view['summary_bands']['conditional_trial']['items']==['T']
    assert view['summary_bands']['not_comparable']['items']==['I']
    assert view['summary_bands']['pending']['items']==['C','N']
    assert view['trial_calculations']['items']==['T']
    assert view['arithmetic_references']['items']==['T','I']

def test_word_csv_json_all_publish_canonical_status_counts():
    import json
    run=status_run()
    raw=json.loads(export_run(run,'json')[0])
    csv_rows=list(csv.reader(export_run(run,'csv')[0].decode('utf-8-sig').splitlines()))
    csv_counts={r[6]:int(r[7]) for r in csv_rows if r and r[0]=='program_level_count'}
    assert csv_counts=={k:v['value'] for k,v in raw['overview']['program_levels'].items()}
    word=Document(BytesIO(export_run(run,'docx')[0]))
    body='\n'.join(p.text for p in word.paragraphs)
    for label in ['正式复算且数值相容','条件试算','有限支持','依据不足·不可比','明确口径冲突或未解释差额','不适用数值计算']:
        assert label+'：1 / 6项。' in body
    assert '上述五类互斥' not in body
