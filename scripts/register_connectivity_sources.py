"""把已有公开报告登记到运行目录，不复制参考答案或研究页码。

本地原件保持原样；发布时可以按登记的公开来源重新取得。
该脚本只读取资料库的报告元数据，不读取字段样本和核读结论。
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.connectivity_schemas import ReportDocument


def register() -> dict:
    research = ROOT.parent / "资料研究"
    library = research / "制造业真实报告资料库_2026-10-15"
    target = ROOT / "backend/runtime/connectivity/sources"
    target.mkdir(parents=True, exist_ok=True)
    rows = json.loads((library / "报告登记.json").read_text(encoding="utf-8"))["reports"]
    documents = []
    for row in rows:
        if row.get("type") not in {"AR", "ESG"} or row.get("role") != "配对主版本":
            continue
        source = library / row["file"]
        digest = hashlib.file_digest(source.open("rb"), "sha256").hexdigest()
        if digest != row["sha256"]:
            raise ValueError(f"登记原件与现有版本不同：{row['id']}")
        destination = target / f"{digest}.pdf"
        if not destination.exists():
            shutil.copy2(source, destination)
        pair_id = f"{row['code']}-{row['report_year']}"
        doc = ReportDocument(document_id=f"{row['id']}_{row['report_year']}", case_id=pair_id,
            company_id=row["code"], company=row["company"], report_type=row["type"], period=str(row["report_year"]),
            version=row.get("version_note", row.get("name", "登记公开版本")), source_url=row["url"],
            disclosure_date=row.get("disclosure_date", ""), retrieved_at=row.get("retrieved_at", ""),
            compilation_basis=json.dumps(row.get("standard_declaration", row.get("accounting_basis", "待从原文核对")), ensure_ascii=False),
            pages=row.get("pages", 0), file_sha256=digest, available=True)
        documents.append(doc.model_dump())
    # 补充期间的来源登记与2025报告严格分开，不带入人工定位结果。
    extra = research / "创新复核与方案收敛_2026-10-15/原件/宝钢股份"
    extras = [
        ("BAO24_AR", "AR", "BAO24_AR_2024_年报_巨潮原件.pdf", "https://static.cninfo.com.cn/finalpage/2025-04-26/1223329102.PDF", "official"),
        ("BAO24_ESG", "ESG", "BAO24_ESG_2024_可持续发展报告_新浪公告镜像.pdf", "https://file.finance.sina.com.cn/211.154.219.97%3A9494/MRGG/CNSESH_STOCK/2025/2025-4/2025-04-26/11006049.PDF", "announcement_mirror"),
    ]
    import pymupdf
    for identity, kind, filename, url, source_kind in extras:
        source = extra / filename
        if not source.exists():
            continue
        with source.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        destination = target / f"{digest}.pdf"
        if not destination.exists():
            shutil.copy2(source, destination)
        with pymupdf.open(source) as pdf:
            pages = len(pdf)
        documents.append(ReportDocument(document_id=identity, case_id="600019-2024", company_id="600019",
            company="宝钢股份", report_type=kind, period="2024", source_url=url, source_kind=source_kind,
            version="2024年度公告原件" if source_kind == "official" else "2024年度公告镜像，未冒充官方字节副本",
            pages=pages, file_sha256=digest, available=True).model_dump())
    manifest = {"schema_version": "connectivity_sources_v1", "documents": documents}
    path = ROOT / "backend/connectivity_reports.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(documents), "pairs": len({d['case_id'] for d in documents}), "manifest": str(path)}, ensure_ascii=False))
    return manifest


if __name__ == "__main__":
    register()
