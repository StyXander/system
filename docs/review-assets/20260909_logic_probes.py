"""本轮离线审查反例；只构造内存夹具，不联网、不写业务资料。

2026-09-09 更新：五项缺陷修复后，本脚本从"复现缺陷"改为"复核修复结果"。
- C03 修复后 validate_pdf 会抛 CNInfoError，脚本把它记成 rejected 而不是崩溃；
- C04 修复后 assess_official_document 走 httpx，必须注入 MockTransport，
  否则会真的向巨潮发起请求。
所有断言的期望值都写在 expected 字段里，便于逐条核对。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx
import pymupdf as fitz
from backend.app.cninfo import CNInfoClient, CNInfoError
from backend.app.field_extraction import FIELD_CONFIG, _find_page_candidate
from backend.app.knowledge_rag import retrieve_knowledge
from backend.app.knowledge_ingest import assess_official_document

observations = []
page = "合并资产负债表\n单位：元\n项目 2024年末 2023年末\n应收账款\n80\n120\n"
candidate = _find_page_candidate([page], FIELD_CONFIG['accounts_receivable'], report_year=2024)
observations.append({'probe': 'C01_small_current_amount', 'expected_raw_value': 80, 'actual_raw_value': candidate['raw_value'],
                     'column_identity': candidate['column_identity']})

entry = {'source_id': 'FIXTURE-KB', 'source_category': 'auditing_standard', 'title': '审计抽样程序', 'published_at': '2024-01-01', 'validation_status': 'passed', 'retrieval_excerpt': '抽样程序须记录总体和样本。'}
request = {'case_id': 'FIXTURE', 'question_id': '火星土壤化学组成', 'query_text': '火星土壤的化学组成是什么', 'ticker': '999999', 'cutoff_date': '2026-09-09', 'source_categories': ['auditing_standard']}
observations.append({'probe': 'C02_irrelevant_knowledge', 'expected_hits': 0, 'actual_hits': len(retrieve_knowledge([entry], request))})

doc = fitz.open()
for _ in range(12):
    doc.new_page().insert_text((40, 60), 'Fixture Corporation 600302 2022 annualreport')
pdf = doc.tobytes()
doc.close()
announcement = {'report_year': 2024, 'announcement_title': '2024 annualreport', 'company_name': 'Fixture Corporation'}
with CNInfoClient(client=httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200)))) as cn:
    try:
        result = cn.validate_pdf(pdf, announcement, {'company_name': 'Fixture Corporation', 'ticker': '600302'})
        status = result['validation_status']
        year_source = result['content_checks']['year_source']
    except CNInfoError as error:
        status = f"rejected:{error.code}"
        year_source = (error.detail or {}).get('year_source')
observations.append({'probe': 'C03_wrong_report_year', 'expected_validation': 'rejected:PDF_REPORT_YEAR_UNCONFIRMED',
                     'actual_validation': status, 'year_source': year_source})


def _fake_pdf_transport(request: httpx.Request) -> httpx.Response:
    if request.url.host == 'www.cninfo.com.cn':
        return httpx.Response(302, headers={'location': 'https://evil.example/not-official.pdf'}, request=request)
    return httpx.Response(200, content=b'<html>not a PDF</html>', headers={'content-type': 'application/pdf'}, request=request)


mock_client = httpx.Client(transport=httpx.MockTransport(_fake_pdf_transport))
assessment = assess_official_document('https://www.cninfo.com.cn/test.pdf', expect_pdf=True, client=mock_client)
observations.append({'probe': 'C04_nonpdf_and_external_redirect', 'expected_ok': False, 'actual_ok': assessment.ok,
                     'code': assessment.code, 'final_url': assessment.final_url})

calls = []


def handler(req: httpx.Request) -> httpx.Response:
    calls.append(str(req.url))
    return httpx.Response(503)


with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
    cn = CNInfoClient(client=transport, min_delay_seconds=0, max_retries=2)
    response = cn._request('GET', 'https://www.cninfo.com.cn/', source='offline fixture')
observations.append({'probe': 'C05_transient_503_retry', 'expected_requests': 3, 'configured_retries': 2,
                     'actual_requests': len(calls), 'status': response.status_code,
                     'stop_reason': cn.retry_summary()['stop_reason']})

print(json.dumps(observations, ensure_ascii=False, indent=2))
