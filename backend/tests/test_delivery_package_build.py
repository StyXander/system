"""仅在源码仓库执行的交付包白名单检查；不随清洁运行包分发。"""

from pathlib import Path, PurePath
import subprocess
import sys
import zipfile
import pytest

pytestmark = pytest.mark.repository_only
REPO_ROOT = Path(__file__).resolve().parents[2]


def test_clean_delivery_package_is_present_and_zero_blocker() -> None:
    from scripts.build_delivery_packages import CLEAN_ZIP, scan_archive

    assert CLEAN_ZIP.is_file(), "先运行 scripts/build_delivery_packages.py 生成白名单包"
    result = scan_archive(CLEAN_ZIP)
    assert result.blockers == ()
    with zipfile.ZipFile(CLEAN_ZIP) as archive:
        names = archive.namelist()
        readme = archive.read("README_运行说明.txt").decode("utf-8")
    assert ".env.example" in names
    assert not any(PurePath(name).name == ".env" for name in names)
    assert not any(name.lower().endswith((".md", ".log", ".pyc", ".ndjson")) for name in names)
    assert "仅限团队内部技术复验，禁止外发" in readme


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
    for flag in ("--package", "--validate-only", "--skip-validate", "--output-dir", "--python-executable"):
        assert flag in result.stdout, flag


def test_judge_package_can_build_without_legacy_office_files(tmp_path: Path) -> None:
    """旧教师包的 DOCX 缺失，绝不能阻断评委包构建。"""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_delivery_packages.py",
            "--package",
            "judge",
            "--skip-validate",
            "--output-dir",
            str(tmp_path),
        ],
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
