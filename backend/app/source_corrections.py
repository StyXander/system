"""公开工程更正与来源日期冲突闸门，保留历史快照和真实人工记录。

自动更正必须绑定原字段哈希和原件哈希；不能覆盖已改变的字段或真人判断。
URL路径日期仅用于发现冲突，不冒充官方公告日期，也不自动改变冻结T0。
同一编号的历史运行保持原内容，新计算携带工程更正版本和原值回查记录。
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any


def public_source_access_url(document: dict[str, Any]) -> str:
    """修复已实测失效的公开访问地址，不改冻结原件、披露日期或历史输出。

    2026-10-10 官网查询返回紫金矿业2025年报公告1225550242。
    完整下载79,925,886字节，SHA256与登记原件一致，原页码可继续使用。
    仅对该原件及原错误地址生效；其他版本沿用自身登记地址。
    """
    original = str(document.get("source_url") or "")
    if (
        document.get("document_id") == "CNINFO-601899-2025-01819E1C7DAA"
        and str(document.get("file_sha256") or document.get("sha256") or "").lower()
        == "01819e1c7daad939d1779a8aa729f50f02151192e609cb28c2c405634a8f343d"
        and original == "https://static.cninfo.com.cn/finalpage/2026-03-21/1225023658.PDF"
    ):
        return "https://static.cninfo.com.cn/finalpage/2026-03-21/1225550242.PDF"
    return original


@lru_cache(maxsize=16)
def _read_public_json_version(path: Path, modified_ns: int, size: int) -> tuple[Any, bytes]:
    """只缓存部署中的只读公开文件；调用方不修改返回对象。

    文件版本作为键，更正文件换版立即重新读取；字段及原件的哈希绑定仍照常校验。
    此缓存不接受用户上传、私有案例或真人写回记录，不能跨租户复用运行材料。
    """
    raw = path.read_bytes()
    return json.loads(raw), raw


def read_versioned_public_json(path: Path) -> tuple[Any, bytes]:
    """避免每次取一个案例都反复解析全量台账，缺失或损坏仍由调用方处理。"""
    path = path.resolve()
    stat = path.stat()
    return _read_public_json_version(path, stat.st_mtime_ns, stat.st_size)


def row_fingerprint(row: dict[str, Any]) -> str:
    """字段指纹保留原始候选及人工状态，避免隐式覆盖别人的更正。"""
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def source_document_date(case: dict[str, Any], document_id: str, fallback: str = "") -> str:
    """检索沿用当前原件日期，旧索引不能凭过时日期越过查询截止日。

    官方同公告核验已绑定原件时使用核验日期；尚未核验的链接冲突保守取较晚日。
    私有副本不套用公共日期台账，未登记文档继续由调用方原有来源闸门处理。
    """
    document = next((d for d in case.get("documents", []) if str(d.get("document_id") or "") == document_id), None)
    if not document:
        return fallback
    registered = str(document.get("disclosure_date") or fallback)
    verification = document.get("official_date_verification") or {}
    if verification.get("status") == "matched_same_announcement":
        return registered
    match = re.search(r"/finalpage/(\d{4}-\d{2}-\d{2})/", str(document.get("source_url") or ""))
    return max(registered, match[1]) if match else registered


def apply_public_corrections(root: Path, case: dict[str, Any]) -> dict[str, Any]:
    """仅作用于公开巨潮快照，私有副本不读取公共更正文件。"""
    if case.get("sample_type") != "public" or case.get("registry_mode") != "cninfo_official_auto" or case.get("tenant_id"):
        return case
    corrected = deepcopy(case)
    corrections_path = root / "backend" / "source_corrections_20261009.json"
    try:
        ledger, ledger_bytes = read_versioned_public_json(corrections_path)
        if not isinstance(ledger, dict):
            raise ValueError("工程更正台账格式不正确")
    except (OSError, ValueError):
        ledger, ledger_bytes = {}, b""
    entries = [e for e in ledger.get("entries", []) if e.get("case_id") == case.get("case_id")]
    try:
        date_payload, date_bytes = read_versioned_public_json(root / "backend/source_date_verifications_20261009.json")
        if not isinstance(date_payload, dict):
            raise ValueError("日期核验台账格式不正确")
        date_records = date_payload.get("verifications", [])
    except (OSError, ValueError):
        date_records, date_bytes = [], b""
    documents = {d["document_id"]: d for d in corrected.get("documents", [])}
    changes = []
    for row in corrected.get("financial_fields", []):
        entry = next((e for e in entries if e.get("evidence_id") == row.get("evidence_id")), None)
        if entry:
            document = documents.get(str(row.get("document_id")), {})
            doc_hash = str(document.get("file_sha256") or document.get("sha256") or "").lower()
            existing = row.get("engineering_correction") or {}
            # 同一公共bundle可能经过目录与运行两次合并。核对新候选正文和旧指纹后
            # 才承认“已应用”，不能把任意携带revision_id的字段当作有效更正。
            ignored = {"engineering_correction", "disclosure_date", "source_conflicts"}
            current_body = {k: v for k, v in row.items() if k not in ignored}
            expected_body = {k: v for k, v in entry["replacement"].items() if k not in ignored}
            already_applied = bool(existing and existing.get("revision_id") == ledger.get("revision_id") and row_fingerprint(existing.get("previous_row") or {}) == entry.get("previous_row_sha256") and current_body == expected_body and doc_hash == entry.get("document_sha256", "").lower())
            if already_applied:
                changes.append(row.get("evidence_id"))
            elif row_fingerprint(row) == entry.get("previous_row_sha256") and doc_hash == entry.get("document_sha256", "").lower():
                original = deepcopy(row)
                row.clear()
                row.update(deepcopy(entry["replacement"]))
                # 原值随新快照保留，绝不把工程修复标成human_corrected。
                row["engineering_correction"] = {"revision_id": ledger.get("revision_id"), "previous_row": original, "professional_review": "pending"}
                changes.append(row.get("evidence_id"))
            elif row.get("source_review_status") not in {"human_confirmed", "human_corrected", "owner_confirmed_registered_public_evidence"}:
                row.setdefault("source_conflicts", []).append("工程更正与当前字段或原件指纹不同，需回查版本；未自动覆盖。")
    date_conflicts = []
    for document in documents.values():
        match = re.search(r"/finalpage/(\d{4}-\d{2}-\d{2})/", str(document.get("source_url") or ""))
        url_date = match[1] if match else None
        registered = document.get("registered_disclosure_date", document.get("disclosure_date"))
        verification = next((v for v in date_records if v.get("document_id") == document["document_id"] and v.get("document_sha256", "").lower() == str(document.get("file_sha256") or document.get("sha256") or "").lower() and str(v.get("announcement_id") or "") == str(document.get("source_url", "")).rsplit("/", 1)[-1].split(".")[0] and v.get("status") == "matched_same_announcement"), None)
        official_date = verification.get("official_announcement_date") if verification else None
        if official_date:
            # 同一公告编号的官方日期是新计算元数据；原登记日期和T0仍保留。
            document["disclosure_date"] = official_date
            document["registered_disclosure_date"] = registered
            document["official_date_verification"] = deepcopy(verification)
            for row in corrected.get("financial_fields", []):
                if row.get("document_id") == document["document_id"]:
                    row["disclosure_date"] = official_date
        effective_date = official_date or url_date
        if effective_date and registered and effective_date != registered:
            conflict = {"document_id": document["document_id"], "registered_disclosure_date": registered, "url_path_date": url_date, "official_announcement_date": official_date, "status": "official_date_confirmed_t0_adoption_pending" if official_date else "pending_official_date_confirmation", "cutoff_conflict": bool(case.get("t0") and registered <= case["t0"] < effective_date)}
            document["source_date_conflict"] = conflict
            date_conflicts.append(conflict)
            if conflict["cutoff_conflict"]:
                for row in corrected.get("financial_fields", []):
                    if row.get("document_id") == document["document_id"]:
                        message = "同一公告的官方披露日晚于冻结截止日，不参与当前计算。" if official_date else "登记披露日与官方链接日期冲突，可能越过冻结截止日；确认前不参与计算。"
                        if message not in row.setdefault("source_conflicts", []):
                            row["source_conflicts"].append(message)
                # 同一冲突原件的旧检索片段也不能绕过字段闸门进入模型。
                corrected["demo_rag_evidence"] = [e for e in corrected.get("demo_rag_evidence", []) if e.get("document_id") != document["document_id"]]
    if changes or date_conflicts:
        corrected["engineering_snapshot"] = {"revision_id": ledger.get("revision_id", "SOURCE-DATE-GUARD-20261009"), "ledger_sha256": hashlib.sha256(ledger_bytes).hexdigest() if ledger_bytes else None, "date_verifications_sha256": hashlib.sha256(date_bytes).hexdigest() if date_bytes else None, "corrected_fields": changes, "source_date_conflicts": date_conflicts, "professional_adoption": "pending", "frozen_t0_unchanged": True}
    return corrected
