"""认定级资料用途、条件检验和取证队列；不计算专业结论或模型置信概率。"""

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .evidence_decision_schemas import AuditInvestigation, EvidenceCheckResponse

DATA_ROOT = Path(__file__).resolve().parents[1]
NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
BOUNDARY = "条件满足仅表示登记字段通过本规则检验；原件真实性、文字语义支持和专业采用均未由程序确认。"


def digest(value: Any) -> str:
    """排序后散列用于重放；不使用运行时随机编号或模型措辞作为真值。"""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_rulebook() -> dict[str, Any]:
    return json.loads((DATA_ROOT / "evidence_decision_rules.json").read_text(encoding="utf-8"))


def load_scenarios() -> list[dict[str, Any]]:
    return json.loads((DATA_ROOT / "evidence_validation_scenarios.json").read_text(encoding="utf-8"))["scenarios"]


def _number(value: Any) -> Decimal | None:
    # 不把缺失值补成零，也不接受无限大或非数；金额比较保持十进制口径。
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _scope_reason(atom: dict, base: dict, granularity: str) -> str | None:
    """先检查案例、日期、客户/交易及粒度；缺失的归属不能用公司相同代替。"""
    if atom.get("case_id") != base["case_id"]:
        return "案例不一致"
    if atom.get("source_state") not in {"registered", "synthetic_registered"}:
        return "资料未登记或来源状态不足"
    try:
        if date.fromisoformat(atom["available_at"]) > date.fromisoformat(base["t0"]):
            return "资料可得日期晚于T0"
    except (KeyError, ValueError, TypeError):
        return "资料可得日期或T0未登记"
    # 已发生业务记录的业务日期不能晚于声明的资料可得日，防止未来记录提前支持。
    for key in ("event_date", "posting_date"):
        if atom.get(key):
            try:
                if date.fromisoformat(atom[key]) > date.fromisoformat(atom["available_at"]):
                    return "业务日期晚于声明的资料可得日"
            except (ValueError, TypeError):
                return "业务日期不可核对"
    # 条件规定最低明细粒度；带客户和债权归属的逐笔资料可用于客户级核对。
    allowed_granularities = {"transaction": {"transaction"}, "customer": {"customer", "transaction"}}
    if atom.get("granularity") not in allowed_granularities[granularity]:
        return "汇总或其他粒度不能替代对应明细"
    for key in (["customer_id", "transaction_id"] if granularity == "transaction" else ["customer_id"]):
        if not base.get(key) or atom.get(key) != base[key]:
            return "客户或交易归属不足/不一致"
    return None


