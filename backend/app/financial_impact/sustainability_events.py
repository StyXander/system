"""任务2：可持续事项自动抽取。

三条硬约束：
1. 阶段与金额性质分开判断，未来承诺不得写成当期已发生交易。
2. 项目身份只能来自原文明确写出的名称（书名号、引号或“项目/工程”后缀），
   不从金额相似性反推项目。
3. 模型只做字段补全，补全结果必须逐字回溯到原文，否则丢弃该字段。
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Callable

from .models import AmountNature, Stage, SustainabilityEvent
from .textutil import (activity_type, clean_quote, compact, detect_amount_nature,
                       detect_stage, period_from_text, project_name, sentences, strip_leading_verbs,
                       to_amounts)

EVENTS_VERSION = "sustainability_events_v1"
MAX_EVENTS = 24
REQUIRED_FIELDS = ("subject", "project_name", "period", "stage", "amount", "scope")
# “其他”类事项必须同时出现明确的环境/低碳词，否则只是普通经营表述。
STRONG_ENV = ("环保", "节能", "减排", "降碳", "绿色", "低碳", "污染", "碳排", "生态", "循环利用",
              "清洁生产", "资源综合利用", "环境治理", "超低排放", "固废", "危废", "余热", "余压")

STAGE_BY_LABEL = {
    "strategy": Stage.STRATEGY, "planned": Stage.PLANNED, "contracted": Stage.CONTRACTED,
    "executing": Stage.EXECUTING, "completed": Stage.COMPLETED, "settled": Stage.SETTLED,
    "recognized": Stage.RECOGNIZED, "unknown": Stage.UNKNOWN,
}
NATURE_BY_LABEL = {item.value: item for item in AmountNature}


def _event_id(document_id: str, page: int, quote: str) -> str:
    return "EV-" + hashlib.sha256(f"{document_id}|{page}|{compact(quote)[:60]}".encode()).hexdigest()[:10].upper()


def _bbox_of(page: dict, quote: str) -> list[float]:
    """优先用抽取阶段留下的坐标；没有则返回空，绝不编造坐标。"""
    for block in page.get("blocks_detail") or []:
        if quote[:24] and quote[:24] in str(block.get("text") or ""):
            return [round(float(v), 2) for v in (block.get("bbox") or [])]
    return []


def _score(sentence: str, amounts: list, stage: Stage, name: str) -> int:
    score = 0
    if any(amount.dimension == "money" for amount in amounts):
        score += 4
    if name:
        score += 3
    if stage not in {Stage.UNKNOWN, Stage.STRATEGY}:
        score += 2
    if any(amount.dimension in {"energy", "co2", "mass", "volume", "electricity"} for amount in amounts):
        score += 1
    if len(sentence) < 18:
        score -= 2
    return score


def _missing(fields: dict) -> list[str]:
    missing = []
    for key in REQUIRED_FIELDS:
        value = fields.get(key)
        if value in (None, "", [], "未明示", Stage.UNKNOWN, AmountNature.NONE):
            missing.append(key)
    return missing


def build_event(document, page: dict, sentence: str, *, subject: str = "") -> SustainabilityEvent:
    page_no = int(page.get("page") or 0)
    quote = clean_quote(sentence)
    stage = detect_stage(quote)
    amounts = to_amounts(quote, period_from_text(quote, str(getattr(document, "period", ""))))
    key, _label = activity_type(quote)
    raw_name = project_name(quote)
    name = strip_leading_verbs(raw_name)
    aliases = [alias for alias in {raw_name, name} if alias and alias != name]
    period = period_from_text(quote, str(getattr(document, "period", "")))
    nature = detect_amount_nature(quote)
    performance = [amount for amount in amounts if amount.dimension != "money"]
    money = [amount for amount in amounts if amount.dimension == "money"]
    for amount in money:
        amount.nature = nature if nature != AmountNature.NONE else AmountNature.NONE
    event = SustainabilityEvent(
        event_id=_event_id(document.document_id, page_no, quote),
        company=document.company, company_id=getattr(document, "company_id", ""),
        subject=subject, project_name=name, aliases=aliases,
        activity_type=key, period=period, stage=stage,
        amounts=amounts, amount_nature=nature, performance=performance,
        scope="未明示", document_id=document.document_id,
        file_sha256=getattr(document, "file_sha256", ""),
        report_type=getattr(document, "report_type", ""),
        pdf_page=page_no, bbox=_bbox_of(page, quote), quote=quote,
        page_verified=bool(compact(quote)) and compact(quote) in compact(page.get("text") or ""),
        currency="人民币" if re.search(r"人民币|RMB|CNY", quote, re.I) else "未明示",
    )
    event.missing_fields = _missing({
        "subject": event.subject, "project_name": event.project_name, "period": event.period,
        "stage": event.stage, "amount": event.amounts, "scope": event.scope,
    })
    return event


def collect_candidates(pages: list[dict], document, *, limit: int = MAX_EVENTS) -> list[SustainabilityEvent]:
    """规则候选：只保留同时出现经济活动词与金额/阶段线索的句子。"""
    events: list[SustainabilityEvent] = []
    seen: set[str] = set()
    for page in pages:
        text = "\n".join(str(block.get("text") if isinstance(block, dict) else block)
                          for block in (page.get("blocks_detail") or page.get("blocks") or [])) or str(page.get("text") or "")
        # 页级环境语境：同一页出现环境/低碳词时，允许“其他”类事项凭项目名进入候选。
        page_env = any(term in text for term in STRONG_ENV)
        for sentence in sentences(text):
            key, label = activity_type(sentence)
            stage = detect_stage(sentence)
            amounts = to_amounts(sentence)
            if key == "other" and not any(term in sentence for term in STRONG_ENV) and not (
                    page_env and project_name(sentence) and any(verb in sentence for verb in
                                                                ("配套", "建设", "投运", "改造", "实施"))):
                continue
            if stage == Stage.UNKNOWN and not amounts and not (project_name(sentence) and page_env):
                continue
            # 纯财务指标句（分红、股价、品牌价值）没有经济活动动词，不当作可持续事项。
            if not any(verb in sentence.replace("投资者", "") for verb in ("投入", "投资", "建设", "改造", "实施", "开展", "推进",
                                                     "采购", "购置", "建成", "投运", "治理", "履约", "研发",
                                                     "修复", "签订", "立项")):
                continue
            if any(word in sentence for word in ("分红", "股利", "品牌价值", "市值", "股价", "议题矩阵", "排名")):
                continue
            quote = clean_quote(sentence)
            money_hit = any(amount.dimension == "money" for amount in amounts)
            if not money_hit and len(project_name(quote)) < 6:
                continue
            fingerprint = compact(quote)[:46]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            event = build_event(document, page, sentence)
            event.activity_type = key
            events.append(event)
    events.sort(key=lambda item: (-_score(item.quote, item.amounts, item.stage, item.project_name),
                                  item.pdf_page, item.event_id))
    return events[:limit]


def apply_model_fields(candidates: list[SustainabilityEvent], runner: Callable[[str], str],
                       page_texts: dict[int, str]) -> tuple[list[SustainabilityEvent], dict]:
    """模型只补全字段，不新增事件、不改金额。

    返回 (events, receipt)。runner 接收提示词、返回 JSON 字符串。
    任何字段若不能在该页原文中逐字找到，直接丢弃并记录 rejected。
    """
    if not candidates:
        return candidates, {"status": "skipped", "reason": "无候选事项"}
    payload = [{"event_id": item.event_id, "quote": item.quote,
                "project_name": item.project_name, "subject": item.subject,
                "stage": item.stage.value, "amount_nature": item.amount_nature.value}
               for item in candidates]
    prompt = (
        "你是审计助理。只根据给出的原文句子补全字段，不得新增事件、不得修改金额、不得猜测项目名。"
        "返回 JSON 数组，每项含 event_id、project_name、subject、stage（strategy/planned/contracted/"
        "executing/completed/settled/unknown）、amount_nature（budget/planned_investment/actual_payment/"
        "investment_incurred/period_increase/period_decrease/closing_balance/expense/performance/none）。\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        raw = runner(prompt)
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get("events") or []
    except Exception as error:  # 模型不可用不影响规则结果
        return candidates, {"status": "degraded", "reason": f"{type(error).__name__}: {error}"[:160]}
    by_id = {item.event_id: item for item in candidates}
    accepted, rejected = [], []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            rejected.append({"field": "row", "reason": "必须是对象"})
            continue
        event = by_id.get(str(row.get("event_id") or ""))
        if event is None:
            continue
        page_text = compact(event.quote)
        for field in ("project_name", "subject"):
            value = str(row.get(field) or "").strip()
            if value and compact(value) in page_text:
                if field == 'project_name' and event.project_name and event.project_name != value:
                    event.aliases = list(dict.fromkeys([*event.aliases, event.project_name]))[:6]
                setattr(event, field, value[:80])
                event.extraction_method = "rule+model"
            elif value:
                rejected.append({"event_id": event.event_id, "field": field, "value": value[:40]})
        stage = STAGE_BY_LABEL.get(str(row.get("stage") or "").lower())
        # 未知不能只凭模型变成已知；阶段与性质仍须独立的原文规则支持。
        if stage and event.stage == Stage.UNKNOWN and stage != Stage.UNKNOWN and detect_stage(event.quote) == stage:
            event.stage = stage
            event.extraction_method = "rule+model"
        nature = NATURE_BY_LABEL.get(str(row.get("amount_nature") or "").lower())
        if nature and event.amount_nature == AmountNature.NONE and nature != AmountNature.NONE and detect_amount_nature(event.quote) == nature:
            event.amount_nature = nature
            for amount in event.amounts:
                if amount.dimension == "money":
                    amount.nature = nature
            event.extraction_method = "rule+model"
        accepted.append(event.event_id)
    return candidates, {"status": "applied", "accepted": len(accepted),
                        "rejected": rejected[:10], "rejected_count": len(rejected)}


def extract_events(pages: list[dict], document, *, limit: int = MAX_EVENTS,
                   model_runner: Callable[[str], str] | None = None) -> tuple[list[SustainabilityEvent], dict]:
    candidates = collect_candidates(pages, document, limit=limit)
    receipt = {"version": EVENTS_VERSION, "candidates": len(candidates), "status": "rule_only"}
    if model_runner is None:
        receipt["note"] = "未配置模型或未授权调用，保留规则抽取结果，不伪装为模型抽取。"
        return candidates, receipt
    page_texts = {int(page.get("page") or 0): str(page.get("text") or "") for page in pages}
    events, model_receipt = apply_model_fields(candidates, model_runner, page_texts)
    receipt.update(model_receipt)
    receipt["events"] = len(events)
    return events, receipt
