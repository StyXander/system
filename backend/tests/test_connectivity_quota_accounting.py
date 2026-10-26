"""超限用量不能从账本消失，批量入口不能绕过已消费token。"""
import pytest
from backend.app.public_model import PublicModelLedger, PublicModelQuotaError, QuotaConfig


def test_exceeded_consumption_is_saved_and_blocks_both_admission_paths(tmp_path):
    ledger = PublicModelLedger(tmp_path, config=QuotaConfig(daily_input_tokens=10))
    reservation = ledger.reserve_batch('test')
    with pytest.raises(PublicModelQuotaError, match='输入'):
        ledger.settle(reservation, input_tokens=11, output_tokens=2)
    with ledger._connect() as db:
        row = db.execute('select input_tokens,output_tokens,released,settled from model_usage').fetchone()
        assert tuple(row) == (11, 2, 0, 1)
    for reserve in (lambda: ledger.reserve_batch('next'), lambda: ledger.reserve('next')):
        with pytest.raises(PublicModelQuotaError, match='token'):
            reserve()


def test_inflight_estimates_are_shared_across_ledger_instances(tmp_path):
    config=QuotaConfig(daily_input_tokens=100,max_concurrent=2)
    first=PublicModelLedger(tmp_path,config=config);second=PublicModelLedger(tmp_path,config=config)
    a=first.reserve_batch('a');b=second.reserve_batch('b')
    first.checkpoint_usage(a,input_tokens=70,output_tokens=10)
    with pytest.raises(PublicModelQuotaError):second.checkpoint_usage(b,input_tokens=40,output_tokens=1)
    first.checkpoint_usage(a,input_tokens=20,output_tokens=5)
    second.checkpoint_usage(b,input_tokens=40,output_tokens=1)
    with first._connect() as db:
        assert db.execute('select sum(input_tokens) from model_usage').fetchone()[0]==60
        assert db.execute('select sum(settled) from model_usage').fetchone()[0]==0


def test_crashed_inflight_usage_survives_lease_expiry(tmp_path):
    import time
    ledger=PublicModelLedger(tmp_path,config=QuotaConfig(reservation_ttl_seconds=1,daily_input_tokens=50))
    reservation=ledger.reserve_batch('crash')
    ledger.checkpoint_usage(reservation,input_tokens=50,output_tokens=4)
    with ledger._connect() as db:db.execute('update model_usage set last_activity_at=?,reserved_at=?',(time.time()-5,time.time()-5))
    ledger.quota_snapshot()
    with pytest.raises(PublicModelQuotaError):ledger.reserve_batch('after-crash')
    with ledger._connect() as db:
        assert tuple(db.execute('select input_tokens,released,settled from model_usage').fetchone())==(50,0,1)


def test_settled_lease_cannot_reopen_for_more_calls(tmp_path):
    ledger=PublicModelLedger(tmp_path);reservation=ledger.reserve_batch('done')
    ledger.settle(reservation,input_tokens=3)
    with pytest.raises(PublicModelQuotaError):ledger.checkpoint_usage(reservation,input_tokens=5,output_tokens=1)


def test_single_user_skips_stale_daily_and_frequency_quotas(monkeypatch):
    from starlette.requests import Request
    from backend.app import main, company_discovery
    monkeypatch.setenv('AUDITTRACE_SINGLE_USER','true')
    monkeypatch.setenv('AUDITTRACE_PUBLIC_DEMO','true')
    monkeypatch.setenv('AUDITTRACE_DEMO_USE_EXTERNAL_MODEL','true')
    monkeypatch.setenv('DEEPSEEK_API_KEY','test-not-sent')
    monkeypatch.setenv('AUDITTRACE_PUBLIC_QUOTA_SECRET','')
    def forbidden():raise AssertionError('must not open a quota ledger')
    monkeypatch.setattr(main,'_public_model_ledger',forbidden)
    request=Request({'type':'http','method':'POST','path':'/','headers':[],'client':('203.0.113.4',1234)})
    for _ in range(200):
        assert main._enforce_public_model_quota(request,force=True) is None
        company_discovery.enforce_discovery_quota('single-user-test')
