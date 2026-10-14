"""原文页阅读：显示所引用的真实 PDF 页，全文不作为附件自动下载。"""

import base64
import hashlib
from html import escape
from pathlib import Path
import re
import secrets

import httpx
import pymupdf
from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from .schemas import AI_GENERATED_CONTENT_NOTICE
from .secure_download import download_bounded, SecureDownloadError
from .source_corrections import public_source_access_url


def preview_path(root: Path, document: dict, local_path: Path | None, *, public: bool) -> Path:
    """只取登记的官方原件；缓存及新下载均核对整份文件哈希。"""
    expected = str(document.get("sha256") or document.get("file_sha256") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise HTTPException(409, "原件未登记有效哈希，无法展示已核验原文页。")
    target = local_path or root / "backend/runtime/source-preview" / f"{expected}.pdf"
    if target.is_file():
        with target.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual == expected:
            return target
        # 已有原件不删除、不覆盖；哈希不一致时明确停止阅读。
        raise HTTPException(409, "原件哈希与登记值不一致，已停止原文预览。")
    if not public:
        raise HTTPException(404, "授权原件不在当前实例，无法显示原文页。")
    url = public_source_access_url(document)
    allowed = lambda value: bool(re.fullmatch(r"https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/\d+\.pdf", value, re.IGNORECASE))
    if not allowed(url):
        raise HTTPException(404, "原件没有可核验的官方来源地址。")
    try:
        # 使用现有逐跳白名单、体积限制、PDF 文件头和整文件哈希校验。
        with httpx.Client(timeout=60, trust_env=False, headers={"Referer": "https://www.cninfo.com.cn/", "User-Agent": "Mozilla/5.0"}) as client:
            download_bounded(url, target, client=client, max_bytes=120 * 1024 * 1024, require_pdf=True, is_allowed_url=allowed, expected_sha256=expected)
    except (SecureDownloadError, OSError, httpx.HTTPError) as error:
        raise HTTPException(503, "官方原件暂时无法取得，原文预览失败；请稍后重试或使用原件链接。") from error
    return target


def source_page_response(path: Path, document: dict, page: int, source_path: str) -> HTMLResponse:
    """真实页码渲染为图片，浏览器无需 PDF 插件或官方页面脚本。"""
    try:
        with pymupdf.open(path) as pdf:
            count = len(pdf)
            if page > count:
                raise HTTPException(404, f"PDF 共 {count} 页，所请求页码不存在。")
            original = pdf[page - 1]
            # 限制超大页面的像素尺寸，保留页图比例并避免浏览器回查耗尽内存。
            scale = min(1.8, 2400 / max(original.rect.width, original.rect.height))
            pixmap = original.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            png = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
            text = original.get_text()
    except (pymupdf.FileDataError, RuntimeError) as error:
        raise HTTPException(409, "登记原件无法解析为 PDF，未生成替代页面。") from error
    title = escape(str(document.get("announcement_title") or document.get("source_file") or document.get("document_id")))
    nonce = secrets.token_urlsafe(18)
    def link(number, label):
        return f'<a href="{escape(source_path, quote=True)}?view=true&amp;page={number}">{label}</a>'
    navigation = (link(page - 1, "上一页") if page > 1 else "") + (link(page + 1, "下一页") if page < count else "")
    html = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · PDF 第 {page} 页</title>
<style nonce="{nonce}">*{{box-sizing:border-box}}body{{margin:0;color:#202833;background:#eef1f5;font:16px/1.6 "Microsoft YaHei",sans-serif}}header{{padding:16px 24px;background:#fff;border-bottom:1px solid #ccd3dd}}h1{{font-size:20px;margin:0 0 6px}}p{{margin:4px 0}}nav{{display:flex;flex-wrap:wrap;gap:12px 24px}}a{{color:#165ac7;min-height:44px;display:inline-flex;align-items:center}}a:focus-visible,summary:focus-visible{{outline:3px solid #165ac7;outline-offset:3px}}small{{display:block;color:#596675}}main{{max-width:1100px;margin:20px auto;padding:0 16px}}img{{width:100%;height:auto;display:block;box-shadow:0 1px 5px #ccd3dd}}details{{margin-top:20px;background:#fff;padding:16px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}@media(max-width:600px){{header{{padding:12px 16px}}h1{{font-size:18px}}main{{margin:12px auto;padding:0 8px}}}}</style></head><body>
<header><h1>{title}</h1><p>PDF 第 {page} 页 / 共 {count} 页 · 原件页图，未改写内容</p><nav>{navigation}<a href="{escape(source_path, quote=True)}" target="_blank" rel="noopener noreferrer">打开全文 PDF</a></nav><small>{escape(AI_GENERATED_CONTENT_NOTICE)}</small></header>
<main><img src="data:image/png;base64,{png}" alt="{title}，PDF 第 {page} 页；该页提取文字见下方"><details><summary>该页提取文字（以原件页图为准）</summary><pre>{escape(text)}</pre></details></main></body></html>'''
    # 私有页图禁止共享缓存，样式仅放行本次 nonce，页面只加载内嵌真实页图。
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Content-Security-Policy": f"default-src 'none'; img-src data:; style-src 'nonce-{nonce}'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'", "X-Frame-Options": "DENY"})
