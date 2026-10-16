"""短暂读取失败只重取一次，写请求和身份错误不得自动重放。"""
import httpx
import pytest

from app import supabase_adapter as adapter


def client(monkeypatch, outcomes):
    calls=[]
    class Transport:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def request(self,method,url,**kwargs):
            calls.append(method)
            outcome=outcomes.pop(0)
            if isinstance(outcome,Exception):raise outcome
            return httpx.Response(outcome,json={"ok":True})
    monkeypatch.setattr(adapter.httpx,"Client",lambda **kwargs:Transport())
    monkeypatch.setattr(adapter.time,"sleep",lambda seconds:None)
    config=adapter.SupabaseConfig("supabase","https://example.invalid",None,"synthetic-key","private",60,1)
    return adapter.SupabaseClient(config),calls


def test_get_retries_temporary_connection_failure_once(monkeypatch):
    instance,calls=client(monkeypatch,[httpx.ConnectError("synthetic"),200])
    assert instance._request("GET","rest/v1/test",service=True)=={"ok":True}
    assert calls==["GET","GET"]


def test_post_does_not_replay_ambiguous_connection_failure(monkeypatch):
    instance,calls=client(monkeypatch,[httpx.ReadError("synthetic"),200])
    with pytest.raises(adapter.SupabaseUnavailable):instance._request("POST","rest/v1/test",service=True,json_body={})
    assert calls==["POST"]


def test_get_does_not_retry_identity_failure(monkeypatch):
    instance,calls=client(monkeypatch,[401,200])
    with pytest.raises(adapter.SupabaseAuthError):instance._request("GET","rest/v1/test",service=True)
    assert calls==["GET"]
