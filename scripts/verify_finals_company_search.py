"""真实官方身份检索及本地 HTTP 扩展案例验收；不消耗模型额度。"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import company_discovery as discovery

OUT = ROOT / "outputs" / "决赛系统优化_2026-10-09"


def main():
    """52个身份输入加8个真实HTTP边界检查，记录事实及未通过项。"""
    OUT.mkdir(parents=True, exist_ok=True)
    groups = {
        "明确名称": ["贵州茅台", "美的集团", "恒瑞医药", "用友网络", "爱尔眼科", "中国建筑", "万科A", "工商银行", "金山办公", "宁德时代", "海康威视", "比亚迪", "中国平安", "招商银行", "京东方A", "伊利股份", "格力电器", "中兴通讯"],
        "输入规范化": ["ＳＨ６００２７６", "600276.SH", "SH600276", "SZ 000333", "000333.sz", "  美的集团  ", "贵 州 茅 台", "美的集团股份有限公司", "江苏恒瑞医药股份有限公司", "mdjt"],
        "模糊候选": ["银行", "医药", "科技", "中国", "软件", "建筑", "集团", "股份"],
        "非预置企业": ["920002", "920106", "603893", "688256", "603501", "688981", "301269", "300896"],
        "范围外或无匹配": ["腾讯", "阿里巴巴", "华为技术有限公司", "OpenAI", "不存在的测试企业XYZ", "999999", "00700.HK", "AAPL"],
    }
    records = []
    for group, queries in groups.items():
        for query in queries:
            start = time.monotonic()
            try:
                result = discovery.search(ROOT, query)
                passed = result["match_count"] >= 1 if group in {"明确名称", "输入规范化", "非预置企业"} else bool(result["candidates"] and result["requires_confirmation"]) if group == "模糊候选" else result["match_count"] == 0
                records.append({"group": group, "query": query, "passed": passed, "seconds": round(time.monotonic() - start, 3), "response": result})
            except Exception as error:
                records.append({"group": group, "query": query, "passed": False, "error_code": getattr(error, "code", type(error).__name__)})
    api_checks = []
    with httpx.Client(base_url="http://127.0.0.1:8019", timeout=45, trust_env=False) as client:
        checks = [("匿名查询", "/api/companies/search", {"q": "600999"}, 200), ("空输入", "/api/companies/search", {"q": ""}, 422), ("短输入", "/api/companies/search", {"q": "美"}, 422), ("错误市场", "/api/companies/search", {"q": "SZ600276"}, 422), ("过长输入", "/api/companies/search", {"q": "a" * 121}, 422), ("未来截止日", "/api/companies/000333/reports", {"year": 2025, "source_cutoff_date": (date.today() + timedelta(days=1)).isoformat()}, 422), ("非法年度", "/api/companies/000333/reports", {"year": 1900}, 422)]
        for label, path, params, status in checks:
            response = client.get(path, params=params)
            api_checks.append({"label": label, "status": response.status_code, "expected": status, "passed": response.status_code == status, "response": response.json()})
        response = client.post("/api/pipelines/cninfo", json={"company_query": "920002"})
        api_checks.append({"label": "匿名新企业写入被阻断", "status": response.status_code, "expected": 403, "passed": response.status_code == 403})
    expanded = []
    with httpx.Client(base_url="http://127.0.0.1:8018", timeout=45, trust_env=False) as client:
        cases = client.get("/api/demo/expanded-cases").json()["cases"]
        for case in cases:
            response = client.post("/api/pipelines/cninfo", json={"company_query": case["ticker"], "years": len(case["report_years"]), "latest_year": max(case["report_years"]), "analysis_mode": "rag_only"})
            task = response.json()
            if response.status_code == 202:
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    task = client.get(f"/api/pipelines/{task['task_id']}").json()
                    if task["status"] in {"completed", "needs_human", "failed"}:
                        break
                    time.sleep(.3)
            result = task.get("result") or {}
            passed = bool(result.get("case_id") == case["case_id"] and result.get("analysis", {}).get("run_id"))
            expanded.append({"case": case, "passed": passed, "task": task})
    payload = {"official_identity_inputs": records, "http_boundary_checks": api_checks, "expanded_case_runs": expanded, "identity_passed": sum(item["passed"] for item in records), "identity_count": len(records), "http_passed": sum(item["passed"] for item in api_checks), "http_count": len(api_checks), "expanded_passed": sum(item["passed"] for item in expanded), "expanded_count": len(expanded), "boundary": "身份查找使用真实巨潮目录或其本轮官方缓存；扩展案例为真实HTTP计算预检，不包含外部模型成功或真人专业评分。"}
    (OUT / "真实身份与案例验收.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in payload.items() if not isinstance(value, list)}, ensure_ascii=False))
    for item in records:
        if not item["passed"]:
            print("FAILED", item["query"], item.get("error_code") or item["response"]["status"])
    return 0 if all(item["passed"] for item in records + api_checks + expanded) else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
