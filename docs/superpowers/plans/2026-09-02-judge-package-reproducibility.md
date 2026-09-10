# 评委复现包与可复现版本冻结 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让评委代码复现包能独立构建、解压后零失败、并在干净虚拟环境里可复算；同时把 34 个测试文件与复现所需配置真正提交进 Git，使"347 passed"成为评委从 GitHub 下载后可复现的数字。

**Architecture:** 测试按"离线基础集 / 年报全文依赖集 / 仓库专属集"三档分层，第二档用 pytest marker + 根 conftest 闸门在无年报时显式跳过；打包脚本改成按包独立构建并可只跑校验；校验器改为新建临时虚拟环境安装依赖后运行；文档数字一律从实测结果同步，未实测不得写入。

**Tech Stack:** Python 3 + FastAPI + pytest 8、zipfile 白名单打包、Playwright（真实浏览器验收）、Git archive（干净导出）。

---

## 计划前提：本轮实测事实（2026-09-02）

| 事实 | 证据位置 |
| --- | --- |
| 正常构建流程在队员包阶段就中止 | `交付包/交付包构建与独立复验日志.txt` 第 4–13 行：`最终状态：FAILED`，`FileNotFoundError: 白名单源文件缺失：<WORKSPACE>\12_审迹智链_闭环整改实施与验收记录_2026-07-28.docx；<WORKSPACE>\13_..._2026-07-29.docx`，栈顶 `scripts/build_delivery_packages.py:790` |
| `交付包/` 内不存在 `04_..._评委代码复现包_*.zip` | 目录实测只有 01/02/03 两批（2026-07-28、2026-08-09）与 `老师材料包.zip` |
| 交付清单是 2026-08-10 的旧口径 | `交付包/交付清单与扫描报告.txt:2` 与 `:7`（`171 passed`） |
| 评委包隔离实测 | 用户提供：`321 passed, 19 failed, 1 skipped`，共收 341 项 |
| 源码仓库实测 | `347 passed, 1 warning`，34 个测试文件，5 组顺序数字一致（日志 `tmp/battery-347.txt`，脚本结论"通过"、退出码 0） |
| 341 与 347 的差额来源 | `_clean_sources()` 排除 `test_forensic_editorial_route.py`、`test_delivery_package_build.py`、`test_jack_case_package.py`（`build_delivery_packages.py:181-190`） |
| 打包脚本无 CLI 参数 | 无 `argparse`；`main()` 从 786 行起硬排 队员包→老师包→清洁包→评委包 |
| 校验器复用当前解释器 | `_verify_judge_archive` 第 619/632/652 行都是 `sys.executable` |
| 包内 README 命令链不闭合 | `JUDGE_README:242` 让装 `requirements.txt`，但 `pytest` 只在 `requirements-dev.txt:4`（安装段的修复属 Task 5 Step 3）；原"预期 340 passed、1 skipped"已在写计划时改为指向实测登记并写明 remediation_required |
| Git 未跟踪本轮测试 | 本机 34 个测试文件，仓库只跟踪 6 个；`pytest.ini`、根 `requirements*.txt`、根 `conftest.py`、打包/清单脚本均未提交 |
| `340` 的来历：推算值被当成实测 | 评委包真实只在 346 基线下测过 `339 passed, 1 skipped`；升到 347 后未复测，按"收 341 项 − 1 skip = 340"**推算**并登记为实测。写计划时已先把 `PROJECT_STATUS.json`（`status=remediation_required` + `superseded_claim`）、`README_RUN.md:114`、`JUDGE_README` 三处改为如实登记 `321 passed, 19 failed, 1 skipped`；Phase 1 完成后按本计划 Step 7 回填真正的实测数字 |

**发布指针 `competition_release_ready` 保持 false，直到 Phase 4 真人门槛完成。**

**授权门禁：** Phase 2 的 `git add/commit`、Phase 1 Task 5 需要联网 pip、Phase 4 的模型调用与对外发送，都必须先取得用户明确同意（AGENTS.md §6）。

**执行顺序：** 正文按 Phase 1/2/3/4 编号编排，但实际按 **Phase 0 → Phase 1 → Phase 3 → Phase 2 → Phase 4** 执行：Phase 3 的三项代码改动（Task 9/10/11）必须先落地，否则 Git 冻结后又要再补一次提交，"从快照复算"的证据就不完整。

---

## Phase 0：先把上一轮两条未补跑的校验做完

### Task 0: 复验 JSON 结构与 .gitignore 否定规则

**Files:**
- 只读校验：`PROJECT_STATUS.json`、`.gitignore`

- [ ] **Step 1: 跑两条命令**

```bash
backend/.venv/Scripts/python.exe -c "import json;json.load(open('PROJECT_STATUS.json',encoding='utf-8'));print('JSON_OK')"
git check-ignore -v docs/TEST_INVENTORY.md scripts/test_inventory.py scripts/build_delivery_packages.py scripts/axe_inject.py scripts/browser_demo_final_acceptance.py
```

Run: 上两条
Expected: 第一条输出 `JSON_OK`；第二条**无任何输出且退出码 1**（表示这些路径都没被忽略）。若仍列出命中规则，说明 `.gitignore` 的 `!/docs/` + `/docs/*` + `!/docs/TEST_INVENTORY.md` 组合没生效，必须先修再继续 Phase 2。

- [ ] **Step 2: 把结果登记进状态文件**

在 `PROJECT_STATUS.json` 的 `tests.source_repository.note` 末尾追加"两项复验已执行（日期+命令+结果）"，并删掉上一轮写的"因 Bash 分类器临时不可用尚未补跑"。

---

## Phase 1（P0）：评委复现包修到可验收

### Task 1: 一次性取到 19 个失败的真实名单

不猜失败项，先测量。

**Files:**
- Create: `scripts/diagnose_judge_package.py`
- Output: `tmp/judge-failures-20260902.md`（诊断产物，不入库）

- [ ] **Step 1: 写诊断脚本**

