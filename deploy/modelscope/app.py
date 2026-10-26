"""ModelScope Docker 启动入口：配置身份，准备来源，再启动同源网站。"""

import json
import os
from pathlib import Path

import uvicorn


def main() -> None:
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "deployment-source.json").read_text(encoding="utf-8"))
    # 内容快照和原工作区提交分别记录；不把含未提交修改的快照冒充原提交。
    os.environ["AUDITTRACE_DEPLOYMENT_PLATFORM"] = "modelscope"
    os.environ["AUDITTRACE_DEPLOYMENT_SERVICE"] = "burgerhaamm/audittrace"
    os.environ["AUDITTRACE_SOURCE_SNAPSHOT_SHA256"] = manifest["source_snapshot_sha256"]
    os.environ["AUDITTRACE_SOURCE_BASELINE_COMMIT"] = manifest["source_baseline_commit"]
    # 队长个人演示无需组织登录，也不启用每日token或次数配额。
    os.environ.setdefault("AUDITTRACE_SINGLE_USER", "true")
    from backend.app.public_demo_bootstrap import prepare_public_demo
    from backend.app import company_discovery, public_catalog_bootstrap

    print(json.dumps(prepare_public_demo(allow_missing_sources=True), ensure_ascii=False), flush=True)
    print(json.dumps(company_discovery.refresh_deployment_snapshot(root), ensure_ascii=False), flush=True)
    public_catalog_bootstrap.main()
    # 单个 Web 执行器保持现有任务租约与中断语义；完成结果使用 Supabase。
    uvicorn.run("backend.app.connectivity_app:app", host="0.0.0.0", port=7860, proxy_headers=True)


if __name__ == "__main__":
    main()
