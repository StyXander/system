"""案例注册表、证据闸门、标准模板与安全导入边界。

所有公司共用同一导入协议，不允许增加公司专用后端分支。
内置标准股份只是预登记案例，不能成为接口层的唯一允许对象。
新案例必须通过案例清单登记公司、时点、口径和来源文件。
导入器只读取已结构化字段，不从任意年报自由猜测财务数字。
来源文件必须放在案例包规定目录，不能引用本机绝对路径。
压缩包路径在解压前标准化，拒绝盘符、反斜杠和路径穿越。
压缩包文件数量、解压体积和压缩比均设上限，防止资源滥用。
加密压缩包无法审查内容，因此在导入阶段直接拒绝。
案例编号只允许稳定字符，防止编号被解释为目录路径。
案例编号一旦存在不会静默覆盖，避免新资料破坏旧版本链。
每份年报都要登记披露日期、官方链接和整份文件哈希。
导入时重新计算文件哈希，不能只信任案例清单中的声明值。
文件哈希不一致属于来源失败，案例不得部分导入后继续运行。
来源披露日晚于案例时点时，相关字段不能进入当期证据包。
案例时点控制的是可见信息边界，不代表资料专业上已经充分。
金额单位只允许有限枚举，防止不同单位在计算中静默混用。
报表口径必须统一为合并或母公司，不能跨口径拼接增长率。
币种保留在案例上下文，当前规则不会自动执行汇率换算。
公开、授权脱敏与合成案例必须显式区分，不靠文件名猜测。
公开资料仍需个人信息检查，公开属性不等于可以任意传播。
非公开资料必须同时确认授权与脱敏，否则导入流程关闭。
文本文件会扫描高风险个人信息，年报 PDF 不做不可靠的文本误判。
字段证据编号在案例内保持唯一，便于模型和人工共同引用。
财务字段必须绑定已登记文档、页码、定位说明和口径说明。
营业收入主字段使用报表披露值，不允许用模型生成估计金额。
应收账款主字段必须明确账面余额或净额，不能省略计量基础。
R1 正式比较优先使用账面余额，避免坏账准备变动扭曲增速。
坏账准备作为增强证据独立登记，不覆盖应收账款主字段。
应收账款净额作为勾稽证据独立登记，不参与主口径增长比较。
账面余额减坏账准备应与净额一致，差异必须由人工解释。
R1 至少需要连续两个年度的营业收入和应收账款主字段。
三年趋势只在三个连续期间均登记完整时开放，不能补造缺年。
辅助规则缺少现金流或净利润字段时可以跳过，但必须显示边界。
公开账龄以独立案例证据保存，不冒充客户级账龄明细。
公开账龄每个区间都绑定原年报文档和 PDF 页码。
公开账龄合计必须与登记的应收账款账面余额完成程序勾稽。
账龄勾稽通过只说明转录结构一致，不说明客户余额真实存在。
期后回款为空时保留资料缺口，不用合成数据冒充公开事实。
合同结算条款为空时保留资料缺口，不从通用会计政策推断客户条款。
信用政策未取得时必须保持未验证，不因行业相同而自动补齐。
案例包的增强证据进入运行证据包，但不会改写原始报表数字。
增强证据关闭同名资料缺口时仍保留人工专业复核状态。
标准案例模板默认禁止模型传输，避免合成资料误入外部模型。
公开案例可以声明允许模型传输，但真实调用仍受运行模式控制。
模型传输许可属于案例级属性，不由前端复选框临时绕过。
案例来源存储按案例编号隔离，跨案例文档引用必须返回未登记。
RAG 索引目录同样按案例编号隔离，避免检索结果相互污染。
来源下载接口只允许案例清单中的文档编号，不能读取任意文件。
旧标准股份来源链接只读兼容，不作为新案例的接入方式。
案例详情接口公开必要元数据，不公开本机真实存储绝对路径。
公开来源记录保留哈希和页码，使评委能够回到原文复核。
字段结构校验通过不等于专业口径签字，状态必须保留待确认。
案例技术导入通过不等于合规负责人已经冻结正式样例。
第二案例的同行业属性来自公开信息，不能据此声称风险可比。
R1 未触发只说明未出现规定增长错配，不代表公司没有其他风险。
导入失败时只清理由本次创建的隔离目录，不触碰其他案例。
清理目标必须先确认位于案例根目录下，防止异常路径扩大影响。
运行命名空间用于隔离自动化测试与人工运行记录。
测试命名空间不能被正式状态接口当成人工复核证据。
模板内容变更时必须保持案例模式向后兼容或明确升级路径。
新增字段种类时必须同步前缀、口径校验、来源选择和测试。
新增结构化表时必须决定它是主字段、增强证据还是资料缺口。
任何自动提取能力上线前都应保留人工页码确认与原文回查入口。
本模块的核心原则是先证明来源可回查，再允许计算和模型使用。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import uuid
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import fitz
from openpyxl import load_workbook

from . import data as standard_data
from .schemas import AI_GENERATED_CONTENT_NOTICE


CASE_SCHEMA_VERSION = "case_manifest_v1"
TEMPLATE_VERSION = "case-template-v1.0"
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 150 * 1024 * 1024
MAX_FILES = 64
MAX_COMPRESSION_RATIO = 120
CASE_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")
DOCUMENT_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,63}$")
SHA256_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")
ALLOWED_AMOUNT_UNITS = {"元", "千元", "万元", "百万元"}
ALLOWED_SAMPLE_TYPES = {"public", "authorized_deidentified", "synthetic"}
ALLOWED_STATEMENT_SCOPES = {"合并", "母公司"}
ALLOWED_FILE_NAMES = {
    "case_manifest.json",
    "financial_fields.csv",
    "financial_fields.xlsx",
    "aging.csv",
    "aging.xlsx",
    "subsequent_receipts.csv",
    "subsequent_receipts.xlsx",
    "contract_terms.csv",
    "contract_terms.json",
    "deidentification_log.csv",
    "deidentification_log.xlsx",
    "README.md",
    "README_填写说明.txt",
}
ALLOWED_FIELD_KINDS = {
    "revenue",
    "accounts_receivable",
    "accounts_receivable_allowance",
    "accounts_receivable_net",
    "operating_cash_flow",
    "net_profit",
}
FIELD_PREFIX = {
    "revenue": "REV",
    "accounts_receivable": "AR",
    "accounts_receivable_allowance": "AR_ALLOW",
    "accounts_receivable_net": "AR_NET",
    "operating_cash_flow": "CFO",
    "net_profit": "NP",
}


def _runtime_base(workspace_root: Path) -> Path:
    namespace = re.sub(r"[^A-Za-z0-9_-]", "", os.getenv("AUDITTRACE_RUNTIME_NAMESPACE", ""))
    base = workspace_root / "backend" / "runtime"
    return base / namespace if namespace else base


def _cases_dir(workspace_root: Path) -> Path:
    path = _runtime_base(workspace_root) / "cases"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _case_dir(workspace_root: Path, case_id: str) -> Path:
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise ValueError("案例编号只允许 3—40 位大写字母、数字、下划线或连字符。")
    return _cases_dir(workspace_root) / case_id


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest().upper()


def _iso_date(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    try:
        date.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"{field_name} 必须是 YYYY-MM-DD。") from error
    return text


def _bool(value: Any, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError(f"{field_name} 必须是 JSON 布尔值。")


def _safe_zip_name(raw_name: str) -> str:
    """ZIP 内路径在解压前标准化；拒绝盘符、绝对路径、反斜杠和 ``..``。"""
    if not raw_name or "\\" in raw_name or re.match(r"^[A-Za-z]:", raw_name):
        raise ValueError("ZIP 包含不安全路径。")
    path = PurePosixPath(raw_name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("ZIP 包含路径穿越或空路径。")
    normalized = path.as_posix()
    if normalized.startswith("documents/"):
        if len(path.parts) != 2 or path.suffix.lower() != ".pdf":
            raise ValueError("documents 目录只允许直接存放 PDF。")
    elif normalized not in ALLOWED_FILE_NAMES:
        raise ValueError(f"ZIP 包含未允许的文件：{normalized}")
    return normalized


def _read_zip(content: bytes) -> dict[str, bytes]:
    if len(content) > MAX_ZIP_BYTES:
        raise ValueError("案例包超过 50MB 限制。")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as error:
        raise ValueError("上传文件不是有效 ZIP。") from error
    with archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if not infos or len(infos) > MAX_FILES:
            raise ValueError("案例包文件数量必须在 1—64 之间。")
        total = sum(item.file_size for item in infos)
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ValueError("案例包解压后超过 150MB 限制。")
        result: dict[str, bytes] = {}
        for info in infos:
            name = _safe_zip_name(info.filename)
            if info.flag_bits & 0x1:
                raise ValueError("不接受加密 ZIP。")
            if info.file_size > 0 and info.compress_size == 0:
                raise ValueError("ZIP 压缩信息异常。")
            ratio = info.file_size / max(1, info.compress_size)
            if ratio > MAX_COMPRESSION_RATIO:
                raise ValueError("ZIP 压缩比异常，疑似压缩炸弹。")
            if name in result:
                raise ValueError(f"ZIP 中存在重复路径：{name}")
            result[name] = archive.read(info)
        return result


def _scan_high_risk_personal_information(files: dict[str, bytes]) -> list[str]:
    """扫描可解释的人类文本，跳过哈希、URL、金额和各类技术编号。

    直接对整份 manifest 做正则会把 SHA-256 或公告 URL 中偶然出现的
    11/18 位数字误判成手机号或身份证号。这里按 JSON 键和 CSV 列筛选，
    既保留公司名称、备注、合同摘要等文本检查，也避免技术元数据误报。
    """
    patterns = {
        "居民身份证号": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
        "中国大陆手机号": re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "疑似银行卡号": re.compile(r"(?<!\d)\d{16,19}(?!\d)"),
    }
    technical_keys = {
        "sha256",
        "file_sha256",
        "source_url",
        "case_id",
        "document_id",
        "evidence_id",
        "approval_reference",
        "t0",
        "disclosure_date",
        "retention_expires_at",
        "report_year",
        "year",
        "value",
        "pdf_page",
        "print_page",
    }

    def json_segments(value: Any, key: str = "") -> list[str]:
        if key in technical_keys:
            return []
        if isinstance(value, dict):
            return [segment for child_key, child in value.items() for segment in json_segments(child, str(child_key))]
        if isinstance(value, list):
            return [segment for child in value for segment in json_segments(child, key)]
        return [value] if isinstance(value, str) else []

    findings: list[str] = []
    for name, content in files.items():
        suffix = Path(name).suffix.lower()
        if suffix not in {".json", ".csv", ".md"}:
            continue
        text = content.decode("utf-8-sig", errors="ignore")
        if suffix == ".json":
            try:
                segments = json_segments(json.loads(text))
            except json.JSONDecodeError:
                segments = [text]
        elif suffix == ".csv":
            try:
                rows = csv.DictReader(io.StringIO(text))
                segments = [
                    str(value)
                    for row in rows
                    for key, value in row.items()
                    if key not in technical_keys and value not in (None, "")
                ]
            except csv.Error:
                segments = [text]
        else:
            segments = [text]
        searchable = "\n".join(segments)
        for label, pattern in patterns.items():
            if pattern.search(searchable):
                findings.append(f"{name} 检出{label}")
    return findings


def _required_text(data: dict[str, Any], key: str, label: str, max_length: int = 200) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise ValueError(f"case_manifest.json 缺少 {label}。")
    if len(value) > max_length:
        raise ValueError(f"{label} 过长。")
    return value


def _validate_manifest(raw: Any, files: dict[str, bytes]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("case_manifest.json 必须是 JSON 对象。")
    if raw.get("schema_version") != CASE_SCHEMA_VERSION:
        raise ValueError(f"schema_version 必须为 {CASE_SCHEMA_VERSION}。")
    case_id = _required_text(raw, "case_id", "case_id", 40).upper()
    if not CASE_ID_PATTERN.fullmatch(case_id):
        raise ValueError("case_id 只允许 3—40 位大写字母、数字、下划线或连字符。")
    if case_id == standard_data.CASE_ID:
        raise ValueError("不能覆盖内置标准股份案例。")
    amount_unit = _required_text(raw, "amount_unit", "金额单位", 10)
    if amount_unit not in ALLOWED_AMOUNT_UNITS:
        raise ValueError("金额单位只允许元、千元、万元或百万元。")
    statement_scope = _required_text(raw, "statement_scope", "报表口径", 20)
    if statement_scope not in ALLOWED_STATEMENT_SCOPES:
        raise ValueError("报表口径只允许合并或母公司。")
    sample_type = _required_text(raw, "sample_type", "样例类型", 40)
    if sample_type not in ALLOWED_SAMPLE_TYPES:
        raise ValueError("样例类型必须是 public、authorized_deidentified 或 synthetic。")
    retention_expires_at = _iso_date(raw.get("retention_expires_at"), "保存期限")
    if retention_expires_at < date.today().isoformat():
        raise ValueError("案例保存期限已经届满。")
    model_transfer_allowed = _bool(raw.get("model_transfer_allowed"), "model_transfer_allowed")
    transfer_confirmation: dict[str, str] | None = None
    if model_transfer_allowed:
        # 勾选“来源合法”不自动等于允许外部模型传输。开启模型链前必须把
        # 确认人、依据、供应商和最小传输范围固化在案例包中，便于事后回查。
        raw_confirmation = raw.get("model_transfer_confirmation")
        if not isinstance(raw_confirmation, dict):
            raise ValueError("允许模型传输时必须提供 model_transfer_confirmation 对象。")
        confirmed_on = _iso_date(raw_confirmation.get("confirmed_on"), "模型传输确认日期")
        if confirmed_on > date.today().isoformat():
            raise ValueError("模型传输确认日期不得晚于今天。")
        transfer_confirmation = {
            "confirmed_by": _required_text(raw_confirmation, "confirmed_by", "模型传输确认人", 100),
            "confirmed_on": confirmed_on,
            "permission_basis": _required_text(raw_confirmation, "permission_basis", "模型传输许可依据", 300),
            "model_provider": _required_text(raw_confirmation, "model_provider", "模型供应商", 100),
            "transmission_scope": _required_text(raw_confirmation, "transmission_scope", "最小传输范围", 300),
            "approval_reference": _required_text(raw_confirmation, "approval_reference", "许可记录编号", 120),
        }

    documents_raw = raw.get("documents")
    if not isinstance(documents_raw, list) or not documents_raw:
        raise ValueError("manifest 至少登记一份来源 PDF。")
    documents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for item in documents_raw:
        if not isinstance(item, dict):
            raise ValueError("documents 每项必须是对象。")
        document_id = _required_text(item, "document_id", "document_id", 64).upper()
        if not DOCUMENT_ID_PATTERN.fullmatch(document_id) or document_id in seen_ids:
            raise ValueError("document_id 非法或重复。")
        source_file = _required_text(item, "source_file", "source_file", 160)
        source_file = _safe_zip_name(source_file)
        if not source_file.startswith("documents/") or source_file in seen_paths:
            raise ValueError("来源文件必须位于 documents/ 且路径不得重复。")
        if source_file not in files:
            raise ValueError(f"登记来源不存在：{source_file}")
        expected_hash = _required_text(item, "sha256", "来源 SHA-256", 64).upper()
        if not SHA256_PATTERN.fullmatch(expected_hash):
            raise ValueError("来源 SHA-256 格式错误。")
        actual_hash = _sha256_bytes(files[source_file])
        if actual_hash != expected_hash:
            raise ValueError(f"{source_file} 实际哈希与 manifest 不一致。")
        report_year = int(item.get("report_year"))
        if not 2000 <= report_year <= 2100:
            raise ValueError("report_year 超出允许范围。")
        documents.append(
            {
                "document_id": document_id,
                "source_file": source_file,
                "document_type": str(item.get("document_type") or "annual_report")[:40],
                "report_year": report_year,
                "disclosure_date": _iso_date(item.get("disclosure_date"), "披露日期"),
                "source_url": str(item.get("source_url") or "")[:500],
                "sha256": actual_hash,
            }
        )
        seen_ids.add(document_id)
        seen_paths.add(source_file)

    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": case_id,
        "company_name": _required_text(raw, "company_name", "公司名称"),
        "company_alias": str(raw.get("company_alias") or "")[:100],
        "ticker": str(raw.get("ticker") or "")[:30],
        "t0": _iso_date(raw.get("t0"), "T0"),
        "currency": _required_text(raw, "currency", "币种", 10).upper(),
        "amount_unit": amount_unit,
        "statement_scope": statement_scope,
        "sample_type": sample_type,
        "model_transfer_allowed": model_transfer_allowed,
        "model_transfer_confirmation": transfer_confirmation,
        "retention_expires_at": retention_expires_at,
        "documents": documents,
    }


def _rows_from_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _rows_from_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    values = list(sheet.iter_rows(values_only=True))
    if not values:
        return []
    headers = [str(item or "").strip() for item in values[0]]
    return [dict(zip(headers, row)) for row in values[1:] if any(value not in (None, "") for value in row)]


def _validate_financial_rows(
    rows: list[dict[str, Any]], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    document_ids = {item["document_id"] for item in manifest["documents"]}
    documents = {item["document_id"]: item for item in manifest["documents"]}
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(rows, start=2):
        row_case_id = str(row.get("case_id") or manifest["case_id"]).strip().upper()
        if row_case_id != manifest["case_id"]:
            raise ValueError(f"financial_fields 第 {index} 行发生跨案例串包。")
        kind = str(row.get("field_kind") or "").strip()
        if kind not in ALLOWED_FIELD_KINDS:
            raise ValueError(f"financial_fields 第 {index} 行 field_kind 不受支持。")
        try:
            year = int(row.get("year"))
            value = float(str(row.get("value")).replace(",", ""))
            pdf_page = int(row.get("pdf_page"))
        except (TypeError, ValueError) as error:
            raise ValueError(f"financial_fields 第 {index} 行的年度、金额或 PDF 页码无效。") from error
        document_id = str(row.get("document_id") or "").strip().upper()
        if document_id not in document_ids:
            raise ValueError(f"financial_fields 第 {index} 行引用未登记 document_id。")
        if documents[document_id]["disclosure_date"] > manifest["t0"]:
            raise ValueError(f"financial_fields 第 {index} 行来源披露日晚于 T0。")
        key = (kind, year)
        if key in seen:
            raise ValueError(f"financial_fields 重复登记 {kind}/{year}。")
        seen.add(key)
        unit = str(row.get("unit") or manifest["amount_unit"]).strip()
        if unit != manifest["amount_unit"]:
            raise ValueError(f"financial_fields 第 {index} 行金额单位与 manifest 不一致。")
        statement_scope = str(row.get("statement_scope") or manifest["statement_scope"]).strip()
        if statement_scope != manifest["statement_scope"]:
            raise ValueError(f"financial_fields 第 {index} 行报表口径与 manifest 不一致。")
        locator = str(row.get("locator") or "").strip()
        if not locator:
            raise ValueError(f"financial_fields 第 {index} 行缺少来源定位。")
        basis = str(row.get("field_basis") or ("net" if kind == "accounts_receivable" else "reported"))
        if kind == "accounts_receivable" and basis not in {"gross", "net"}:
            raise ValueError("应收账款 field_basis 只允许 gross 或 net。")
        if kind == "accounts_receivable_allowance" and basis not in {"allowance", "reported"}:
            raise ValueError("坏账准备 field_basis 只允许 allowance 或 reported。")
        if kind == "accounts_receivable_net" and basis not in {"net", "reported"}:
            raise ValueError("应收账款净额 field_basis 只允许 net 或 reported。")
        evidence_id = str(row.get("evidence_id") or f"{manifest['case_id']}_{FIELD_PREFIX[kind]}_{year}").upper()
        if not DOCUMENT_ID_PATTERN.fullmatch(evidence_id):
            raise ValueError(f"financial_fields 第 {index} 行 evidence_id 非法。")
        normalized.append(
            {
                "case_id": manifest["case_id"],
                "evidence_id": evidence_id,
                "field_kind": kind,
                "year": year,
                "value": value,
                "unit": unit,
                "currency": manifest["currency"],
                "statement_scope": statement_scope,
                "field_basis": basis,
                "document_id": document_id,
                "pdf_page": pdf_page,
                "print_page": int(row["print_page"]) if str(row.get("print_page") or "").strip() else None,
                "locator": locator[:300],
            }
        )
    if not normalized:
        raise ValueError("financial_fields 没有数据行。")
    year_kinds: dict[int, set[str]] = {}
    for row in normalized:
        year_kinds.setdefault(row["year"], set()).add(row["field_kind"])
    complete_years = sorted(
        (year for year, kinds in year_kinds.items() if {"revenue", "accounts_receivable"}.issubset(kinds)),
        reverse=True,
    )
    if len(complete_years) < 2:
        raise ValueError("R1 至少需要连续两年的营业收入和应收账款字段。")
    if any(a - b != 1 for a, b in zip(complete_years, complete_years[1:])):
        raise ValueError("R1 基本计算要求至少两年连续期间。")
    return normalized


def _validate_public_case_evidence(
    files: dict[str, bytes],
    manifest: dict[str, Any],
    financial_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """读取案例包中的公开账龄；它只补充解释证据，不覆盖 R1 主字段。"""
    evidence: list[dict[str, Any]] = []
    material_gaps: list[str] = []
    documents = {item["document_id"]: item for item in manifest["documents"]}
    if "aging.csv" in files:
        rows = _rows_from_csv(files["aging.csv"])
        totals: dict[int, float] = {}
        for index, row in enumerate(rows, start=2):
            case_id = str(row.get("case_id") or "").strip().upper()
            if case_id != manifest["case_id"]:
                raise ValueError(f"aging.csv 第 {index} 行发生跨案例串包。")
            try:
                year = int(row.get("year"))
                amount = float(str(row.get("gross_amount")).replace(",", ""))
                pdf_page = int(row.get("pdf_page"))
            except (TypeError, ValueError) as error:
                raise ValueError(f"aging.csv 第 {index} 行的年度、金额或页码无效。") from error
            document_id = str(row.get("document_id") or "").strip().upper()
            if document_id not in documents or documents[document_id]["disclosure_date"] > manifest["t0"]:
                raise ValueError(f"aging.csv 第 {index} 行引用未登记或晚于 T0 的来源。")
            if str(row.get("unit") or "").strip() != manifest["amount_unit"] or amount < 0 or pdf_page < 1:
                raise ValueError(f"aging.csv 第 {index} 行的单位、金额或页码不符合案例口径。")
            bucket = str(row.get("aging_bucket") or "").strip()[:40]
            if not bucket:
                raise ValueError(f"aging.csv 第 {index} 行缺少账龄区间。")
            totals[year] = totals.get(year, 0.0) + amount
            evidence.append(
                {
                    "evidence_id": f"{manifest['case_id']}-AGING-{year}-{index - 1:02d}",
                    "evidence_kind": "public_aging",
                    "field_label": f"{year}年应收账款账龄：{bucket}",
                    "details": {"year": year, "aging_bucket": bucket, "gross_amount": amount, "unit": manifest["amount_unit"]},
                    "document_id": document_id,
                    "pdf_page": pdf_page,
                    "source_url": documents[document_id]["source_url"],
                    "file_sha256": documents[document_id]["sha256"],
                    "source_mode": "case_package_public",
                    "support_status": "import_validated_pending_human_professional_confirmation",
                }
            )
        gross_by_year = {
            row["year"]: row["value"]
            for row in financial_rows
            if row["field_kind"] == "accounts_receivable" and row["field_basis"] == "gross"
        }
        for year, total in totals.items():
            expected = gross_by_year.get(year)
            if expected is None or abs(total - expected) > 0.02:
                raise ValueError(f"aging.csv {year} 年合计与应收账款账面余额不勾稽。")
    if not evidence:
        material_gaps.append("账龄结构")
    if not _rows_from_csv(files.get("subsequent_receipts.csv", b"")):
        material_gaps.append("期后回款")
    if not _rows_from_csv(files.get("contract_terms.csv", b"")):
        material_gaps.extend(["信用政策变动", "主要客户合同结算条款"])
    return evidence, material_gaps


def _standard_case(workspace_root: Path) -> dict[str, Any]:
    documents: dict[str, dict[str, Any]] = {}
    for evidence in standard_data.EVIDENCE.values():
        document_id = f"STD-AR-{evidence['year']}-{evidence['file_sha256'][:12]}"
        documents.setdefault(
            document_id,
            {
                "document_id": document_id,
                "source_file": evidence["source_file"],
                "storage_relpath": evidence["source_file"],
                "document_type": "annual_report",
                "report_year": evidence["year"],
                "disclosure_date": evidence["disclosure_date"],
                "announcement_title": evidence["announcement_title"],
                "source_url": evidence["source_url"],
                "sha256": evidence["file_sha256"],
            },
        )
    return {
        "schema_version": CASE_SCHEMA_VERSION,
        "case_id": standard_data.CASE_ID,
        "company_name": standard_data.CASE_NAME,
        "company_alias": "标准股份",
        "ticker": standard_data.TICKER,
        "t0": max(item["t0"] for item in standard_data.PERIODS.values()),
        "currency": "CNY",
        "amount_unit": "元",
        "statement_scope": "合并",
        "sample_type": "public",
        # 标准股份仍是待真人确认的开发案例。公开披露不自动等于允许把原文
        # 传给外部模型或无限期保存，因此默认关闭模型链，待真实许可记录后再开。
        "model_transfer_allowed": False,
        "retention_expires_at": "2026-12-31",
        "legal_sample_confirmation_status": "pending_human_confirmation",
        "source_snapshot_id": standard_data.SOURCE_SNAPSHOT_ID,
        "source_review_status": standard_data.SOURCE_REVIEW_STATUS,
        "documents": list(documents.values()),
        "available_years": sorted(standard_data.PERIODS, reverse=True),
        "three_year_r1_ready": True,
        "registry_mode": "built_in",
    }


def get_case(workspace_root: Path, case_id: str) -> dict[str, Any] | None:
    if case_id == standard_data.CASE_ID:
        return _standard_case(workspace_root)
    if not CASE_ID_PATTERN.fullmatch(case_id):
        return None
    path = _case_dir(workspace_root, case_id) / "case.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_cases(workspace_root: Path) -> list[dict[str, Any]]:
    cases = [_standard_case(workspace_root)]
    for path in sorted(_cases_dir(workspace_root).glob("*/case.json")):
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        cases.append(case)
    return cases


def import_case_zip(
    workspace_root: Path,
    content: bytes,
    *,
    authorized: bool,
    desensitized: bool,
) -> dict[str, Any]:
    if not authorized:
        raise ValueError("必须确认案例资料已获授权或来自合法公开来源。")
    if not desensitized:
        raise ValueError("必须确认非公开资料已脱敏；公开资料也需完成个人信息检查。")
    files = _read_zip(content)
    if "case_manifest.json" not in files:
        raise ValueError("案例包缺少 case_manifest.json。")
    financial_name = "financial_fields.csv" if "financial_fields.csv" in files else "financial_fields.xlsx" if "financial_fields.xlsx" in files else None
    if financial_name is None:
        raise ValueError("案例包缺少 financial_fields.csv 或 financial_fields.xlsx。")
    findings = _scan_high_risk_personal_information(files)
    if findings:
        raise ValueError("案例包检出高风险个人信息：" + "；".join(findings))
    try:
        raw_manifest = json.loads(files["case_manifest.json"].decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("case_manifest.json 无法解析。") from error
    manifest = _validate_manifest(raw_manifest, files)
    raw_rows = _rows_from_csv(files[financial_name]) if financial_name.endswith(".csv") else _rows_from_xlsx(files[financial_name])
    financial_rows = _validate_financial_rows(raw_rows, manifest)
    structured_evidence, material_gaps = _validate_public_case_evidence(files, manifest, financial_rows)
    case_dir = _case_dir(workspace_root, manifest["case_id"])
    if case_dir.exists():
        raise ValueError("case_id 已存在；系统不会静默覆盖旧案例。")
    case_dir.mkdir(parents=True, exist_ok=False)
    documents_dir = case_dir / "documents"
    documents_dir.mkdir()
    try:
        normalized_documents: list[dict[str, Any]] = []
        for document in manifest["documents"]:
            stored_name = f"{document['document_id']}.pdf"
            destination = documents_dir / stored_name
            destination.write_bytes(files[document["source_file"]])
            normalized_documents.append(
                {
                    **document,
                    "original_package_path": document["source_file"],
                    "source_file": Path(document["source_file"]).name,
                    "storage_relpath": destination.relative_to(workspace_root).as_posix(),
                }
            )
        complete_years = sorted(
            {
                row["year"]
                for row in financial_rows
                if row["field_kind"] in {"revenue", "accounts_receivable"}
            },
            reverse=True,
        )
        document_by_id = {item["document_id"]: item for item in normalized_documents}
        for row in financial_rows:
            document = document_by_id[row["document_id"]]
            row.update(
                {
                    "source_file": document["source_file"],
                    "storage_relpath": document["storage_relpath"],
                    "disclosure_date": document["disclosure_date"],
                    "file_sha256": document["sha256"],
                    "source_review_status": "import_validated_pending_human_professional_confirmation",
                }
            )
        case = {
            **manifest,
            "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
            "documents": normalized_documents,
            "available_years": [year for year in complete_years if year - 1 in complete_years],
            "three_year_r1_ready": len(complete_years) >= 3,
            "source_snapshot_id": f"{manifest['case_id'].lower()}-{_sha256_bytes(content)[:12].lower()}",
            "source_review_status": "import_validated_pending_human_professional_confirmation",
            "legal_sample_confirmation_status": (
                "operator_attested_manifest_record_pending_independent_review"
                if manifest["model_transfer_allowed"]
                else "pending_human_confirmation"
            ),
            "import_confirmation": {
                "authorized_or_public_source_asserted": authorized,
                "desensitization_or_personal_information_review_asserted": desensitized,
                "boundary": "接口勾选和manifest记录用于留痕，不替代独立真人或必要合规人员复核。",
            },
            "registry_mode": "imported_template",
            "structured_evidence": structured_evidence,
            "material_gaps": material_gaps,
            "imported_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "package_sha256": _sha256_bytes(content),
            "package_id": f"PKG-{uuid.uuid4().hex[:12].upper()}",
        }
        (case_dir / "financial_fields.json").write_text(
            json.dumps(financial_rows, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (case_dir / "case.json").write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
        return case
    except Exception:
        # 仅清理由本次导入刚创建、且已确认位于 cases/<case_id> 的隔离目录。
        for child in sorted(case_dir.rglob("*"), reverse=True):
            if child.is_file():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        case_dir.rmdir()
        raise


def _standard_financial_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for evidence_id, evidence in standard_data.EVIDENCE.items():
        document_id = f"STD-AR-{evidence['year']}-{evidence['file_sha256'][:12]}"
        rows.append(
            {
                "case_id": standard_data.CASE_ID,
                "evidence_id": evidence_id,
                "field_kind": evidence["field_kind"],
                "year": evidence["year"],
                "value": evidence["value"],
                "unit": evidence["unit"],
                "currency": "CNY",
                "statement_scope": "合并",
                "field_basis": "net" if evidence["field_kind"] == "accounts_receivable" else "reported",
                "document_id": document_id,
                "source_file": evidence["source_file"],
                "storage_relpath": evidence["source_file"],
                "disclosure_date": evidence["disclosure_date"],
                "announcement_title": evidence["announcement_title"],
                "source_url": evidence["source_url"],
                "pdf_page": evidence["pdf_page"],
                "print_page": evidence["print_page"],
                "locator": evidence["locator"],
                "file_sha256": evidence["file_sha256"],
                "source_review_status": standard_data.SOURCE_REVIEW_STATUS,
            }
        )
    return rows


def get_financial_rows(workspace_root: Path, case_id: str) -> list[dict[str, Any]]:
    if case_id == standard_data.CASE_ID:
        return _standard_financial_rows()
    case = get_case(workspace_root, case_id)
    if case is None:
        raise KeyError(case_id)
    path = _case_dir(workspace_root, case_id) / "financial_fields.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_case_documents(workspace_root: Path, case_id: str) -> list[dict[str, Any]]:
    case = get_case(workspace_root, case_id)
    if case is None:
        raise KeyError(case_id)
    return deepcopy(case["documents"])


def resolve_case_document(workspace_root: Path, case_id: str, document_id: str) -> tuple[Path, dict[str, Any]] | None:
    case = get_case(workspace_root, case_id)
    if case is None:
        return None
    document = next((item for item in case["documents"] if item["document_id"] == document_id), None)
    if document is None:
        return None
    path = (workspace_root / document["storage_relpath"]).resolve()
    if not path.is_file():
        return None
    allowed_root = workspace_root.resolve()
    try:
        path.relative_to(allowed_root)
    except ValueError:
        return None
    return path, deepcopy(document)


def _select(rows: Iterable[dict[str, Any]], kind: str, year: int) -> dict[str, Any] | None:
    return next((deepcopy(row) for row in rows if row["field_kind"] == kind and row["year"] == year), None)


def get_period_sources(
    workspace_root: Path,
    case_id: str,
    current_year: int,
    rule_ids: tuple[str, ...] = ("R1",),
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    case = get_case(workspace_root, case_id)
    if case is None:
        raise KeyError(case_id)
    if current_year not in case["available_years"]:
        raise KeyError(current_year)
    rows = get_financial_rows(workspace_root, case_id)
    previous_year = current_year - 1
    prior_year = current_year - 2
    requested: list[tuple[str, str, str, int]] = []
    if "R1" in rule_ids:
        requested.extend(
            [
                ("revenue_current", "本年营业收入", "revenue", current_year),
                ("revenue_previous", "上年营业收入", "revenue", previous_year),
                ("ar_current", "本年应收账款", "accounts_receivable", current_year),
                ("ar_previous", "上年应收账款", "accounts_receivable", previous_year),
            ]
        )
        if _select(rows, "revenue", prior_year) and _select(rows, "accounts_receivable", prior_year):
            requested.extend(
                [
                    ("revenue_prior", "前两年营业收入", "revenue", prior_year),
                    ("ar_prior", "前两年应收账款", "accounts_receivable", prior_year),
                ]
            )
        # 账面余额是 R1 增长比较的唯一主口径；准备与净额只作为解释和勾稽证据，
        # 不得静默替代主口径。某一公开年报未登记增强字段时，基础 R1 仍可运行。
        optional_r1_fields = (
            ("ar_allowance_current", "本年应收账款坏账准备", "accounts_receivable_allowance", current_year),
            ("ar_allowance_previous", "上年应收账款坏账准备", "accounts_receivable_allowance", previous_year),
            ("ar_net_current", "本年应收账款净额", "accounts_receivable_net", current_year),
            ("ar_net_previous", "上年应收账款净额", "accounts_receivable_net", previous_year),
        )
        requested.extend(item for item in optional_r1_fields if _select(rows, item[2], item[3]))
    if "R2" in rule_ids:
        requested.extend(
            [
                ("revenue_current", "本年营业收入", "revenue", current_year),
                ("revenue_previous", "上年营业收入", "revenue", previous_year),
                ("operating_cash_flow_current", "本年经营活动现金流量净额", "operating_cash_flow", current_year),
                ("operating_cash_flow_previous", "上年经营活动现金流量净额", "operating_cash_flow", previous_year),
            ]
        )
        if _select(rows, "net_profit", current_year):
            requested.append(("net_profit_current", "本年净利润（R2增强项）", "net_profit", current_year))
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field_id, label, kind, year in requested:
        if field_id in seen:
            continue
        source = _select(rows, kind, year)
        if source is None:
            if kind in {
                "accounts_receivable_allowance",
                "accounts_receivable_net",
                "operating_cash_flow",
                "net_profit",
            }:
                continue
            raise KeyError(f"{kind}/{year}")
        source.update({"field_id": field_id, "field_label": label})
        sources.append(source)
        seen.add(field_id)
    context = {
        "case_id": case_id,
        "company_name": case["company_name"],
        "company_alias": case.get("company_alias", ""),
        "ticker": case.get("ticker", ""),
        "current_year": current_year,
        "previous_year": previous_year,
        "prior_year": prior_year if any(row["field_id"].endswith("_prior") for row in sources) else None,
        "t0": case["t0"],
        "currency": case["currency"],
        "amount_unit": case["amount_unit"],
        "statement_scope": case["statement_scope"],
        "sample_type": case["sample_type"],
        "model_transfer_allowed": case["model_transfer_allowed"],
        "source_snapshot_id": case["source_snapshot_id"],
        "source_review_status": case["source_review_status"],
        "three_year_r1_ready": case["three_year_r1_ready"],
        "case_evidence_count": len(case.get("structured_evidence", [])),
        "case_material_gaps": deepcopy(case.get("material_gaps", [])),
    }
    return context, sources


def registered_page_metadata(
    workspace_root: Path, case_id: str, document_id: str, pdf_page: int
) -> dict[str, Any]:
    rows = get_financial_rows(workspace_root, case_id)
    matched = [row for row in rows if row.get("document_id") == document_id and row.get("pdf_page") == pdf_page]
    print_pages = {row.get("print_page") for row in matched if row.get("print_page")}
    return {
        "print_page": next(iter(print_pages)) if len(print_pages) == 1 else None,
        "linked_field_evidence_ids": [row["evidence_id"] for row in matched],
    }


def _placeholder_pdf(year: int) -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 96), "AuditTrace synthetic template", fontsize=18)
    page.insert_text((72, 130), f"Synthetic annual-report placeholder for {year}.", fontsize=11)
    page.insert_text((72, 154), "Replace with an authorized public or de-identified PDF before formal use.", fontsize=9)
    content = document.tobytes(garbage=4, deflate=True)
    document.close()
    return content


def build_case_template_zip() -> bytes:
    """生成可直接导入的三年合成模板；其模型传输许可默认关闭。"""
    pdfs = {year: _placeholder_pdf(year) for year in (2022, 2023, 2024)}
    documents = []
    for year, content in pdfs.items():
        documents.append(
            {
                "document_id": f"SYNTH-AR-{year}",
                "source_file": f"documents/synthetic_annual_report_{year}.pdf",
                "document_type": "synthetic_annual_report",
                "report_year": year,
                "disclosure_date": f"{year + 1}-04-30",
                "source_url": "",
                "sha256": _sha256_bytes(content),
            }
        )
    manifest = {
        "schema_version": CASE_SCHEMA_VERSION,
        "ai_generated_content_notice": AI_GENERATED_CONTENT_NOTICE,
        "template_version": TEMPLATE_VERSION,
        "case_id": "SYNTH_DEMO_T0",
        "company_name": "合成演示企业（仅用于系统验收）",
        "company_alias": "合成案例",
        "ticker": "",
        "t0": "2025-04-30",
        "currency": "CNY",
        "amount_unit": "元",
        "statement_scope": "合并",
        "sample_type": "synthetic",
        "model_transfer_allowed": False,
        "retention_expires_at": "2026-12-31",
        "documents": documents,
    }
    financial = io.StringIO()
    writer = csv.writer(financial, lineterminator="\n")
    writer.writerow(
        [
            "case_id",
            "evidence_id",
            "field_kind",
            "year",
            "value",
            "unit",
            "statement_scope",
            "field_basis",
            "document_id",
            "pdf_page",
            "print_page",
            "locator",
        ]
    )
    synthetic_values = {
        2024: {"revenue": 125000000, "accounts_receivable": 41000000, "operating_cash_flow": 8500000, "net_profit": 9300000},
        2023: {"revenue": 110000000, "accounts_receivable": 30000000, "operating_cash_flow": 7800000, "net_profit": 8100000},
        2022: {"revenue": 100000000, "accounts_receivable": 25000000, "operating_cash_flow": 7200000, "net_profit": 7500000},
    }
    for year, fields in synthetic_values.items():
        for kind, value in fields.items():
            writer.writerow(
                [
                    "SYNTH_DEMO_T0",
                    f"SYNTH_DEMO_T0_{FIELD_PREFIX[kind]}_{year}",
                    kind,
                    year,
                    value,
                    "元",
                    "合并",
                    "net" if kind == "accounts_receivable" else "reported",
                    f"SYNTH-AR-{year}",
                    1,
                    1,
                    "合成模板 / 字段登记表（不是 PDF 自动取数）",
                ]
            )
    readme = """审迹智链标准案例包模板\n\n本包为合成验收样例，不是第二个正式案例，也不包含实验结论。\n导入器只读取 financial_fields 中已登记并可回查的字段；不会从任意 PDF 自动取数。\n正式使用前应更换为合法公开或已授权脱敏资料、更新哈希，并由会计专业人员复核口径。\n"""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("case_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("financial_fields.csv", financial.getvalue().encode("utf-8-sig"))
        archive.writestr("aging.csv", "customer_id,aging_bucket,amount,as_of_date,evidence_note\n")
        archive.writestr("subsequent_receipts.csv", "customer_id,receipt_date,amount,reference,evidence_note\n")
        archive.writestr("contract_terms.csv", "contract_id,customer_id,credit_days,settlement_terms,acceptance_terms,evidence_note\n")
        archive.writestr("deidentification_log.csv", "field_or_file,action,reviewer,status,note\n")
        archive.writestr("README_填写说明.txt", readme.encode("utf-8-sig"))
        for year, content in pdfs.items():
            archive.writestr(f"documents/synthetic_annual_report_{year}.pdf", content)
    return output.getvalue()