```python
"""把评委包源码集物化到临时目录并按隔离环境跑一次，输出失败清单。

评委包 19 个失败必须先拿到真实名单，否则"该跳过的跳过"只能靠猜。
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bdp", ROOT / "scripts" / "build_delivery_packages.py")
bdp = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bdp)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="audittrace-judge-diag-") as temporary:
        stage = Path(temporary) / "package"
        stage.mkdir()
        for name, source in bdp._judge_sources():
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name, text in bdp._judge_generated().items():
            (stage / name).write_text(text, encoding="utf-8")
        environment = os.environ.copy()
        for key in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            environment.pop(key, None)
        process = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-rf", "-rs", "--no-header"],
            cwd=stage,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2400,
            check=False,
        )
        lines = [line.strip() for line in process.stdout.splitlines() if line.startswith(("FAILED ", "SKIPPED ", "ERROR "))]
        summary = [line.strip() for line in process.stdout.splitlines() if "passed" in line][-1:]
        print(f"摘要: {summary[0] if summary else '无'}")
        print(f"条目: {len(lines)}")
        for line in lines:
            print(line)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 运行并存档**

Run: `backend/.venv/Scripts/python.exe -u scripts/diagnose_judge_package.py > tmp/judge-failures-20260902.md 2>&1`
Expected: 文件里出现 19 行 `FAILED backend/tests/test_xxx.py::test_yyy`，摘要行与用户实测的 `321 passed / 19 failed / 1 skipped` 一致。**若数字不同，以本次实测为准并同步修正文档，不得沿用任一旧数字。**

- [ ] **Step 3: 按三档归类**

把这 19 项逐行写成表格存进 `tmp/judge-failures-20260902.md` 末尾，列为 `测试项 / 依赖的真实数据 / 归档档位`：

- `年报全文`：需要 `标准股份*.pdf` 或其派生 RAG 索引、来源哈希；
- `仓库专属`：需要 `outputs/`、旧官网文件、打包脚本自身的产物；
- `真缺陷`：既不依赖年报也不依赖仓库文件 —— **这一类必须修生产代码，不允许用 skip 掩盖**。

Expected: 19 项全部归档，且"真缺陷"类为空或已单独立项。

---

### Task 2: 三档测试分层与无年报跳过闸门

**Files:**
- Modify: `pytest.ini`（注册 marker）
- Modify: `conftest.py:1-31`（闸门）
- Test: `backend/tests/test_full_corpus_skip_gate.py`（新建）
- Modify: Task 1 归为"年报全文"的测试文件，逐项加 marker

- [ ] **Step 1: 写跳过闸门的失败测试**

```python
"""评委包不带年报时必须显式跳过，而不是失败，也不能静默漏跑。

闸门只认根 conftest 里的真实实现：测试把该 conftest 原样写进临时工程，
再跑一个带 marker 的样例用例，确保线上闸门与断言同源。
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "requires_full_corpus"


def _root_conftest() -> str:
    """取根 conftest 源码但剥掉 pytest_plugins 声明，避免嵌套会话二次加载插件。"""

    text = (ROOT / "conftest.py").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("pytest_plugins")) + "\n"


def _stage(pytester: pytest.Pytester, *, with_corpus: bool) -> None:
    (pytester.path / "conftest.py").write_text(_root_conftest(), encoding="utf-8")
    (pytester.path / "pytest.ini").write_text(
        f"[pytest]\nmarkers =\n    {MARKER}: 需要标准股份年报全文才可运行\n", encoding="utf-8"
    )
    (pytester.path / "test_sample.py").write_text(
        f"import pytest\n\n\n@pytest.mark.{MARKER}\ndef test_needs_pdf():\n    assert True\n", encoding="utf-8"
    )
    if with_corpus:
        (pytester.path / "标准股份：2023年年度报告.pdf").write_bytes(b"%PDF-1.4 fake")


def test_gate_skips_when_corpus_absent(pytester: pytest.Pytester) -> None:
    _stage(pytester, with_corpus=False)
    result = pytester.runpytest("-q", "-rs")
    result.assert_outcomes(passed=0, skipped=1, failed=0)
    assert any("缺少标准股份年报全文" in line for line in result.outlines), result.outlines


def test_gate_runs_when_corpus_present(pytester: pytest.Pytester) -> None:
    _stage(pytester, with_corpus=True)
    pytester.runpytest("-q").assert_outcomes(passed=1, skipped=0)


def test_repo_itself_never_skips_full_corpus() -> None:
    """源码仓库本机有年报，基线里不得出现 requires_full_corpus 跳过。"""
    assert any(ROOT.glob("标准股份*.pdf")), "本机年报缺失会使本项无法判定，先恢复本地资料再跑"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_full_corpus_skip_gate.py -q`
Expected: FAIL（当前根 `conftest.py` 没有闸门，缺全文时样例用例会 failed 而非 skipped）。

- [ ] **Step 3: 注册 marker**

`pytest.ini` 在 `addopts = -ra` 之后追加：

```ini
markers =
    requires_full_corpus: 需要标准股份年报全文（RAG 索引、来源哈希、标准案例路由）才可运行；评委包内按边界跳过
    repository_only: 只在源码仓库可运行，不随任何交付包分发
```

- [ ] **Step 4: 在根 conftest 实现闸门**

先把 `conftest.py` 顶部 import 段补齐并启用 `pytester`（Step 1 的契约测试要用它起嵌套会话；`pytest_plugins` 只允许写在 rootdir 这一层 conftest）：

```python
import os
import sys
import tempfile
from pathlib import Path

import pytest

pytest_plugins = "pytester"
```

随后在文件末尾追加闸门：

```python
FULL_CORPUS_MARKER = "requires_full_corpus"


def full_corpus_available() -> bool:
    """年报全文是否在本机可读：这是跳过闸门的唯一判据，不看配置也不看环境变量。"""
    return any(ROOT.glob("标准股份*.pdf"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """无年报时把依赖全文的用例改成 skip，并打印一条不静默的汇总。

    跳过理由必须写清"为什么跳、怎么补齐"，否则评委无法区分"边界内正常"
    与"环境坏了"；补齐方式固定为 scripts/prepare_full_corpus.py。
    """
    if full_corpus_available():
        return
    pending = [item for item in items if item.get_closest_marker(FULL_CORPUS_MARKER)]
    if not pending:
        return
    skip = pytest.mark.skip(
        reason="缺少标准股份年报全文（评委包按边界不分发全文）；运行 python scripts/prepare_full_corpus.py 下载并校验 SHA-256 后复算"
    )
    for item in pending:
        item.add_marker(skip)
    print(f"\n[full-corpus] 已跳过 {len(pending)} 项依赖年报全文的测试（评委包默认边界，非缺陷）。")
```

- [ ] **Step 5: 给 Task 1 的"年报全文"档测试加 marker**

逐个在函数（或整文件用 `pytestmark`）上加 `@pytest.mark.requires_full_corpus`。Expected: `grep -c "requires_full_corpus" backend/tests/*.py` 命中的用例数与 Task 1 表格"年报全文"行数一致。

- [ ] **Step 6: 复跑闸门测试**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_full_corpus_skip_gate.py -q`
Expected: `3 passed`。

- [ ] **Step 7: 复算评委包隔离结果**

Run: `backend/.venv/Scripts/python.exe -u scripts/diagnose_judge_package.py > tmp/judge-failures-after.md 2>&1`
Expected: `0 failed`，`passed + skipped = 341`，且 skipped 理由全部含"缺少标准股份年报全文"。此时 Phase 1 验收标准"解压后零失败、跳过项有明确原因"成立。

---

### Task 3: 年报全文准备脚本（下载 + SHA-256 校验）

**Files:**
- Create: `scripts/prepare_full_corpus.py`
- Test: `backend/tests/test_prepare_full_corpus.py`（新建）

- [ ] **Step 1: 写校验逻辑的失败测试**

```python
"""全文准备脚本必须能校验哈希并拒绝半残文件。

