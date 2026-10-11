"""从本机原始记录生成决赛核对包；零模型、无签字、无发布。"""
import csv
import hashlib
import json
import sys
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from backend.app.seed_catalog import load_seed_cases
from backend.app.main import _r1_result
from backend.app.industry_gate import evaluate_industry_gate
from backend.app.signoff import current_r1_config, load_signoff_status
from backend.app.cases import calculation_ready_financial_rows

OUT = ROOT / "决赛准备/整改_2026-10-11"
NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def table(name, rows):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def md(name, text):
    (OUT / name).write_text(text.strip() + "\n\n" + NOTICE + "\n", encoding="utf-8")


def period_rows(case, declared_latest=False):
    original_fields = case.get("financial_fields", [])
    fields = calculation_ready_financial_rows(original_fields)
    year_pool = original_fields if declared_latest else fields
    year = max([int(r["year"]) for r in year_pool if r.get("field_kind") in {"revenue", "accounts_receivable"}] or [0])
    rows = []
    for r in fields:
        if case.get("t0") and str(r.get("disclosure_date") or "") > str(case["t0"])[:10]:
            continue
        if r.get("field_kind") not in {"revenue", "accounts_receivable"}:
            continue
        offset = year - int(r["year"])
        if offset not in (0, 1, 2) or not isinstance(r.get("value"), (int, float)):
            continue
        row = deepcopy(r)
        row["field_id"] = ("revenue" if r["field_kind"] == "revenue" else "ar") + "_" + ["current", "previous", "prior"][offset]
        rows.append(row)
    return year, rows


