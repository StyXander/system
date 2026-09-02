"""仅在源码仓库执行的交付包白名单检查；不随清洁运行包分发。"""

from pathlib import PurePath
import zipfile


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
