"""本地 RAG 的来源隔离、确定性索引、固定问题与检索留痕。

RAG 只处理已经登记的案例年报，不扫描工作区中的任意文件。
每个案例使用独立目录、数据库、向量索引和来源指纹。
案例编号在创建目录前再次标准化，拒绝异常字符和路径语义。
来源清单来自案例注册表，不能由检索请求临时追加文件。
建库前重新计算整份年报哈希，哈希不符时拒绝继续索引。
来源文件缺失时明确报错，不使用旧索引掩盖缺失文档。
来源指纹包含文件名与哈希，用于判断索引是否需要重建。
索引版本变化时强制重建，避免旧向量与新检索逻辑混用。
PDF 按页读取，使每个候选片段始终能够回到具体页码。
切块保留适度重叠，减少会计政策段落被边界截断的风险。
切块编号包含案例、年度、页码和片段序号，便于追踪。
标准案例与导入案例使用同一索引逻辑，不增加专用检索分支。
文本向量采用确定性的字符片段哈希，不调用在线嵌入服务。
确定性向量便于离线复现，但不声称具有通用语义最优效果。
向量索引只负责召回候选，专业锚点负责排除词面噪声。
固定问题为 R1 和 R2 指定检索主题、锚点与无命中提示。
问题编号与问题集版本随检索记录保存，支持后续复验。
请求的规则必须与固定问题允许的规则一致，防止跨规则误用。
检索时同时过滤案例编号、公司名称和不晚于时点的披露日期。
三个过滤条件任何一个不匹配，都不能进入候选结果。
公司名称来自案例上下文，调用方不能借此读取其他案例索引。
向量位置与数据库行号建立明确映射，不能依赖不稳定排序。
向量相似度与关键词命中共同评分，避免单一信号决定返回。
专业锚点至少命中一个主题词，否则宁可返回无命中状态。
锚点命中不代表披露充分，只说明片段与固定问题相关。
候选片段截取时保留字符起止位置，方便核对是否为原文。
片段明确标记逐字来源，但仍要求人工回到完整 PDF 页复核。
来源定位包含文档编号、PDF 页码和切块编号，不使用模糊链接。
登记页存在财务字段时，把对应字段证据编号附加到候选结果。
登记页没有字段时仍可返回原文，但不能伪造字段勾稽关系。
检索结果携带整份文件哈希，支持确认原文版本没有被替换。
检索结果不会修改风险卡，是否形成资料缺口仍由主流程决定。
无命中时返回固定的证据缺口提示，不从其他案例借用片段。
无命中不是系统故障，它是需要向评委如实展示的检索结果。
索引尚未准备时检索直接失败，不在请求中偷偷自动建库。
准备索引与执行检索分成两个接口，便于分别验收运行时间。
索引序列化到内存后写入路径，规避中文路径的底层兼容问题。
SQLite 保存片段元数据与检索日志，FAISS 只保存向量结构。
检索日志保存查询、过滤器、返回切块和版本，不保存模型密钥。
检索日志编号随机生成，但返回内容仍可由输入与索引复验。
日志读取会遍历已登记案例，不接受外部传入数据库路径。
运行清理只能操作当前案例的 RAG 目录，不扩大到运行根目录。
自动化测试使用独立命名空间，不能覆盖真人演示索引。
第二公开案例必须生成独立索引，并验证结果只含自身切块编号。
同行业案例也不能共享索引，因为相似公司名称容易造成串包。
RAG 进入 Agent 前仍要转换为证据编号白名单。
模型引用检索编号不等于引用片段，必须引用明确的证据编号。
检索片段的支持状态始终是候选待回页，不自动标为已核实。
年报中的审计意见、会计政策和风险披露应按问题分别检索。
通用关键词过宽时应修改固定问题，而不是提高返回数量掩盖噪声。
检索数量上限防止大量低分片段挤占模型证据上下文。
评分阈值以下的片段不返回，避免页面显示看似相关的空证据。
查询为空时拒绝执行，固定问题模式除外。
修改切块策略时必须同步索引版本并重建所有案例索引。
修改锚点时必须补充命中、无命中和近义噪声回归测试。
修改来源过滤时必须优先验证跨案例引用仍被拦截。
索引重建先写入唯一版本目录，未完成目录不会被活动指针公开。
活动指针只在数据库、向量和清单全部落盘后原子切换。
一次检索固定读取同一活动版本，指针并发变化不能造成文件串版。
状态检查和证据块导出同样固定版本目录，避免检查与读取之间的竞态。
Windows 活动指针共享冲突只有限重试，失败后保留旧版本继续可读。
强制重建不会原地修改旧数据库，正在检索的请求仍能完成原快照读取。
检索日志保存在对应索引版本中，后续重建不能让既有编号失去回查能力。
历史日志读取只遍历案例自己的版本目录，不能借编号搜索任意 SQLite 文件。
单个旧版本损坏时跳过该版本，其他完整版本的留痕仍可继续查询。
SQLite 连接在成功和异常路径都显式关闭，避免悬挂句柄阻塞版本发布。
检索数量在内部函数再次校验，后台调用不能绕过 API 模型上限。
索引清单损坏时返回未构建，不能仅凭 FAISS 文件存在宣称就绪。
导出的证据块排除本机存储路径，只携带公开持久化需要的最小元数据。
旧索引版本为审计留痕暂时保留，未来清理必须先建立引用和保留策略。
并发安全保证版本一致性，不提升向量召回本身的专业准确性。
RAG 成功只证明候选原文可召回，不证明风险识别正确。
本模块的核心目标是让模型看到可回查原文，同时保持案例隔离。
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import faiss
import fitz
import numpy as np

from .cases import (
    get_case,
    get_case_documents,
    list_cases,
    registered_page_metadata,
)
from .data import CASE_ID, CASE_NAME, TICKER
from .schemas import AI_GENERATED_CONTENT_NOTICE


_INDEX_LOCKS: dict[str, threading.Lock] = {}
_INDEX_LOCKS_GUARD = threading.Lock()
_INDEX_BUILD_STATES: dict[str, dict[str, Any]] = {}


def _index_lock(workspace_root: Path, case_id: str) -> threading.Lock:
    key = f"{workspace_root.resolve()}::{str(case_id).upper()}"
    with _INDEX_LOCKS_GUARD:
        return _INDEX_LOCKS.setdefault(key, threading.Lock())


def _index_state_key(workspace_root: Path, case_id: str) -> str:
    return f"{workspace_root.resolve()}::{str(case_id).upper()}"


VECTOR_DIM = 384
INDEX_VERSION = "rag-v1.2-case-isolated-hash-ngram-faiss-20260728"
RETRIEVAL_VERSION = "rag-retrieval-v1.2-case-isolated-20260728"
QUESTION_SET_VERSION = "rag-question-set-w3-v1.1-20260727"
QUESTION_SET_REVIEW_STATUS = "professional_input_received_pending_team_source_page_review"
ACTIVE_POINTER_RETRY_SECONDS = 2.0

# A 成员提交的 6 个专业问题经过队长审校后形成受控问题集。这里保留问题、
# 检索词、目标章节、返回字段和无命中提示，避免前端各自改写专业口径。
# `no_hit_prompt` 只能说明“本次未检索到”，不能反推“年报未披露”。
RAG_QUESTIONS: tuple[dict[str, Any], ...] = (
    {
        "question_id": "RAG-Q1",
        "rule_ids": ["R1"],
        "title": "信用政策与结算周期变更",
        "question": "本报告期与上年相比，公司年报是否明确披露销售信用政策、客户账期或结算方式的调整？如有，披露的内容、原因、时间和适用范围是什么？",
        "retrieval_query": "信用政策 信用期 客户账期 结算方式 回款政策 调整 变更",
        "anchor_terms": ["信用政策", "信用期", "客户账期", "结算方式", "回款政策"],
        "target_sections": ["管理层讨论与分析 / 销售模式与回款政策", "应收账款或应收票据附注", "经营风险与应对"],
        "expected_fields": ["明确披露的政策或结算方式变化", "生效时间与适用范围（如披露）", "管理层说明的原因（如披露）"],
        "no_hit_prompt": "本次检索未返回关于信用政策、账期或结算方式变更的可回查片段；不能据此认定年报未披露或政策未变化。建议人工回查相关章节，并将正式信用政策、主要客户合同关键条款列为待索取资料候选。",
    },
    {
        "question_id": "RAG-Q2",
        "rule_ids": ["R1"],
        "title": "主要欠款方与客户结构变化",
        "question": "本报告期与上年相比，年报披露的应收款项前五名欠款方、余额、占比或账龄是否发生变化？年报是否明确说明新增大额客户或特殊结算约定？",
        "retrieval_query": "应收账款 前五名 欠款方 余额 占比 账龄 客户结构 新增客户 结算约定",
        "anchor_terms": ["前五名", "欠款方", "客户集中度", "账龄", "应收账款"],
        "target_sections": ["应收账款附注 / 按欠款方归集的期末余额前五名", "客户集中度与主要客户", "市场拓展与客户开发"],
        "expected_fields": ["年报实际披露的欠款方标识、余额、占比和账龄", "新增大额客户说明（如披露）", "特殊账期或结算方式（仅在原文明确披露时返回）"],
        "no_hit_prompt": "本次检索未返回主要欠款方、客户结构变化或特殊结算约定的可回查片段；不能据此认定没有变化。建议人工回查应收款项附注，并将前五大客户合同关键页、账龄明细和信用评级资料列为待索取资料候选。",
    },
    {
        "question_id": "RAG-Q3",
        "rule_ids": ["R2"],
        "title": "经营活动现金流变动说明",
        "question": "管理层如何解释报告期经营活动现金流量净额的变化？年报是否将其与营业收入、净利润或回款节奏的变化联系说明？",
        "retrieval_query": "经营活动现金流量净额 变动 原因 营业收入 净利润 回款 现金流分析",
        "anchor_terms": ["经营活动产生的现金流量净额", "经营活动现金流", "现金流量净额"],
        "target_sections": ["管理层讨论与分析 / 现金流量分析", "主营业务与盈利能力分析", "合并现金流量表及附注"],
        "expected_fields": ["原文披露的现金流金额或变动幅度", "管理层列明的变动原因", "与收入、利润或回款关系的原文说明（如披露）"],
        "no_hit_prompt": "本次检索未返回经营活动现金流量净额变动原因的可回查片段；不能据此认定年报未说明。建议人工回查现金流量分析及附注，并将经营现金流明细和大额收支凭证列为待索取资料候选。",
    },
    {
        "question_id": "RAG-Q4",
        "rule_ids": ["R2"],
        "title": "存货与采购付款变化",
        "question": "年报如何披露本期存货规模及其变动原因？是否明确提及备货策略、采购付款安排或集中支付对经营现金流的影响？",
        "retrieval_query": "存货 备货 采购 付款周期 应付账款 集中支付 经营现金流 变动原因",
        "anchor_terms": ["存货", "备货", "采购付款", "应付账款"],
        "target_sections": ["主营业务分析 / 存货与供应链", "存货及应付账款附注", "经营风险与成本控制"],
        "expected_fields": ["存货余额与原文披露的变动说明", "备货策略说明（如披露）", "采购付款安排或集中支付说明（如披露）"],
        "no_hit_prompt": "本次检索未返回存货备货或采购付款变化的可回查片段；不能据此认定相关事项未发生或未披露。建议人工回查存货、应付账款附注，并将存货明细、采购合同和付款计划列为待索取资料候选。",
    },
    {
        "question_id": "RAG-Q5",
        "rule_ids": ["R1"],
        "title": "收入季节性与期末交付",
        "question": "公司年报如何描述行业或业务的季节性特征？是否明确披露第四季度或年末集中交付、验收及收入确认安排？",
        "retrieval_query": "季节性 第四季度 年末 集中交付 验收 收入确认 分季度收入",
        "anchor_terms": ["季节性", "第四季度", "年末集中", "集中交付", "分季度收入"],
        "target_sections": ["行业格局与经营模式", "主营业务分析 / 收入季度分布", "收入确认政策及分解信息"],
        "expected_fields": ["季节性特征的原文表述", "季度收入数据或比例（仅返回原文已披露内容）", "年末交付、验收或收入确认安排（如披露）"],
        "no_hit_prompt": "本次检索未返回季节性或期末集中交付的可回查片段；不能据此认定不存在季节性或集中交付。建议人工回查收入分解及经营模式章节，并将分季度收入明细、期末订单和验收记录列为待索取资料候选。",
    },
    {
        "question_id": "RAG-Q6",
        "rule_ids": ["R1", "R2"],
        "title": "公司对行业结算环境的披露",
        "question": "公司年报如何描述其所在行业的结算特点、信用环境或回款周期变化？公司披露了哪些应对措施？",
        "retrieval_query": "行业 结算周期 回款周期 信用环境 应收账款回收风险 应对措施",
        "anchor_terms": ["结算周期", "回款周期", "信用环境", "应收账款回收风险", "行业特点"],
        "target_sections": ["行业发展格局与趋势", "经营风险与应对 / 应收账款回收风险", "公司业务概要 / 行业特点"],
        "expected_fields": ["公司年报对行业结算或信用环境的原文表述", "回款周期变化的管理层表述（如披露）", "公司披露的应对措施"],
        "no_hit_prompt": "本次检索未返回公司对行业结算环境或回款周期变化的可回查片段。公司年报的管理层表述不能单独证明行业惯例；同行年报或行业报告须由审计人员另行取得、核验并登记后才能作为辅助资料。",
    },
)


def question_set() -> dict[str, Any]:
    """返回前端可直接呈现的受控问题集，不把它标成已专业验收。"""

    return {
        "version": QUESTION_SET_VERSION,
        "review_status": QUESTION_SET_REVIEW_STATUS,
        "boundary": "固定问题集是专业输入初稿；命中仍须回到原 PDF 页人工复核。",
        "questions": [dict(item) for item in RAG_QUESTIONS],
    }


def _get_question(question_id: str | None) -> dict[str, Any] | None:
    if not question_id:
        return None
    question = next((item for item in RAG_QUESTIONS if item["question_id"] == question_id), None)
    if question is None:
        raise ValueError("未知的 RAG 固定问题编号")
    return question


def _runtime_dir(workspace_root: Path, case_id: str = CASE_ID) -> Path:
    safe_case_id = re.sub(r"[^A-Z0-9_-]", "", case_id.upper())
    if safe_case_id != case_id.upper() or not safe_case_id:
        raise ValueError("非法案例编号。")
    namespace = re.sub(r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", ""))
    base = workspace_root / "backend" / "runtime"
    base = base / namespace if namespace else base
    path = base / "rag" / safe_case_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _active_data_dir(workspace_root: Path, case_id: str = CASE_ID) -> Path:
    """读取已原子发布的索引版本；没有指针时兼容旧版根目录索引。"""

    root = _runtime_dir(workspace_root, case_id)
    pointer = root / "active.json"
    if pointer.is_file():
        try:
            version = str(json.loads(pointer.read_text(encoding="utf-8")).get("version") or "")
        except (OSError, json.JSONDecodeError, AttributeError):
            version = ""
        if re.fullmatch(r"[a-f0-9]{16}-[A-Z0-9]{8,32}", version):
            candidate = root / "versions" / version
            if candidate.is_dir():
                return candidate
    return root


def _version_dir(workspace_root: Path, case_id: str, fingerprint: str) -> Path:
    version = f"{fingerprint[:16]}-{uuid.uuid4().hex[:12].upper()}"
    path = _runtime_dir(workspace_root, case_id) / "versions" / version
    path.mkdir(parents=True, exist_ok=False)
    return path


def _publish_version(workspace_root: Path, case_id: str, version_dir: Path) -> None:
    """只替换小型 active 指针，检索线程不会看到未完成的版本目录。"""

    root = _runtime_dir(workspace_root, case_id)
    pointer = root / "active.json"
    temporary = root / f"active.{uuid.uuid4().hex}.tmp"
    temporary.write_text(
        json.dumps({"version": version_dir.name, "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}),
        encoding="utf-8",
    )
    try:
        # Windows 上轮询接口可能正短暂读取 active.json，文件共享冲突不应让
        # 已完整建好的索引误报失败；只重试这个瞬时错误，超时仍然失败关闭。
        started = time.monotonic()
        while True:
            try:
                temporary.replace(pointer)
                break
            except PermissionError:
                if time.monotonic() - started >= ACTIVE_POINTER_RETRY_SECONDS:
                    raise
                time.sleep(0.02)
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def _db_path(workspace_root: Path, case_id: str = CASE_ID) -> Path:
    return _active_data_dir(workspace_root, case_id) / "rag.sqlite3"


def _index_path(workspace_root: Path, case_id: str = CASE_ID) -> Path:
    return _active_data_dir(workspace_root, case_id) / "rag.faiss"


def _manifest_path(workspace_root: Path, case_id: str = CASE_ID) -> Path:
    return _active_data_dir(workspace_root, case_id) / "manifest.json"


def _connect(workspace_root: Path, case_id: str = CASE_ID, *, data_dir: Path | None = None) -> sqlite3.Connection:
    database = (data_dir or _active_data_dir(workspace_root, case_id)) / "rag.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=15000")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chunk_id TEXT UNIQUE NOT NULL,
        case_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        ticker TEXT NOT NULL,
        document_id TEXT NOT NULL,
        source_file TEXT NOT NULL,
        storage_relpath TEXT NOT NULL,
        source_sha256 TEXT NOT NULL,
        disclosure_date TEXT NOT NULL,
        report_year INTEGER NOT NULL,
        page INTEGER NOT NULL,
        title TEXT NOT NULL,
        text TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS retrieval_logs (
        retrieval_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        case_id TEXT NOT NULL,
        company_name TEXT NOT NULL,
        t0 TEXT NOT NULL,
        rule_id TEXT NOT NULL,
        query TEXT NOT NULL,
        top_k INTEGER NOT NULL,
        returned_chunk_ids TEXT NOT NULL,
        filter_summary TEXT NOT NULL,
        index_version TEXT NOT NULL
        )"""
    )
    connection.commit()
    return connection


