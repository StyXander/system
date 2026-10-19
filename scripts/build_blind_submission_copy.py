"""从 26 号实名母版派生一份初赛盲审提交候选版，不修改母版本身。

手册同时要求“评委盲审”和“队员出镜介绍”，匿名范围未写明，因此保留两份：
母版用于内部核对与最终署名，盲审版用于按盲审口径提交。生成动作只替换身份字段
与签名图像，正文、图表、表格结构与页序一律不动。

匿名不是“把图片从页面上擦掉”。DOCX 里的图片由部件、关系和显示节点三层组成：
只删显示节点，关系仍会被 python-docx 写回包，媒体文件也就还在压缩包里，评委
解压即可还原签名图像。因此本脚本在保存前删除已无人引用的关系，保存后再以 ZIP
逐部件复验，任何残留都直接判定生成失败。

用法：

    backend/.venv/Scripts/python.exe scripts/build_blind_submission_copy.py
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from docx import Document
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "02_最终确定方案/26_审迹智链_AuditTrace_初赛方案书_竞赛核对修订稿_2026-09-08.docx"
TARGET = ROOT / "02_最终确定方案/27_审迹智链_AuditTrace_初赛方案书_盲审提交候选_2026-09-08.docx"
EVIDENCE = ROOT / "artifacts/competition-improvement-20260908/blind-copy-changes.json"
ANONYMITY_REPORT = ROOT / "artifacts/competition-improvement-20260908/blind-copy-anonymity-verification.json"
# 上一版有缺陷的盲审件不删除，移到证据目录留档，避免静默覆盖历史产物。
DEFECT_ARCHIVE = ROOT / "artifacts/independent-plan-acceptance-20260908/A01-defective-blind-copy-27.docx"

# 需要在全文中清除的身份线索：导师姓名、院校、职称、手机号与签名图像。
IDENTITY_PATTERNS = re.compile(r"刘金钊|北京工商大学|商学院|副教授|1[3-9]\d{9}")
COVER_BLIND_NOTE = "（盲审提交版：院校、队名、姓名与联系方式已按盲审口径隐去，身份信息以竞赛公众号报名表为准）"
CELL_BLIND_MARK = "（盲审隐去）"
# 部件之间引用图片、OLE 对象与超链接时使用的关系属性名。
RELATION_ATTRIBUTES = (qn("r:embed"), qn("r:id"), qn("r:link"))


def _rewrite(paragraph, value: str) -> str:
    """保留首 run 字符格式，只替换文字；返回替换前的原文。"""

    fmt = deepcopy(paragraph.runs[0]._r.rPr) if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None
    old = paragraph.text
    for run in list(paragraph.runs):
        paragraph._p.remove(run._r)
    new = paragraph.add_run(value)
    if fmt is not None:
        new._r.insert(0, fmt)
    return old


def _referenced_rids(element) -> set[str]:
    """收集一个部件 XML 内全部关系引用；按属性值取，避免 rId1 与 rId10 前缀误判。"""

    found: set[str] = set()
    for node in element.iter():
        for attribute, value in node.attrib.items():
            if attribute in RELATION_ATTRIBUTES:
                found.add(str(value))
    return found


def _strip_drawings(cell) -> tuple[int, set[str]]:
    """删除单元格内的图片与签名笔迹；返回删除数量和它们引用的关系 ID。"""

    removed = 0
    rids: set[str] = set()
    for tag in ("w:drawing", "w:pict", "w:object"):
        for node in list(cell._tc.iter(qn(tag))):
            rids |= _referenced_rids(node)
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)
                removed += 1
    return removed, rids


def _drop_unreferenced_parts(document, candidate_rids: set[str]) -> list[str]:
    """删除正文里已无人引用的关系；关系一断，孤立的媒体部件就不会再被写进包。"""

    if not candidate_rids:
        return []
    still_referenced = _referenced_rids(document.element)
    dropped: list[str] = []
    for rid in sorted(candidate_rids):
        if rid in still_referenced:
            continue  # 正文图仍在使用，删了就破坏版面。
        document.part.drop_rel(rid)
        dropped.append(rid)
    return dropped


def _part_text(zf: zipfile.ZipFile, name: str) -> str:
    """取出一个 XML 部件里的纯文本，用于身份线索扫描。"""

    try:
        raw = zf.read(name).decode("utf-8", "replace")
    except KeyError:
        return ""
    stripped = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", stripped)


def _normalize_target(owner: str, target: str) -> str:
    """把关系目标解析成包内路径；关系目标按 OOXML 约定相对于所属部件所在目录。"""

    base_directory, _, _ = owner.rpartition("/")
    parts = [*(base_directory.split("/") if base_directory else []), *target.split("/")]
    resolved: list[str] = []
    for segment in parts:
        if segment in ("", "."):
            continue
        if segment == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(segment)
    return "/".join(resolved)


def _owner_part(rels_name: str) -> str:
    """把 `.rels` 路径还原成它所属的部件路径。

    `word/_rels/document.xml.rels` 属于 `word/document.xml`；`_rels/.rels` 属于包根的
    `docx` 主部件。搞错一层就会把仍在使用的图片误判成悬空关系。
    """

    directory, _, filename = rels_name.rpartition("/")
    if directory == "_rels":
        directory = ""
    elif directory.endswith("/_rels"):
        directory = directory[: -len("/_rels")]
    target_name = filename[: -len(".rels")] or "document.xml"  # 根 `.rels` 指向包本身的主部件
    return f"{directory}/{target_name}" if directory else target_name


def _image_relation_state(zf: zipfile.ZipFile) -> tuple[list[str], set[str]]:
    """返回悬空 image 关系清单，以及仍被部件引用的媒体路径集合。

    关系只要还写在 .rels 里，打包时对应媒体部件就会继续被写进去；所以删掉显示节点
    之后必须连关系一起清掉。这里既查悬空关系，也反查还有哪些媒体真正在用。
    """

    dangling: list[str] = []
    live_targets: set[str] = set()
    names = set(zf.namelist())
    for rels_name in sorted(n for n in names if n.endswith(".rels")):
        try:
            tree = ElementTree.fromstring(zf.read(rels_name))
        except ElementTree.ParseError:
            dangling.append(f"{rels_name}: 无法解析")
            continue
        owner = _owner_part(rels_name)
        owner_xml = zf.read(owner).decode("utf-8", "replace") if owner in names else ""
        for rel in tree:
            if not str(rel.attrib.get("Type", "")).endswith("/image"):
                continue
            rid = str(rel.attrib.get("Id", ""))
            target = str(rel.attrib.get("Target", ""))
            if target.startswith(("http://", "https://", "file:")):
                continue  # 外链图片不落盘，不构成包内残留。
            resolved = target.lstrip("/") if target.startswith("/") else _normalize_target(owner, target)
            if re.search(r'"' + re.escape(rid) + r'"', owner_xml):
                live_targets.add(resolved)
            else:
                dangling.append(f"{rels_name} -> {rid} ({resolved})")
    return dangling, live_targets


def _verify_anonymity(source: Path, target: Path, dropped_relations: list[str]) -> dict[str, Any]:
    """保存后逐部件复验匿名效果；发现问题就返回明细，由调用方判定失败。"""

    with zipfile.ZipFile(source) as named, zipfile.ZipFile(target) as blind:
        source_media = sorted(n for n in named.namelist() if n.startswith("word/media/"))
        target_media = sorted(n for n in blind.namelist() if n.startswith("word/media/"))
        blind_members = set(blind.namelist())
        scanned_parts = [
            n
            for n in sorted(blind_members)
            if re.match(r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments|commentsExtended)\.xml$", n)
            or re.match(r"^docProps/.*\.xml$", n)
        ]
        identity_hits = {}
        for name in scanned_parts:
            hits = IDENTITY_PATTERNS.findall(_part_text(blind, name))
            if hits:
                identity_hits[name] = sorted(set(hits))
        dangling, live_targets = _image_relation_state(blind)
        embedded_objects = [n for n in sorted(blind_members) if n.startswith("word/embeddings/")]
    # 没有任何在用关系指向的媒体就是残留，与它叫什么名字无关。
    orphan_media = [n for n in target_media if n not in live_targets]
    # 母版里有、盲审件里不再出现的媒体，逐个登记哈希，便于与验收点名的签名图哈希对上。
    with zipfile.ZipFile(source) as named:
        removed_media = {
            name: "sha256:" + hashlib.sha256(named.read(name)).hexdigest()
            for name in source_media
            if name not in target_media
        }
    report = {
        "source_media_count": len(source_media),
        "target_media_count": len(target_media),
        "target_media": target_media,
        "removed_media_sha256": removed_media,
        "referenced_media": sorted(live_targets),
        "orphan_media_parts": orphan_media,
        "dropped_relations": sorted(dropped_relations),
        "dangling_image_relations": dangling,
        "embedded_objects": embedded_objects,
        "identity_text_hits_by_part": identity_hits,
        "core_properties": {},
    }
    document = Document(str(target))
    properties = document.core_properties
    for field in ("author", "last_modified_by", "title", "subject", "keywords", "category", "comments"):
        report["core_properties"][field] = str(getattr(properties, field) or "")
    report["identity_text_hits_total"] = sum(len(v) for v in identity_hits.values())
    report["passed"] = bool(not orphan_media and not dangling and not embedded_objects and not identity_hits)
    return report


def main() -> int:
    if not SOURCE.is_file():
        raise SystemExit("找不到 26 号实名母版，盲审版不生成")
    previous_target_sha256 = hashlib.sha256(TARGET.read_bytes()).hexdigest() if TARGET.is_file() else None
    if TARGET.is_file() and not DEFECT_ARCHIVE.exists():
        DEFECT_ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET, DEFECT_ARCHIVE)

    document = Document(SOURCE)
    changes: list[dict[str, str]] = []
    removed_rids: set[str] = set()

    # 封面四行身份字段整体替换为盲审说明，避免出现“待填写”被误认为需要填真名。
    for paragraph in document.paragraphs[:12]:
        text = paragraph.text.strip()
        if re.match(r"^(队伍名称|院校名称|队长姓名|联系方式)\s*[:：]", text):
            old = _rewrite(paragraph, "")
            changes.append({"location": f"cover:{text[:6]}", "before": old, "after": ""})
    cover_anchor = next((p for p in document.paragraphs[:12] if p.text.strip().startswith("作品全称")), None)
    if cover_anchor is not None:
        note = deepcopy(cover_anchor._p)
        cover_anchor._p.addnext(note)
        from docx.text.paragraph import Paragraph

        note_paragraph = Paragraph(note, cover_anchor._parent)
        for run in list(note_paragraph.runs):
            note_paragraph._p.remove(run._r)
        note_paragraph.add_run(COVER_BLIND_NOTE)
        changes.append({"location": "cover:note", "before": None, "after": COVER_BLIND_NOTE})

    # 前两张表是参赛人员与指导教师信息。
    for table_index, table in enumerate(document.tables[:2]):
        for row_index, row in enumerate(table.rows):
            if row_index == 0:
                continue  # 表头保留，评委需要看清字段含义。
            for cell in row.cells:
                removed, rids = _strip_drawings(cell)
                removed_rids |= rids
                for paragraph in cell.paragraphs:
                    text = paragraph.text.strip()
                    if not text:
                        continue
                    if text == "待填写" or IDENTITY_PATTERNS.search(text):
                        old = _rewrite(paragraph, CELL_BLIND_MARK)
                        changes.append(
                            {
                                "location": f"table{table_index}:r{row_index}",
                                "before": old,
                                "after": CELL_BLIND_MARK,
                                "drawings_removed": removed,
                            }
                        )

    # 正文其余位置若出现身份线索也一并清除，避免漏网。
    for index, paragraph in enumerate(document.paragraphs):
        if index < 12 or IDENTITY_PATTERNS.search(paragraph.text or "") is None:
            continue
        old = _rewrite(paragraph, IDENTITY_PATTERNS.sub(CELL_BLIND_MARK, paragraph.text))
        changes.append({"location": f"paragraph:{index}", "before": old, "after": paragraph.text})

    dropped_relations = _drop_unreferenced_parts(document, removed_rids)

    # 元数据也是身份线索来源，逐项清空后由复验段核实。
    properties = document.core_properties
    properties.title = "审迹智链初赛方案书盲审提交候选"
    for field in ("author", "last_modified_by", "subject", "keywords", "category", "comments"):
        setattr(properties, field, "")
    document.save(TARGET)

    verification = _verify_anonymity(SOURCE, TARGET, dropped_relations)
    if not verification["passed"]:
        raise SystemExit("盲审版匿名复验未通过：" + json.dumps(verification, ensure_ascii=False))

    evidence = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "target": str(TARGET.relative_to(ROOT)),
        "target_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
        "previous_target_sha256": previous_target_sha256,
        "defective_copy_archived_at": str(DEFECT_ARCHIVE.relative_to(ROOT)) if DEFECT_ARCHIVE.exists() else None,
        "drawings_removed_relations": sorted(removed_rids),
        "dropped_relations": dropped_relations,
        "anonymity_verification": verification,
        "manual_basis": [
            "手册第五章阶段提交表：提交《项目方案书》(PDF) + 5 分钟介绍视频，评委盲审",
            "手册第六章 6.1：MP4 格式，5 分钟以内，1080P 以上，包含队员出镜介绍 + 方案陈述",
            "手册第三章：报名表经竞赛公众号填写队伍名称、成员信息、指导教师信息并上传参赛承诺书",
        ],
        "open_question": "手册未写明盲审是否要求隐去院校与姓名，且与“队员出镜”并存；提交哪一版由队长按组委会口径决定。",
        "status": "blind_candidate_pending_captain_choice",
        "changes": changes,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    ANONYMITY_REPORT.write_text(
        json.dumps({**verification, "target_sha256": evidence["target_sha256"], "generated_at": evidence["generated_at"]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "target": str(TARGET.name),
                "changed_cells": len(changes),
                "dropped_relations": dropped_relations,
                "target_media_count": verification["target_media_count"],
                "target_sha256": evidence["target_sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
