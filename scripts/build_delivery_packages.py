"""用显式白名单生成三类交付包，并在落盘前递归扫描。"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DELIVERY_DIR = ROOT / "交付包"
OFFICE_DIR = ROOT / "outputs" / "2026-07-28-v4-closure"

PROPOSAL_DOCX = ROOT / "02_最终确定方案" / "05_审迹智链_项目方案书_V3_全面复盘修订版.docx"
PROPOSAL_PDF = ROOT / "02_最终确定方案" / "05_审迹智链_项目方案书_V3.3_审计计划单场景与AI主链闭环版.pdf"
DETAILED_DOCX = ROOT / "02_最终确定方案" / "05_审迹智链_详细项目计划书_V2.4_资料入口指标库与快速MVP补充版.docx"
DIVISION_DOCX = ROOT / "02_最终确定方案" / "01_审迹智链_四人团队职责分工书_V3_对齐最终计划书.docx"
WEEK3_DOCX = ROOT / "05_第三周任务与成果" / "08_审迹智链_第三周滚动任务分工_2026-07-25至07-31.docx"
CLOSURE_DOCX = ROOT / "12_审迹智链_闭环整改实施与验收记录_2026-07-28.docx"
HUMAN_GATE_DOCX = ROOT / "13_审迹智链_0.7.1人工门槛待签与自动指标记录_2026-07-29.docx"
CASE_GUIDE_DOCX = ROOT / "02_最终确定方案" / "06_审迹智链_标准案例包填写与合规说明_V1.docx"
CASE_XLSX = OFFICE_DIR / "审迹智链_标准案例字段与合规模板_V1.xlsx"
CONTROLLED_EVAL_XLSX = (
    ROOT
    / "outputs"
    / "2026-07-29-controlled-evaluation"
    / "审迹智链_B0-B3受控评估合同与原始评分账本_V2.xlsx"
)
SECOND_CASE_REVIEW_DOCX = (
    ROOT
    / "02_最终确定方案"
    / "07_杰克科技第二公开案例_2026-07-28"
    / "杰克科技第二案例_双人独立复核与合法样例确认表_V2.1_待真人签字版.docx"
)
CASE_ZIP = OFFICE_DIR / "审迹智链_标准案例包_V1.zip"

TEAM_ZIP = DELIVERY_DIR / "01_队员Word_Excel材料包_2026-08-09.zip"
TEACHER_ZIP = DELIVERY_DIR / "02_老师方案材料包_2026-08-09.zip"
CLEAN_ZIP = DELIVERY_DIR / "03_审迹智链0.7.1_无密钥清洁运行包_2026-08-09.zip"
JUDGE_ZIP = DELIVERY_DIR / "04_审迹智链_评委代码复现包_2026-09-01.zip"
REPORT = DELIVERY_DIR / "交付清单与扫描报告.txt"
VALIDATION_LOG = DELIVERY_DIR / "交付包构建与独立复验日志.txt"
AI_NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"

FORBIDDEN_SUFFIXES = {".md", ".log", ".pyc", ".pyo", ".ndjson", ".tmp"}
FORBIDDEN_PARTS = {".git", "__pycache__", ".pytest_cache", "runtime", "artifacts", "temp", "tmp"}
TEXT_SUFFIXES = {
    ".txt", ".json", ".csv", ".xml", ".rels", ".py", ".html", ".css", ".js", ".bat", ".ini", ".yaml", ".yml",
}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(
        r"(?im)^[ \t]*(?:DEEPSEEK|OPENAI|ANTHROPIC|GEMINI|GOOGLE)_API_KEY"
        r"[ \t]*=[ \t]*[^ \t\r\n#][^ \t\r\n]*"
    ),
    re.compile(r"(?i)\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{25,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"),
)
PERSONAL_MARKERS = (
    "C:\\Users\\",
    "C:/Users/",
    "file:///C:/Users/",
    "D:\\wx qq dd",
    "wxid_",
    ".codex/attachments",
    "张宏博",
)


@dataclass(frozen=True)
class ScanResult:
    file_count: int
    nested_file_count: int
    total_bytes: int
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    summary: str
    detail: str


def _iter_asset_files() -> list[tuple[str, Path]]:
    base = ROOT / "assets" / "official-v4"
    return [(path.relative_to(ROOT).as_posix(), path) for path in sorted(base.rglob("*")) if path.is_file()]


def _iter_python_files(base: Path) -> list[tuple[str, Path]]:
    return [(path.relative_to(ROOT).as_posix(), path) for path in sorted(base.glob("*.py"))]


def _office_sources() -> list[tuple[str, Path]]:
    return [
        ("01_项目方案书_V3.3.docx", PROPOSAL_DOCX),
        ("02_详细项目计划书_V2.4.6.docx", DETAILED_DOCX),
        ("03_四人职责分工书_V3.5.docx", DIVISION_DOCX),
        ("04_第三周滚动任务分工_2026-07-25至07-31.docx", WEEK3_DOCX),
        ("05_闭环整改实施与验收记录.docx", CLOSURE_DOCX),
        ("06_标准案例包填写与合规说明_V1.docx", CASE_GUIDE_DOCX),
        ("07_标准案例字段与合规模板_V1.xlsx", CASE_XLSX),
        ("08_人工门槛待签与自动指标记录.docx", HUMAN_GATE_DOCX),
        ("09_B0-B3受控评估合同与原始评分账本_V2.xlsx", CONTROLLED_EVAL_XLSX),
        ("10_杰克科技第二案例_双人独立复核与合法样例确认表_V2.1_待真人签字版.docx", SECOND_CASE_REVIEW_DOCX),
    ]


def _teacher_sources() -> list[tuple[str, Path]]:
    return [
        ("01_项目方案书_V3.3.docx", PROPOSAL_DOCX),
        ("02_项目方案书_V3.3_提交版.pdf", PROPOSAL_PDF),
        ("03_详细项目计划书_V2.4.6.docx", DETAILED_DOCX),
        ("04_四人职责分工书_V3.5.docx", DIVISION_DOCX),
        ("05_闭环整改实施与验收记录.docx", CLOSURE_DOCX),
        ("06_标准案例包填写与合规说明_V1.docx", CASE_GUIDE_DOCX),
        ("07_人工门槛待签与自动指标记录.docx", HUMAN_GATE_DOCX),
        ("08_B0-B3受控评估合同与原始评分账本_V2.xlsx", CONTROLLED_EVAL_XLSX),
        ("09_杰克科技第二案例_双人独立复核与合法样例确认表_V2.1_待真人签字版.docx", SECOND_CASE_REVIEW_DOCX),
    ]


PACKAGE_DATA_FILES = (
    # 这些是只读的仓库内数据，不是运行态产物：清洁包与评委包的测试会直接读它们。
    # 漏一项就会让包内测试数与源码仓库不一致，所以必须和源码一起进包。
    "backend/audit_procedure_map.json",
    "backend/knowledge_sources.manifest.json",
    "backend/cache_seed.materialized.json",
)


def _release_record_sources() -> list[tuple[str, Path]]:
    """发布证据快照：随包只带机器可读记录，README.md 属交付禁止后缀因此排除。

    backend/runtime/ 是可写运行态（sqlite、额度台账），明确不进任何交付包。
    """

    records = ROOT / "backend" / "release_records"
    return [
        (path.relative_to(ROOT).as_posix(), path)
        for path in sorted(records.rglob("*"))
        if path.is_file() and path.suffix in {".json", ".jsonl"}
    ]


def _clean_sources() -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = [
        ("index.html", ROOT / "index.html"),
        (".env.example", ROOT / ".env.example"),
        ("PROJECT_STATUS.json", ROOT / "PROJECT_STATUS.json"),
        ("PROJECT_AUTHORIZATION.json", ROOT / "PROJECT_AUTHORIZATION.json"),
        ("pytest.ini", ROOT / "pytest.ini"),
        ("render.yaml", ROOT / "render.yaml"),
        ("启动审迹智链.bat", ROOT / "启动审迹智链.bat"),
        ("backend/__init__.py", ROOT / "backend" / "__init__.py"),
        ("backend/requirements.txt", ROOT / "backend" / "requirements.txt"),
        ("backend/requirements-lock.txt", ROOT / "backend" / "requirements-lock.txt"),
        ("backend/cache_seed.example.json", ROOT / "backend" / "cache_seed.example.json"),
        ("backend/cache_seed.lock.json", ROOT / "backend" / "cache_seed.lock.json"),
        ("supabase/schema.sql", ROOT / "supabase" / "schema.sql"),
        ("模板/审迹智链_标准案例包_V1.zip", CASE_ZIP),
        ("模板/审迹智链_标准案例包填写与合规说明_V1.docx", CASE_GUIDE_DOCX),
    ]
    items.extend((name, ROOT / name) for name in PACKAGE_DATA_FILES)
    items.extend(_release_record_sources())
    items.extend(_iter_asset_files())
    items.extend(_iter_python_files(ROOT / "backend" / "app"))
    # 旧官网兼容入口与交付包构建检查只属于源码仓库，清洁运行包不携带其依赖。
    repository_only_tests = {
        "test_forensic_editorial_route.py",
        "test_delivery_package_build.py",
        "test_jack_case_package.py",
    }
    items.extend(
        item
        for item in _iter_python_files(ROOT / "backend" / "tests")
        if Path(item[0]).name not in repository_only_tests
    )
    for report in sorted(ROOT.glob("标准股份*.pdf")):
        # 内置案例登记的是根目录相对路径；打包时必须保持同一位置，否则哈希与RAG都会失效。
        items.append((report.name, report))
    return items


def _judge_sources() -> list[tuple[str, Path]]:
    """评委代码包：可复现的当前代码 + 完整离线测试，但不含年报全文。

    四份公开年报只在真人确认全文再分发依据后才进内部教师包；评委包改带
    官方来源 URL 与哈希台账（PROJECT_STATUS.json 的
    standard_annual_report_sources 已是该台账）。缺关键新增文件时直接失败，
    不能静默产出一个"看起来完整"的残缺包。Markdown 属交付禁止后缀，
    因此测试清单以随包生成的纯文本成员提供。
    """

    report_names = {report.name for report in sorted(ROOT.glob("标准股份*.pdf"))}
    items = [item for item in _clean_sources() if Path(item[0]).name not in report_names]

    required = [
        "requirements.txt",
        "requirements-dev.txt",
        "conftest.py",
        "backend/competition_demo_cases.json",
        "backend/release_records/current_release.json",
        "scripts/check_chinese_comments.py",
        "scripts/test_inventory.py",
        # B2 契约测试会 import 这个模块；漏打包会让评委侧整个收集阶段失败。
        "scripts/run_controlled_b1_b3_prescore.py",
    ]
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        raise RuntimeError(f"评委包缺少必需文件，先修复再打包：{missing}")
    if not (ROOT / "docs" / "TEST_INVENTORY.md").is_file():
        raise RuntimeError("评委包缺少测试清单来源，先运行 scripts/test_inventory.py。")
    if any(Path(name).name in report_names for name, _path in items):
        raise RuntimeError("评委包仍含年报全文，违反未确认再分发边界。")

    items.extend(
        (name, ROOT / name)
        for name in required
        if name not in {existing for existing, _path in items}
    )
    return items


JUDGE_README = """审迹智链 AuditTrace 评委代码复现包