def _tokens(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    chinese = [normalized[i : i + 2] for i in range(max(0, len(normalized) - 1))]
    latin = re.findall(r"[a-z0-9_.%-]+", text.lower())
    return chinese + latin


def _vector(text: str) -> np.ndarray:
    vector = np.zeros(VECTOR_DIM, dtype="float32")
    for token in _tokens(text):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        position = int.from_bytes(digest[:4], "little") % VECTOR_DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[position] += sign
    norm = float(np.linalg.norm(vector))
    if norm:
        vector /= norm
    return vector


def _chunks(text: str, size: int = 900, overlap: int = 120) -> Iterable[str]:
    clean = re.sub(r"[ \t]+", " ", text).strip()
    if not clean:
        return
    start = 0
    while start < len(clean):
        end = min(len(clean), start + size)
        if end < len(clean):
            boundary = max(clean.rfind("\n", start, end), clean.rfind("。", start, end))
            if boundary > start + size // 2:
                end = boundary + 1
        piece = clean[start:end].strip()
        if len(piece) >= 20:
            yield piece
        if end >= len(clean):
            break
        start = max(start + 1, end - overlap)


def _source_registry(workspace_root: Path, case_id: str) -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    for document in get_case_documents(workspace_root, case_id):
        registry.append(
            {
                "document_id": document["document_id"],
                "source_file": document["source_file"],
                "storage_relpath": document["storage_relpath"],
                "source_sha256": document["sha256"],
                "disclosure_date": document["disclosure_date"],
                "report_year": document["report_year"],
            }
        )
    return sorted(registry, key=lambda item: (item["report_year"], item["document_id"]))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def snapshot_id_for_chunks(chunks: list[dict[str, Any]]) -> str:
    """按远端发布合同计算完整 chunk 快照摘要，供本机/远端一致性比较。"""

    canonical = [
        {
            "chunk_id": str(chunk.get("chunk_id") or ""),
            "document_id": chunk.get("document_id"),
            "pdf_page": chunk.get("pdf_page"),
            "content": str(chunk.get("content") or ""),
            "metadata": chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {},
        }
        for chunk in chunks
        if chunk.get("chunk_id") and chunk.get("content")
    ]
    digest = hashlib.sha256()
    for chunk in sorted(canonical, key=lambda item: item["chunk_id"]):
        digest.update(json.dumps(chunk, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\0")
    return f"RAG-SNAPSHOT-{digest.hexdigest()[:24].upper()}"


def prepare_index(workspace_root: Path, *, case_id: str = CASE_ID, force: bool = False) -> dict[str, Any]:
    """按案例 singleflight 建库；并发请求共享同一次完整发布结果。"""

    key = _index_state_key(workspace_root, case_id)
    with _INDEX_LOCKS_GUARD:
        previous = _INDEX_BUILD_STATES.get(key)
        if previous and previous.get("status") == "building":
            event = previous["event"]
            waiter = True
        else:
            event = threading.Event()
            _INDEX_BUILD_STATES[key] = {"status": "building", "event": event, "result": None, "error": None}
            waiter = False
    if waiter:
        event.wait()
        with _INDEX_LOCKS_GUARD:
            state = _INDEX_BUILD_STATES.get(key) or {}
            if state.get("error"):
                raise RuntimeError("RAG_INDEX_BUILD_FAILED")
            result = state.get("result")
        if isinstance(result, dict):
            return dict(result)
        raise RuntimeError("RAG_INDEX_BUILD_FAILED")
    try:
        with _index_lock(workspace_root, case_id):
            result = _prepare_index_unlocked(workspace_root, case_id=case_id, force=force)
    except Exception as error:
        with _INDEX_LOCKS_GUARD:
            state = _INDEX_BUILD_STATES.get(key)
            if state is not None:
                state.update({"status": "failed", "error": "RAG_INDEX_BUILD_FAILED"})
                state["event"].set()
        raise error
    with _INDEX_LOCKS_GUARD:
        state = _INDEX_BUILD_STATES.get(key)
        if state is not None:
            state.update({"status": "ready", "result": dict(result), "error": None})
            state["event"].set()
    return result


def _prepare_index_unlocked(workspace_root: Path, *, case_id: str = CASE_ID, force: bool = False) -> dict[str, Any]:
    case = get_case(workspace_root, case_id)
    if case is None:
        raise ValueError("案例未登记。")
    registry = _source_registry(workspace_root, case_id)
    fingerprints: list[dict[str, Any]] = []
    for source in registry:
        path = workspace_root / source["storage_relpath"]
        if not path.exists():
            raise FileNotFoundError(source["source_file"])
        actual = _file_sha256(path)
        if actual != source["source_sha256"]:
            raise ValueError(f"{source['source_file']} SHA-256 与登记值不一致")
        fingerprints.append({"source_file": source["source_file"], "sha256": actual})

    fingerprint = hashlib.sha256(
        json.dumps(fingerprints, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    # 缓存判断期间只解析一次 active 指针。若建库线程恰好发布新版本，清单
    # 和 FAISS 文件仍来自同一个目录，不会把两个版本拼成一次“ready”。
    active_dir = _active_data_dir(workspace_root, case_id)
    manifest_path = active_dir / "manifest.json"
    index_path = active_dir / "rag.faiss"
    if not force and manifest_path.exists() and index_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, AttributeError):
            manifest = {}
        if manifest.get("source_fingerprint") == fingerprint and manifest.get("index_version") == INDEX_VERSION:
            return {**manifest, "status": "ready", "rebuilt": False}

    version_dir = _version_dir(workspace_root, case_id, fingerprint)
    connection = _connect(workspace_root, case_id, data_dir=version_dir)
    rows: list[tuple[Any, ...]] = []
    vectors: list[np.ndarray] = []
    try:
        for source in registry:
            path = (workspace_root / source["storage_relpath"]).resolve()
            try:
                path.relative_to(workspace_root.resolve())
            except ValueError as error:
                raise ValueError(f"{source['source_file']}来源文件超出工作区边界") from error
            document = fitz.open(path)
            try:
                for page_number, page in enumerate(document, start=1):
                    page_text = page.get_text("text")
                    for offset, chunk_text in enumerate(_chunks(page_text)):
                        title = next((line.strip() for line in chunk_text.splitlines() if line.strip()), "年报原文")[:120]
                        chunk_prefix = "STD" if case_id == CASE_ID else case_id
                        chunk_id = f"{chunk_prefix}-{source['report_year']}-P{page_number:04d}-C{offset:02d}"
                        rows.append(
                            (
                                chunk_id,
                                case_id,
                                case["company_name"],
                                case.get("ticker", ""),
                                source["document_id"],
                                source["source_file"],
                                source["storage_relpath"],
                                source["source_sha256"],
                                source["disclosure_date"],
                                source["report_year"],
                                page_number,
                                title,
                                chunk_text,
                            )
                        )
                        vectors.append(_vector(f"{title}\n{chunk_text}"))
            finally:
                document.close()
        connection.executemany(
            """INSERT INTO chunks
            (chunk_id,case_id,company_name,ticker,document_id,source_file,storage_relpath,source_sha256,disclosure_date,report_year,page,title,text)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        connection.commit()
    finally:
        connection.close()

    matrix = np.vstack(vectors).astype("float32") if vectors else np.zeros((0, VECTOR_DIM), dtype="float32")
    index = faiss.IndexFlatIP(VECTOR_DIM)
    if len(matrix):
        index.add(matrix)
    # FAISS 的 Windows FileIOWriter 不支持含中文的路径；先序列化到内存再由 pathlib 落盘。
    (version_dir / "rag.faiss").write_bytes(faiss.serialize_index(index).tobytes())
    snapshot_chunks = [
        {
            "chunk_id": row[0],
            "document_id": row[4],
            "pdf_page": row[10],
            "content": row[12],
            "metadata": {
                "title": row[11],
                "source_sha256": row[7],
                "disclosure_date": row[8],
                "report_year": row[9],
                "company_name": row[2],
                "ticker": row[3],
            },
        }
        for row in rows
    ]
    manifest = {
        "status": "ready",
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "rebuilt": True,
        "index_version": INDEX_VERSION,
        "embedding": "deterministic-char-ngram-hashing-v1",
        "vector_backend": "faiss.IndexFlatIP",
        "case_id": case_id,
        "company_name": case["company_name"],
        "source_fingerprint": fingerprint,
        "rag_snapshot_id": snapshot_id_for_chunks(snapshot_chunks),
        "source_count": len(registry),
        "chunk_count": len(rows),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _publish_version(workspace_root, case_id, version_dir)
    return manifest


def status(workspace_root: Path, case_id: str = CASE_ID) -> dict[str, Any]:
    # 状态接口也固定一个版本快照，避免 active 指针切换时出现短暂假阴性。
    key = _index_state_key(workspace_root, case_id)
    with _INDEX_LOCKS_GUARD:
        build_state = dict(_INDEX_BUILD_STATES.get(key) or {})
    if build_state.get("status") == "building":
        return {
            "status": "index_building",
            "source_status": "source_available",
            "index_status": "building",
            "runtime_ready": False,
            "index_version": INDEX_VERSION,
            "case_id": case_id,
            "chunk_count": 0,
            "boundary": "同一案例已有索引构建进行中；并发请求等待同一个版本，不会重复建库。",
        }
    active_dir = _active_data_dir(workspace_root, case_id)
    manifest = active_dir / "manifest.json"
    if not manifest.exists() or not (active_dir / "rag.faiss").exists():
        payload = {
            "status": "not_built",
            "source_status": "source_available",
            "index_status": "not_built",
            "runtime_ready": False,
            "index_version": INDEX_VERSION,
            "case_id": case_id,
            "chunk_count": 0,
        }
        if build_state.get("status") == "failed":
            payload.update({"status": "failed", "index_status": "failed", "failure_code": "RAG_INDEX_BUILD_FAILED"})
        return payload
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("source_status", "source_available")
            payload.setdefault("index_status", "ready")
            payload.setdefault("runtime_ready", payload.get("status") == "ready")
        return payload
    except (OSError, json.JSONDecodeError):
        return {
            "status": "not_built",
            "source_status": "source_available",
            "index_status": "corrupt",
            "runtime_ready": False,
            "index_version": INDEX_VERSION,
            "case_id": case_id,
            "chunk_count": 0,
        }


def export_chunks(workspace_root: Path, case_id: str = CASE_ID) -> list[dict[str, Any]]:
    """导出已发布 RAG 版本的证据块，供公网 Postgres 持久化；不导出本机路径。"""

    # 先固定 active 版本，再用同一路径检查和连接；发布切换不会导致
    # exists() 检查旧库、随后却打开新库的 TOCTOU 串版本。
    active_dir = _active_data_dir(workspace_root, case_id)
    database = active_dir / "rag.sqlite3"
    if not database.exists():
        return []
    connection = _connect(workspace_root, case_id, data_dir=active_dir)
    try:
        rows = connection.execute(
            """SELECT chunk_id, document_id, page, title, text, source_sha256,
                      disclosure_date, report_year, company_name, ticker
               FROM chunks WHERE case_id=? ORDER BY id""",
            (case_id,),
        ).fetchall()
        return [
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "pdf_page": row["page"],
                "content": row["text"],
                "metadata": {
                    "title": row["title"],
                    "source_sha256": row["source_sha256"],
                    "disclosure_date": row["disclosure_date"],
                    "report_year": row["report_year"],
                    "company_name": row["company_name"],
                    "ticker": row["ticker"],
                },
            }
            for row in rows
        ]
    finally:
        connection.close()


def _keyword_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    tokens = _tokens(text)
    counts = sum(1 for token in tokens if token in query_tokens)
    return min(1.0, counts / max(2.0, math.sqrt(len(tokens))))


def _anchor_score(anchor_terms: list[str], text: str) -> float:
    """专业固定问题至少命中一个主题锚点；否则宁可 no_hit，也不返回词面噪声。"""

    normalized = re.sub(r"\s+", "", text.lower())
    hits = sum(1 for term in anchor_terms if re.sub(r"\s+", "", term.lower()) in normalized)
    return min(1.0, hits / max(1, min(3, len(anchor_terms))))


def _matched_excerpt(text: str, terms: list[str], limit: int = 500) -> tuple[str, int, int]:
    """截取包含专业锚点的原文窗口，并返回在当前 chunk 内的字符范围。"""

    lower_text = text.lower()
    positions = [lower_text.find(term.lower()) for term in terms if term and lower_text.find(term.lower()) >= 0]
    match_at = min(positions) if positions else 0
    start = max(0, match_at - 140)
    end = min(len(text), start + limit)
    if end - start < limit and start > 0:
        start = max(0, end - limit)
    return text[start:end], start, end


def _retrieve_candidates(
    connection: sqlite3.Connection,
    active_dir: Path,
    workspace_root: Path,
    *,
    case_id: str,
    company_name: str,
    t0: str,
    effective_query: str,
    top_k: int,
    question: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """在一个固定版本内完成召回，调用方负责事务与连接生命周期。"""

    rows = connection.execute(
        """SELECT * FROM chunks
        WHERE case_id=? AND company_name=? AND disclosure_date<=?
        ORDER BY id""",
        (case_id, company_name, t0),
    ).fetchall()
    if not rows:
        return []

    index_bytes = np.frombuffer((active_dir / "rag.faiss").read_bytes(), dtype="uint8")
    index = faiss.deserialize_index(index_bytes)
    vector = _vector(effective_query).reshape(1, -1)
    search_k = min(max(top_k * 20, 100), index.ntotal)
    scores, positions = index.search(vector, search_k)
    allowed = {row["id"] - 1: row for row in rows}
    query_tokens = set(_tokens(effective_query))
    vector_scores = {
        int(position): float(score)
        for score, position in zip(scores[0], positions[0])
        if int(position) >= 0
    }
    candidate_positions = set(vector_scores)
    if question:
        # 向量前 100 名之外仍可能存在明确专业词命中，因此把主题锚点命中页并入候选池。
        for row in rows:
            if _anchor_score(question["anchor_terms"], f"{row['title']} {row['text']}") > 0:
                candidate_positions.add(row["id"] - 1)

    candidates: list[dict[str, Any]] = []
    for position in candidate_positions:
        row = allowed.get(int(position))
        if row is None:
            continue
        vector_score = vector_scores.get(int(position))
        if vector_score is None:
            vector_score = float(np.dot(vector[0], index.reconstruct(int(position))))
        keyword_score = _keyword_score(query_tokens, f"{row['title']} {row['text']}")
        anchor_score = _anchor_score(question["anchor_terms"], f"{row['title']} {row['text']}") if question else 0.0
        if question and anchor_score <= 0:
            continue
        hybrid_score = (
            float(vector_score) * 0.45 + keyword_score * 0.25 + anchor_score * 0.30
            if question
            else float(vector_score) * 0.65 + keyword_score * 0.35
        )
        page_metadata = registered_page_metadata(workspace_root, case_id, row["document_id"], row["page"])
        excerpt_terms = question["anchor_terms"] if question else [part for part in effective_query.split() if part]
        excerpt, excerpt_start, excerpt_end = _matched_excerpt(row["text"], excerpt_terms)
        candidates.append(
            {
                "evidence_id": f"RAG-{row['chunk_id']}",
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "score": round(hybrid_score, 6),
                "low_confidence": hybrid_score < 0.50,
                "confidence_note": "低置信候选，必须回原页复核。" if hybrid_score < 0.50 else "候选片段仍须回原页复核。",
                "vector_score": round(float(vector_score), 6),
                "keyword_score": round(keyword_score, 6),
                "anchor_score": round(anchor_score, 6),
                "source_file": row["source_file"],
                "source_sha256": row["source_sha256"],
                "disclosure_date": row["disclosure_date"],
                "report_year": row["report_year"],
                "pdf_page": row["page"],
                "print_page": page_metadata["print_page"],
                "linked_field_evidence_ids": page_metadata["linked_field_evidence_ids"],
                "source_locator": f"PDF 第 {row['page']} 页 / {row['chunk_id']}",
                "title": row["title"],
                "excerpt": excerpt,
                "excerpt_char_start": excerpt_start,
                "excerpt_char_end": excerpt_end,
                "chunk_char_length": len(row["text"]),
                "excerpt_is_verbatim": True,
                "review_status": "candidate_fragment_pending_human_page_review",
            }
        )
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return [item for item in candidates[:top_k] if item["score"] > 0]


def retrieve(
    workspace_root: Path,
    *,
    query: str,
    t0: str,
    rule_id: str,
    top_k: int = 5,
    case_id: str = CASE_ID,
    company_name: str | None = None,
    question_id: str | None = None,
) -> dict[str, Any]:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        # API 模型已有同一限制；内部函数仍需自守边界，避免测试或后台调用绕过验证。
        raise ValueError("top_k 必须是 1 至 10 的整数")
    question = _get_question(question_id)
    if question and rule_id not in question["rule_ids"]:
        raise ValueError(f"{question_id} 不属于规则 {rule_id}")
    effective_query = question["retrieval_query"] if question else query.strip()
    if not effective_query:
        raise ValueError("检索词不能为空")
    case = get_case(workspace_root, case_id)
    if case is None:
        raise ValueError("案例未登记。")
    effective_company_name = company_name if company_name is not None else case["company_name"]
    # 清单、向量与数据库固定在同一已发布目录；不能先调 status 再重新读取
    # active，否则并发重建可能让一次请求跨越两个证据快照。
    active_dir = _active_data_dir(workspace_root, case_id)
    manifest_path = active_dir / "manifest.json"
    index_path = active_dir / "rag.faiss"
    try:
        current = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, AttributeError):
        current = {}
    if current.get("status") != "ready" or not index_path.exists():
        raise RuntimeError("RAG 索引尚未构建")

    connection = _connect(workspace_root, case_id, data_dir=active_dir)
    try:
        candidates = _retrieve_candidates(
            connection,
            active_dir,
            workspace_root,
            case_id=case_id,
            company_name=effective_company_name,
            t0=t0,
            effective_query=effective_query,
            top_k=top_k,
            question=question,
        )
        retrieval_id = f"RET-{uuid.uuid4().hex[:12].upper()}"
        connection.execute(
            """INSERT INTO retrieval_logs VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                retrieval_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                case_id,
                effective_company_name,
                t0,
                rule_id,
                effective_query,
                top_k,
                json.dumps([item["chunk_id"] for item in candidates]),
                json.dumps(
                    {
                        "case_id": case_id,
                        "company_name": effective_company_name,
                        "t0_lte": t0,
                        "question_id": question_id,
                        "question_set_version": QUESTION_SET_VERSION if question else None,
                        "retrieval_version": RETRIEVAL_VERSION,
                    },
                    ensure_ascii=False,
                ),
                INDEX_VERSION,
            ),
        )
        connection.commit()
    finally:
        # FAISS 反序列化、页元数据或日志落库任一失败都要立即释放 SQLite；
        # 否则 Windows 上后续版本发布与临时目录清理会被悬挂句柄阻塞。
        connection.close()
    return {
        "retrieval_id": retrieval_id,
        "status": "hit" if candidates else "no_hit",
        "question_set_version": QUESTION_SET_VERSION if question else None,
        "retrieval_version": RETRIEVAL_VERSION,
        "question": dict(question) if question else None,
        "effective_query": effective_query,
        "boundary": "检索结果是候选原文，不构成审计结论；须回到原 PDF 页复核。",
        "filter": {"case_id": case_id, "company_name": effective_company_name, "t0_lte": t0, "rule_id": rule_id},
        "evidence_gap": {
            "status": "retrieval_no_hit" if not candidates else "candidate_fragments_found",
            "label": "资料缺口候选 - 未检索到可回查片段" if not candidates else "已返回候选原文片段",
            "message": (
                question["no_hit_prompt"]
                if question and not candidates
                else "当前没有使用固定问题的专用无命中提示。"
                if not candidates
                else "命中只表示候选片段；是否披露充分、是否形成资料缺口，须人工回页确认。"
            ),
            "requires_human_confirmation": True,
            "auto_sync_to_risk_card": False,
        },
        "results": candidates,
    }


def get_retrieval(workspace_root: Path, retrieval_id: str) -> dict[str, Any] | None:
    """检索编号不暴露案例路径；在案例当前及历史版本日志中逐一查找。"""

    for case in list_cases(workspace_root):
        case_id = case["case_id"]
        root = _runtime_dir(workspace_root, case_id)
        active_dir = _active_data_dir(workspace_root, case_id)
        # 检索日志是审计留痕，不随 active 指针切换而失效。当前版本优先，
        # 其余不可变版本和旧版根目录依次回查，并去掉重复路径。
        candidates = [active_dir / "rag.sqlite3"]
        versions_dir = root / "versions"
        if versions_dir.is_dir():
            candidates.extend(path / "rag.sqlite3" for path in sorted(versions_dir.iterdir(), reverse=True) if path.is_dir())
        candidates.append(root / "rag.sqlite3")
        seen: set[str] = set()
        for path in candidates:
            path_key = str(path.resolve())
            if path_key in seen or not path.is_file():
                continue
            seen.add(path_key)
            connection = sqlite3.connect(path, timeout=5)
            connection.row_factory = sqlite3.Row
            try:
                row = connection.execute(
                    "SELECT * FROM retrieval_logs WHERE retrieval_id=?",
                    (retrieval_id,),
                ).fetchone()
            except sqlite3.DatabaseError:
                # 单个旧版本损坏不能阻断其他已发布版本的留痕回查。
                row = None
            finally:
                connection.close()
            if row:
                return dict(row)
    return None
