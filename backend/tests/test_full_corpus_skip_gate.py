"""评委包不带年报时必须显式跳过，而不是失败，也不能静默漏跑。

闸门只认根 conftest 里的真实实现：测试把该 conftest 原样写进临时工程，
再跑一个带 marker 的样例用例，确保线上闸门与断言同源。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
MARKER = "requires_full_corpus"
STATUS_JSON = ROOT / "PROJECT_STATUS.json"


def _root_conftest() -> str:
    """取根 conftest 源码但剥掉 pytest_plugins 声明，避免嵌套会话二次加载插件。"""

    text = (ROOT / "conftest.py").read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("pytest_plugins")) + "\n"


def _stage(pytester: pytest.Pytester, *, with_corpus: bool, body: str = "assert True") -> None:
    (pytester.path / "conftest.py").write_text(_root_conftest(), encoding="utf-8")
    (pytester.path / "pytest.ini").write_text(
        f"[pytest]\nmarkers =\n    {MARKER}: 需要标准股份年报全文才可运行\n", encoding="utf-8"
    )
    (pytester.path / "test_sample.py").write_text(
        f"import pytest\n\n\n@pytest.mark.{MARKER}\ndef test_needs_pdf():\n    {body}\n", encoding="utf-8"
    )
    if with_corpus:
        (pytester.path / "标准股份：2023年年度报告.pdf").write_bytes(b"%PDF-1.4 fake")


def _root_conftest_module() -> ModuleType:
    """按文件路径加载根 conftest，避免与 backend/tests/conftest.py 的同名模块混淆。"""

    spec = importlib.util.spec_from_file_location("repo_root_conftest", ROOT / "conftest.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ledger_titles() -> list[str]:
    """年报台账里的公告标题决定了 prepare_full_corpus.py 的落盘文件名。"""

    data = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
    return [str(entry["announcement_title"]) for entry in data.get("standard_annual_report_sources", [])]


def test_gate_skips_when_corpus_absent(pytester: pytest.Pytester) -> None:
    _stage(pytester, with_corpus=False)
    result = pytester.runpytest("-q", "-rs")
    result.assert_outcomes(passed=0, skipped=1, failed=0)
    assert any("缺少标准股份年报全文" in line for line in result.outlines), result.outlines


def test_gate_runs_when_corpus_present(pytester: pytest.Pytester) -> None:
    _stage(pytester, with_corpus=True)
    result = pytester.runpytest("-q")
    result.assert_outcomes(passed=1, skipped=0)


def test_gate_never_masks_a_real_defect(pytester: pytest.Pytester) -> None:
    """全文齐备时被 marker 标记的用例若真的失败，必须照常 FAILED，不得被洗成 skip。"""

    _stage(pytester, with_corpus=True, body="assert 1 == 2")
    result = pytester.runpytest("-q")
    result.assert_outcomes(passed=0, skipped=0, failed=1)


def test_prepare_full_corpus_output_is_visible_to_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """台账标题拼出的落盘文件名必须能被闸门判据看到，否则下载成功也永远判“无全文”。"""

    titles = _ledger_titles()
    assert len(titles) == 4, "年报台账应为四份；数量变化需同步确认打包边界"

    module = _root_conftest_module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    assert module.full_corpus_available() is False

    for title in titles:
        (tmp_path / f"{title}.pdf").write_bytes(b"%PDF-1.4 fake")
    assert module.full_corpus_available() is True, (
        "prepare_full_corpus.py 按台账标题落盘，但闸门判据匹配不到这些文件名；"
        "两者必须共用同一命名口径"
    )


@pytest.mark.requires_full_corpus
def test_repo_itself_never_skips_full_corpus() -> None:
    """源码仓库本机有年报时，标记的全文用例必须实际运行而非被静默跳过。"""
    assert any(ROOT.glob("标准股份*.pdf")), "本机年报缺失会使本项无法判定，先恢复本地资料再跑"

    marked = sorted(
        path.name
        for path in (ROOT / "backend" / "tests").glob("test_*.py")
        if f"pytest.mark.{MARKER}" in path.read_text(encoding="utf-8")
    )
    expected = {
        "test_full_corpus_skip_gate.py",
        "test_future_system.py",
        "test_merged_bug_fixes.py",
        "test_r3_continuation_acceptance.py",
        "test_v7_closure.py",
        "test_w3_api.py",
    }
    assert set(marked) == expected, (
        f"全文依赖标记发生漂移：实际={marked}，预期={sorted(expected)}；"
        "新增或删除标记都必须逐项确认评委包边界"
    )
