"""真实连接检查只输出脱敏状态，不显示连接密钥或旧任务正文。"""
import json
from pathlib import Path
import sys
import argparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / ".env")
from app.supabase_adapter import get_demo_task_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cancel-engineering-task")
    args = parser.parse_args()
    client = get_demo_task_client()
    if args.cancel_engineering_task:
        row = client.get_demo_run_task(args.cancel_engineering_task)
        if not row or row.get("task_kind") != "connectivity" or row.get("request_payload", {}).get("mode") != "calculation_only" or row.get("non_interruptible"):
            raise ValueError("仅允许停止明确指定且尚未进入模型阶段的关联核对工程任务")
        result = client.cancel_demo_run_task(task_id=args.cancel_engineering_task)
        print(json.dumps({"task_id":args.cancel_engineering_task,"status":result.get("status") if result else "unchanged","reason":"逐页远程取消查询阻塞，保留旧记录并在修复后显式重试"}))
        return
    rows = client._request("GET", "rest/v1/demo_run_tasks", service=True,
        params={"select": "task_id,task_kind,status", "limit": "1"})
    result = {"connection": "ok", "task_table_accessible": True, "sample_row_count": len(rows),
        "operation": "read_only", "secret_in_output": False}
    target = ROOT / "outputs/connectivity-v1-acceptance/supabase-connection.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"connection": "failed", "error_type": type(error).__name__}))
        sys.exit(1)
