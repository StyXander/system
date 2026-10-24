"""任务5：面向财务关联的混合检索。

BM25 + 精确项目名/别名 + 可选语义向量 → RRF 融合 → 会计规则与主体/期间/范围过滤 → 重排。

三条边界：
1. 检索分数只决定“先核查什么”，不决定“关联成立”；成立与否由 impact_verifier 判定。
2. 没有向量模型时明确标记 degraded_no_vector，只跑 BM25 与精确匹配。
3. 反向证据独立检索，不用正向结果反推。
"""
from __future__ import annotations

import math
import re
import unicodedata
import os
from pathlib import Path
from functools import lru_cache
from collections import Counter
from dataclasses import dataclass, field

from .models import AccountingTreatment, SustainabilityEvent
from .textutil import compact

LINKER_VERSION = "financial_linker_v1.0"
RRF_K = 60
YEAR_RE = re.compile(r"(20\d{2})\s*年?")
SUBJECT_RE = re.compile(r"([\u4e00-\u9fff]{2,8}(?:基地|公司|厂|分公司|子公司|矿业|炼铁|炼钢))")
COUNTER_TERMS = ("尚未", "未发生", "不存在", "不适用", "终止", "取消", "未签订", "未开工", "无实质进展", "未纳入")


def tokenize(text: str) -> list[str]:
    """中文双字切分 + 英文/数字整词；不做同义词扩展，避免把不同口径混为一谈。"""
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    value = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9%.]+", " ", value)
    tokens: list[str] = []
    for chunk in value.split():
        if re.fullmatch(r"[a-z0-9%.]+", chunk):
            tokens.append(chunk)
            continue
        chars = "".join(ch for ch in chunk if "\u4e00" <= ch <= "\u9fff")
        tokens.extend(chars[index:index + 2] for index in range(max(1, len(chars) - 1)))
        if len(chars) == 1:
            tokens.append(chars)
    return [token for token in tokens if token]


@dataclass
class Unit:
    unit_id: str
    document_id: str
    report_type: str
    page: int
    text: str
    bbox: list[float] = field(default_factory=list)
    file_sha256: str = ''


class Index:
    """页面内文本单元的 BM25 索引；单元是段落块，不是整页，避免证据粒度失真。"""

    def __init__(self, units: list[Unit]):
        self.units = units
        self.tokens = [tokenize(unit.text) for unit in units]
        self.lengths = [len(tokens) for tokens in self.tokens]
        self.average = sum(self.lengths) / max(1, len(self.lengths))
        self.term_freq = [Counter(tokens) for tokens in self.tokens]
        df: Counter = Counter()
        for tokens in self.tokens:
            df.update(set(tokens))
        total = max(1, len(units))
        self.idf = {term: math.log(1 + (total - count + 0.5) / (count + 0.5)) for term, count in df.items()}

    def search(self, query: str, *, limit: int = 12) -> list[tuple[int, float]]:
        terms = tokenize(query)
        if not terms:
            return []
        scores = []
        for index, freqs in enumerate(self.term_freq):
            score = 0.0
            norm = 1.5 * (1 - 0.75 + 0.75 * self.lengths[index] / max(1e-6, self.average))
            for term in terms:
                count = freqs.get(term, 0)
                if not count:
                    continue
                score += self.idf.get(term, 0.0) * count / (count + norm)
            if score > 0:
                scores.append((index, round(score, 4)))
        scores.sort(key=lambda item: -item[1])
        return scores[:limit]


