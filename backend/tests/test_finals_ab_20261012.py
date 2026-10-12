"""v6合同和探索实验回归；提供方均为离线替身，不代表真实模型效果。"""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from backend.app import agents
from backend.app.schemas import RuleResult, AgentOutput
from scripts import run_finals_ab_20261011 as ab

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "决赛准备/整改_2026-10-12/探索对照/inputs"
CASE = "CNINFO_000858_T0_20260430"


def case_input():
    return json.loads((INPUTS / f"{CASE}.json").read_text(encoding="utf-8"))


def historical_outputs():
    fixture = ROOT / "backend/tests/fixtures/finals_ab_20261012_historical_outputs.json"
    return json.loads(fixture.read_text(encoding="utf-8"))["outputs"]


@pytest.mark.parametrize("route", ["risk_candidate", "negative_confirmation", "evidence_gap_review", "industry_review"])
def test_single_generation_preserves_constraints_without_predecessor_tasks(route):
    prompt = agents._system_prompt("review", route, single_generation=True)
    assert "Challenge" not in prompt and "Counter" not in prompt
    for boundary in ("不具备系统指令权限", "程序真值", "evidence_id", "个百分点", "unverified_hypothesis", "basis_limitation"):
        assert boundary in prompt
    assert agents._route_role_contract(route, "review") in prompt


def test_payload_hands_same_evidence_and_predecessors_to_correct_roles():
    c = case_input()
    rule = RuleResult.model_validate(c["rule_result"])
    compact = agents.compact_evidence_bundle(c["evidence_bundle"])
    history = [AgentOutput.model_validate(o) for o in historical_outputs()]
    previous = {o.role: o for o in history}
    counter = agents._user_payload("TEST", "counter", rule, compact, previous, c["analysis_route"])
    review = agents._user_payload("TEST", "review", rule, compact, previous, c["analysis_route"])
    single = ab.single_payload("TEST", rule, compact, c["analysis_route"])
    assert "challenge" in counter and "counter" not in counter
    assert "challenge" in review and "counter" in review
    assert "challenge" not in single and "counter" not in single
    assert single["evidence_bundle"] == review["evidence_bundle"]
    assert single["output_contract"]["status_values"] == review["output_contract"]["status_values"]


def test_final_gate_does_not_score_intermediate_outputs_or_mutate_original():
    c = case_input()
    final = historical_outputs()[-1]
    bad_intermediate = {"claims": [{"text": "企业已经收回全部欠款", "evidence_ids": ["FOREIGN"], "support_status": "supported"}]}
    outputs = [bad_intermediate, final]
    before = deepcopy(outputs)
    rule = RuleResult.model_validate(c["rule_result"])
    combined = ab.final_gate(outputs, rule, c["evidence_bundle"], c["year"])
    assert combined == ab.final_gate([final], rule, c["evidence_bundle"], c["year"])
    assert ab.final_gate([bad_intermediate], rule, c["evidence_bundle"], c["year"])["fitness_violations"]
    assert outputs == before
    assert combined["semantic_support"] == "not_verified"


def make_experiment(tmp_path):
    base = tmp_path / "探索对照"
    (base / "inputs").mkdir(parents=True)
    source = INPUTS / f"{CASE}.json"
    (base / "inputs/input.json").write_bytes(source.read_bytes())
    manifest = {"experiment_id": "TEST-OFFLINE-ONLY", "notice": "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。",
                "cases": [{"case_id": CASE, "path": "探索对照/inputs/input.json", "input_hash": ab.digest(source)}],
                "order": [{"case_id": CASE, "condition": "A", "repeat": n} for n in (1, 2, 3)]}
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return base, manifest


