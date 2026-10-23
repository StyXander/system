"""动态企业接入的明确合成合同测试；不联网、不调用付费模型。"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pymupdf
import pytest

from backend.app import connectivity_onboarding as onboarding
from backend.app import connectivity_catalog as catalog
from backend.app import connectivity_catalog_api as api
from backend.app.connectivity_extraction import load_registry


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE', 'local')
    monkeypatch.setenv('AUDITTRACE_PUBLIC_DEMO', 'false')
    return tmp_path


def found():
    return {'state': 'paired', 'query_complete': True, 'period': '2025',
        'version_review': 'synthetic_test_only',
        'company': {'ticker': '600001', 'company_name': '合成企业', 'company_alias': '合成企业'},
        'annual': {'ticker': '600001', 'report_year': 2025, 'announcement_title': '2025年度报告',
            'announcement_date': '2026-03-01', 'source_url': 'https://static.cninfo.com.cn/finalpage/2026-03-01/123.PDF'},
        'sustainability': {'ticker': '600001', 'report_year': 2025, 'announcement_title': '2025可持续发展报告',
            'announcement_date': '2026-03-01', 'source_url': 'https://static.cninfo.com.cn/finalpage/2026-03-01/124.PDF'}}


def downloader(monkeypatch, *, company='合成企业', year='2025'):
    calls = []
    def download(url, path, **kwargs):
        calls.append(url)
        kind = '年度报告' if '123.' in url else '可持续发展报告'
        pdf = pymupdf.open()
        for _ in range(2):
            page = pdf.new_page()
            page.insert_text((50, 80), company + year + kind + ' 本合成文件仅供单元测试。报告范围为集团合并口径。' * 4,
                fontname='china-s', fontsize=10)
        pdf.save(path)
        pdf.close()
        return SimpleNamespace(sha256=sha256(path.read_bytes()).hexdigest())
    monkeypatch.setattr(onboarding, 'download_bounded', download)
    return calls


@pytest.mark.parametrize('url', [
    'http://127.0.0.1/a.pdf', 'https://127.0.0.1/a.pdf', 'file:///etc/passwd',
    'https://static.cninfo.com.cn.evil.com/finalpage/2026-03-01/123.pdf',
    'https://user:pass@static.cninfo.com.cn/finalpage/2026-03-01/123.pdf',
    'https://static.cninfo.com.cn:443/finalpage/2026-03-01/123.pdf',
    'https://static.cninfo.com.cn/finalpage/2026-03-01/123.pdf?redirect=http://localhost',
    'https://static.cninfo.com.cn/finalpage/2026-03-01/../123.pdf',
])
def test_untrusted_sources_rejected_before_network(url):
    assert not onboarding.allowed_source(url)


@pytest.mark.parametrize('title,valid', [
    ('2025年可持续发展报告', True), ('2025年环境、社会和公司治理（ESG）报告', True),
    ('2025年社会责任报告', True), ('2025年可持续发展报告摘要', False),
    ('2025年可持续发展报告（英文版）', False), ('2024年可持续发展报告', False),
    ('关于2025年ESG报告的更正公告', False), ('2025半年度ESG报告', False),
])
def test_full_year_full_text_candidate(title, valid):
    row = {'secCode': '600001', 'announcementTitle': title, 'adjunctUrl': 'finalpage/2026-03-01/124.PDF',
        'announcementTime': int(datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp() * 1000)}
    assert bool(onboarding._candidate(row, found()['company'], 2025)) == valid
    row['secCode'] = '600002'
    assert onboarding._candidate(row, found()['company'], 2025) is None


def test_pair_persists_and_is_loadable_after_reopen(root, monkeypatch):
    calls = downloader(monkeypatch)
    pair = onboarding.prepare_pair(root, found())
    assert len(calls) == 2 and pair['parse_status'] == 'complete'
    assert len(catalog.list_pairs(root)[0]) == 1
    docs = load_registry(root)
    assert len(docs) == 2 and all(d.available for d in docs)
    again = onboarding.prepare_pair(root, found())
    assert again['pair_id'] == pair['pair_id'] and len(calls) == 2
    assert [d['document_id'] for d in again['documents']] == [d['document_id'] for d in pair['documents']]


@pytest.mark.parametrize('company,year', [('另一主体', '2025'), ('合成企业', '2024')])
def test_wrong_pdf_identity_never_published(root, monkeypatch, company, year):
    downloader(monkeypatch, company=company, year=year)
    with pytest.raises(ValueError, match='主体|企业与报告年度'):
        onboarding.prepare_pair(root, found())
    assert catalog.list_pairs(root)[0] == []


def test_changed_sustainability_keeps_both_pair_versions(root, monkeypatch):
    calls = downloader(monkeypatch)
    before = onboarding.prepare_pair(root, found())
    newer = found()
    newer['sustainability']['source_url'] = 'https://static.cninfo.com.cn/finalpage/2026-03-01/125.PDF'
    base = onboarding.download_bounded
    def revised(url, path, **kwargs):
        result = base(url, path, **kwargs)
        if '125.' in url:
            with pymupdf.open(path) as pdf:
                pdf[0].insert_text((50, 100), 'Revision 2')
                pdf.saveIncr()
            result.sha256 = sha256(path.read_bytes()).hexdigest()
        return result
    monkeypatch.setattr(onboarding, 'download_bounded', revised)
    after = onboarding.prepare_pair(root, newer)
    assert before['pair_id'] != after['pair_id']
    docs = load_registry(root)
    assert len(docs) == 4 and len({d.document_id for d in docs}) == 4
    assert len({d.file_sha256 for d in docs}) == 3
    assert len(calls) == 3


def test_partial_or_unconfirmed_import_never_downloads(root, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('不得下载不完整报告对')
    monkeypatch.setattr(onboarding, 'download_bounded', forbidden)
    data = found()
    data['state'] = 'partial'
    with pytest.raises(ValueError):
        onboarding.prepare_pair(root, data)
    app = FastAPI()
    app.include_router(api.build_catalog_router(root))
    client = TestClient(app)
    assert client.post('/api/connectivity/catalog/imports', json={'ticker': '600001', 'year': 2025}).status_code == 422


def test_public_heavy_import_requires_verified_login(root, monkeypatch):
    monkeypatch.setenv('AUDITTRACE_PUBLIC_DEMO', 'true')
    app = FastAPI()
    app.include_router(api.build_catalog_router(root))
    client = TestClient(app)
    response = client.post('/api/connectivity/catalog/imports', json={'ticker': '600001', 'year': 2025, 'confirmed_identity': True})
    assert response.status_code == 401
    assert client.get('/api/connectivity/catalog').json()['can_import'] is False


def test_supabase_reuses_metadata_without_legacy_results(root, monkeypatch):
    downloader(monkeypatch)
    record = onboarding.prepare_pair(root, found())
    stored = []
    class FakeClient:
        def insert_table(self, table, rows, **kwargs):
            assert table == 'cases' and kwargs['on_conflict'] == 'case_scope'
            stored[:] = deepcopy(rows)
        def select_table(self, table, **kwargs):
            assert kwargs['filters']['case_id'] == 'like.CONNPAIR-*'
            assert kwargs['filters']['tenant_id'] == 'is.null'
            assert kwargs['select'] == 'case_id,metadata'
            return stored
    from backend.app import supabase_adapter
    monkeypatch.setattr(supabase_adapter, 'get_demo_task_client', lambda: FakeClient())
    monkeypatch.setenv('AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE', 'supabase')
    catalog.save_pair(root, record)
    assert catalog.list_pairs(root, refresh=True)[0] == [record]
    assert 'financial_fields' not in stored[0]['metadata']


def test_old_seed_cannot_be_overwritten_by_dynamic_hash(root, monkeypatch):
    downloader(monkeypatch)
    record = onboarding.prepare_pair(root, found())
    seed = deepcopy(record['documents'][0])
    seed['file_sha256'] = 'f' * 64
    path = root / 'backend/connectivity_reports.json'
    path.write_text(json.dumps({'documents': [seed]}), encoding='utf-8')
    with pytest.raises(ValueError, match='覆盖历史'):
        load_registry(root)


def test_authenticated_session_is_httponly_and_never_returns_tokens(root, monkeypatch):
    monkeypatch.setenv('AUDITTRACE_PUBLIC_DEMO', 'true')
    class Client:
        def sign_in_with_password(self, **kwargs):
            assert kwargs['password'] == 'synthetic-test-password'
            return {'access_token': 'synthetic-access', 'refresh_token': 'synthetic-refresh', 'expires_in': 3600}
        def verify_user(self, token):
            assert token == 'synthetic-access'
            return {'id': 'synthetic-user'}
        def list_memberships(self, user_id, **kwargs):
            return [{'role': 'reviewer', 'organization_id': 'synthetic-org'}]
    monkeypatch.setattr(api, 'get_demo_task_client', lambda: Client())
    app = FastAPI()
    app.include_router(api.build_catalog_router(root))
    client = TestClient(app)
    response = client.post('/api/auth/login', json={'email': 'synthetic@example.com', 'password': 'synthetic-test-password'})
    assert response.status_code == 200
    assert response.json()['can_import'] is True
    assert 'synthetic-access' not in response.text and 'synthetic-refresh' not in response.text
    cookies = response.headers.get_list('set-cookie')
    assert len(cookies) == 2 and all('HttpOnly' in c and 'Secure' in c for c in cookies)
    assert client.post('/api/auth/logout', headers={'Origin': 'https://untrusted.example'}).status_code == 403


def test_anonymous_cannot_start_paid_model(root, monkeypatch):
    monkeypatch.setenv('AUDITTRACE_PUBLIC_DEMO', 'true')
    from backend.app.connectivity_api import build_router
    app = FastAPI()
    app.include_router(build_router(root, lambda _: pytest.fail('不得预留模型额度'), lambda: None))
    response = TestClient(app).post('/api/connectivity/runs', json={'pair_id': '600001-2025', 'mode': 'three_agents'})
    assert response.status_code == 401


def test_import_queue_is_bounded_and_duplicates_reuse_pending(root, monkeypatch):
    class Store:
        def __init__(self, *args, **kwargs):
            self.rows = {}
        def get(self, task_id):
            return self.rows.get(task_id)
        def create(self, case_id, body, executor, **kwargs):
            task_id = 'CIMPORT-' + str(len(self.rows))
            row = {'task_id': task_id, 'status': 'queued', 'run_body': body}
            self.rows[task_id] = row
            return row
    monkeypatch.setattr(api, 'DemoRunTaskStore', Store)
    def discover(_, ticker, year):
        data = found()
        data['company']['ticker'] = ticker
        for field in ('annual', 'sustainability'):
            data[field]['source_url'] += ticker
        return data
    monkeypatch.setattr(api, 'discover_pair', discover)
    app = FastAPI()
    app.include_router(api.build_catalog_router(root))
    client = TestClient(app)
    def create(ticker):
        return client.post('/api/connectivity/catalog/imports', json={'ticker': ticker, 'year': 2025, 'confirmed_identity': True})
    first = create('600001')
    assert first.status_code == 202
    for ticker in ('600002', '600003', '600004'):
        assert create(ticker).status_code == 202
    assert create('600001').json()['task_id'] == first.json()['task_id']
    assert create('600005').status_code == 429


def test_cache_corruption_is_not_shown_as_ready(root, monkeypatch):
    downloader(monkeypatch)
    record = onboarding.prepare_pair(root, found())
    path = root / 'backend/runtime/connectivity/sources' / (record['documents'][0]['file_sha256'] + '.pdf')
    path.write_bytes(b'corrupted synthetic file')
    cards, _ = catalog.company_cards(root)
    assert cards[0]['state'] == 'partial' and cards[0]['can_run'] is False


def test_download_budget_rejects_without_deleting_existing_sources(root, monkeypatch):
    monkeypatch.setenv('AUDITTRACE_REPORT_CACHE_MAX_MB', '200')
    source = root / 'backend/runtime/connectivity/sources/keep.bin'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'preserve-history')
    calls = downloader(monkeypatch)
    with pytest.raises(ValueError, match='存储预算'):
        onboarding.prepare_pair(root, found())
    assert calls == [] and source.read_bytes() == b'preserve-history'


@pytest.mark.parametrize('code,status', [('COMPANY_QUERY_TOO_SHORT', 422), ('COMPANY_NOT_FOUND', 404),
    ('DISCOVERY_BUSY', 409), ('DISCOVERY_RATE_LIMITED', 429), ('CNINFO_NETWORK_ERROR', 503)])
def test_discovery_errors_are_recoverable_and_correctly_classified(code, status):
    assert api.failure(onboarding.CNInfoError(code, '合成故障')).status_code == status


def test_verified_local_pair_survives_remote_outage_and_memory_reset(root, monkeypatch):
    downloader(monkeypatch)
    record = onboarding.prepare_pair(root, found())
    from backend.app import supabase_adapter
    class OfflineClient:
        def select_table(self, *args, **kwargs):
            raise supabase_adapter.SupabaseUnavailable('合成网络故障')
    monkeypatch.setattr(supabase_adapter, 'get_demo_task_client', lambda: OfflineClient())
    monkeypatch.setenv('AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE', 'supabase')
    catalog._remote_cache.pop(str(root.resolve()), None)
    catalog._remote_failures.pop(str(root.resolve()), None)
    rows, status = catalog.list_pairs(root, refresh=True)
    assert rows == [record] and status == 'snapshot_only_remote_unavailable'
    assert len(load_registry(root)) == 2


def test_global_catalog_does_not_enumerate_private_task_links(root, monkeypatch):
    downloader(monkeypatch)
    record = onboarding.prepare_pair(root, found())
    record['last_model_run'] = {'task_id': 'CONNJOB-SYNTHETIC-PRIVATE-LINK', 'model_status': 'not_run'}
    catalog.save_pair(root, record)
    public_metadata = json.dumps(catalog.list_pairs(root)[0])
    assert 'CONNJOB-SYNTHETIC-PRIVATE-LINK' not in public_metadata
    assert 'task_reference_sha256' in public_metadata
