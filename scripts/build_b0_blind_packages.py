# -*- coding: utf-8 -*-
"""生成 B0 人工基线的 8 案统一盲包（evaluation_v4/blind-packages）。

2026-08-22 外部审查整改版，相对初版的关键修正：
1. 哈希按实际文件字节（read_bytes）计算并覆盖 MD 与 JSON 两类文件；
   不再用写盘前的 LF 字符串哈希（Windows 写盘产生 CRLF 导致 8/8 不匹配）。
2. 盲性保护：评分人分发的 packages.manifest.json 不含分层（stratum）信息；
   含分层的协调人清单单独放在 coordinator/ 子目录并限制访问。
3. 字段表显式携带冻结状态列（待复核/已确认）和回页标记，
   防止评分人把候选值误当已冻结事实。
包内不包含任何程序输出、AI 输出或其他案例的数据；已存在时拒绝覆盖。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_ID = "EVAL-20260822-COMPETITION-8CASE-V3"
AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"

TASK_INSTRUCTION = """## 任务说明（八案统一，不得更改）

你是审计项目组成员，正在为一家 A 股公司制定销售与收款循环的审计计划。
你只能使用本包提供的财务字段和公开年报来源（可打开来源 URL 回到原文核对）。
字段表中标注“待复核”的数值是自动提取候选，使用前请回到来源页自行核对；
你也可以在判断中写明“因字段未核实而不作金额判断”。

请在 60 分钟内完成：
1. 判断该公司的收入与应收变动关系是否需要列入待核查事项；
2. 如需列入，写出你关注的具体事项和理由；
3. 列出你希望索取的补充资料清单；
4. 如认为信息不足或行业不适用，明确写出暂缓或不适用的理由。

边界：不得认定舞弊、不得出具审计意见、不得给投资建议；
你的判断只是审计计划阶段的待核查候选。
按“输出模板”格式作答，并如实填写开始与结束时间。
"""

OUTPUT_TEMPLATE = """## 输出模板（照此格式填写）

