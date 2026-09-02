"""公网案例临时物化的租户隔离、远端权威回退与路径边界回归。"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.app import data as standard_data
from backend.app.cases import (
    _case_dir,
    _runtime_base,
    build_case_template_zip,
    get_case,
    get_case_documents,
    get_financial_rows,
    import_case_zip,
    list_cases,
    resolve_case_document,
)


CASE_ID = "SYNTH_DEMO_T0"


def _package(
    *,
    company_name: str,
    revenue_2024: float,
    pdf_marker: str,
    sample_type: str = "synthetic",
    case_id: str = CASE_ID,
) -> bytes:
    """复用正式模板，构造 case_id 相同但内容指纹不同的两个租户包。"""

    with zipfile.ZipFile(io.BytesIO(build_case_template_zip())) as source:
        files = {item.filename: source.read(item) for item in source.infolist() if not item.is_dir()}
    manifest = json.loads(files["case_manifest.json"].decode("utf-8"))
    original_case_id = manifest["case_id"]
    manifest["case_id"] = case_id
    manifest["company_name"] = company_name
    manifest["sample_type"] = sample_type
    # 客户端即使提交同名字段，也不能替代认证层传入的租户作用域。
    manifest["tenant_id"] = "../../CLIENT-CONTROLLED"
    first_document = manifest["documents"][0]
    source_name = first_document["source_file"]
    files[source_name] = files[source_name] + f"\n% tenant marker: {pdf_marker}\n".encode("utf-8")
    first_document["sha256"] = hashlib.sha256(files[source_name]).hexdigest().upper()

    # 模板的所有结构化 CSV 都绑定 case_id；改名测试必须整包同步，不能
    # 通过删除辅助表规避正式导入器的跨案例校验。
    for name, content in list(files.items()):
        if not name.endswith(".csv"):
            continue
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        rows = list(reader)
        if not reader.fieldnames:
            continue
        for row in rows:
            if "case_id" in row:
                row["case_id"] = case_id
            if row.get("evidence_id"):
                row["evidence_id"] = row["evidence_id"].replace(original_case_id, case_id)
            if name == "financial_fields.csv" and row["field_kind"] == "revenue" and int(row["year"]) == 2024:
                row["value"] = str(revenue_2024)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        files[name] = output.getvalue().encode("utf-8-sig")
    files["case_manifest.json"] = json.dumps(manifest, ensure_ascii=False).encode("utf-8")

    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return archive_bytes.getvalue()


def test_same_case_id_materializes_per_tenant_without_shadowing_remote_authority(tmp_path: Path) -> None:
    """A/B 可登记同名私有案例，本地无作用域读取不会误选任一租户副本。"""

    package_a = _package(company_name="租户A合成企业", revenue_2024=111_000_000, pdf_marker="A")
    package_b = _package(company_name="租户B合成企业", revenue_2024=222_000_000, pdf_marker="B")
    case_a = import_case_zip(
        tmp_path,
        package_a,
        authorized=True,
        desensitized=True,
        tenant_id="tenant-a",
        owner_user_id="user-a",
    )
    case_b = import_case_zip(
        tmp_path,
        package_b,
        authorized=True,
        desensitized=True,
        tenant_id="tenant-b",
        owner_user_id="user-b",
    )

    assert case_a["case_id"] == case_b["case_id"] == CASE_ID
    assert case_a["tenant_id"] == "tenant-a"
    assert case_b["tenant_id"] == "tenant-b"
    assert case_a["runtime_materialization"] == case_b["runtime_materialization"] == "tenant_scoped_ephemeral"
    assert get_case(tmp_path, CASE_ID) is None
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-a")["company_name"] == "租户A合成企业"
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-b")["company_name"] == "租户B合成企业"
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-c") is None

    rows_a = get_financial_rows(tmp_path, CASE_ID, tenant_id="tenant-a")
    rows_b = get_financial_rows(tmp_path, CASE_ID, tenant_id="tenant-b")
    revenue_a = next(row["value"] for row in rows_a if row["field_kind"] == "revenue" and row["year"] == 2024)
    revenue_b = next(row["value"] for row in rows_b if row["field_kind"] == "revenue" and row["year"] == 2024)
    assert revenue_a == 111_000_000
    assert revenue_b == 222_000_000
    with pytest.raises(KeyError):
        get_financial_rows(tmp_path, CASE_ID, tenant_id="tenant-c")

    document_id = get_case_documents(tmp_path, CASE_ID, tenant_id="tenant-a")[0]["document_id"]
    resolved_a = resolve_case_document(tmp_path, CASE_ID, document_id, tenant_id="tenant-a")
    resolved_b = resolve_case_document(tmp_path, CASE_ID, document_id, tenant_id="tenant-b")
    assert resolved_a is not None and resolved_b is not None
    assert resolved_a[0] != resolved_b[0]
    assert hashlib.sha256(resolved_a[0].read_bytes()).hexdigest() != hashlib.sha256(resolved_b[0].read_bytes()).hexdigest()
    assert resolve_case_document(tmp_path, CASE_ID, document_id, tenant_id="tenant-c") is None
    assert [row["company_name"] for row in list_cases(tmp_path, tenant_id="tenant-a") if row["case_id"] == CASE_ID] == ["租户A合成企业"]
    assert [row["company_name"] for row in list_cases(tmp_path, tenant_id="tenant-b") if row["case_id"] == CASE_ID] == ["租户B合成企业"]

    # 同名全局公开副本可以与租户副本共存；显式 scope 始终优先精确租户，
    # 无 scope 只读全局副本，不能因目录同名误读 A/B 私有材料。
    public_case = import_case_zip(
        tmp_path,
        _package(
            company_name="全局公开合成企业",
            revenue_2024=999_000_000,
            pdf_marker="PUBLIC",
            sample_type="public",
        ),
        authorized=True,
        desensitized=True,
    )
    assert public_case["sample_type"] == "public"
    assert get_case(tmp_path, CASE_ID)["company_name"] == "全局公开合成企业"
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-a")["company_name"] == "租户A合成企业"
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-b")["company_name"] == "租户B合成企业"


def test_tenant_and_document_paths_cannot_escape_or_cross_scope(tmp_path: Path) -> None:
    """原始租户字符串不进入路径，登记路径被篡改后也不能跨案例读取。"""

    case = import_case_zip(
        tmp_path,
        _package(company_name="路径边界企业", revenue_2024=123_000_000, pdf_marker="SAFE"),
        authorized=True,
        desensitized=True,
        tenant_id="../../tenant-a",
        owner_user_id="user-a",
    )
    case_dir = _case_dir(tmp_path, CASE_ID, tenant_id="../../tenant-a")
    runtime_root = _runtime_base(tmp_path).resolve()
    case_dir.relative_to(runtime_root)
    assert ".." not in case_dir.parts
    assert "tenant-a" not in str(case_dir).lower()
    assert case["tenant_id"] == "../../tenant-a"
    assert get_case(tmp_path, CASE_ID, tenant_id="tenant-a") is None

    document_id = case["documents"][0]["document_id"]
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"%PDF-1.4\nnot a registered tenant document")
    manifest_path = case_dir / "case.json"
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored["documents"][0]["storage_relpath"] = outside.relative_to(tmp_path).as_posix()
    manifest_path.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
    assert resolve_case_document(tmp_path, CASE_ID, document_id, tenant_id="../../tenant-a") is None

    with pytest.raises(ValueError, match="案例编号"):
        _case_dir(tmp_path, "../ESCAPE", tenant_id="tenant-a")
    with pytest.raises(ValueError, match="租户作用域"):
        _case_dir(tmp_path, CASE_ID, tenant_id="tenant-a\x00escape")


def test_explicit_tenant_scope_precedes_builtin_case_with_same_id(tmp_path: Path) -> None:
    """显式租户不能被内置 PUBLIC 同名案例遮蔽，无作用域仍保留本地内置案例。"""

    builtin = get_case(tmp_path, standard_data.CASE_ID)
    assert builtin is not None
    assert get_case(tmp_path, standard_data.CASE_ID, tenant_id="tenant-a") is None
    scoped = import_case_zip(
        tmp_path,
        _package(
            company_name="租户A同名私有企业",
            revenue_2024=444_000_000,
            pdf_marker="PRIVATE-STANDARD-ID",
            sample_type="authorized_deidentified",
            case_id=standard_data.CASE_ID,
        ),
        authorized=True,
        desensitized=True,
        tenant_id="tenant-a",
        owner_user_id="user-a",
    )

    assert scoped["tenant_id"] == "tenant-a"
    assert get_case(tmp_path, standard_data.CASE_ID)["company_name"] == builtin["company_name"]
    assert get_case(tmp_path, standard_data.CASE_ID, tenant_id="tenant-a")["company_name"] == "租户A同名私有企业"
    assert get_case(tmp_path, standard_data.CASE_ID, tenant_id="tenant-b") is None
    tenant_rows = get_financial_rows(tmp_path, standard_data.CASE_ID, tenant_id="tenant-a")
    assert next(row["value"] for row in tenant_rows if row["field_kind"] == "revenue" and row["year"] == 2024) == 444_000_000
    assert [row["company_name"] for row in list_cases(tmp_path, tenant_id="tenant-a")] == ["租户A同名私有企业"]
    with pytest.raises(ValueError, match="不能覆盖内置"):
        import_case_zip(
            tmp_path,
            _package(
                company_name="本地覆盖尝试",
                revenue_2024=555_000_000,
                pdf_marker="LOCAL-OVERRIDE",
                case_id=standard_data.CASE_ID,
            ),
            authorized=True,
            desensitized=True,
        )


def test_local_mode_keeps_legacy_case_directory_and_lookup_contract(tmp_path: Path) -> None:
    """未提供租户时仍写入 backend/runtime/cases/<case_id> 并由旧接口读取。"""

    imported = import_case_zip(
        tmp_path,
        _package(company_name="本地兼容企业", revenue_2024=333_000_000, pdf_marker="LOCAL"),
        authorized=True,
        desensitized=True,
    )
    expected = _runtime_base(tmp_path).resolve() / "cases" / CASE_ID
    assert _case_dir(tmp_path, CASE_ID) == expected
    assert (expected / "case.json").is_file()
    assert imported["runtime_materialization"] == "local_authoritative"
    assert get_case(tmp_path, CASE_ID)["company_name"] == "本地兼容企业"
    assert get_financial_rows(tmp_path, CASE_ID)
