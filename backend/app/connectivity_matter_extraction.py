"""长叙述证据与事项检索。金额不是进入调查的前提，词法与语义通道分别留痕。

叙述证据不依赖金额，风险、目标与估计假设均可进入调查。
长块按原始字符切分并保留上下文，不用模型改写原文。
文字层不足与扫描页面分别计入覆盖限制，不能写成无披露。
缓存只复用解析结果，每次仍校验登记原件的实际字节。
词法与本地语义通道分别记录，未配置语义模型不会冒充融合检索。
首轮上下文有界，剩余已索引原文通过受控工具继续读取。
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import uuid

from .connectivity_matter_schemas import MatterEvidence

INDEX_VERSION = "matter_blocks_v1"
MATTER_TERMS = {
    "climate_risk": ("气候", "极端天气", "洪水", "干旱", "转型风险", "碳价", "碳成本"),
    "transition_project": ("绿色", "节能", "技改", "环保", "改造", "脱硫", "新能源"),
    "commitment": ("承诺", "目标", "净零", "碳中和", "到203", "到202"),
    "resource_efficiency": ("节水", "节电", "能耗", "减排", "用水", "节约"),
    "financial": ("减值", "使用寿命", "残值", "估计", "关键假设", "现金流预测", "在建工程", "资本开支", "预计负债", "折旧", "转固"),
}
ALIASES = {"气候": ["极端天气", "转型风险", "气候变化"], "减值": ["可收回金额", "资产组", "现金流预测"],
           "寿命": ["折旧年限", "残值", "使用年限"], "投入": ["资本开支", "在建工程", "投资", "支出"],
           "投运": ["投产", "转固", "达到预定可使用状态"], "目标": ["承诺", "基准年", "基期", "进展"]}


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()[:20].upper()


def compact(value):
    return re.sub(r"\s+", "", str(value))


def tokens(text):
    parts = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+", text.lower())
    return [token for part in parts for token in ([part] if not re.fullmatch(r"[\u4e00-\u9fff]+", part)
            else [part[i:i+2] for i in range(max(1, len(part)-1))])]


def read_corpus(root, documents, *, cancelled=lambda: False):
    from .connectivity_extraction import ensure_source, INJECTION_PATTERN
    from .source_viewer import PDF_ACCESS_LOCK
    import pymupdf
    corpus, coverage = [], []
    ocr = os.getenv("CONNECTIVITY_MATTER_OCR", "false").lower() in {"true", "1"}
    cache = root / "backend/runtime/connectivity/matter_index"
    cache.mkdir(parents=True, exist_ok=True)
    for doc in documents:
        if cancelled():
            raise InterruptedError("事项解析已取消")
        path = ensure_source(root, doc)
        target = cache / f"{doc.file_sha256}-{INDEX_VERSION}-ocr{int(ocr)}.json"
        if target.exists():
            record = json.loads(target.read_text(encoding="utf-8"))
        else:
            blocks, failed, scanned = [], [], []
            section = ""
            with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
                total_pages = len(pdf)
                for number, page in enumerate(pdf, 1):
                    if cancelled():
                        raise InterruptedError("事项解析已取消")
                    method, textpage = "text", None
                    raw = page.get_text("blocks")
                    if len("".join(str(b[4]) for b in raw if len(b) > 6 and b[6] == 0).strip()) < 20:
                        scanned.append(number)
                        if ocr:
                            try:
                                textpage = page.get_textpage_ocr(language="chi_sim+eng", full=True)
                                raw, method = page.get_text("blocks", textpage=textpage), "ocr"
                            except RuntimeError as error:
                                failed.append({"page": number, "reason": "OCR不可用：" + type(error).__name__})
                        else:
                            failed.append({"page": number, "reason": "文字层不足，OCR未启用"})
                    for block in raw:
                        if len(block) <= 6 or block[6] != 0:
                            continue
                        text = str(block[4]).strip()
                        if not text or INJECTION_PATTERN.search(text):
                            continue
                        first = text.splitlines()[0].strip()
                        if 3 <= len(first) <= 65 and (re.match(r"^(第[一二三四五六七八九十\d]+|[一二三四五六七八九十\d]+[、.．])", first)
                                or any(w in first for w in ("减值", "气候", "会计估计", "在建工程"))):
                            section = first
                        # 原文不拼接或改写；长块重叠分段，原始上下文另外保留。
                        for start in range(0, len(text), 1050):
                            quote = text[start:start+1200]
                            blocks.append({"pdf_page": number, "quote": quote, "context": text[max(0,start-180):start+1380],
                                "bbox": list(block[:4]), "section": section, "extraction_method": method})
            record = {"blocks": blocks, "coverage": {"document_id": doc.document_id, "total_pages": total_pages,
                "failed_pages": failed, "scanned_pages": scanned, "indexed_blocks": len(blocks),
                "ocr_enabled": ocr, "method": INDEX_VERSION}}
            temporary = target.with_suffix("." + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
        cov = dict(record["coverage"], document_id=doc.document_id)
        coverage.append(cov)
        begin=len(corpus)
        for block in record["blocks"]:
            corpus.append(MatterEvidence(evidence_id="ME-" + digest(f"{doc.document_id}|{doc.file_sha256}|{block['pdf_page']}|{block['quote']}"),
                document_id=doc.document_id, source_sha256=doc.file_sha256, company_id=doc.company_id,
                report_type=doc.report_type, report_period=doc.effective_period, disclosure_date=doc.disclosure_date,
                source_verified=True, **block))
        pages={}
        for evidence in corpus[begin:]:pages.setdefault(evidence.pdf_page,[]).append(evidence)
        # 跨页上下文仍拆成各自带页码的证据，不拼成无法定位的长引文。
        for page,items in pages.items():
            for evidence in items:
                neighbors=[]
                if evidence is items[0]:neighbors.extend(pages.get(page-1,[])[-1:])
                if evidence is items[-1]:neighbors.extend(pages.get(page+1,[])[:1])
                evidence.adjacent_evidence_ids=[e.evidence_id for e in neighbors]
    return corpus, coverage


def relevant_evidence(corpus, *, limit=90):
    """首轮上下文明确限制，调查可通过工具继续读取所有已索引块。"""
    scores = []
    for block in corpus:
        text = compact(block.quote)
        score = sum(min(3, text.count(t)) for values in MATTER_TERMS.values() for t in values)
        if score:
            scores.append((score, block))
    # 先各文档轮转，避免长年报挤掉往年和ESG。
    groups = {}
    for score, b in sorted(scores, key=lambda item: (-item[0], item[1].document_id, item[1].pdf_page)):
        groups.setdefault(b.document_id, []).append(b)
    selected = []
    while groups and len(selected) < limit:
        for key in list(groups):
            if len(selected) == limit:
                break
            selected.append(groups[key].pop(0))
            if not groups[key]:
                groups.pop(key)
    return selected, {"indexed_blocks": len(corpus), "relevant_blocks": len(scores), "seed_blocks": len(selected),
        "seed_truncated": len(scores) > len(selected), "note": "首轮上下文有界；未入选块仍可用工具检索，不等于无披露"}


@lru_cache(maxsize=1)
def _local_encoder(path):
    # 仅加载操作方指定的本地模型，不自动下载、不向新供应商外发。
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(path, local_files_only=True)


def search_corpus(corpus, query, *, document_ids=None, report_type=None, periods=None, limit=8, encoder=None):
    selected = [b for b in corpus if (not document_ids or b.document_id in document_ids)
                and (not report_type or b.report_type == report_type) and (not periods or b.report_period in periods)]
    expanded = query + " " + " ".join(alias for term, values in ALIASES.items() if term in query for alias in values)
    qt = set(tokens(expanded));counts = [Counter(tokens(b.quote + " " + b.section)) for b in selected]
    n = len(counts);avg = sum(sum(c.values()) for c in counts)/max(1,n)
    df = Counter(t for c in counts for t in c)
    scored = []
    for i,c in enumerate(counts):
        length = sum(c.values())
        score = sum(math.log(1+(n-df[t]+.5)/(df[t]+.5)) * c[t]*2.2 /
                    (c[t]+1.2*(.25+.75*length/max(1,avg))) for t in qt if c[t])
        if score > 0:
            scored.append((score,i))
    lexical = [i for _,i in sorted(scored,reverse=True)]
    semantic, semantic_state = [], "not_configured"
    model_path = os.getenv("CONNECTIVITY_MATTER_EMBEDDING_MODEL", "")
    if encoder is not None or model_path:
        try:
            import numpy as np
            enc = encoder or _local_encoder(model_path)
            if selected:
                vectors = np.asarray(enc.encode([query] + [b.quote for b in selected], normalize_embeddings=True))
                similarities = vectors[1:] @ vectors[0]
                semantic = [int(i) for i in np.argsort(-similarities)[:max(20,limit)]]
            semantic_state = "completed"
        except (ImportError, OSError, ValueError, RuntimeError):
            semantic_state = "unavailable"
    rrf = Counter()
    for ranking in (lexical, semantic):
        for rank,i in enumerate(ranking):
            rrf[i] += 1/(60+rank+1)
    indices = [i for i,_ in rrf.most_common(limit)]
    hits=[selected[i] for i in indices];ids={b.evidence_id for b in hits}
    neighbors={eid for b in hits for eid in b.adjacent_evidence_ids}
    context=[b for b in selected if b.evidence_id in neighbors and b.evidence_id not in ids]
    return {"query": query, "expanded_query": expanded, "method": "bm25_alias_rrf" + ("_semantic" if semantic_state == "completed" else ""),
        "semantic_status": semantic_state, "searched_blocks": len(selected), "candidate_count": len(rrf),
        "truncated": len(rrf) > limit, "evidence": [b.model_dump(mode="json") for b in [*hits,*context]], "adjacent_context_blocks":len(context),
        "note": "检索命中是候选证据；不证明项目身份、因果关系或企业披露真实"}