def _predicate(question_id: str, groups: dict[str, list[dict]]) -> tuple[list[str], list[str], list[dict]]:
    """只复算明示字段；所有候选资料一起检验，不能挑选一份有利资料掩盖冲突。"""
    missing, conflicts, facts = [], [], []
    if question_id == "REV-CUT":
        events = {a.get("recognition_event") for a in groups["contract"]}
        if events != {"acceptance"}:
            missing.append("合同确认条件尚非本规则支持的验收条件，不能推断截止")
        else:
            for acceptance in groups["acceptance"]:
                for posting in groups["posting"]:
                    try:
                        event_date, posting_date = date.fromisoformat(acceptance["event_date"]), date.fromisoformat(posting["posting_date"])
                        same_period = (event_date.year, event_date.month) == (posting_date.year, posting_date.month)
                        facts.append({"condition": "验收与入账月份一致", "satisfied": same_period, "evidence_ids": [acceptance["evidence_id"], posting["evidence_id"]]})
                        if not same_period:
                            conflicts.append("登记验收日期与入账月份不同，需取得截止调整或合同解释")
                    except (KeyError, ValueError, TypeError):
                        missing.append("验收日期或入账日期未登记")
    if question_id == "REV-ACC":
        # 只有同一币种、计量基础及单位才能复算数量单价折扣。
        rows = [a for values in groups.values() for a in values]
        if any(not a.get(k) for a in rows for k in ("currency", "unit", "basis")) or any(len({a.get(k) for a in rows}) != 1 for k in ("currency", "unit", "basis")):
            missing.append("币种、单位或含税/不含税基础缺失或不一致")
        else:
            for contract in groups["contract"]:
                q, p, d = [_number(contract.get(k)) for k in ("quantity", "unit_price", "discount")]
                expected = q * p - d if None not in (q, p, d) else None
                if expected is None:
                    missing.append("合同数量、单价或折扣未登记")
                    continue
                for row in groups["invoice"] + groups["posting"]:
                    amount = _number(row.get("amount"))
                    if amount is None:
                        missing.append("发票或入账金额未登记")
                    else:
                        same = amount == expected
                        facts.append({"condition": "合同复算金额与登记金额一致", "expected": str(expected), "actual": str(amount), "satisfied": same, "evidence_ids": [contract["evidence_id"], row["evidence_id"]]})
                        if not same:
                            conflicts.append("合同复算金额与发票或入账金额不一致")
    if question_id == "AR-EXI":
        for balance in groups["balance"]:
            amount = _number(balance.get("amount"))
            matches = [a for a in groups["corroboration"] if a.get("balance_id") == balance.get("balance_id") and a.get("balance_id")]
            if amount is None or amount <= 0:
                missing.append("客户债权余额金额未登记或不为正数")
                continue
            compatible = [a for a in matches if all(a.get(k) == balance.get(k) and a.get(k) for k in ("currency", "basis", "unit"))]
            if not compatible:
                missing.append("确认或回款未对应相同债权编号及金额口径")
                continue
            receipts = [_number(a.get("amount")) for a in compatible if a["kind"] == "receipt_record"]
            confirmations = [_number(a.get("amount")) for a in compatible if a["kind"] == "confirmation_response"]
            if any(x is None or x < 0 for x in receipts + confirmations):
                missing.append("回款或确认金额缺失/无效")
                continue
            covered = sum(receipts, Decimal(0))
            full_confirmation = any(x == amount for x in confirmations)
            facts.append({"condition": "登记余额的对应金额覆盖", "balance": str(amount), "receipts": str(covered), "receipt_coverage_ratio": str(covered / amount), "evidence_ids": [balance["evidence_id"], *[a["evidence_id"] for a in compatible]]})
            if covered > amount or any(x != amount for x in confirmations):
                conflicts.append("对应回款超过余额或确认金额与余额不一致")
            elif covered < amount and not full_confirmation:
                missing.append(f"仅回款{covered}，余额{amount - covered}仍缺对应确认或其他核查资料")
    if question_id == "AR-VAL":
        # 估计是否恰当由专业人员决定；字段齐备也不能产生“减值充分”。
        balance_ids = {a.get("balance_id") for rows in groups.values() for a in rows}
        if None in balance_ids or "" in balance_ids or len(balance_ids) != 1:
            missing.append("账龄、回款及减值依据未对应同一债权编号")
        if any(_number(a.get("amount")) is None or _number(a.get("amount")) <= 0 for a in groups["balance"]):
            missing.append("客户债权余额金额未登记或不为正数")
        if any(not a.get(k) for rows in groups.values() for a in rows for k in ("currency", "unit", "basis")) or any(len({a.get(k) for rows in groups.values() for a in rows}) != 1 for k in ("currency", "unit", "basis")):
            missing.append("余额、账龄、回款及减值依据的币种、单位或口径不一致/缺失")
        if any(not a.get("method") for a in groups["impairment"]):
            missing.append("减值方法或估计依据未登记")
        if any(not isinstance(a.get("aging_days"), int) or a["aging_days"] < 0 for a in groups["aging"]):
            missing.append("客户账龄天数未登记或无效")
        if any(_number(a.get("amount")) is None for a in groups["receipts"]):
            missing.append("客户回款金额未登记")
    return list(dict.fromkeys(missing)), list(dict.fromkeys(conflicts)), facts


