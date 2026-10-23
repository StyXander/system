"""任务4：会计处理路径映射。

模型负责提出路径，规则库负责给出适用前提与必须取得的证据。
这里不判断金额，也不生成“已确认”结论：treatment 初始状态一律是 hypothesis。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .models import AccountingRule, AccountingTreatment, SustainabilityEvent

RULES_PATH = Path(__file__).with_name("accounting_rules.json")
MAPPING_VERSION = "accounting_mapping_v1.0"

# 条件与证据的对应关系：用于把“待验证前提”翻译成可执行的补证动作。
CONDITION_EVIDENCE = {
    "项目已立项": "项目立项批复或董事会决议",
    "实际发生": "本期增加额或现金支付额",
    "实际支出": "本期增加额或现金支付额",
    "经济利益": "投产或使用记录",
    "可靠计量": "合同金额或发票",
    "预定可使用状态": "验收或投产公告",
    "资本化": "研发资本化政策与项目进度",
    "法定义务": "监管要求或复垦方案",
    "减值迹象": "停产、闲置或政策变化证据",
    "交叉索引": "年报附注中的项目名称",
    "期间一致": "同一会计期间的报表与附注",
}


@lru_cache(maxsize=1)
def load_rules(path: str | None = None) -> tuple[AccountingRule, ...]:
    raw = json.loads(Path(path or RULES_PATH).read_text(encoding="utf-8"))
    return tuple(AccountingRule.model_validate(item) for item in raw["rules"])


def rules_for_activity(activity_type: str) -> list[AccountingRule]:
    return [rule for rule in load_rules() if activity_type in rule.activity_types]


def _condition_key(index: int, label: str) -> str:
    for token, evidence in CONDITION_EVIDENCE.items():
        if token in label:
            return f"c{index:02d}:{token}"
    return f"c{index:02d}:{label[:12]}"


def _infer_activity(event: SustainabilityEvent) -> str:
    """“其他”类事项按原文再判一次活动类型，避免只落到兜底规则。"""
    from .textutil import activity_type
    inferred, _label = activity_type(event.quote)
    return inferred if inferred != "other" else event.activity_type


def map_event(event: SustainabilityEvent) -> list[AccountingTreatment]:
    """为一个事项给出候选会计路径；同一事项可有多条互斥路径。"""
    treatments: list[AccountingTreatment] = []
    activity = _infer_activity(event)
    for rule in rules_for_activity(activity):
        conditions = []
        for index, label in enumerate(rule.applies_when, start=1):
            evidence = next((value for token, value in CONDITION_EVIDENCE.items() if token in label), "")
            conditions.append({"key": _condition_key(index, label), "label": label,
                               "status": "unknown", "how_to_verify": evidence})
        treatments.append(AccountingTreatment(
            treatment_id=f"{event.event_id}:{rule.rule_id}", rule_id=rule.rule_id,
            scene=rule.scene, accounts=list(rule.accounts), conditions=conditions,
            required_evidence=list(rule.required_evidence), basis=list(rule.basis),
            cash_flow_class=getattr(rule, "cash_flow_class", ""), status="hypothesis",
        ))
    if not treatments:
        treatments.append(AccountingTreatment(
            treatment_id=f"{event.event_id}:AR-00", rule_id="AR-00",
            scene="未匹配到专用会计规则", accounts=[],
            conditions=[{"key": "c01:业务实质", "label": "需要人工判断业务实质", "status": "unknown",
                         "how_to_verify": "补充项目合同与支出性质说明"}],
            required_evidence=["项目合同", "支出性质说明"],
            basis=[{"title": "企业会计准则——基本准则", "issuer": "财政部", "version": "2014年修订",
                    "locator": "会计确认与计量基础", "note": "仅作兜底，不指向具体科目"}],
            status="hypothesis"))
    return treatments


def map_events(events: list[SustainabilityEvent]) -> tuple[list[AccountingTreatment], dict]:
    treatments: list[AccountingTreatment] = []
    for event in events:
        treatments.extend(map_event(event))
    receipt = {
        "version": MAPPING_VERSION,
        "rules_loaded": len(load_rules()),
        "rules_with_pending_review": sum(1 for rule in load_rules() if rule.verification != "verified"),
        "treatments": len(treatments),
        "note": "每条路径都是待验证假设；规则库条款位置未逐条核对的不写条号。",
    }
    return treatments, receipt
