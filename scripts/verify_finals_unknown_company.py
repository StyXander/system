"""本机授权模式真实新企业接入，资料准备路线不请求外部模型。"""
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def main():
    out = ROOT / "outputs/决赛整改_2026-10-09/陌生企业/资料准备"
    out.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url="http://127.0.0.1:8027", trust_env=False, timeout=40) as client:
        bootstrap = client.get("/api/demo/bootstrap")
        bootstrap.raise_for_status()
        assert bootstrap.json()["capabilities"]["onsite_live_sample"]
        request = {"company_query": "920106", "years": 2, "latest_year": 2025, "analysis_mode": "rag_only", "rule_ids": ["R1"], "force_refresh": True}
        started = time.monotonic()
        response = client.post("/api/pipelines/cninfo", json=request)
        response.raise_for_status()
        task = response.json()
        (out / "创建任务.json").write_text(json.dumps({"request": request, "response": task}, ensure_ascii=False, indent=2), encoding="utf-8")
        task_id = task["task_id"]
        previous = None
        for _ in range(180):
            response = client.get(f"/api/pipelines/{task_id}")
            response.raise_for_status()
            task = response.json()
            if task.get("status") != previous:
                print(task_id, task.get("status"), flush=True)
                previous = task.get("status")
            (out / "最新任务.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
            if task.get("status") in {"completed", "needs_human", "failed", "cancelled", "ready_for_analysis"}:
                break
            time.sleep(2)
        summary = {"task_id": task_id, "status": task.get("status"), "elapsed_seconds": round(time.monotonic() - started, 3), "request": request, "error": task.get("error")}
        result = task.get("result") or {}
        if result:
            extraction = result.get("field_extraction") or {}
            analysis = result.get("analysis") or {}
            summary.update({"documents": len(result.get("documents") or []), "rag_chunks": (result.get("rag") or {}).get("chunk_count"), "field_rows": extraction.get("row_count"), "field_issues": extraction.get("issues"), "analysis_run_id": analysis.get("run_id"), "provider_calls": analysis.get("model_check", {}).get("provider_call_count"), "rule_results": analysis.get("rule_results")})
            assert summary["provider_calls"] in (None, 0)
        (out / "验收摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