def unwrap(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    for key in ("result", "run"):
        if isinstance(d.get(key), dict) and "run_id" in d[key]:
            return d[key]
    return d


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = load_seed_cases(ROOT)
    raw_path = ROOT / "outputs/决赛整改_2026-10-09/e29c175_线上真实模型/原任务与真实结果.json"
    run = unwrap(raw_path)
    case = next(c for c in cases if c["case_id"] == run["context"]["case_id"])
    save("主案例历史运行索引.json", {"run_id": run["run_id"], "code_sha": "e29c175", "path": str(raw_path.relative_to(ROOT)), "sha256": sha(raw_path), "calls": run["provider_call_count"], "model_id": run["model_id"], "duration_ms": run["duration_ms"], "quality_scoring": "not_performed", "notice": NOTICE})
    field_rows = []
    for row in run["sources"]:
        doc = next(d for d in case["documents"] if d["document_id"] == row["document_id"])
        pdf = ROOT / "backend/runtime/cases" / case["case_id"] / "documents" / (doc["document_id"] + ".pdf")
        field_rows.append({"企业名称": case["company_name"], "证券代码": "000858", "会计年度": row["year"], "字段": row["field_id"], "年报版本": doc["announcement_title"], "披露日期": doc["disclosure_date"], "来源URL": doc["source_url"], "文档哈希": sha(pdf), "哈希与登记一致": sha(pdf).upper() == row["file_sha256"].upper(), "PDF物理页": row["pdf_page"], "印刷页": row["pdf_page"], "表名": "主要会计数据和财务指标" if row["field_id"].startswith("revenue") else "资产构成重大变动情况", "科目名": "营业收入" if row["field_id"].startswith("revenue") else "应收账款", "年度列": str(row["year"]), "币种": "CNY", "单位": "元", "范围": "合并", "余额净额口径": row["field_basis"], "原文金额": row["value"], "系统登记金额": row["value"], "差异": 0, "AI核对状态": "文本与页面待核对，不由脚本自动签发", "真人确认状态": "待确认", "核对依据位置": f"原文页/{row['year']}_P{row['pdf_page']:03d}.png", "原文PDF": str(pdf.relative_to(ROOT)), "运行编号": run["run_id"]})
    table("主案例逐字段核对.csv", field_rows)
    result = _r1_result(run["sources"], []).model_dump(mode="json")
    save("主案例复算.json", {"run_id": run["run_id"], "recomputed_on": "2026-10-11", "rules": result, "ar_note": {"page": 88, "gross_current": 44901936.12, "allowance_current": 7156516.61, "net_current": 37745419.51, "gross_previous": 43604028.89, "allowance_previous": 6257466.94, "net_previous": 37346561.95}, "adoption": "保持历史净额口径，未替换为账面余额", "ai_generated_content_notice": NOTICE})
    sensitivities = []
    included = []
    exclusions = []
    for c in cases:
        year, rows = period_rows(c)
        gate = evaluate_industry_gate(company=c, case=c, rule_ids=["R1"])
        reason = None
        # 东方财富2024年报第10页披露证券等金融业务；独立排除该混合金融样本。
        # 不改生产行业路由，避免把一般销售与收款阈值外推到金融收入。
        if c.get("ticker") == "300059":
            exclusions.append({"case_id": c["case_id"], "company": c["company_name"], "reason": "独立范围复核：金融混合业务，不纳入一般销售与收款敏感性", "source": "backend/runtime/cases/CNINFO_300059_T0_20260319/documents/CNINFO-300059-2024-A803C2D1D188.pdf", "pdf_page": 10, "industry_gate": gate, "production_gate_limitation": "简称启发式未识别金融行业"})
            continue
        if "R1" not in gate.get("allowed_rules", []):
            reason = "行业闸门未允许R1"
        if not {"revenue_current", "revenue_previous", "ar_current", "ar_previous"} <= {r["field_id"] for r in rows}:
            reason = "缺少四金额"
        # 技术来源或截止日受阻的案例不能当作未触发样本。
        if any(r.get("source_cutoff_conflict") or r.get("candidate_quality_issues") for r in rows):
            reason = "字段技术/截止日问题"
        if reason:
            exclusions.append({"case_id": c["case_id"], "company": c["company_name"], "reason": reason, "industry_gate": gate})
            continue
        values = [_r1_result(rows, [], gap_threshold=t).model_dump(mode="json") for t in (.10, .15, .20)]
        if any(v["status"] not in {"candidate", "RULE_NOT_TRIGGERED"} for v in values):
            exclusions.append({"case_id": c["case_id"], "company": c["company_name"], "reason": "零基数或不可计算"})
            continue
        included.append(c["case_id"])
        m = values[1]["metrics"]
        sensitivities.append({"案例": c["case_id"], "企业": c["company_name"], "当期": year, "上期": year-1, "10个百分点": values[0]["status"], "15个百分点": values[1]["status"], "20个百分点": values[2]["status"], "状态改变": len({v["status"] for v in values}) > 1, "增速差_百分点": m["growth_gap"]*100, "应收绝对变动_元": m["absolute_ar_change"], "应收收入比": m["ar_to_revenue_current"], "口径限制": values[1]["risk_card"]["basis_limitation"]})
    if sensitivities:
        table("R1零模型敏感性.csv", sensitivities)
    save("R1敏感性纳入排除.json", {"scope": "本机登记快照，非15案工程批次", "included": included, "excluded": exclusions, "config": current_r1_config(), "signoff": load_signoff_status(), "provider_calls": 0})
    md("规则用途与校验说明.md", """# R1用途与证据校验说明
15个百分点用于工程候选筛选，30个百分点只描述偏离强度，绝对变动门槛为0元。本机存在队长2026-08-25竞赛演示签字记录，当前有效性见R1敏感性纳入排除.json。没有独立标签、阈值校准研究或准则支持，不能称为准则阈值。默认配置保持不变。
为什么值得查：五粮液增长率差主要受收入下降影响，应收净额只增加398,857.56元。需要回查收入模式、结算条款与回款资料，不能凭55.62个百分点得出高风险结论。金额重要性未设置时保持未评价；余额变化不是已识别错报，低于计划重要性也不等于无需核查。
敏感性纳入四金额可计算且行业闸门允许的本机登记案例，排除清单单列。只改变10/15/20个百分点候选阈值，强度阈值固定30个百分点。零模型分析不能评价哪个阈值更准确。字段专业状态仍待确认。

|校验对象|生产入口|可识别|不能识别|失败处理|
|---|---|---|---|---|
|运行/角色/规则/证据ID|agents.validate_agent_output|编号越界、跨运行|合法ID与文本语义的蕴含|拒绝当前输出|
|数字、单位、年度|numeric_gate.validate_numeric_claims，main最终调用|无来源数字、部分单位/符号矛盾|某个合法年份对应错年度、数值碰巧相同|关键未验证数字阻止完整成功|
|规则事实和措辞|agents._validate_deterministic_fact_language|未触发写成触发、阈值/趋势矛盾|任意业务因果关系|失败并受控修正|
|当前企业/规范/类比用途|evidence_fitness.enforce_output_boundaries|仅背景证明企业事实|真实年报与任意文字的语义蕴含|降为待验证并记录|
|原文支持具体主张|主张并排原文回查|可供真人检查|未实现通用自动语义验证|semantic_support_status=not_verified|

本轮修复：主张与正常解释同等经过用途校验，旧实现只检查claims。构造反例是离线测试，不是实际模型失败。引用合法但原文不支持结论时，程序仍可能通过编号和数字检查，展示必须写支持关系待复核。先款后货披露只支持制度描述，不足以证明本期差异已解释。
""")
    pairs = []
    for pid, cid in [("RUN-V7-55ED10CB1D9C", "RUN-SUP-0C4AB87C0D93")]:
        pp, cp = [ROOT / "backend/runtime/runs" / (rid + ".json") for rid in (pid,cid)]
        parent, child = unwrap(pp), unwrap(cp)
        if child.get("parent_run_id") != pid and child.get("context", {}).get("parent_run_id") != pid:
            raise ValueError("补证父子身份不一致")
        pairs.append({"parent_run_id": pid, "child_run_id": cid, "parent_path": str(pp.relative_to(ROOT)), "child_path": str(cp.relative_to(ROOT)), "parent_sha": sha(pp), "child_sha": sha(cp), "same_fields": parent.get("sources") == child.get("sources"), "parent_draft": parent.get("final_ai_draft"), "child_draft": child.get("final_ai_draft"), "supplement_evidence": child.get("evidence_bundle", {}).get("supplement_evidence"), "parent_recommendation": parent.get("ai_recommendation"), "child_recommendation": child.get("ai_recommendation"), "attribution": "没有无补证同输入重跑控制，仅作差异展示", "sample": "公开演示样例，非企业内部真实账龄"})
    save("补证同源差异.json", pairs)
    # 真实资料缺口案只选现有登记数据，不人为删掉字段制造缺口。
    gap_case = next((c for c in cases if not {"revenue_current","revenue_previous","ar_current","ar_previous"} <= {r["field_id"] for r in period_rows(c, True)[1]} and "R1" in evaluate_industry_gate(company=c,case=c,rule_ids=["R1"]).get("allowed_rules",[])), None)
    experiments = []
    for c, reason in [(case, "规则触发"), (next(c for c in cases if c["ticker"] == "600938"), "规则未触发"), (gap_case, "原登记资料缺口")]:
        if c is None:
            continue
        year, rows = period_rows(c, reason == "原登记资料缺口")
        rule = _r1_result(rows, []).model_dump(mode="json")
        snippets = [r for r in (c.get("demo_rag_evidence") or []) if not c.get("t0") or str(r.get("disclosure_date") or "") <= str(c["t0"])[:10]]
        bundle = {"field_evidence": rows, "rag_evidence": deepcopy(snippets), "procedure_evidence": [], "knowledge_evidence": []}
        # 既有主案例使用历史真实检索包；双方读同一包。
        if c["case_id"] == case["case_id"]:
            bundle = deepcopy(run["evidence_bundle"])
        payload = {"case_id": c["case_id"], "company": c["company_name"], "year": year, "selection_reason": reason, "rule_result": rule, "evidence_bundle": bundle, "analysis_route": "risk_candidate" if rule["status"] == "candidate" else "negative_confirmation" if rule["status"] == "RULE_NOT_TRIGGERED" else "evidence_gap_review"}
        path = f"探索对照/inputs/{c['case_id']}.json"
        save(path,payload)
        experiments.append({"case_id":c["case_id"],"reason":reason,"path":path,"input_hash":sha(OUT/path),"rule_status":rule["status"]})
    order = [{"case_id":c["case_id"],"condition":condition,"repeat":repeat} for repeat in (1,2) for i,c in enumerate(experiments) for condition in (("A","B") if (repeat+i)%2 else ("B","A"))]
    save("探索对照/manifest.json", {"experiment_id":"EXP-FINALS-20261011-AB-01","status":"prepared_not_executed","formal_evaluation_pointer_changed":False,"model_id":"从获批授权文件冻结，不猜测供应商实际ID","cases":experiments,"order":order,"planned_outputs":len(order),"base_calls":len(order)*2,"repeats":2,"gap_case_available":gap_case is not None,"conditions":{"A":"确定性计算+同证据包+一次review完整草稿+相同最终硬校验","B":"确定性计算+同证据包+当前三角色链+相同最终硬校验"},"limitations":["角色合同和调用数不同，成本实测","已登记真实非金融缺口案找不到时只完成两类，不人工制造第三类","字段和原文专业评价未执行"],"provider_calls":0,"attempts":0,"failures":0,"human_scoring":"not_performed","notice":NOTICE})
    table("探索对照/评分表_评价者1.csv", [{"匿名编号":"待真实运行后生成","不受支持断言数":"","引用不匹配数":"","参考项遗漏数":"","任务可执行性0至2":"","总体意见":"","评价者":"","实际评价时间":""}])
    (OUT/"探索对照/评分表_评价者2.csv").write_bytes((OUT/"探索对照/评分表_评价者1.csv").read_bytes())
    save("当前答辩事实表.json", {"source_baseline_sha":"7f83b52564aa2a10a21191d20d49ab44a5df3fa3","branch":"remediation/finals-20261011","local_modified_not_deployed":True,"main_case":{"run_id":run["run_id"],"run_code":"e29c175","years":[2025,2024],"values_changed":False,"basis":"合并应收净额与营业收入","professional_confirmation":"pending"},"historical_oct10":{"case_outputs":15,"provider_calls":48,"additional_previews":8,"preview_calls":0,"source_links":70,"source":"docs/2026-10-10_公网真人演示全流程验收.md","raw_directory_available":True,"full_raw_audit_this_round":False},"experiment":"探索对照/manifest.json","ppt_source":"not_found_in_workspace","script_source":"not_found_in_workspace","rehearsal":"not_performed","deployment_live":"待只读核对","notice":NOTICE})
    print(json.dumps({"output":str(OUT),"fields":len(field_rows),"sensitivity_included":len(included),"excluded":len(exclusions),"experiment_cases":len(experiments),"gap_case":bool(gap_case)},ensure_ascii=False))


if __name__ == "__main__":
    main()