def investigate(base: dict[str, Any], selected_ids: list[str] | None = None) -> AuditInvestigation:
    """从不可变底稿和选择集合生成五项稳定问题；不修改来源或人工作业状态。"""
    rules = load_rulebook()
    catalog = base["evidence"]
    identifiers = [a["evidence_id"] for a in catalog]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("底稿包含重复证据编号")
    selected = set(base["default_evidence_ids"] if selected_ids is None else selected_ids)
    if not selected.issubset(set(identifiers)):
        raise ValueError("证据编号不属于该底稿白名单")
    decisions, questions, tasks = [], [], []
    # 同一原件同一内容的重复登记只参加一次，重复上传不能增加覆盖率。
    seen, active = set(), []
    for atom in catalog:
        identity = (atom.get("original_id") or atom["evidence_id"], atom.get("content_sha256") or digest({k: v for k, v in atom.items() if k != "evidence_id"}))
        duplicate = atom["evidence_id"] in selected and identity in seen
        if atom["evidence_id"] in selected and not duplicate:
            seen.add(identity)
            active.append(atom)
        decisions.append({"evidence_id": atom["evidence_id"], "title": atom["title"], "kind": atom["kind"], "selected": atom["evidence_id"] in selected, "duplicate": duplicate, "supports_assertions": rules["kind_assertions"].get(atom["kind"], []), "uses": [], "semantic_support_status": "not_verified"})
    by_id = {d["evidence_id"]: d for d in decisions}
    for definition in rules["questions"]:
        qid, groups = definition["question_id"], {}
        missing, supporting = [], []
        applicable = definition["account"] in base.get("accounts", ["收入", "应收账款"])
        for requirement in definition["requirements"]:
            accepted = []
            for atom in active:
                if atom["kind"] not in requirement["kinds"]:
                    continue
                reason = _scope_reason(atom, base, requirement["granularity"])
                by_id[atom["evidence_id"]]["uses"].append({"question_id": qid, "requirement_id": requirement["id"], "accepted": reason is None and applicable, "reason": reason or ("该账户不在底稿范围" if not applicable else "归属、可得日期及粒度条件通过"), "purpose": requirement["purpose"]})
                if reason is None and applicable:
                    accepted.append(atom)
            groups[requirement["id"]] = accepted
            supporting.extend(a["evidence_id"] for a in accepted)
            if not accepted and applicable:
                missing.append(requirement["purpose"])
                tasks.append({"request_id": f"{qid}:{requirement['id']}", "question_id": qid, "assertion": definition["assertion"], "purpose": requirement["purpose"], "accepted_kinds": requirement["kinds"], "granularity": requirement["granularity"], "priority_reason": "取得前置明细资料", "priority": 0, "closes_condition": requirement["id"], "boundary": "取得资料后仍须核对原件及登记条件"})
        predicate_missing, conflicts, facts = ([], [], [])
        if applicable and not missing:
            predicate_missing, conflicts, facts = _predicate(qid, groups)
        missing.extend(predicate_missing)
        for index, reason in enumerate(conflicts + predicate_missing):
            tasks.append({"request_id": f"{qid}:check-{index}", "question_id": qid, "assertion": definition["assertion"], "purpose": reason, "accepted_kinds": [], "granularity": "transaction" if qid.startswith("REV") else "customer", "priority_reason": "解释登记字段冲突" if reason in conflicts else "取得区分解释的依据", "priority": 1 if reason in conflicts else 2, "closes_condition": "predicate", "boundary": "补充解释不能自动覆盖原始字段"})
        state = "not_applicable" if not applicable else "conflicting" if conflicts else "rule_supported" if not missing else "partial" if supporting else "missing"
        questions.append({"question_id": qid, "title": definition["title"], "assertion": definition["assertion"], "state": state, "supporting_evidence_ids": list(dict.fromkeys(supporting)), "missing_conditions": missing, "conflicts": conflicts, "computed_facts": facts, "alternative_explanation": definition["alternative"], "alternative_status": "unverified_hypothesis", "boundary": BOUNDARY})
    tasks.sort(key=lambda t: (t["priority"], t["question_id"], t["request_id"]))
    for rank, task in enumerate(tasks, 1):
        task["rank"] = rank
    scope_boundary = "金融专用规则范围不应用本通用销售收款条件，参考原运行的行业专用规则与资料任务。" if not base.get("accounts", ["收入", "应收账款"]) else ""
    return AuditInvestigation(rulebook_version=rules["version"], rulebook_sha256=digest(rules), source_snapshot_sha256=digest(base), case_id=base["case_id"], company_name=base["company_name"], source_mode=base["source_mode"], questions=questions, material_requests=tasks, evidence_decisions=decisions, evidence_catalog=catalog, default_evidence_ids=base["default_evidence_ids"], boundary=BOUNDARY + scope_boundary)


def check_evidence(base: dict, *, base_kind: str, base_id: str, include: list[str], exclude: list[str]) -> EvidenceCheckResponse:
    """独立检验不落库、不调用供应商，排除只作用于本次视图。"""
    registered = {a["evidence_id"] for a in base["evidence"]}
    if not (set(include) | set(exclude)).issubset(registered):
        raise ValueError("证据编号不属于该底稿白名单")
    if set(include) & set(exclude):
        raise ValueError("不能同时加入及排除同一证据")
    original = investigate(base)
    selected = sorted((set(base["default_evidence_ids"]) | set(include)) - set(exclude))
    checked = investigate(base, selected)
    changes = [{"question_id": before["question_id"], "before": before["state"], "after": after["state"], "missing_before": before["missing_conditions"], "missing_after": after["missing_conditions"], "conflicts_after": after["conflicts"]} for before, after in zip(original.questions, checked.questions) if before != after]
    identifier = digest({"base": checked.source_snapshot_sha256, "rules": checked.rulebook_sha256, "selected": selected})[:24]
    return EvidenceCheckResponse(check_id=f"CHECK-{identifier}", base_kind=base_kind, base_id=base_id, investigation=checked, changes=changes)


