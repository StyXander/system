"""读取已完成的真实保存结果，核对修订链及三种导出，不创建模型任务。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import zipfile

import httpx

ROOT = Path(__file__).resolve().parents[1]


def verify(task_id: str, base_url: str):
    target = ROOT / "outputs/connectivity-v1-acceptance/exports" / task_id
    target.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=base_url, timeout=60, trust_env=False) as client:
        response = client.get(f"/api/connectivity/runs/{task_id}")
        response.raise_for_status()
        task = response.json()
        assert task["status"] in {"completed", "degraded"}, task["status"]
        run = task["result"]
        exports = {}
        for kind in ("json", "csv", "docx"):
            exported = client.get(f"/api/connectivity/runs/{task_id}/export/{kind}")
            exported.raise_for_status()
            if kind == "json":
                assert exported.json() == run, "导出JSON与持久化结果不同"
            elif kind == "csv":
                text = exported.content.decode("utf-8-sig")
                assert all(check["check_id"] in text for check in run["checks"])
            else:
                with zipfile.ZipFile(BytesIO(exported.content)) as archive:
                    xml = archive.read("word/document.xml").decode("utf-8")
                    assert all(check["check_id"] in xml for check in run["checks"])
                    assert "宋体" in xml and "黑体" in xml
            (target / f"result.{kind}").write_bytes(exported.content)
            exports[kind] = {"bytes":len(exported.content), "content_type":exported.headers["content-type"]}
        parent_id = task.get("parent_task_id")
        parent_preserved = None
        if parent_id:
            parent_response = client.get(f"/api/connectivity/runs/{parent_id}")
            parent_response.raise_for_status()
            parent = parent_response.json()["result"]
            assert parent["run_id"] == run["parent_run_id"]
            assert parent["result_revision"] + 1 == run["result_revision"]
            assert parent["occurrences"] == run["occurrences"], "修订不应改写提取原始事实"
            assert parent["provider_calls"] == run["provider_calls"], "修订不应伪造新调用"
            parent_preserved = True
        proof = {"checked_at":datetime.now(timezone.utc).isoformat(), "task_id":task_id,
            "run_id":run["run_id"], "result_revision":run["result_revision"], "parent_task_id":parent_id,
            "parent_facts_and_calls_preserved":parent_preserved, "exports":exports,
            "word_visual_layout_verified":False, "passed":True}
        (target / "verification.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(proof,ensure_ascii=True),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    parser.add_argument("--base-url",default="http://127.0.0.1:8765")
    args = parser.parse_args()
    verify(args.task_id,args.base_url)
