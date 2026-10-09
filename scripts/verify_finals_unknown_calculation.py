"""仅从已下载公开原件提取候选，再请求calculation_only；没有付费分析入口。"""
import json
import os
from pathlib import Path
import sys

os.environ["AUDITTRACE_RUNTIME_NAMESPACE"] = "finals_unknown_20261009"
os.environ["AUDITTRACE_DEMO_USE_EXTERNAL_MODEL"] = "false"
os.environ["AUDITTRACE_PROVIDER_PROBE_ENABLED"] = "false"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
import httpx
from backend.app.field_extraction import extract_cninfo_fields


def main():
    out = ROOT / "outputs/决赛整改_2026-10-09/陌生企业/零模型字段与计算"
    out.mkdir(parents=True, exist_ok=True)
    prep = json.loads((ROOT / "outputs/决赛整改_2026-10-09/陌生企业/最新任务.json").read_text(encoding="utf-8"))
    case_id = prep["result"]["case_id"]
    extraction = extract_cninfo_fields(ROOT, case_id, rule_ids=["R1"], requested_years=[2025, 2024])
    (out / "实际字段抽取.json").write_text(json.dumps(extraction, ensure_ascii=False, indent=2), encoding="utf-8")
    with httpx.Client(base_url="http://127.0.0.1:8027", trust_env=False, timeout=40) as client:
        response = client.post("/api/runs", json={"case_id": case_id, "current_year": 2025, "rule_ids": ["R1"], "run_mode": "calculation_only"})
        response.raise_for_status()
        run = response.json()
        assert run["model_check"]["provider_call_count"] == 0
        (out / "真实规则运行.json").write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
        print("case", case_id, "field_rows", extraction["row_count"], "issues", len(extraction["issues"]), "run", run["run_id"], "model_calls", 0)
        print([(r["rule_id"], r["status"], r["metrics"].get("growth_gap")) for r in run["rule_results"]])


if __name__ == "__main__":
    main()