正式范围：审计计划阶段—销售与收款循环。
本包用途：从零安装依赖、启动服务、复算完整离线测试；不含四份公开年报全文。
运行要求：Python 3.10 或更高版本，Windows、macOS、Linux 同一条命令。
安装：python -m pip install -r requirements.txt
启动：python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
访问：http://127.0.0.1:8000
测试（离线，无需密钥）：python -m pytest -q
预期结果：以 PROJECT_STATUS.json 的 tests.judge_package.latest_result 登记的**当次隔离实测**为准。
截至 2026-09-02，该口径为 321 passed、19 failed、1 skipped，本包处于 remediation_required
状态、暂不可作为验收依据。19 项失败的具体成因尚未逐项测量确认（怀疑与按边界不分发的
四份年报全文有关，但未经 scripts/diagnose_judge_package.py 逐项证实前不作为结论）。
整改完成后此段将回填为实测的 <N> passed、<M> skipped、0 failed，并逐项列出跳过理由。
源码仓库口径另记为 347 passed。
唯一固定 skip 为 test_superseded_captain_signoff_remains_traceable（队长签字原件属团队内部
outputs/ 证据，不随包分发）；两套数字分开登记。
测试清单与联网项边界：见随包“测试清单.txt”。
依赖锁定复现：python -m pip install -r backend/requirements-lock.txt
验收脚本：python scripts/check_chinese_comments.py；python scripts/test_inventory.py
模型 Key：可选，只写入本机 .env；本包只含 .env.example 空值模板。
年报边界：四份公开年报全文未随包分发。来源 URL、下载日期与 SHA-256 见
PROJECT_STATUS.json 的 standard_annual_report_sources。缺少年报全文时，
标准案例的来源哈希复验与 RAG 检索会如实返回来源不完整，不会伪装成功；
需要复现这两项时由真人确认全文再分发依据后另发。
真实性边界：系统输出待核查线索和 AI 草稿，不认定舞弊、重大错报，不出具审计意见或投资建议。
AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。
"""


def _judge_generated() -> dict[str, str]:
    """评委包的随包生成成员：跨平台说明与纯文本测试清单。"""

    inventory = (ROOT / "docs" / "TEST_INVENTORY.md").read_text(encoding="utf-8")
    header = (
        "审迹智链测试清单（与源码仓库 docs/TEST_INVENTORY.md 同一内容，改为纯文本以符合交付后缀白名单）\n\n"
    )
    return {
        "README_评委复现说明.txt": JUDGE_README,
        "测试清单.txt": header + inventory,
    }


RUN_README = """审迹智链 AuditTrace 0.7.1 清洁运行包