def base_from_run(context: dict, bundle: dict) -> dict:
    """年报及既有检索只登记汇总背景；不从自由文本猜客户、交易或原件字段。"""
    case_id = str(context.get("case_id") or "unknown")
    catalog = []
    for key, kind in (("field_evidence", "annual_field"), ("rag_evidence", "annual_disclosure"), ("supplement_evidence", "annual_disclosure"), ("procedure_evidence", "normative_basis")):
        for row in bundle.get(key, []):
            eid = row.get("evidence_id")
            if not eid or any(a["evidence_id"] == eid for a in catalog):
                continue
            atom = {"evidence_id": eid, "case_id": case_id, "title": str(row.get("field_label") or row.get("field_name") or row.get("title") or row.get("account_label") or eid), "kind": kind, "granularity": "summary", "source_state": "registered", "available_at": str(row.get("disclosure_date") or row.get("published_at") or row.get("as_of_date") or ""), "original_id": str(row.get("source_id") or eid), "content_sha256": digest(row), "provenance": row}
            if key == "supplement_evidence" and row.get("evidence_kind") == "assertion_evidence_atom":
                from .evidence_decision_schemas import RegisteredEvidenceFields
                fields = RegisteredEvidenceFields.model_validate(row["details"]).model_dump(mode="json", exclude_none=True)
                atom.update(fields)
                # 同文件中不同原子保留区别，同文件同字段的重复登记则只计一次。
                atom["original_id"] = str(row.get("file_sha256") or eid)
                atom["content_sha256"] = digest(fields)
            catalog.append(atom)
    typed = [a for a in catalog if a["kind"] not in {"annual_field", "annual_disclosure", "normative_basis"}]
    customers, transactions = {a.get("customer_id") for a in typed}, {a.get("transaction_id") for a in typed}
    # 一份底稿最多锁定一个明示交易范围；多个客户/交易不被拼成同一笔勾稽。
    customer = next(iter(customers)) if len(customers) == 1 else None
    transaction = next(iter(transactions)) if len(transactions) == 1 else None
    # 沿用已有金融行业边界，不把通用销售合同/发票条件套到贷款或保险业务。
    family = (context.get("industry_gate") or {}).get("industry_family")
    accounts = [] if family in {"banking", "insurance", "securities"} else ["收入", "应收账款"]
    return {"case_id": case_id, "company_name": str(context.get("company_name") or case_id), "source_mode": "registered_supplement" if typed else "public_annual_report", "t0": str(context.get("t0") or ""), "customer_id": customer, "transaction_id": transaction, "accounts": accounts, "evidence": catalog, "default_evidence_ids": [a["evidence_id"] for a in catalog]}


def handoff_contribution(investigation: AuditInvestigation, steps: list[Any]) -> dict:
    """计数仅表示结构化新增引用与任务，不等于反证正确或解释专业质量。"""
    questions = {q["question_id"] for q in investigation.questions}
    evidence = {a["evidence_id"] for a in investigation.evidence_catalog}
    materials = {t["request_id"] for t in investigation.material_requests}
    used, results = set(), []
    for step in steps:
        if step.output is None:
            continue
        handoffs = getattr(step.output, "investigation_handoffs", [])
        current = set()
        for item in handoffs:
            if item.question_id not in questions or not set(item.evidence_ids).issubset(evidence) or not set(item.material_request_ids).issubset(materials):
                raise ValueError("角色交接引用了未登记问题、证据或资料任务")
            current.update((item.question_id, "evidence", eid) for eid in item.evidence_ids)
            current.update((item.question_id, "material", mid) for mid in item.material_request_ids)
        results.append({"role": step.role, "new_reference_count": len(current - used), "reference_count": len(current), "handoff_count": len(handoffs), "status": "recorded" if handoffs else "not_recorded", "boundary": "新增引用计数，不代表独立证据或专业评分"})
        used.update(current)
    return {"roles": results, "professional_quality_score": None, "semantic_support_status": "not_verified"}


def model_investigation_registry(investigation: AuditInvestigation) -> dict:
    """模型只接收当前问题、用途及任务；不重复外发完整来源台账或原件路径。"""
    return {"rulebook_version": investigation.rulebook_version, "questions": investigation.questions,
            "material_requests": investigation.material_requests, "boundary": investigation.boundary}