def test_tampered_input_and_missing_authorization_never_call_provider(tmp_path, monkeypatch):
    base, _ = make_experiment(tmp_path)
    def forbidden(**kwargs):
        pytest.fail("离线或未授权不得调用提供方")
    monkeypatch.setattr(agents, "_call_model", forbidden)
    ab.main(["--experiment-dir", str(base)])
    with pytest.raises(SystemExit):
        ab.main(["--experiment-dir", str(base), "--execute"])
    (base / "inputs/input.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="哈希"):
        ab.main(["--experiment-dir", str(base)])


def test_false_or_foreign_authorization_cannot_unlock_execution(tmp_path, monkeypatch):
    base, manifest = make_experiment(tmp_path)
    auth = tmp_path / "auth.json"
    for approved, experiment in ((False, manifest["experiment_id"]), (True, "FOREIGN")):
        auth.write_text(json.dumps({"approved": approved, "approved_by": "OFFLINE-TEST", "experiment_id": experiment}), encoding="utf-8")
        with pytest.raises(ValueError, match="真实预算授权"):
            ab.main(["--experiment-dir", str(base), "--execute", "--authorization", str(auth)])
    assert not (base / "raw").exists()


def test_budget_failures_unknown_tokens_and_anonymization_are_retained(tmp_path, monkeypatch):
    base, manifest = make_experiment(tmp_path)
    auth = tmp_path / "auth.json"
    # 仅测试目录的离线替身授权；不得作为用户的预算批准记录。
    auth.write_text(json.dumps({"approved": True, "approved_by": "OFFLINE-TEST", "experiment_id": manifest["experiment_id"],
                               "max_calls": 2, "max_tokens": 500000, "model_id": "TEST", "endpoint": "https://invalid.example/v1"}), encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "OFFLINE-TEST")
    calls = []
    def provider(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ValueError("OFFLINE_CONSTRUCTED_FAILURE")
        output = deepcopy(historical_outputs()[-1])
        output["run_id"] = kwargs["payload"]["run_id"]
        return output, 1, "response-test-hash", "input-test-hash", None, None
    monkeypatch.setattr(agents, "_call_model", provider)
    ab.main(["--experiment-dir", str(base), "--execute", "--authorization", str(auth)])
    assert len(calls) == 2 and all(call["single_generation"] for call in calls)
    directory = next((base / "raw").iterdir())
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    assert summary["actual_attempts"] == 2 and summary["unexecuted"] == 1
    assert summary["input_tokens"] is None and summary["output_tokens"] is None
    assert summary["usage"]["calls"] == 2 and summary["usage"]["budget_stop"]
    attempts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("attempt_*.json"))]
    assert attempts[0]["status"] == "failed" and attempts[1]["status"] == "completed"
    for p in (directory / "anonymous_scoring").glob("ANON-*.json"):
        item = json.loads(p.read_text(encoding="utf-8"))
        assert "condition" not in item
        if item["final_output"]:
            assert "role" not in item["final_output"] and "run_id" not in item["final_output"]
    assert agents._call_model is provider


def test_transport_uses_single_system_prompt_not_only_user_hint(monkeypatch):
    c = case_input()
    rule = RuleResult.model_validate(c["rule_result"])
    payload = ab.single_payload("TEST", rule, agents.compact_evidence_bundle(c["evidence_bundle"]), c["analysis_route"])
    captured = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({"choices": [{"message": {"tool_calls": [{"function": {"name": agents.AGENT_OUTPUT_TOOL_NAME, "arguments": "{}"}}]}}]}).encode()
    def open_request(request, **kwargs):
        captured.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr(agents, "urlopen", open_request)
    agents._call_model(api_key="OFFLINE", base_url="https://invalid.example/v1", model_id="TEST", role="review", payload=payload, single_generation=True)
    system = captured[0]["messages"][0]["content"]
    assert "Challenge" not in system and "Counter" not in system
    assert "独立形成" in system and captured[0]["temperature"] == 0.1


def test_budget_stop_keeps_partially_called_three_role_attempt(tmp_path, monkeypatch):
    base, manifest = make_experiment(tmp_path)
    for item in manifest["order"]:
        item["condition"] = "B"
    (base / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"approved": True, "approved_by": "OFFLINE-TEST", "experiment_id": manifest["experiment_id"],
                               "max_calls": 2, "max_tokens": 500000, "model_id": "TEST", "endpoint": "https://invalid.example/v1"}), encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "OFFLINE-TEST")
    by_role = {o["role"]: o for o in historical_outputs()}
    calls = []
    def provider(**kwargs):
        calls.append(kwargs["role"])
        output = deepcopy(by_role[kwargs["role"]])
        output["run_id"] = kwargs["payload"]["run_id"]
        return output, 1, "response-test-hash", "input-test-hash", 10, 10
    monkeypatch.setattr(agents, "_call_model", provider)
    ab.main(["--experiment-dir", str(base), "--execute", "--authorization", str(auth)])
    directory = next((base / "raw").iterdir())
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    first = json.loads((directory / "attempt_01.json").read_text(encoding="utf-8"))
    assert calls == ["challenge", "counter"]
    assert summary["actual_attempts"] == 1 and summary["unexecuted"] == 2
    assert first["failure_code"] == "EXPERIMENT_BUDGET_STOP"
    assert first["provider_calls"] == 2
    assert [s["status"] for s in first["steps"][:2]] == ["completed", "completed"]