正式范围：审计计划阶段—销售与收款循环。
运行要求：Windows 下使用 Python 3.10 或更高版本；双击“启动审迹智链.bat”后首次运行会创建本地虚拟环境并按 requirements-lock.txt 安装依赖。
访问地址：http://127.0.0.1:8000
模型 Key：可选。不开启模型时仍可执行“仅计算预检”，页面会明确显示运行不完整；不要把真实 Key 发给队员或老师。
标准案例：网页可下载模板；“模板”目录也提供同一合成案例包。新公司需先填写字段、来源页和真实哈希，系统不承诺任意 PDF 自动取数。
外发边界：本包为保留标准案例 RAG 与来源复验能力而包含四份公开年报全文；在真人确认全文再分发边界前，仅限团队内部技术复验，禁止外发。队员 Word/Excel 包和老师方案材料包不含年报全文。
源码仓库最近复验：177 passed、1 warning；本包独立复验：171 passed、1 warning。两套测试口径分开登记。
测试命令：backend\\.venv\\Scripts\\python.exe -m pytest -q
预期结果：0 failed；具体通过项以包内当前测试实际输出为准。打包脚本已在独立临时目录执行同一测试及RAG/R1烟测。
AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。
真实性边界：系统输出待核查线索和 AI 草稿，不认定舞弊、重大错报，不出具审计意见或投资建议。
人工门槛：R1专业签字、第二公开案例冻结、合法样例确认、真人复核、B0—B3评分。
"""


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16-le", "utf-16-be"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def _path_blockers(name: str) -> list[str]:
    path = PurePosixPath(name)
    lowered_parts = {part.lower() for part in path.parts}
    blockers: list[str] = []
    normalized = name.replace("\\", "/")
    if "\\" in name:
        blockers.append(f"压缩包内使用反斜杠路径：{name}")
    if name.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", name):
        blockers.append(f"压缩包内绝对路径：{name}")
    if ".." in PurePosixPath(normalized).parts:
        blockers.append(f"压缩包内路径穿越：{name}")
    if any(part in FORBIDDEN_PARTS for part in lowered_parts):
        blockers.append(f"禁止目录：{name}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        blockers.append(f"禁止后缀：{name}")
    if path.name.lower() == ".env" or path.name.startswith("~$"):
        blockers.append(f"禁止文件：{name}")
    if "09_官网" in name or "旧网站" in name:
        blockers.append(f"旧网站文件：{name}")
    return blockers


def _zip_info_blockers(info: zipfile.ZipInfo, display_name: str) -> list[str]:
    blockers: list[str] = []
    if info.flag_bits & 0x1:
        blockers.append(f"加密压缩成员：{display_name}")
    if info.file_size > 128 * 1024 * 1024:
        blockers.append(f"单文件解压体积过大：{display_name}")
    if info.compress_size and info.file_size > 1024 * 1024:
        ratio = info.file_size / info.compress_size
        if ratio > 1000:
            blockers.append(f"异常压缩率：{display_name} -> {ratio:.1f}x")
    return blockers


def _content_blockers(name: str, content: bytes) -> list[str]:
    suffix = PurePosixPath(name).suffix.lower()
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-4096:]:
            return [f"PDF结构标记异常：{name}"]
        return []
    text_candidate = suffix in TEXT_SUFFIXES or PurePosixPath(name).name.lower() == ".env.example"
    if not text_candidate or len(content) > 6 * 1024 * 1024:
        return []
    text = _decode_text(content)
    blockers: list[str] = []
    if suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError:
            blockers.append(f"JSON无法解析：{name}")
    for marker in PERSONAL_MARKERS:
        if marker in text:
            blockers.append(f"本机/个人标记：{name} -> {marker}")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            blockers.append(f"疑似密钥：{name}")
    return blockers


def _scan_zip_bytes(content: bytes, prefix: str, depth: int = 0) -> tuple[int, list[str]]:
    if depth > 5:
        return 0, [f"嵌套压缩层级过深：{prefix}"]
    nested_count = 0
    blockers: list[str] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        seen: set[str] = set()
        for info in archive.infolist():
            if info.is_dir():
                continue
            nested_count += 1
            nested_name = f"{prefix}!/{info.filename}"
            normalized_name = info.filename.casefold()
            if normalized_name in seen:
                blockers.append(f"重复压缩成员：{nested_name}")
            seen.add(normalized_name)
            blockers.extend(_path_blockers(info.filename))
            blockers.extend(_zip_info_blockers(info, nested_name))
            data = archive.read(info)
            blockers.extend(_content_blockers(nested_name, data))
            if PurePosixPath(info.filename).suffix.lower() in {".zip", ".docx", ".xlsx"}:
                child_count, child_blockers = _scan_zip_bytes(data, nested_name, depth + 1)
                nested_count += child_count
                blockers.extend(child_blockers)
    return nested_count, blockers


def scan_archive(path: Path) -> ScanResult:
    blockers: list[str] = []
    total_bytes = 0
    file_count = 0
    nested_count = 0
    with zipfile.ZipFile(path) as archive:
        seen: set[str] = set()
        for info in archive.infolist():
            if info.is_dir():
                continue
            file_count += 1
            total_bytes += info.file_size
            normalized_name = info.filename.casefold()
            if normalized_name in seen:
                blockers.append(f"重复压缩成员：{info.filename}")
            seen.add(normalized_name)
            blockers.extend(_path_blockers(info.filename))
            blockers.extend(_zip_info_blockers(info, info.filename))
            data = archive.read(info)
            blockers.extend(_content_blockers(info.filename, data))
            if PurePosixPath(info.filename).suffix.lower() in {".zip", ".docx", ".xlsx"}:
                child_count, child_blockers = _scan_zip_bytes(data, info.filename)
                nested_count += child_count
                blockers.extend(child_blockers)
        corrupt_member = archive.testzip()
        if corrupt_member is not None:
            blockers.append(f"CRC校验失败：{corrupt_member}")
    return ScanResult(file_count, nested_count, total_bytes, tuple(sorted(set(blockers))))


def _verify_clean_archive(path: Path) -> ValidationResult:
    """在隔离目录复现随包测试与关键API，避免“工作区通过、交付包失效”。"""
    with tempfile.TemporaryDirectory(prefix="audittrace-clean-verify-") as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(extracted)
        environment = os.environ.copy()
        # 清洁包验收不应产生真实模型费用，也不能依赖开发机密钥。
        for key in (
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ):
            environment.pop(key, None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=extracted,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if tests.returncode:
            raise RuntimeError("清洁包独立测试失败：\n" + tests.stdout[-6000:] + tests.stderr[-2000:])
        result_match = re.search(r"(?P<passed>\d+ passed)(?:, (?P<warnings>\d+ warnings?))?", tests.stdout)
        if result_match is None:
            raise RuntimeError("清洁包独立测试通过，但无法从 pytest 输出提取可登记的结果。")
        test_result = result_match.group("passed")
        if result_match.group("warnings"):
            test_result += f", {result_match.group('warnings')}"
        status_snapshot = json.loads((extracted / "PROJECT_STATUS.json").read_text(encoding="utf-8"))
        clean_package_status = status_snapshot["tests"]["clean_package"]
        if clean_package_status.get("status") != "passed":
            raise RuntimeError("PROJECT_STATUS.json 尚未把本轮清洁包登记为 passed。")
        if clean_package_status.get("latest_result") != test_result:
            raise RuntimeError(
                "清洁包实测与 PROJECT_STATUS.json 登记不一致："
                f"实测 {test_result}；登记 {clean_package_status.get('latest_result')!r}。"
            )
        environment["AUDITTRACE_CLEAN_TEST_RESULT"] = test_result
        smoke_script = """