评委若要复算年报依赖档，唯一入口是这个脚本；它把"下载成功"与
"来源可信且哈希一致"分开判定，不允许只判存在。
"""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("pfc", ROOT / "scripts" / "prepare_full_corpus.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def test_expected_entries_come_from_status_ledger() -> None:
    entries = module.ledger()
    assert len(entries) == 4, "标准股份年报台账应为 4 条（PROJECT_STATUS.json standard_annual_report_sources）"
    for entry in entries:
        assert entry["announcement"].endswith(".pdf") or entry["announcement"].endswith(".PDF")
        assert len(entry["sha256"]) == 64


def test_verify_rejects_partial_file(tmp_path: Path) -> None:
    target = tmp_path / "标准股份：2024年年度报告.pdf"
    target.write_bytes(b"%PDF-1.4 truncated")
    digest = hashlib.sha256(b"%PDF-1.4 truncated").hexdigest()
    assert module.verify(target, digest) is True
    assert module.verify(target, "0" * 64) is False
    assert module.verify(tmp_path / "missing.pdf", digest) is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_prepare_full_corpus.py -q`
Expected: 收集阶段即 `FileNotFoundError`（脚本尚不存在）。

- [ ] **Step 3: 实现脚本**

```python
"""按台账下载标准股份年报全文并校验 SHA-256，供年报依赖档复算使用。

只读官方来源 URL（PROJECT_STATUS.json 的 standard_annual_report_sources
已是登记过核验状态的台账），哈希不符时删除临时文件并拒绝落盘为正式资料。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "PROJECT_STATUS.json"
TIMEOUT_SECONDS = 120


def ledger() -> list[dict[str, str]]:
    """从状态文件读取年报台账：标题、URL、期望哈希。"""
    data: dict[str, Any] = json.loads(STATUS.read_text(encoding="utf-8"))
    return [
        {
            "announcement": f"{entry['announcement_title']}.pdf",
            "url": entry["source_url"],
            "sha256": entry["file_sha256"],
        }
        for entry in data["standard_annual_report_sources"]
    ]