def build_index(pages_by_document: dict[str, list[dict]], *, max_units: int = 4000) -> tuple[Index, dict]:
    units: list[Unit] = []
    for document_id, pages in pages_by_document.items():
        for page in pages:
            page_no = int(page.get("page") or 0)
            blocks = page.get("blocks_detail") or []
            texts = [block.get("text") for block in blocks] if blocks else str(page.get("text") or "").split("\n")
            for offset, text in enumerate(texts):
                value = compact(text or "")
                if len(value) < 12:
                    continue
                bbox = (blocks[offset].get("bbox") if blocks and offset < len(blocks) else []) or []
                report_type = "ESG" if "esg" in str(page.get("report_type", "")).lower() else str(page.get("report_type") or "")
                units.append(Unit(f"{document_id}#{page_no}#{offset}", document_id, report_type, page_no,
                                  value[:600], [round(float(v), 2) for v in bbox] if bbox else [],
                                  str(page.get('file_sha256') or '')))
                if len(units) >= max_units:
                    break
            if len(units) >= max_units:
                break
        if len(units) >= max_units:
            break
    return Index(units), {"version": LINKER_VERSION, "units": len(units), "truncated": len(units) >= max_units}


def _query(event: SustainabilityEvent, treatments: list[AccountingTreatment]) -> str:
    parts = [event.project_name, event.subject, event.quote[:80]]
    for treatment in treatments[:2]:
        parts.extend(treatment.accounts[:3])
        parts.append(treatment.scene)
    return " ".join(part for part in parts if part)


def _years(text: str) -> set[str]:
    return set(YEAR_RE.findall(text))


def _subjects(text: str) -> set[str]:
    return {compact(item) for item in SUBJECT_RE.findall(text)}


def _amount_kind(text: str) -> str:
    if re.search(r"预算|计划投资", text):
        return "budget"
    if re.search(r"期末余额|期初余额", text):
        return "balance"
    if re.search(r"本期增加|本期减少|转固", text):
        return "movement"
    if re.search(r"费用|支出", text):
        return "expense"
    return "unknown"


def filter_unit(event: SustainabilityEvent, unit: Unit) -> tuple[bool, list[str]]:
    """硬过滤只排除能明确判定不兼容的单元；判不了的一律放行并记录 unknown。"""
    reasons: list[str] = []
    ok = True
    years = _years(unit.text)
    if years and event.period and event.period not in years:
        ok = False
        reasons.append(f"期间不匹配：候选仅含{'/'.join(sorted(years))}，事项为{event.period}")
    subjects = _subjects(unit.text)
    if event.subject and subjects and event.subject not in subjects:
        ok = False
        reasons.append(f"主体不匹配：候选主体为{'/'.join(sorted(subjects))[:30]}")
    if "母公司" in unit.text and event.scope.startswith("合并"):
        ok = False
        reasons.append("范围不匹配：候选为母公司口径，事项为合并口径")
    if event.amount_nature.value in {"budget", "planned_investment"} and _amount_kind(unit.text) in {"movement", "balance", "expense"}:
        reasons.append("金额性质待核对：事项为预算/计划，候选为发生额或余额")
    return ok, reasons


def vector_scores(query: str, units: list[Unit]) -> tuple[list[tuple[int, float]] | None, dict]:
    """可选语义检索。未安装模型时返回 None 并记录降级原因，不假装已启用。"""
    model_path = os.getenv('AUDITTRACE_FINANCIAL_VECTOR_MODEL', '')
    if not model_path or not Path(model_path).is_dir():
        return None, {'status': 'degraded_no_vector', 'reason': '本地向量模型不可用：未配置模型目录，不自动下载或外发原文'}
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as error:
        return None, {"status": "degraded_no_vector", "reason": f"{type(error).__name__}: 未安装 sentence-transformers"}
    try:
        model = _local_vector_model(model_path)
        import numpy as np
        query_vector = model.encode([query], normalize_embeddings=True)[0]
        matrix = model.encode([unit.text for unit in units], normalize_embeddings=True)
        scores = (matrix @ query_vector).tolist()
        ranked = sorted(enumerate(scores), key=lambda item: -item[1])[:20]
        return [(index, round(float(score), 4)) for index, score in ranked], {"status": "vector_enabled", "model": "BAAI/bge-m3"}
    except Exception as error:
        return None, {"status": "degraded_no_vector", "reason": f"{type(error).__name__}: 向量模型不可用"}