import json
import os
from fastapi.testclient import TestClient
from backend.app.main import app

notice = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
expected_clean_test_result = os.environ["AUDITTRACE_CLEAN_TEST_RESULT"]
client = TestClient(app)
health_response = client.get("/api/health")
assert health_response.status_code == 200
health = health_response.json()
assert health["ai_generated_content_notice"] == notice
status_response = client.get("/api/status")
assert status_response.status_code == 200
status = status_response.json()
assert status["engine_version"] == "0.7.1"
assert status["formal_scope"] == "审计计划阶段—销售与收款循环"
assert status["ai_generated_content_notice"] == notice
# 公开演示模式的 /api/status 只透出白名单键，历史登记不外泄；因此以磁盘上的
# PROJECT_STATUS.json 为登记口径，HTTP 载荷带该键时再要求两者一致。
projected_tests = status.get("tests")
assert projected_tests is None or projected_tests["clean_package"]["status"] == "passed"
assert projected_tests is None or projected_tests["clean_package"]["latest_result"] == expected_clean_test_result
standard_case = next(item for item in status["cases"] if item["case_id"] == "STD_DEV_T0")
assert standard_case["model_transfer_allowed"] is True
assert client.get("/api/cases/template").status_code == 200
prepared = client.post("/api/rag/prepare")
assert prepared.status_code == 200, prepared.text
rag = prepared.json()
assert rag["status"] == "ready"
assert rag["chunk_count"] > 100
assert rag["ai_generated_content_notice"] == notice
retrieved_response = client.post(
    "/api/rag/retrieve",
    json={"question_id": "RAG-Q1", "t0": "2026-04-30", "rule_id": "R1", "top_k": 3},
)
assert retrieved_response.status_code == 200, retrieved_response.text
retrieved = retrieved_response.json()
assert retrieved["status"] == "hit"
assert retrieved["results"]
assert retrieved["ai_generated_content_notice"] == notice
run = client.post(
    "/api/runs",
    json={
        "case_id": "STD_DEV_T0",
        "current_year": 2023,
        "rule_ids": ["R1"],
        "run_mode": "calculation_only",
        "planned_materiality": 10000000,
    },
)
assert run.status_code == 200, run.text
body = run.json()
assert body["screening_status"] != "SOURCE_INCOMPLETE", body
assert not body["source_validation"]["issues"], body
assert body["run_completeness"] == "incomplete_calculation_only", body
assert body["ai_recommendation"] == "not_generated", body
assert body["ai_generated_content_notice"] == notice
print(json.dumps({
    "health": health["service_status"],
    "engine": status["engine_version"],
    "case_count": status["case_count"],
    "standard_model_transfer_allowed": standard_case["model_transfer_allowed"],
    "rag_status": rag["status"],
    "rag_chunk_count": rag["chunk_count"],
    "rag_retrieval_id": retrieved["retrieval_id"],
    "rag_result_count": len(retrieved["results"]),
    "run_id": body["run_id"],
    "screening_status": body["screening_status"],
    "run_completeness": body["run_completeness"],
    "ai_recommendation": body["ai_recommendation"],
}, ensure_ascii=False))
"""
        smoke = subprocess.run(
            [sys.executable, "-c", smoke_script],
            cwd=extracted,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if smoke.returncode:
            raise RuntimeError("清洁包关键API烟测失败：\n" + smoke.stdout[-3000:] + smoke.stderr[-3000:])
        pytest_lines = [line.strip() for line in tests.stdout.splitlines() if line.strip()]
        pytest_summary = pytest_lines[-1] if pytest_lines else "pytest完成但未返回摘要"
        smoke_lines = [line.strip() for line in smoke.stdout.splitlines() if line.strip()]
        smoke_summary = smoke_lines[-1] if smoke_lines else "{}"
        # 成功日志只保留摘要和结构化 smoke，避免把解释器告警中的本机路径写入交付记录。
        detail = "\n".join(
            [
                "[pytest]",
                pytest_summary,
                "warning=Starlette TestClient httpx compatibility deprecation warning",
                "",
                "[关键API、状态、RAG与R1 smoke]",
                smoke_summary,
            ]
        )
        return ValidationResult(
            summary=f"{pytest_summary}；状态/API/RAG/R1 smoke通过：{smoke_summary}",
            detail=detail,
        )


JUDGE_COMMENT_TARGET = 0.11
JUDGE_COMMENT_FLOOR = 0.10

# 随包公开边界烟测：只允许走前端真正会调的接口，并确认内部诊断面对非本机
# 调用保持关闭，避免“源码仓库通过、交付包泄露”这类口径分裂。
_JUDGE_SMOKE = """
import json
from fastapi.testclient import TestClient
from backend.app.main import app