- 开始时间 / 结束时间：
- 初步判断（四选一）：不触发 / 待核查 / 暂缓 / 行业不适用
- 关注事项（逐条，含理由）：
- 引用来源（字段/页码/URL）：
- 希望索取的补充资料：
- 其他说明：
"""

FIELD_KIND_LABELS = {
    "revenue": "营业收入",
    "accounts_receivable": "应收账款",
    "operating_cash_flow": "经营活动现金流量净额",
    "net_profit": "净利润",
}

STATUS_LABELS = {
    "candidate_pending_human_review": "待复核（自动候选）",
    "human_confirmed": "已确认",
    "human_rejected": "已拒绝",
    "registry_technical_crosscheck_pending_human": "待复核（注册表技术核对）",
}


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status or "待复核（自动候选）")


def _field_rows(case: dict) -> list[list[str]]:
    rows = []
    for f in sorted(case["financial_fields"], key=lambda x: (x.get("year") or 0, str(x.get("field_kind"))), reverse=True):
        doc = next((d for d in case["documents"] if d.get("document_id") == f.get("document_id")), {})
        flags = "；".join(f.get("review_flags") or [])
        rows.append([
            str(f.get("field_id") or f.get("evidence_id")),
            FIELD_KIND_LABELS.get(f.get("field_kind"), str(f.get("field_kind"))),
            str(f.get("year")),
            f"{f.get('value'):,.2f}" if isinstance(f.get("value"), (int, float)) else str(f.get("value")),
            str(f.get("unit") or ""),
            _status_label(f.get("field_freeze_status")),
            flags or "—",
            str(f.get("pdf_page") or "—"),
            str(f.get("locator") or "—"),
            str(doc.get("source_url") or "—"),
        ])
    return rows


def build_package_md(case: dict) -> str:
    lines = [
        f"# B0 盲包 · {case['company_name']}（{case['case_id']}）",
        "",
        f"评估编号：{EVALUATION_ID} · 分析年度：{case['analysis_year']} · T0：{case['t0']}",
        f"统一 AI 声明：{AI_NOTICE}",
        "",
        "> 本包仅供 B0 人工基线使用：只含字段与公开来源，不含任何程序或 AI 输出。",
        "",
        TASK_INSTRUCTION,
        "## 财务字段表",
        "",
        "| 字段 | 类别 | 年度 | 金额/值 | 单位 | 冻结状态 | 回页标记 | PDF 页 | 定位 | 来源 URL |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in _field_rows(case):
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "## 来源清单", "", "| 文档 | 年度 | 披露日 | SHA-256 | URL |", "|---|---|---|---|---|"]
    for doc in case["documents"]:
        lines.append(f"| {doc.get('announcement_title')} | {doc.get('report_year')} | {doc.get('disclosure_date')} | `{doc.get('sha256')}` | {doc.get('source_url')} |")
    lines += ["", OUTPUT_TEMPLATE]
    return "\n".join(lines)


def _write_with_newline(path: Path, text: str) -> None:
    """统一写为 LF 字节，避免 Windows 换行转换导致哈希口径漂移。"""
    path.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 B0 盲包；字节哈希、分层隔离、拒绝覆盖。")
    parser.add_argument("--output-root", type=Path, default=ROOT / "outputs" / "evaluation_v4",
                        help="正式目录默认 outputs/evaluation_v4；机制自测请指向临时目录。")
    args = parser.parse_args()

    eval_dir = args.output_root / EVALUATION_ID
    contract = json.loads((eval_dir / "contract.json").read_text(encoding="utf-8"))
    # 盲包是评分人直接接触的输入：字段未完成人工回页复核的合同禁止生成，
    # 否则待复核候选值会被当作冻结事实发放（B0-B3-0 初版的教训）。
    if str(contract.get("meta", {}).get("status", "")).startswith("pending_field_review"):
        raise SystemExit(
            f"拒绝生成盲包：合同状态为 {contract['meta']['status']}（字段待人工复核）。"
            "先完成《字段回页复核工作底稿》并在复核后重新冻结合同。"
        )
    out_dir = eval_dir / "blind-packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "packages.manifest.json"
    coordinator_dir = out_dir / "coordinator"
    coordinator_path = coordinator_dir / "manifest-stratum.json"
    if manifest_path.exists() or coordinator_path.exists():
        raise SystemExit(f"拒绝覆盖：盲包清单已存在 {manifest_path}")

    manifest = {"evaluation_id": EVALUATION_ID, "ai_generated_content_notice": AI_NOTICE, "packages": []}
    coordinator = {
        "evaluation_id": EVALUATION_ID,
        "access": "仅协调人可访问；评分人在评分锁定前不得查看本文件（含预期分层信息）",
        "packages": [],
    }
    for case in contract["cases"]:
        safe_id = case["case_id"].replace("/", "_")
        md_path = out_dir / f"{safe_id}.md"
        json_path = out_dir / f"{safe_id}.json"
        if md_path.exists() or json_path.exists():
            raise SystemExit(f"拒绝覆盖：盲包已存在 {md_path}")
        md = build_package_md(case)
        payload = {
            "case_id": case["case_id"],
            "company_name": case["company_name"],
            "analysis_year": case["analysis_year"],
            "t0": case["t0"],
            "task_instruction": TASK_INSTRUCTION,
            "output_template": OUTPUT_TEMPLATE,
            "financial_fields": case["financial_fields"],
            "documents": case["documents"],
            "ai_generated_content_notice": AI_NOTICE,
        }
        _write_with_newline(md_path, md)
        _write_with_newline(json_path, json.dumps(payload, ensure_ascii=False, indent=2))
        # 哈希按实际文件字节计算，与分发物逐字节一致。
        entry = {
            "case_id": case["case_id"],
            "company_name": case["company_name"],
            "md_file": md_path.name,
            "md_sha256": hashlib.sha256(md_path.read_bytes()).hexdigest(),
            "json_file": json_path.name,
            "json_sha256": hashlib.sha256(json_path.read_bytes()).hexdigest(),
        }
        manifest["packages"].append(entry)
        coordinator["packages"].append({**entry, "stratum": case["stratum"]})

    coordinator_dir.mkdir(parents=True, exist_ok=True)
    _write_with_newline(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    _write_with_newline(coordinator_path, json.dumps(coordinator, ensure_ascii=False, indent=2))
    print(json.dumps({
        "manifest": str(manifest_path),
        "coordinator": str(coordinator_path),
        "packages": len(manifest["packages"]),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