@lru_cache(maxsize=1)
def _local_vector_model(path: str):
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(path, local_files_only=True)


def rrf(*ranked_lists: list[tuple[int, float]]) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (index, _score) in enumerate(ranked, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: -item[1])


def search(event: SustainabilityEvent, treatments: list[AccountingTreatment], index: Index, *,
           allow_vector: bool = False, limit: int = 10) -> dict:
    query = _query(event, treatments)
    lexical = index.search(query, limit=40)
    exact: list[tuple[int, float]] = []
    names = [name for name in [event.project_name, *event.aliases] if name and len(name) >= 4]
    if names:
        exact = [(offset, 1.0) for offset, unit in enumerate(index.units)
                 if any(compact(name) in unit.text for name in names)][:20]
    semantic, vector_receipt = (None, {"status": "degraded_no_vector", "reason": "未启用本地向量模型；实际使用BM25、精确匹配和RRF"})
    if allow_vector:
        semantic, vector_receipt = vector_scores(query, index.units)
    fused = rrf(*[item for item in (lexical, exact, semantic) if item])
    candidates = []
    for index_value, score in fused:
        unit = index.units[index_value]
        ok, reasons = filter_unit(event, unit)
        candidates.append({
            "unit_id": unit.unit_id, "document_id": unit.document_id, "report_type": unit.report_type,
            "file_sha256": unit.file_sha256, "verified": bool(unit.file_sha256),
            "pdf_page": unit.page, "bbox": unit.bbox, "quote": unit.text[:240],
            "rrf": round(score, 6), "in_bm25": any(i == index_value for i, _ in lexical),
            "in_exact": any(i == index_value for i, _ in exact),
            "in_vector": bool(semantic) and any(i == index_value for i, _ in semantic),
            "filter_ok": ok, "filter_reasons": reasons,
            "amount_kind": _amount_kind(unit.text), "years": sorted(_years(unit.text)),
        })
        if len(candidates) >= limit * 3:
            break
    candidates.sort(key=lambda item: (not item["filter_ok"], -item["rrf"]))
    return {
        "query": query[:200], "candidates": candidates[:limit],
        "receipt": {"version": LINKER_VERSION, "bm25": len(lexical), "exact": len(exact),
                    "vector": vector_receipt, "fused": len(fused),
                    "note": "相似度只决定核查顺序，不决定关联是否成立。"},
    }


def search_counter(event: SustainabilityEvent, index: Index, *, limit: int = 6) -> list[dict]:
    """反向证据独立检索：否定词必须与同一项目名出现在同一句，才计为反证。

    没有项目名就无法把否定表述归属到该事项，返回空而不是拿别的“尚未”凑数。
    """
    name = compact(event.project_name)
    if len(name) < 4:
        return []
    result = []
    for index_value, score in index.search(f"{name} 尚未 未实施 终止 取消 不存在", limit=limit * 6):
        unit = index.units[index_value]
        text = compact(unit.text)
        if name not in text:
            continue
        position = text.find(name)
        window = text[max(0, position - 40):position + len(name) + 40]
        if not any(term in window for term in COUNTER_TERMS):
            continue
        # 只把同一句中直接修饰本项目的否定保留为反证，不能借用另一项目的“尚未”。
        segments = re.split(r'[。；;\n]', text)
        if not any(name in part and re.search(re.escape(name) + r'.{0,16}(?:尚未|未发生|不存在|不适用|终止|取消|未开工|未实施|无实质进展|未纳入)', part) for part in segments):
            continue
        result.append({"unit_id": unit.unit_id, "document_id": unit.document_id, "pdf_page": unit.page,
                       "file_sha256": unit.file_sha256, "report_type": unit.report_type,
                       "verified": bool(unit.file_sha256), "bbox": unit.bbox,
                       "quote": unit.text[:240], "rrf": score, "matched_term":
                       next(term for term in COUNTER_TERMS if term in window)})
        if len(result) >= limit:
            break
    return result