notice = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
client = TestClient(app)
assert client.get("/api/health").json()["ai_generated_content_notice"] == notice
status = client.get("/api/status")
assert status.status_code == 200
text = json.dumps(status.json(), ensure_ascii=False)
for marker in ("outputs/", "artifacts/", ".zcode", "backend/runtime", "ai_prescore_mean"):
    assert marker not in text, marker
listing = client.get("/api/cases?summary=true").json()
assert listing["cases"], "评委包案例目录为空"
assert client.get("/api/internal/status").status_code == 403
print(json.dumps({"case_count": len(listing["cases"])}, ensure_ascii=False))
"""


def _verify_judge_archive(path: Path) -> ValidationResult:
    """在隔离目录复现评委包：确认无年报、离线测试全通过、注释门与公开边界。"""

    with tempfile.TemporaryDirectory(prefix="audittrace-judge-verify-") as temporary:
        extracted = Path(temporary)
        with zipfile.ZipFile(path) as archive:
            archive.extractall(extracted)
        if sorted(p.name for p in extracted.glob("标准股份*.pdf")):
            raise RuntimeError("评委包解包后仍含年报全文，违反未确认再分发边界。")
        environment = os.environ.copy()
        # 评委包必须能在完全没有密钥的环境复现，不能依赖开发机凭据。
        for key in (
            "DEEPSEEK_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
        ):
            environment.pop(key, None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        tests = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=extracted,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            check=False,
        )
        if tests.returncode:
            raise RuntimeError("评委包离线测试失败：\n" + tests.stdout[-6000:] + tests.stderr[-2000:])
        comments = subprocess.run(
            [sys.executable, "scripts/check_chinese_comments.py"],
            cwd=extracted,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if comments.returncode:
            raise RuntimeError("评委包中文注释门失败：\n" + comments.stdout[-2000:] + comments.stderr[-2000:])
        ratio_line = next((line.strip() for line in comments.stdout.splitlines() if line.startswith("TOTAL:")), "")
        ratio = re.search(r"=\s+(\d+(?:\.\d+)?)%", ratio_line)
        if ratio is None:
            raise RuntimeError(f"无法从注释检查输出解析占比：{ratio_line!r}")
        measured = float(ratio.group(1)) / 100.0
        if measured < JUDGE_COMMENT_FLOOR:
            raise RuntimeError(f"评委包中文注释占比 {ratio_line} 低于手册要求的 10%。")
        smoke = subprocess.run(
            [sys.executable, "-c", _JUDGE_SMOKE],
            cwd=extracted,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            check=False,
        )
        if smoke.returncode:
            raise RuntimeError("评委包公开边界烟测失败：\n" + smoke.stdout[-2000:] + smoke.stderr[-3000:])
        pytest_lines = [line.strip() for line in tests.stdout.splitlines() if line.strip()]
        pytest_summary = pytest_lines[-1] if pytest_lines else "pytest完成但未返回摘要"
        smoke_lines = [line.strip() for line in smoke.stdout.splitlines() if line.strip()]
        smoke_summary = smoke_lines[-1] if smoke_lines else "{}"
        target_note = "达到11%目标" if measured >= JUDGE_COMMENT_TARGET else "未达11%目标（手册10%门槛已过）"
        return ValidationResult(
            summary=(
                f"{pytest_summary}；中文注释 {ratio_line} {target_note}；"
                f"公开边界与无年报降级烟测通过：{smoke_summary}"
            ),
            detail="\n".join(
                [
                    "[评委包 pytest（无密钥、无年报）]",
                    pytest_summary,
                    "",
                    "[中文注释门]",
                    ratio_line,
                    target_note,
                    "",
                    "[公开边界与无年报降级 smoke]",
                    smoke_summary,
                ]
            ),
        )


def _build_zip(
    destination: Path,
    files: list[tuple[str, Path]],
    generated: dict[str, str] | None = None,
    validator: Callable[[Path], ValidationResult] | None = None,
) -> tuple[ScanResult, ValidationResult | None]:
    missing = [str(source) for _, source in files if not source.is_file()]
    if missing:
        raise FileNotFoundError("白名单源文件缺失：" + "；".join(missing))
    destination.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(prefix="audittrace-package-", suffix=".zip", dir=destination.parent, delete=False)
    temp_path = Path(handle.name)
    handle.close()
    try:
        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for archive_name, source in files:
                archive.write(source, archive_name)
            for archive_name, text in (generated or {}).items():
                archive.writestr(archive_name, text.encode("utf-8-sig"))
        result = scan_archive(temp_path)
        if result.blockers:
            raise RuntimeError("交付包扫描阻断：\n" + "\n".join(result.blockers))
        validation = validator(temp_path) if validator is not None else None
        os.replace(temp_path, destination)
        return result, validation
    finally:
        temp_path.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def _entry_manifest(path: Path) -> list[str]:
    lines: list[str] = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            content = archive.read(info)
            lines.append(
                f"{info.filename}\t{info.file_size}\t{hashlib.sha256(content).hexdigest().upper()}"
            )
    return lines


def _source_manifest(label: str, files: list[tuple[str, Path]]) -> list[str]:
    lines = [f"[{label} 白名单源文件]"]
    for archive_name, source in files:
        lines.append(
            f"{archive_name}\t{_relative(source)}\t{source.stat().st_size}\t{_sha256(source)}"
        )
    return lines


def _sanitize_local_paths(text: str) -> str:
    sanitized = text.replace(str(ROOT), "<WORKSPACE>")
    sanitized = sanitized.replace(str(Path.home()), "<USER_HOME>")
    sanitized = re.sub(r"(?i)[A-Z]:\\Users\\[^\\\r\n]+", "<USER_HOME>", sanitized)
    sanitized = re.sub(r"(?i)(?:\.\.\\)+Users\\[^\\\r\n]+", "<USER_HOME>", sanitized)
    return sanitized


def _write_failure_log(started_at: str, error: BaseException) -> None:
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    detail = _sanitize_local_paths(traceback.format_exc())
    error_text = _sanitize_local_paths(str(error))
    VALIDATION_LOG.write_text(
        "\n".join(
            [
                "审迹智链交付包构建与独立复验日志",
                f"开始时间：{started_at}",
                f"结束时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
                "最终状态：FAILED",
                f"错误：{type(error).__name__}: {error_text}",
                "",
                detail,
            ]
        ),
        encoding="utf-8-sig",
    )


def main() -> None:
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    team_sources = _office_sources()
    teacher_sources = _teacher_sources()
    clean_sources = _clean_sources()
    try:
        team_scan, _ = _build_zip(TEAM_ZIP, team_sources)
        teacher_scan, _ = _build_zip(TEACHER_ZIP, teacher_sources)
        clean_scan, clean_validation = _build_zip(
            CLEAN_ZIP,
            clean_sources,
            {"README_运行说明.txt": RUN_README},
            validator=_verify_clean_archive,
        )
    except Exception as error:
        _write_failure_log(started_at, error)
        raise

    # 三个既有包已经产出并留痕；评委包异常只如实追加登记，不把已通过的复验
    # 日志改写成 FAILED，否则一次评委包试跑会毁掉整轮交付记录。
    judge_sources: list[tuple[str, Path]] = []
    judge_scan: ScanResult | None = None
    judge_validation: ValidationResult | None = None
    judge_error: str | None = None
    try:
        judge_sources = _judge_sources()
        judge_scan, judge_validation = _build_zip(
            JUDGE_ZIP,
            judge_sources,
            _judge_generated(),
            validator=_verify_judge_archive,
        )
    except Exception as error:
        judge_detail = _sanitize_local_paths(str(error)).strip().splitlines()
        judge_error = f"{type(error).__name__}：{judge_detail[0] if judge_detail else '无明细'}"

    results: list[tuple[Path, ScanResult]] = [
        (TEAM_ZIP, team_scan),
        (TEACHER_ZIP, teacher_scan),
        (CLEAN_ZIP, clean_scan),
    ]
    if judge_scan is not None:
        results.append((JUDGE_ZIP, judge_scan))
    if clean_validation is None:
        raise RuntimeError("内部错误：清洁运行包未执行独立复验。")
    generated_date = datetime.now().astimezone().date().isoformat()
    package_count = len(results)
    judge_summary = (
        f"评委代码包独立复验：{judge_validation.summary}"
        if judge_validation is not None
        else f"评委代码包未完成：{judge_error}"
    )
    lines = [
        "审迹智链 0.7.1 交付清单与白名单扫描报告",
        f"生成日期：{generated_date}",
        f"扫描结论：{package_count} 个包均为 0 阻断项；递归检查了 DOCX、XLSX 与嵌套 ZIP。",
        "扫描范围：.env、Markdown、日志、缓存、临时文件、旧网站、路径穿越/重复成员、本机路径、个人标记和常见密钥/令牌形态。",
        "说明：.env.example 仅含空值模板；四份标准股份年报位于ZIP根目录；清洁运行包已独立解包完成pytest、状态/API、RAG准备与检索、2023年R1烟测。",
        "外发边界：清洁运行包含四份公开年报全文；在真人确认全文再分发边界前，仅限团队内部技术复验，禁止外发。队员包、老师包和评委包不含年报全文。",
        "评委包复现边界：完整离线测试、依赖安装与公开接口边界可复算；缺年报全文时标准案例来源哈希复验与RAG检索按设计返回来源不完整，不复现这两项即不得宣称全量复现。",
        f"独立复验：{clean_validation.summary}",
        judge_summary,
        "",
    ]
    for path, result in results:
        lines.extend(
            [
                f"文件：{path.name}",
                f"SHA-256：{_sha256(path)}",
                f"顶层文件数：{result.file_count}",
                f"递归容器文件数：{result.nested_file_count}",
                f"解压后字节数：{result.total_bytes}",
                "阻断项：0",
                "",
            ]
        )
    REPORT.write_text("\n".join(lines), encoding="utf-8-sig")
    log_lines = [
        "审迹智链交付包构建与独立复验日志",
        f"开始时间：{started_at}",
        f"结束时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "最终状态：PASSED",
        f"评委包状态：{'完成并通过独立复验' if judge_validation is not None else f'未完成（{judge_error}）'}",
        f"统一AI声明：{AI_NOTICE}",
        "外发边界：清洁运行包含四份公开年报全文，合法再分发真人确认前仅限团队内部技术复验，禁止外发；队员包、老师包和评委包不含年报全文。",
        "",
        *_source_manifest("队员包", team_sources),
        "",
        *_source_manifest("老师包", teacher_sources),
        "",
        *_source_manifest("清洁运行包", clean_sources),
        "",
    ]
    if judge_sources:
        log_lines.extend([*_source_manifest("评委代码包", judge_sources), ""])
    for package_path, result in results:
        log_lines.extend(
            [
                f"[{package_path.name}]",
                f"SHA-256={_sha256(package_path)}",
                f"top_level_files={result.file_count}",
                f"nested_files={result.nested_file_count}",
                f"uncompressed_bytes={result.total_bytes}",
                "blockers=0",
                "entry\tbytes\tsha256",
                *_entry_manifest(package_path),
                "",
            ]
        )
    log_lines.extend(["[清洁运行包独立复验明细]", clean_validation.detail, ""])
    if judge_validation is not None:
        log_lines.extend(["[评委代码包独立复验明细]", judge_validation.detail, ""])
    else:
        log_lines.extend(["[评委代码包独立复验明细]", f"未完成：{judge_error}", ""])
    VALIDATION_LOG.write_text("\n".join(log_lines), encoding="utf-8-sig")
    print(REPORT)
    print(VALIDATION_LOG)


if __name__ == "__main__":
    main()
