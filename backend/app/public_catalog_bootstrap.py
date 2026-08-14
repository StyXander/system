"""将仓库内的公开目录种子幂等发布到 Supabase。

Render 构建包只携带已校验的元数据和字段候选，不携带已忽略的
PDF 与 FAISS 运行目录。发布后的新实例可以立即展示 50 家企业，
需要原文时仍通过正常的巨潮流程按需下载、校验和建立 RAG。
只发布公开案例卡、年报登记和字段证据，不上传本机路径或密钥。
字段的候选质量状态原样保留，发布不会把待回页候选提升为人工确认。
幂等写入允许每次部署重试，相同案例不因重复构建而新建副本。
单家企业失败不会隐藏其他企业的成功记录，最多回显前五条稳定错误码。
短时 Supabase 不可用时返回 deferred，不让静态网页因外部持久化故障
整体构建失败；下次部署会重试同一批可复验写入。
未配置 Supabase 的本地竞赛模式显式跳过，不伪装成远程发布成功。
"""

from __future__ import annotations

import json
from pathlib import Path

from .seed_catalog import load_seed_cases
from .supabase_adapter import SupabaseError, get_supabase_client, supabase_enabled


WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    """读取当前种子并逐案例发布，最终输出可机器读取的汇总状态。"""

    cases = load_seed_cases(WORKSPACE_ROOT)
    if not cases:
        print(json.dumps({"status": "skipped", "reason": "seed_missing"}, ensure_ascii=False))
        return
    if not supabase_enabled():
        print(json.dumps({"status": "skipped", "reason": "persistence_not_supabase", "case_count": len(cases)}, ensure_ascii=False))
        return
    try:
        client = get_supabase_client()
    except SupabaseError as error:
        print(json.dumps({"status": "deferred", "reason": getattr(error, "code", "SUPABASE_ERROR"), "case_count": len(cases)}, ensure_ascii=False))
        return

    succeeded = 0
    failures: list[dict[str, str]] = []
    for case in cases:
        try:
            client.persist_case_metadata(
                workspace_root=WORKSPACE_ROOT,
                case=case,
                rows=case.get("financial_fields") or [],
                upload_private_documents=False,
            )
            succeeded += 1
        except SupabaseError as error:
            failures.append({"case_id": str(case.get("case_id") or ""), "code": getattr(error, "code", "SUPABASE_ERROR")})
    print(
        json.dumps(
            {
                "status": "ready" if succeeded == len(cases) else "partial",
                "case_count": len(cases),
                "succeeded": succeeded,
                "failed": len(failures),
                "failures": failures[:5],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
