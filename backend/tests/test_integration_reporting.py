"""修复统计入口的回归：不能把未知币种漏出分母或把账本矛盾当有效反证。"""
from types import SimpleNamespace
from tools.integration_compare import summarize as compare
from tools.hardening.run_pairs import summarize as pairs


def run():
    return SimpleNamespace(versions={}, documents=[SimpleNamespace(case_id="PAIR", document_id="AR", file_sha256="hash")],
        checks=[], occurrences=[], candidate_rejections=[], ai_analyses=[], provider_calls=[],
        claim_ledger=[], model_status="not_requested")


def test_token_receipts_and_nested_material_contradictions():
    result = run()
    result.provider_calls = [{"input_tokens": 52225, "output_tokens": 8869}]
    result.claim_ledger = [{"support_status": "contradicted", "material_contradictions": [{"material": True}]}]
    summary = compare(result, 0, "single_model")
    assert summary["tokens"] == 61094
    assert summary["pair_id"] == "PAIR"
    assert summary["claim_material_contradictions"] == 1


def test_unknown_currency_is_counted_in_money_population():
    result = run()
    result.occurrences = [SimpleNamespace(unit="万元", currency=""),
                          SimpleNamespace(unit="元", currency="CNY"),
                          SimpleNamespace(unit="人", currency="")]
    summary = pairs(result)
    assert (summary["money_rows"], summary["currency_unknown"], summary["pair_id"]) == (2, 1, "PAIR")
