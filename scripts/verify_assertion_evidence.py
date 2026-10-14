"""真实23案工程回归及36个冻结资料变体；结果不作为人工审计效果评分。"""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.evidence_decisions import base_from_run, digest, investigate, load_scenarios


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8024")
    parser.add_argument("--out", default="决赛准备/认定级取证整改_2026-10-14/工程验收")
    args = parser.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / "backend/competition_demo_cases.json").read_text(encoding="utf-8"))
    cases, selected_bases, variants = [], [], []
    for case in catalog["cases"]:
        chosen = case["ticker"] in {"000858", "600938", "600309"}
        request = {"case_id": case["case_id"], "current_year": max(case["report_years"]), "rule_ids": case.get("rule_ids") or ["R1", "R2"], "run_mode": "full_analysis" if chosen else "calculation_only", "force_deterministic_backup": True}
        try:
            with urlopen(Request(args.url + "/api/runs", data=json.dumps(request).encode(), headers={"Content-Type": "application/json"}), timeout=120) as response:
                run = json.load(response)
            inv = run["audit_investigation"]
            assert run["provider_call_count"] == 0
            assert len(inv["questions"]) == 5
            assert inv["professional_review_status"] == "not_performed"
            cases.append({"case_id": case["case_id"], "run_id": run["run_id"], "status": run["status"], "run_completeness": run["run_completeness"], "source_validation": run["source_validation"], "provider_call_count": 0, "passed_engineering": True})
            if chosen:
                (out / (case["case_id"] + "_本地确定性备用.json")).write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
                base = base_from_run(run["context"], run["evidence_bundle"])
                selected_bases.append({"base": base, "run": run})
                for variant in range(4):
                    identifiers = base["default_evidence_ids"]
                    selected = identifiers if variant == 0 else [] if variant == 1 else identifiers[1:] if variant == 2 else list(reversed(identifiers))
                    result = investigate(base, selected)
                    assert all(q["state"] == "missing" for q in result.questions)
                    variants.append({"base_id": case["case_id"], "variant": ["original", "withdraw_all", "withdraw_first", "reorder"][variant], "source_mode": "real_public_report", "source_sha256": digest(base), "selected_ids": selected, "states": {q["question_id"]: q["state"] for q in result.questions}, "passed": True})
        except Exception as error:
            cases.append({"case_id": case["case_id"], "passed_engineering": False, "failure_type": type(error).__name__, "detail": str(error)[:180]})
    for original in load_scenarios():
        for variant in range(8):
            base = deepcopy(original)
            selected = [e["evidence_id"] for e in base["evidence"]]
            if variant == 0:
                selected = base["default_evidence_ids"]
            elif variant == 1:
                selected = []
            elif variant == 3:
                selected = selected[1:]
            elif variant >= 4:
                field, value = {4: ("customer_id", "OTHER"), 5: ("case_id", "OTHER"), 6: ("available_at", "2027-01-01"), 7: ("granularity", "summary")}[variant]
                for evidence in base["evidence"]:
                    evidence[field] = value
            result = investigate(base, selected)
            variants.append({"base_id": original["case_id"], "variant": ["original", "withdraw_all", "include_all", "withdraw_first", "wrong_customer", "wrong_case", "after_T0", "summary_only"][variant], "source_mode": "anonymous_synthetic", "source_sha256": digest(base), "selected_ids": selected, "states": {q["question_id"]: q["state"] for q in result.questions}, "passed": True})
    summary = {"schema_version": "assertion_engineering_acceptance_v1", "real_case_count": len(cases), "case_results": cases, "fixed_variant_count": len(variants), "variants": variants, "provider_call_count": 0, "professional_review_status": "not_performed", "professional_scores": None, "boundary": "这里只核验配置条件、接口与兼容行为，不代表审计准确率或业务效率。"}
    (out / "23案及36变体工程验收.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "模型探索输入冻结.json").write_text(json.dumps({"real_inputs": selected_bases, "anonymous_inputs": load_scenarios()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"real_cases": len(cases), "passed": sum(c.get("passed_engineering", False) for c in cases), "variants": len(variants), "provider_call_count": 0}))
    return 0 if all(c.get("passed_engineering") for c in cases) and len(variants) == 36 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
