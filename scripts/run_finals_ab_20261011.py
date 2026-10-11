"""独立探索性A/B入口；默认仅离线检查，付费执行须提供本实验授权与硬预算。"""
import argparse
import hashlib
import json
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from backend.app import agents
from backend.app.schemas import RuleResult
from backend.app.evidence_fitness import enforce_output_boundaries, fitness_map_for_evidence
from backend.app.numeric_gate import validate_numeric_claims

BASE = ROOT / "决赛准备/整改_2026-10-11/探索对照"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def single_payload(run_id, rule, compact, route):
    """复用共同事实与最终review合同，去掉三角色专用的前序输出依赖。"""
    payload = agents._user_payload(run_id, "challenge", rule, compact, {}, route)
    payload["role"] = "review"
    contract = payload["output_contract"]
    contract["role"] = "review"
    statuses = agents.ROUTE_ROLE_ALLOWED_STATUSES.get(route, agents.ROLE_ALLOWED_STATUSES)["review"]
    contract["status_values_for_this_role"] = statuses
    contract["status_values"] = statuses
    return payload


def final_gate(outputs, rule, bundle, year):
    """A/B共用用途与数字闸门；不把引用存在性称为语义验证。"""
    violations, bindings = [], []
    for output in outputs:
        violations.extend(enforce_output_boundaries(output, fitness_map_for_evidence(bundle)))
        for key in ("claims", "normal_explanations"):
            bindings.extend(output.get(key) or [])
        for key in ("reason_for_status", "draft_observation", "draft_title"):
            bindings.append({"text": output.get(key) or "", "evidence_ids": []})
    numeric = validate_numeric_claims("", rule_results=[rule.model_dump(mode="json")], evidence_bundle=bundle,
                                    allowed_years={year, year-1, year-2}, claim_evidence_bindings=bindings)
    return {"fitness_violations": violations, "numeric": numeric, "semantic_support": "not_verified",
            "passed": not violations and bool(numeric.get("passed"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    cases = {}
    for item in manifest["cases"]:
        path = BASE.parent / item["path"]
        if digest(path) != item["input_hash"]:
            raise ValueError("冻结输入哈希不一致")
        cases[item["case_id"]] = json.loads(path.read_text(encoding="utf-8"))
    if not args.execute:
        checks = []
        for c in cases.values():
            rule = RuleResult.model_validate(c["rule_result"])
            compact = agents.compact_evidence_bundle(c["evidence_bundle"])
            payload = single_payload("EXP-DRYRUN", rule, compact, c["analysis_route"])
            json.dumps(payload)
            checks.append({"case_id": c["case_id"], "route": c["analysis_route"], "evidence_count":len(compact), "status":rule.status})
        print(json.dumps({"offline_checks":checks,"planned_attempts":len(manifest["order"]),"provider_calls":0,"human_scoring":"not_performed"},ensure_ascii=False))
        return
    if args.authorization is None:
        parser.error("--execute需要--authorization，不能凭已有密钥推定实验预算")
    auth = json.loads(args.authorization.read_text(encoding="utf-8"))
    if auth.get("approved") is not True or auth.get("experiment_id") != manifest["experiment_id"] or not auth.get("approved_by"):
        raise ValueError("没有该探索实验的真实预算授权")
    cap_calls, cap_tokens = int(auth["max_calls"]), int(auth["max_tokens"])
    model, endpoint = str(auth["model_id"]), str(auth["endpoint"])
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key or cap_calls <= 0 or cap_tokens <= 0:
        raise ValueError("密钥或预算缺失")
    # 每次执行独立目录，不覆盖首次失败或过去尝试。记录源码身份和授权哈希。
    directory = BASE / "raw" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory.mkdir(parents=True, exist_ok=False)
    write_new(directory/"execution_binding.json", {"manifest_hash":digest(BASE/"manifest.json"),"authorization_hash":digest(args.authorization),"model_id":model,"endpoint":endpoint,"temperature":0.1,"prompt_version":agents.PROMPT_VERSION,"source_hashes":{str(p.relative_to(ROOT)):digest(p) for p in [Path(__file__),ROOT/"backend/app/agents.py",ROOT/"backend/app/evidence_fitness.py",ROOT/"backend/app/numeric_gate.py"]},"budget":{"calls":cap_calls,"tokens":cap_tokens},"prices":"unknown","money_limit":"not_claimed"})
    usage = {"calls":0,"input_tokens":0,"output_tokens":0,"reserved_tokens":0}
    records = []
    original = agents._call_model
    trial = {}
    def metered(**kwargs):
        # UTF8字节数作保守输入上界，再预留角色输出上限；缺token用量仍不突破硬预算。
        role = kwargs["role"]
        reserve = len((agents._system_prompt(role,kwargs.get("analysis_route","risk_candidate"))+json.dumps(kwargs["payload"],ensure_ascii=False)).encode("utf-8"))+int(agents.ROLE_MAX_OUTPUT_TOKENS[role])+4096
        if usage["calls"] >= cap_calls or usage["reserved_tokens"]+reserve > cap_tokens:
            raise RuntimeError("EXPERIMENT_BUDGET_STOP")
        usage["calls"] += 1
        usage["reserved_tokens"] += reserve
        index = usage["calls"]
        start = datetime.now(timezone.utc).isoformat()
        try:
            result = original(**kwargs)
            # 保留返回的原始工具参数；此后校验不能重写这一文件。
            write_new(directory/f"provider_{index:03d}.json", {"start":start,"end":datetime.now(timezone.utc).isoformat(),"trial":trial,"role":role,"input_hash":hashlib.sha256(json.dumps(kwargs["payload"],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),"raw_tool_output":result[0],"response_sha256":result[2],"input_tokens":result[4],"output_tokens":result[5]})
            usage["input_tokens"] += result[4] or 0
            usage["output_tokens"] += result[5] or 0
            return result
        except Exception as error:
            write_new(directory/f"provider_{index:03d}_failure.json", {"start":start,"trial":trial,"role":role,"error_type":type(error).__name__,"failure_code":getattr(error,"code",type(error).__name__),"tokens":"unknown"})
            raise
    agents._call_model = metered
    try:
        for number,item in enumerate(manifest["order"],1):
            trial = dict(item)
            c=cases[item["case_id"]]
            rid="EXP-"+uuid.uuid4().hex[:12].upper()
            rule=RuleResult.model_validate(c["rule_result"])
            bundle=c["evidence_bundle"]
            compact=agents.compact_evidence_bundle(bundle)
            start=time.monotonic(); utc_start=datetime.now(timezone.utc).isoformat(); calls_before=usage["calls"]
            record={**item,"experiment_id":manifest["experiment_id"],"run_id":rid,"model_id":model,"start":utc_start,"cost":"unknown","human_score":None}
            try:
                if item["condition"]=="A":
                    payload=single_payload(rid,rule,compact,c["analysis_route"])
                    payload["single_generation_task"]="独立完成完整草稿，同时考虑异常、正常解释、资料缺口、具体后续程序及专业边界。使用全部相同证据包，保持与三角色最终复核相同输出合同。"
                    raw=metered(api_key=key,base_url=endpoint,model_id=model,role="review",payload=payload,analysis_route=c["analysis_route"])[0]
                    output=agents.validate_agent_output(raw,run_id=rid,role="review",rule_id="R1",allowed_evidence_ids={r["evidence_id"] for r in compact},rule_result=rule,analysis_route=c["analysis_route"])
                    outputs=[output.model_dump(mode="json")]
                else:
                    steps=agents.run_agent_chain(run_id=rid,rule_result=rule,evidence_bundle=bundle,enabled=True,api_key=key,base_url=endpoint,model_id=model,analysis_route=c["analysis_route"])
                    record["steps"]=[s.model_dump(mode="json") for s in steps]
                    if not any(s.role=="review" and s.status=="completed" for s in steps):
                        raise ValueError("THREE_ROLE_CHAIN_INCOMPLETE")
                    outputs=[s.output.model_dump(mode="json") for s in steps if s.output]
                gate=final_gate(outputs,rule,bundle,c["year"])
                record.update({"outputs":outputs,"final_gate":gate,"status":"completed" if gate["passed"] else "validation_failed"})
            except Exception as error:
                record.update({"status":"failed","failure_code":str(error) if str(error)=="EXPERIMENT_BUDGET_STOP" else getattr(error,"code",type(error).__name__)})
            record.update({"end":datetime.now(timezone.utc).isoformat(),"end_to_end_seconds":time.monotonic()-start,"provider_calls":usage["calls"]-calls_before,"usage_cumulative":dict(usage)})
            write_new(directory/f"attempt_{number:02d}.json",record)
            records.append(record)
            # 首次失败保持在分母；预算耗尽后剩余项目记未执行，不能补成失败或成功。
            if record.get("failure_code")=="EXPERIMENT_BUDGET_STOP":
                break
    finally:
        agents._call_model=original
    # 只将实际发生的尝试匿名化，失败也保留；映射不放入评价者目录。
    order=list(records); random.SystemRandom().shuffle(order)
    pack=directory/"anonymous_scoring";pack.mkdir()
    mapping=[]
    for index,record in enumerate(order,1):
        anonymous_id=f"ANON-{index:02d}"
        outputs=record.get("outputs") or []
        final=dict(outputs[-1]) if outputs else None
        if final:
            final.pop("role",None);final.pop("run_id",None)
        write_new(pack/f"{anonymous_id}.json",{"anonymous_id":anonymous_id,"case_id":record["case_id"],"status":record["status"],"failure_code":record.get("failure_code"),"final_output":final,"semantic_support":"not_verified"})
        mapping.append({"anonymous_id":anonymous_id,"case_id":record["case_id"],"condition":record["condition"],"repeat":record["repeat"],"run_id":record["run_id"]})
    write_new(directory/"private_anonymous_mapping.json",mapping)
    write_new(pack/"limitations.json",{"blinding":"移除模型、角色和条件字段；模型正文可能透露处理过程，因此不声称完全盲评。","human_scoring":"not_performed","actual_attempts":len(records),"planned_attempts":len(manifest["order"]),"unexecuted":len(manifest["order"])-len(records)})
    print(json.dumps({"raw_directory":str(directory),"usage":usage,"semantic_scoring":"not_performed"},ensure_ascii=False))


if __name__=="__main__":
    main()