def verify(path: Path, expected_sha256: str) -> bool:
    """逐块哈希比对：文件缺失或哈希不符都判 False。"""
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().lower() == expected_sha256.lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="下载并校验标准股份年报全文（供年报依赖档测试复算）")
    parser.add_argument("--force", action="store_true", help="哈希已一致时仍重新下载")
    arguments = parser.parse_args(argv)
    failures: list[str] = []
    for entry in ledger():
        target = ROOT / entry["announcement"]
        if verify(target, entry["sha256"]) and not arguments.force:
            print(f"OK   {entry['announcement']}")
            continue
        temporary = target.with_suffix(".pdf.download")
        print(f"FETCH {entry['announcement']} <- {entry['url']}")
        try:
            with urllib.request.urlopen(entry["url"], timeout=TIMEOUT_SECONDS) as response:
                temporary.write_bytes(response.read())
        except Exception as error:  # noqa: BLE001 - 网络失败要逐条报出但不能中断其余文件
            temporary.unlink(missing_ok=True)
            failures.append(f"{entry['announcement']}: {type(error).__name__}: {error}")
            continue
        if not verify(temporary, entry["sha256"]):
            temporary.unlink(missing_ok=True)
            failures.append(f"{entry['announcement']}: SHA-256 与台账不符，已丢弃")
            continue
        temporary.replace(target)
        print(f"OK   {entry['announcement']}（哈希一致）")
    if failures:
        for line in failures:
            print(f"FAIL {line}", file=sys.stderr)
        print("至少一份年报未就绪；依赖档测试将继续按边界跳过，不得当作全量复现。", file=sys.stderr)
        return 1
    print("全部 4 份年报就绪，可运行 backend/.venv/Scripts/python.exe -m pytest -q 复算完整档位。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_prepare_full_corpus.py -q`
Expected: `2 passed`。

- [ ] **Step 5: 实跑一次（需用户同意联网）**

Run: `backend/.venv/Scripts/python.exe scripts/prepare_full_corpus.py`
Expected: 4 行 `OK`，退出码 0；退出码非 0 时把 FAIL 行原样记入状态文件，**不得**改台账哈希迁就结果。

---

### Task 4: 打包脚本支持按包独立构建与只校验

**Files:**
- Modify: `scripts/build_delivery_packages.py:784-903`
- Test: `backend/tests/test_delivery_package_build.py`（既有仓库专属测试文件，追加用例）

- [ ] **Step 1: 写 CLI 的失败测试**

```python
def test_judge_package_can_build_without_legacy_office_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """旧教师包的 DOCX 缺失，绝不能阻断评委包构建。"""
    result = subprocess.run(
        [sys.executable, "scripts/build_delivery_packages.py", "--package", "judge", "--skip-validate", "--output-dir", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert any(path.name.startswith("04_") and path.suffix == ".zip" for path in tmp_path.iterdir())


def test_help_lists_package_option() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_delivery_packages.py", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    assert result.returncode == 0
    for flag in ("--package", "--validate-only", "--skip-validate", "--output-dir"):
        assert flag in result.stdout, flag
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_delivery_package_build.py -q -k "judge_package_can_build_without_legacy or help_lists"`
Expected: 两项 FAIL（当前无 argparse，`--help` 会被 Python 当成未知参数报错，构建仍走全量并因缺 DOCX 抛 `FileNotFoundError`）。

- [ ] **Step 3: 重构入口**

`main()` 改为按选择逐项构建，每包独立捕获缺件：

```python
PACKAGE_BUILDERS = {
    "team": lambda: ("01_队员", TEAM_ZIP, _office_sources, None, None),
    "teacher": lambda: ("02_老师", TEACHER_ZIP, _teacher_sources, None, None),
    "clean": lambda: ("03_清洁", CLEAN_ZIP, _clean_sources, RUN_README, _verify_clean_archive),
    "judge": lambda: ("04_评委", JUDGE_ZIP, _judge_sources, None, _verify_judge_archive),
}


def _build_one(kind: str, output_dir: Path, *, skip_validate: bool) -> dict[str, str]:
    """单个包的失败只影响该包的记录：旧教师材料缺失不得连坐评委包。"""
    label, default_path, sources_fn, readme_fn, validator_fn = PACKAGE_BUILDERS[kind]()
    target = output_dir / default_path.name
    try:
        generated = {"README_运行说明.txt": readme_fn()} if readme_fn else None
        if kind == "judge":
            generated = _judge_generated()
        scan, validation = _build_zip(
            target, sources_fn(), generated, validator=None if skip_validate else validator_fn
        )
    except FileNotFoundError as error:
        return {"包": label, "状态": "未构建（白名单源文件缺失）", "明细": str(error)}
    return {
        "包": label,
        "文件": target.name,
        "SHA-256": _sha256(target),
        "状态": "已构建",
        "复验": validation.summary if validation else "按参数跳过",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="构建审迹智链交付包（可按包独立构建，可只跑复验）")
    parser.add_argument("--package", choices=(*PACKAGE_BUILDERS, "all"), default="all")
    parser.add_argument("--validate-only", action="store_true", help="只解包复验已有 ZIP，不重新构建")
    parser.add_argument("--skip-validate", action="store_true", help="只构建不复验（仅用于本地诊断）")
    parser.add_argument("--output-dir", type=Path, default=DELIVERY_DIR)
    arguments = parser.parse_args(argv)
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    kinds = tuple(PACKAGE_BUILDERS) if arguments.package == "all" else (arguments.package,)
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    if arguments.validate_only:
        records = [_validate_only(kind, arguments.output_dir) for kind in kinds]
    else:
        records = [_build_one(kind, arguments.output_dir, skip_validate=arguments.skip_validate) for kind in kinds]
    _write_records(started_at, records)
    return 0 if all(record["状态"] in {"已构建", "已复验"} for record in records) else 1
```

- [ ] **Step 4: 加 `_validate_only` 与 `_write_records`**

`_validate_only` 直接对已存在的 ZIP 调 `_verify_judge_archive` / `_verify_clean_archive` 并返回 `{"状态": "已复验", ...}`。`_write_records` 写 `交付清单与扫描报告.txt` 时**必须逐包写实际状态**，未构建的包写"未构建+原因"，不得沿用"3 个包均为 0 阻断项"这类固定句式。

- [ ] **Step 5: 跑测试确认通过**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_delivery_package_build.py -q`
Expected: 全 passed；`--package judge --skip-validate --output-dir tmp/pkgcheck` 退出码 0 且产出 `04_*.zip`。

---

### Task 5: 校验器改在干净虚拟环境里跑（真正的"从零安装"）

**Files:**
- Modify: `scripts/build_delivery_packages.py:598-690`
- Test: `backend/tests/test_judge_package_from_scratch.py`（新建，默认 skip，显式开启）

- [ ] **Step 1: 写校验器的新行为**

`_verify_judge_archive` 内把 `sys.executable` 换成临时新建 venv 的解释器：

```python
def _isolated_interpreter(root: Path) -> Path:
    """新建虚拟环境并安装 requirements-dev.txt：证明包自带依赖清单可闭合。

    复用当前解释器只能证明开发机能跑，评委按 README 从零装时 pytest
    其实来自开发依赖，这条链必须在这里真正走一遍。
    """
    venv_dir = root / ".venv-verify"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], cwd=root, check=True, capture_output=True, text=True, timeout=600)
    python = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    install = subprocess.run(
        [str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=2400,
        check=False,
    )
    if install.returncode:
        raise RuntimeError("从零安装依赖失败：\n" + install.stdout[-4000:] + install.stderr[-2000:])
    return python
```

随后 pytest / 注释门 / smoke 三处改用 `str(python)`；`ValidationResult.detail` 增加一行 `venv=<新建虚拟环境> 安装=requirements-dev.txt`。

- [ ] **Step 2: 写显式开启的复现测试**

```python
"""评委包"从零安装 + 解压复算"验收（默认跳过，需显式开关与联网）。

这条链耗时长且要下载依赖，所以不进默认基线；正式复验必须跑它。
"""

from __future__ import annotations

import importlib.util
import os
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("bdp", ROOT / "scripts" / "build_delivery_packages.py")
bdp = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(bdp)

pytestmark = pytest.mark.skipif(
    os.environ.get("AUDITTRACE_FROM_SCRATCH") != "1",
    reason="需联网新建虚拟环境安装依赖，正式复验时用 AUDITTRACE_FROM_SCRATCH=1 显式开启",
)


def test_judge_package_installs_and_runs_from_scratch(tmp_path: Path) -> None:
    archive = tmp_path / "judge.zip"
    _, _ = bdp._build_zip(archive, bdp._judge_sources(), bdp._judge_generated(), validator=None)
    unpacked = tmp_path / "package"
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(unpacked)
    result = bdp._verify_judge_archive(archive)
    assert "虚拟环境" in result.detail
    assert " failed" not in result.summary
    assert "passed" in result.summary
```

- [ ] **Step 3: 修包内 README 的命令链与预期数字**

`JUDGE_README` 安装段改为：

```
安装（复现测试与验收依赖）：python -m pip install -r requirements-dev.txt
只跑服务不跑测试：python -m pip install -r requirements.txt
启动：python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
测试（离线，无需密钥）：python -m pytest -q
预期结果：以 Task 1/Step 7 的实测行为准（<N> passed、<M> skipped、0 failed、1 warning），
跳过项理由均为"缺少标准股份年报全文"，完整清单见随包“测试清单.txt”。
```

**数字必须填实测值，禁止沿用 340/347 推算。**

- [ ] **Step 4: 跑一次完整从零复验（需授权）**

Run: `set AUDITTRACE_FROM_SCRATCH=1 && backend/.venv/Scripts/python.exe -m pytest backend/tests/test_judge_package_from_scratch.py -q -rs`
Expected: `1 passed`（耗时长）。把摘要行、venv 路径、pip 退出码写进 `交付包/交付包构建与独立复验日志.txt`（由脚本自动落盘）。

---

## Phase 2（P0）：冻结成真正可复现的 Git 版本

### Task 6: 逐项审查未跟踪文件

- [ ] **Step 1:** Run: `git status --porcelain=v1 | grep '^??' > tmp/untracked-20260902.txt` 与 `git ls-files backend/tests`
  Expected: 28 个未跟踪测试文件 + `conftest.py`、`pytest.ini`、`requirements.txt`、`requirements-dev.txt`、`backend/requirements-lock.txt`、本轮新增脚本、`assets/official-v4/illustrations/*` 全部列出。
- [ ] **Step 2:** 逐个确认每个待提交文件里没有真实密钥、手机号、本机绝对路径、年报全文（复用 `build_delivery_packages.py` 的 `SECRET_PATTERNS`/`PERSONAL_MARKERS` 做一次 `git grep -I -e <pattern>` 扫描）。
  Expected: 命中为 0；任何命中先脱敏再提交。

### Task 7: 提交（需用户授权）

- [ ] **Step 1:** Run: `git add` 逐文件加入（禁止 `git add -A`），随后 `git status` 复核暂存清单只含本轮文件。
- [ ] **Step 2:** Run: `git commit -m "make the full test suite reproducible from a clean clone"`
- [ ] **Step 3:** Run: `git ls-files backend/tests | wc -l`
  Expected: `34`。

### Task 8: 从 Git 快照复算

- [ ] **Step 1:** Run: `git archive --format=tar -o tmp/repro.tar HEAD && mkdir -p tmp/repro && tar -xf tmp/repro.tar -C tmp/repro`
- [ ] **Step 2:** 在 `tmp/repro` 内新建 venv 并按 README 安装、运行：
  ```
  python -m venv .venv
  .venv/Scripts/python.exe -m pip install -r requirements-dev.txt
  .venv/Scripts/python.exe -m pytest -q
  ```
  Expected: 与文档一致的 `<N> passed, <M> skipped, 1 warning`，且 `tmp/repro` 内确认无 `.env`、无 `标准股份*.pdf`。
- [ ] **Step 3:** 起服务跑 15 案例目录烟测与真实浏览器打开主页（控制台无未捕获异常）。
  Expected: `/api/cases?summary=true` 返回 15 条；主页四类结论、三张 Agent 卡、折叠展开均正常。
- [ ] **Step 4:** 只有本 Task 全部通过，才把该数字写进方案书、`PROJECT_STATUS.json`、`README_RUN.md` 与视频口播（用户原始门禁：最终测试数字确认后才允许更新对外材料）。

---

## Phase 3（P1）：页面与接口验收补证

### Task 9: 进度观察器降级写进运行元数据并在时间线显示

**关键约束（实测）：** `backend/app/demo_run_tasks.py:440-450` 的 `_persist()` 只把固定列白名单（`status / steps / agent_steps / run_id / failure_code / error / result / result_expires_at / non_interruptible`）写回 Supabase，`_mutate()` 之后又从持久行重读。因此**新增一个顶层 `observer_status` 字段会在刷新后静默丢失**；降级状态必须落在已持久化的 `result.context` 里（`result` 列在白名单内），既不迁移表结构，又满足"跨刷新可读回"。

**Files:**
- Modify: `backend/app/main.py:3377-3390`（`_note_observer_failure` 之外，新增模块级判定函数）与 `main.py:3440` 的 `context.update({...})`
- Modify: `assets/official-v4/demo-app.js:1019-1057`（`renderRunTrace`）
- Test: `backend/tests/test_progress_observer_observability.py`（既有，追加）
- Test: `backend/tests/test_frontend_contract.py`（新建）

- [ ] **Step 1: 追加失败的后端测试**

```python
def test_observer_status_is_ok_when_no_failure() -> None:
    """健康运行必须显式给出 ok，而不是缺字段，前端才能区分"没降级"和"没测"。"""

    assert main_module._observer_status([]) == {"status": "ok", "failure_count": 0, "notice": "留痕通道正常"}


def test_observer_status_reports_degraded_with_main_chain_impact_none() -> None:
    failures = [
        {"scope": "stage", "run_id": "RUN-X", "pipeline_task_id": "T-1", "stage": "structured_output", "error_type": "RuntimeError"},
        {"scope": "agent_step_live", "run_id": "RUN-X", "pipeline_task_id": "T-1", "role": "challenger", "error_type": "RuntimeError"},
    ]
    status = main_module._observer_status(failures)
    assert status["status"] == "degraded"
    assert status["failure_count"] == 2
    assert status["affected_stages"] == ["structured_output"]
    assert status["affected_roles"] == ["challenger"]
    assert status["main_chain_impact"] == "none"
    assert status["notice"] == "留痕通道降级，主分析未受影响"
    assert status["samples"] == failures[:5]


def test_observer_status_survives_into_persisted_task_result() -> None:
    """降级事实必须随 result 落库：顶层新字段会被 _persist 的列白名单丢掉。"""

    assert "result" in main_module._DEMO_TASK_PERSIST_FIELDS, "依赖 demo_run_tasks._persist 的列白名单包含 result"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_progress_observer_observability.py -q`
Expected: 3 项 FAIL（`AttributeError: module 'backend.app.main' has no attribute '_observer_status'`）。

- [ ] **Step 3: 实现判定函数并写进 context**

`main.py` 在 `_run_pipeline` 之前新增模块级函数（放在 `_note_observer_failure` 可引用的位置）：

```python
def _observer_status(failures: list[dict[str, str]]) -> dict[str, Any]:
    """把旁路观察器失败压成一条可展示状态：只描述留痕通道，绝不改写主链结论。"""

    if not failures:
        return {"status": "ok", "failure_count": 0, "notice": "留痕通道正常"}
    return {
        "status": "degraded",
        "failure_count": len(failures),
        "affected_stages": sorted({item["stage"] for item in failures if "stage" in item}),
        "affected_roles": sorted({item["role"] for item in failures if "role" in item}),
        "main_chain_impact": "none",
        "notice": "留痕通道降级，主分析未受影响",
        "samples": failures[:5],
    }
```

在 `main.py:3440` 的 `context.update({...})` 里加一项，让它随 `result` 一起持久化：

```python
            "observer_status": _observer_status(progress_observer_failures),
```

若降级在 context 落库之后才发生（例如最后一步回调失败），在构造 `RunResponse`（`main.py:4313`）之前用同一函数覆盖一次：

```python
    context["observer_status"] = _observer_status(progress_observer_failures)
```

并在 `demo_run_tasks.py` 顶部补一个常量，供测试锚定白名单事实：

```python
_DEMO_TASK_PERSIST_FIELDS = (
    "status", "steps", "agent_steps", "run_id", "failure_code", "error", "result",
    "result_expires_at", "non_interruptible",
)
```

`_persist()` 改为 `fields = {name: task.get(name) for name in _DEMO_TASK_PERSIST_FIELDS}` 后再对 `steps/agent_steps/non_interruptible` 补默认值，行为与现状等价但白名单成为单一事实源。`main.py` 用 `from backend.app.demo_run_tasks import _DEMO_TASK_PERSIST_FIELDS` 暴露为 `main_module._DEMO_TASK_PERSIST_FIELDS`。

- [ ] **Step 4: 前端只在真实降级时显示徽章**

`renderRunTrace`（`demo-app.js:1019`）在阶段列表渲染之后插入：

```javascript
    const observer = run.context?.observer_status;
    if (observer && observer.status === "degraded") {
      const li = document.createElement("li");
      li.dataset.observerStatus = "degraded";
      li.innerHTML = `<strong>留痕通道降级 · ${escapeHtml(String(observer.failure_count || 0))}次</strong><span>${escapeHtml(observer.notice || "留痕通道降级，主分析未受影响")}</span><small>${escapeHtml([...(observer.affected_stages || []), ...(observer.affected_roles || [])].join(" · ") || "未标注阶段")}</small>`;
      list.prepend(li);
    }
```

健康运行不显示任何降级行（`status === "ok"` 时省略），避免把正常任务误报成有问题。

- [ ] **Step 5: 前端契约测试（新建）**

```python
"""前端只按后端事实渲染降级徽章：不得缺席，也不得在无降级时误报。"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_JS = (ROOT / "assets" / "official-v4" / "demo-app.js").read_text(encoding="utf-8")


def test_timeline_reads_observer_status_from_run_context() -> None:
    assert "run.context?.observer_status" in APP_JS
    assert "留痕通道降级，主分析未受影响" in APP_JS


def test_badge_is_conditional_on_degraded() -> None:
    assert 'observer.status === "degraded"' in APP_JS
```

- [ ] **Step 6: 复验**

```
backend/.venv/Scripts/python.exe -m pytest backend/tests/test_progress_observer_observability.py backend/tests/test_frontend_contract.py -q
backend/.venv/Scripts/python.exe -m pytest -q
```
Expected: 定向全 passed；全量为 `0 failed` 的新基线（项数比 347 增加，必须如实记录新数字，供 Task 8/Phase 2 使用）。

- [ ] **Step 7: 真实浏览器取证（与 Task 11 同一轮）**

起后端后人为制造一次回调异常（在 `.env` 里临时置 `AUDITTRACE_FORCE_OBSERVER_FAILURE=1`，该开关只在本地开、不写进任何交付配置），确认时间线首行出现"留痕通道降级 · 主分析未受影响"，且六阶段与结果区仍完整；关闭开关复跑，确认徽章不出现。控制台无新增错误。

### Task 10: 内部状态端点不再默认信任回环地址

**风险实测依据：** `_is_loopback_request`（`main.py:4577-4586`）只看 `request.client.host`。Render 免费 Web 上 uvicorn 绑定 `0.0.0.0`、平台代理常从同机回环连进来，此时 `/api/internal/status` 会被判成"本机"而对公网请求者敞开完整诊断（历史评估、内部路径、旧模型窗口）。

**Files:**
- Modify: `backend/app/main.py:4577-4586`
- Modify: `backend/tests/test_public_status_boundary.py`（既有夹具 `_fake_request`，见该文件第 18 行）
- Modify: `.env.example`、`README_RUN.md`

- [ ] **Step 1: 追加失败测试**

```python
def test_loopback_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """同机反代不能再自动等于可信本机：必须显式开关。"""

    monkeypatch.delenv("AUDITTRACE_TRUST_LOOPBACK", raising=False)
    assert main_module._is_loopback_request(_fake_request("127.0.0.1")) is False
    assert main_module._is_loopback_request(_fake_request("::1")) is False


def test_loopback_opt_in_restores_local_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_TRUST_LOOPBACK", "1")
    assert main_module._is_loopback_request(_fake_request("127.0.0.1")) is True
    assert main_module._is_loopback_request(_fake_request("203.0.113.7")) is False


def test_internal_status_rejects_public_caller_without_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDITTRACE_DEMO_MODE", "true")
    monkeypatch.setenv("AUDITTRACE_PUBLIC_DEMO", "true")
    monkeypatch.delenv("AUDITTRACE_TRUST_LOOPBACK", raising=False)
    client = TestClient(main_module.app, client=("127.0.0.1", 54321))
    assert client.get("/api/internal/status").status_code == 403
```

- [ ] **Step 2: 跑测试确认失败**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_public_status_boundary.py -q`
Expected: 第一条 FAIL（当前无条件信任 127.0.0.1，返回 True）。

- [ ] **Step 3: 先修既有测试再改实现**

既有 `test_loopback_detection_covers_ipv4_ipv6_and_missing_peer`（该文件第 25 行）断言的是"无开关时回环即真"，会被本改动打破。改为在函数开头 `monkeypatch.setenv("AUDITTRACE_TRUST_LOOPBACK", "1")` 并加形参 `monkeypatch: pytest.MonkeyPatch`，另补一行 `assert main_module._is_loopback_request(_fake_request("127.0.0.1")) is True` 保持原有 IPv4/IPv6/localhost/None 四组断言不变。

- [ ] **Step 4: 实现显式开关**

```python
_TRUST_LOOPBACK_FLAG = "AUDITTRACE_TRUST_LOOPBACK"


def _loopback_trusted_by_config() -> bool:
    """回环是否可作为本机判据：默认关闭，只有本机开发显式开启。

    部署环境里同机反向代理会让外部请求看起来像 127.0.0.1，
    所以"对端是回环"不再是充分条件，必须由显式开关授权。
    """

    return str(os.environ.get(_TRUST_LOOPBACK_FLAG, "")).strip().lower() in {"1", "true", "yes", "on"}


def _is_loopback_request(http_request: Request) -> bool:
    """对等地址是否回环：仅在显式开关下采信，不复因历史状态文件。"""

    if not _loopback_trusted_by_config():
        return False
    peer = str(http_request.client.host if http_request.client else "").strip()
    if not peer:
        return False
    try:
        return ipaddress.ip_address(peer).is_loopback
    except ValueError:
        return peer.lower() == "localhost"
```

`_is_local_or_authenticated_request`（`main.py:4589`）与 `/api/internal/status`（`:4608`）不改逻辑，自动受同一判据约束。`_client_identity` 已有的受信网段解析（`main.py:790-797`）保持不动：转发链只在 `AUDITTRACE_TRUSTED_PROXY_CIDRS` 命中时才参与身份判定。

- [ ] **Step 5: 文档与模板**

`.env.example` 增加：

```
# 仅本机开发时置 1，让 /api/internal/status 与完整状态可读；对外部署务必留空。
AUDITTRACE_TRUST_LOOPBACK=
# 只有配置了受信代理网段时，才按 X-Forwarded-For 解析真实来源。
AUDITTRACE_TRUSTED_PROXY_CIDRS=
```

`README_RUN.md` 增补一句：本地开发需要看内部诊断时才开 `AUDITTRACE_TRUST_LOOPBACK`，Render 部署不写该变量。

- [ ] **Step 6: 复验**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_public_status_boundary.py backend/tests/test_merged_bug_fixes.py -q`
Expected: 全 passed。再按现有清洁包/评委包 smoke 断言（`_JUDGE_SMOKE` 里 `assert client.get("/api/internal/status").status_code == 403`）确认公开边界未被放宽。

### Task 11: 键盘专项复验与 axe incomplete 复核

**Files:**
- Modify: `scripts/browser_demo_final_acceptance.py:58-110`（`keyboard_check` 逐项证据）与 `:114-140`（`axe_state` 的 incomplete 处理）、`:393` 附近（汇总门禁）
- Output: `artifacts/accessibility-keyboard-20260902/`

- [ ] **Step 1: 让键盘四项证据成为必产物**

`keyboard_check(page)` 的返回值补齐四项显式事实（缺失即为 false，不允许"没测"当成通过）：

```python
def keyboard_acceptance(observed: dict) -> str:
    """键盘专项只在四项全部有真实证据时接受；任一项缺证据即 not_accepted。"""

    required = ("enter_expands", "space_expands", "escape_collapses", "focus_restored", "aria_hidden_synced")
    if all(bool(observed.get(key)) for key in required):
        return "accepted"
    return "not_accepted"
```

在 `main()` 里把结果挂进报告并纳入退出条件（与既有 `report["axe_acceptance"]` 同级）：

```python
    report["keyboard_acceptance"] = keyboard_acceptance(report.get("keyboard", {}).get("collapsible_state") or {})
    report["accepted"] = bool(
        report.get("axe_acceptance") == "accepted"
        and report.get("keyboard_acceptance") == "accepted"
        and report.get("print_expand_accepted")
    )
```

若 `keyboard_check` 目前只写了 `enter_expands/space_expands/escape_collapses` 中的一部分，先补 `focus_restored`（Esc 后 `document.activeElement.id` 等于触发按钮 id）与 `aria_hidden_synced`（`aria-expanded` 与面板 `hidden` 同步变化）两项采集，再启用上面的门禁。

- [ ] **Step 2: incomplete 节点单独留痕**

```python
def flatten_incomplete(violations: list) -> list:
    """incomplete 不是 violation：单独导出给人工判定，绝不并进"0 violation"结论。"""

    nodes = []
    for entry in violations:
        for check in entry.get("incomplete") or []:
            for node in check.get("nodes") or []:
                nodes.append(
                    {
                        "id": check.get("id"),
                        "reason": (check.get("message") or "")[:200],
                        "target": node.get("target"),
                        "any": node.get("any"),
                        "all": node.get("all"),
                        "none": node.get("none"),
                    }
                )
    return nodes
```

`axe_state()` 内记录 `entry["incomplete_nodes"] = flatten_incomplete(...)`，并把 `incomplete` 计数写进每个视口每个状态的报告文件。

- [ ] **Step 3: 真实浏览器跑 4 视口 × 6 状态**

```
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
backend/.venv/Scripts/python.exe -u scripts/browser_demo_final_acceptance.py
```
Expected: 退出码 0，且 `report["accepted"] is True`；landing / case-select / running / result / collapsed / Agent 对话 / 打印预览在 `1440×1000`、`1024×768`、`768×1024`、`390×844` 下每个折叠区都有 `keyboard_acceptance == "accepted"`。任一状态没跑到就是 `not_accepted`，本轮不得记为通过。

- [ ] **Step 4: 人工复核 incomplete 节点**

逐条打开 `artifacts/accessibility-keyboard-20260902/**/axe-*.json` 的 `incomplete_nodes`，对照截图判定"真缺陷 / 不可判定 / 误报"，结论写进同目录 `incomplete-review.md`。判定为真缺陷的，回改 `assets/official-v4/styles.css` 后复跑 Step 3。

- [ ] **Step 5: 表述收口**

`PROJECT_STATUS.json` 与 `README_RUN.md` 里把无障碍结论写成"自动扫描 0 violation，另有 N 项 incomplete 已人工判定为……"，禁止写成"无障碍完全无问题"。

---

## Phase 4（P2）：真人发布门槛（AI 不得代做）

1. 真人冻结 B0 人工基线；跑最新真实 B3（12 次真实模型调用，需逐次授权，失败不得自动重试粉饰）。
2. 两名真人独立完成 6 份评分表；队长补签 R1。
3. 生产环境复验：部署后以真实公网域名重跑 Task 8 Step 3 与 Task 11 Step 2。
4. 方案书更新（测试数字只引用 Phase 2 冻结后的复算结果），重导 PDF，记录页数/大小/SHA-256。
5. 重新构建全部交付包（含 `04_`），生成 ZIP + 文件清单 + SHA-256 + 验收报告，旧包保留。
6. ≤5 分钟、≥1080P、团队成员出镜视频。
7. 以上全部完成并由真人批准后，才把 `competition_release_ready` 置为 true。

---

## 自检（写完后按 spec 复查）

- **覆盖检查：** 用户列出的 5 个未通过项 —— ①评委包不可验收 → Phase 1 Task 1–5；②Git 不可复现 → Phase 2 Task 6–8；③从零安装未验证 → Task 5；④观察性与安全未闭环 → Task 9（降级进 `result.context` 并上时间线）、Task 10（回环信任改为显式开关）、Task 11（键盘专项 + axe incomplete）；⑤发布门槛 → Phase 4。另有上一轮承诺的两项校验（`git check-ignore`、`json.load`）→ Phase 0 Task 0；`340 passed` 说法证伪的收口 → Task 2 Step 7 与 Task 5 Step 3 回填实测数字。
- **占位符扫描：** Task 5 / 8 中形如 `<N> passed` 的位置不是偷懒占位，而是"必须填当次实测数字"的显式约束；执行时若仍留尖括号即视为未完成。其余步骤均给出可执行代码或完整命令。
- **命名一致性：** 跳过判据统一 `full_corpus_available()`，marker 统一 `requires_full_corpus` / `repository_only`；观察器统一 `_observer_status()` 与字段 `status / failure_count / affected_stages / affected_roles / main_chain_impact / notice / samples`（前端读 `run.context.observer_status`）；持久白名单常量为 `_DEMO_TASK_PERSIST_FIELDS`；环境变量统一 `AUDITTRACE_TRUST_LOOPBACK`、`AUDITTRACE_TRUSTED_PROXY_CIDRS`、`AUDITTRACE_FROM_SCRATCH`、`AUDITTRACE_FORCE_OBSERVER_FAILURE`（仅本地）；打包 CLI 统一 `--package / --validate-only / --skip-validate / --output-dir`，构建函数 `_build_one()`、入口 `main(argv=None) -> int`。
- **重复文件：** 同目录 `2026-09-02-judge-package-reproducibility-and-release-gates.md` 是本人误建的重复副本，已改写为指向本文件的占位说明，可直接删除；本文件是唯一口径。
- **主要风险：** ①加 marker 与新增测试都会改变 passed/skipped 计数，因此 Task 2 Step 7 之后才允许写任何对外数字，Phase 2 Task 8 是最终冻结点；②`_verify_judge_archive` 改为新建虚拟环境后单包复验耗时明显增加（pip 安装约 3–10 分钟），正式跑放后台并回读日志；③Task 10 会改变 `/api/internal/status` 的本机可读性，必须同步本地开发文档，否则团队会误判成后端故障。
- **执行顺序不可打乱：** Phase 0 → 1 → 3 → 2（先修完代码与补完证据，再提交冻结，最后从 Git 快照复算）→ 4。Phase 3 放在 Phase 2 之前，是为了让这三项改动一起进入被复现的版本。
