"""官方双报告发现与受控接入；身份命中、配对、原件验证、模型运行各自留痕。

身份目录复用原有官方快照，模糊匹配不能自动选中企业。
年报沿用已实现的年度公告适配器，不另建爬虫。
ESG 查询只扩展报告标题，不接受任意网址作为来源。
官方接口的零结果与错误响应须分别处理。
查询分页被截断时不能把当前第一条当成最新版本。
摘要、英文版、半年报和更正说明不冒充报告全文。
来源证券代码与请求企业必须一致。
报告标题和正文期间需要独立核对。
正文主体优先使用官方简称和年报确认的法定名称。
法定名称仅从年报封面附近提取，不从同业名单推断。
原件采用现有受控下载器，重定向每一跳都验证。
内容头、字节上限、解析页数和文字层覆盖各自检查。
图像内数值没有 OCR 时仍保持能力限制。
下载任务不启动模型，不生成程序结论。
两份原件全部通过才原子发布报告对。
已验证单份原件可留在有界缓存，不能据此进入核验。
重复接入复用相同官方地址与版本的缓存。
同一内容只保留一个哈希 PDF 对象。
配对引用编号同时绑定原件与报告对，避免新 ESG 配旧年报时引用丢失。
临时文件总在退出路径清理；失败不留下已就绪记录。
并发槽位与空间预约同时生效，磁盘不足明确停止。
不通过自动删除历史原件来隐瞒存储不足。
修订发现范围在回执中明示，不承诺穷尽所有公告。
每个成功配对都可以经原流水线独立验证指标条件。
原件技术验证并不等于专业结论，也不等于本次 Agent 已运行。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from threading import BoundedSemaphore, RLock
from urllib.parse import urljoin
import hashlib
import html
import json
import re
import time
import uuid
import os

import httpx
import pymupdf

from . import company_discovery as discovery
from .cninfo import CNInfoError, ANNOUNCEMENT_QUERY_URL, china_today, _date_from_value, _response_json
from .connectivity_catalog import list_pairs, save_pair, cached_documents, cache_document
from .connectivity_schemas import ReportDocument
from .secure_download import download_bounded
from .source_viewer import PDF_ACCESS_LOCK

_slots = BoundedSemaphore(2)
_lock = RLock()
_metadata_cache: dict[tuple, tuple[float, dict]] = {}
_inflight: set[tuple] = set()
_reserved_bytes = 0


@contextmanager
def import_capacity(root: Path):
    """下载有并发与磁盘双上限；不通过删除历史原件腾空间。"""
    global _reserved_bytes
    if not _slots.acquire(blocking=False):
        raise CNInfoError('DISCOVERY_BUSY', '原件准备槽位已满，请稍后重试。')
    reservation = 200 * 1024 * 1024
    reserved = False
    try:
        with _lock:
            base = root / 'backend/runtime/connectivity'
            used = sum(p.stat().st_size for directory in ('sources', 'extraction', 'imports')
                for p in (base / directory).rglob('*') if p.is_file())
            maximum = min(4096, max(200, int(os.getenv('AUDITTRACE_REPORT_CACHE_MAX_MB', '2048')))) * 1024 * 1024
            if used + _reserved_bytes + reservation > maximum:
                raise ValueError('报告存储预算不足；已登记案例仍可读取，未删除历史原件')
            _reserved_bytes += reservation
            reserved = True
        yield
    finally:
        if reserved:
            with _lock:
                _reserved_bytes -= reservation
        _slots.release()


def allowed_source(url: str) -> bool:
    """受控静态官方路径，不接受用户指定域名、凭据、端口、查询串或私网地址。"""
    return bool(re.fullmatch(r'https://static\.cninfo\.com\.cn/finalpage/\d{4}-\d{2}-\d{2}/\d+\.pdf', url, re.I))


def _candidate(row: dict, company: dict, year: int) -> dict | None:
    title = html.unescape(re.sub('<[^>]*>', '', str(row.get('announcementTitle', ''))))
    compact = re.sub(r'\s+', '', title)
    if str(row.get('secCode')) != company['ticker'] or str(year) not in compact:
        return None
    title_years = re.findall(r'20\d{2}', compact)
    if not title_years or title_years[0] != str(year) or re.search(r'20\d{2}[年]?[-—~至]20\d{2}', compact):
        return None
    if not any(term in compact for term in ('可持续发展报告', '社会责任报告')) and not (
        re.search(r'ESG|环境.*(?:社会|管治)', compact, re.I) and re.search(r'报告(?:[（(][^()（）]*[）)])?$', compact)):
        return None
    if any(term in compact for term in ('摘要', '英文', '半年度', '第一季度', '第三季度', '鉴证', '核查意见', '董事会', '更正公告', '编制', '工作报告')):
        return None
    source = urljoin('https://static.cninfo.com.cn/', str(row.get('adjunctUrl', '')).lstrip('/'))
    published = _date_from_value(row.get('announcementTime') or row.get('announcementDate'))
    if not published or published > china_today().isoformat() or not allowed_source(source):
        return None
    return {'ticker': company['ticker'], 'announcement_title': title, 'announcement_date': published,
        'source_url': source, 'report_year': year, 'report_type': 'ESG',
        'is_revised': any(t in title for t in ('修订', '更正', '更新'))}


def discover_pair(root: Path, ticker: str, year: int) -> dict:
    """先使用同一官方身份目录，年报沿用现有适配器；ESG仅增加受控标题查询。"""
    if not re.fullmatch(r'\d{6}', ticker) or not 2000 <= year < china_today().year:
        raise CNInfoError('REPORT_YEAR_INVALID', '请选择六位证券代码及已结束的报告年度。')
    key = (str(root.resolve()), ticker, year)
    with _lock:
        cached = _metadata_cache.get(key)
        if cached and time.monotonic() - cached[0] < 600:
            return json.loads(json.dumps(cached[1]))
        if key in _inflight or len(_inflight) >= 2:
            raise CNInfoError('DISCOVERY_BUSY', '官方双报告查询正在进行，请稍后重试。')
        _inflight.add(key)
    try:
        annual = discovery.annual_reports(root, ticker, year, china_today())
        company = annual['company']
        client = discovery._client()
        candidates, complete = {}, True
        try:
            client.set_operation_deadline(35)
            for keyword in ('可持续', 'ESG', '社会责任', '管治'):
                for page in (1, 2):
                    response = client._request('POST', ANNOUNCEMENT_QUERY_URL, source='可持续报告公告', data={
                        'pageNum': str(page), 'pageSize': '30', 'column': company['column'], 'tabName': 'fulltext',
                        'plate': company['plate'], 'stock': f"{ticker},{company['org_id']}", 'searchkey': keyword,
                        'secid': '', 'category': '', 'trade': '',
                        'seDate': f'{year + 1}-01-01~{china_today().isoformat()}',
                        'sortName': 'time', 'sortType': 'desc', 'isHLtitle': 'true'})
                    body = _response_json(response, source='可持续报告公告')
                    if 'announcements' not in body or (body['announcements'] is not None and not isinstance(body['announcements'], list)):
                        raise CNInfoError('CNINFO_INVALID_ANNOUNCEMENTS', '官方报告查询响应不完整。')
                    for row in body['announcements'] or []:
                        item = _candidate(row, company, year)
                        if item:
                            candidates[item['source_url']] = item
                    if not body.get('hasMore'):
                        break
                    if page == 2:
                        complete = False
        finally:
            client.client.close()
        esg = sorted(candidates.values(), key=lambda r: (r['announcement_date'], r['is_revised']), reverse=True)
        ar = annual.get('selected')
        ar = {**ar, 'report_type': 'AR'} if ar else None
        complete = complete and not annual.get('query_status', {}).get('truncated')
        result = {'company': company, 'period': str(year), 'annual': ar, 'sustainability': esg[0] if esg else None,
            'annual_candidates': annual.get('candidates', []), 'sustainability_candidates': esg,
            'state': 'paired' if ar and esg and complete else 'partial' if ar or esg else 'identity_only',
            'query_complete': complete, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'missing': [kind for kind, present in [('AR', ar), ('ESG', esg)] if not present],
            'boundary': '已查询官方公告元数据；原件下载、正文主体/期间、哈希及逐页解析尚未通过。',
            'version_review': 'bounded_official_title_query' if complete else 'query_truncated_do_not_import'}
        with _lock:
            if len(_metadata_cache) >= 128:
                _metadata_cache.pop(next(iter(_metadata_cache)))
            _metadata_cache[key] = time.monotonic(), result
        return json.loads(json.dumps(result))
    finally:
        with _lock:
            _inflight.discard(key)


def prepare_pair(root: Path, discovered: dict, *, industry: str = '待核行业', progress=None) -> dict:
    """只接收服务端发现结果；下载及所有页解析通过后一次发布双报告。"""
    emit = progress or (lambda *args: None)
    if discovered.get('state') != 'paired' or not discovered.get('query_complete'):
        raise ValueError('双报告缺失或官方查询不完整，不能启动接入')
    capacity = import_capacity(root)
    capacity.__enter__()
    temporary = root / 'backend/runtime/connectivity/imports' / uuid.uuid4().hex
    try:
        temporary.mkdir(parents=True, exist_ok=True)
        company = discovered['company']
        year = str(discovered['period'])
        records, _ = list_pairs(root)
        known = {d['source_url']: d for d in cached_documents(root)}
        known.update({d['source_url']: d for r in records for d in r.get('documents', [])})
        from .connectivity_extraction import load_registry, ensure_source, source_path
        known.update({d.source_url: d.model_dump() for d in load_registry(root)})
        documents, inspections = [], {}
        issuer_names = set()
        for kind, field in [('AR', 'annual'), ('ESG', 'sustainability')]:
            metadata = discovered[field]
            url = metadata['source_url']
            if metadata.get('ticker') != company['ticker'] or str(metadata.get('report_year')) != year or not allowed_source(url):
                raise ValueError('来源身份或年度不匹配')
            emit('download', 'running', f'{kind}：下载官方原件（最多 100MB）')
            path = temporary / (kind + '.pdf')
            if url in known and known[url].get('version') == metadata['announcement_title'] and known[url].get('disclosure_date') == metadata['announcement_date']:
                document = ReportDocument.model_validate(known[url])
                path = ensure_source(root, document)
                digest = document.file_sha256
            else:
                with httpx.Client(timeout=httpx.Timeout(45, connect=8), trust_env=False, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.cninfo.com.cn/'}) as client:
                    downloaded = download_bounded(url, path, client=client, max_bytes=100*1024*1024,
                        min_bytes=4096, require_pdf=True, is_allowed_url=allowed_source)
                digest = downloaded.sha256.lower()
            emit('parse', 'running', f'{kind}：核对主体和年度并逐页解析')
            with PDF_ACCESS_LOCK, pymupdf.open(path) as pdf:
                if pdf.needs_pass or not 2 <= len(pdf) <= 1800:
                    raise ValueError('报告加密或页数超出接入边界')
                texts = []
                page_characters = []
                for page in pdf:
                    text = page.get_text()
                    page_characters.append(len(text.strip()))
                    if len(texts) < 10:
                        texts.append(text)
                heading = re.sub(r'\s+', '', ''.join(texts))
                aliases = {str(company.get(k) or '') for k in ('company_name', 'company_alias', 'name')}
                aliases.discard('')
                aliases.update(issuer_names)
                cover = re.sub(r'\s+', '', '\n'.join(texts[:3]))
                year_cn = ''.join('〇一二三四五六七八九'[int(digit)] for digit in year)
                cover_year = year in cover or year_cn in cover or year_cn.replace('〇', '零') in cover
                period_declaration = re.search(r'(?:报告期间|报告期为|时间范围|报告范围)[^。；]{0,80}' + year + r'年1月1日[^。；]{0,20}' + year + r'年12月31日', heading)
                if not aliases or not any(alias in heading for alias in aliases) or (not cover_year and not period_declaration):
                    raise ValueError(f'{kind} 正文前十页未确认企业与报告年度，保留待核')
                front = re.sub(r'\s+', '', texts[0] if texts else '')
                if re.search(r'(?:年度报告|可持续发展报告|社会责任报告|管治报告|治理报告)摘要', front):
                    raise ValueError(f'{kind} PDF 正文封面为摘要，不能作为完整报告')
                types = ('年度报告', '年报') if kind == 'AR' else ('可持续发展', 'ESG', '社会责任', '环境、社会', '环境社会')
                if not any(t in heading for t in types):
                    raise ValueError(f'{kind} 正文报告性质未确认')
                if sum(n > 40 for n in page_characters) / len(pdf) < .7:
                    raise ValueError('可读文本覆盖不足 70%，需要 OCR，未标为完整解析')
                pages = len(pdf)
                if kind == 'AR':
                    # ESG 有时只写法定全称。仅从已验证年报封面前三页提取同简称的法定名称。
                    # 不从行业同业列表或整份报告猜测主体，且不能借此覆盖公告证券代码门禁。
                    core = re.sub(r'股份$|集团$', '', str(company.get('company_alias') or company.get('company_name') or ''))
                    for line in '\n'.join(texts[:3]).splitlines():
                        cleaned = re.sub(r'\s+', '', line)
                        cleaned = re.split(r'[:：]|公司中文名称|公司的中文名称', cleaned)[-1]
                        issuer_names.update(name for name in re.findall(r'[\u4e00-\u9fff]{2,30}股份有限公司', cleaned)
                            if len(core) >= 2 and core in name)
                scope = [t[:500] for t in texts if re.search('范围|边界|合并|本报告', t)][:3]
                inspections[kind] = {'pages_read': pages, 'text_pages': sum(n > 40 for n in page_characters),
                    'identity_verified': True, 'report_type_verified': True, 'scope_evidence': scope,
                    'period_evidence': period_declaration.group(0) if period_declaration else f'封面前三页明确包含 {year} 报告年度',
                    'boundary_status': 'report_scope_recorded_metric_scope_requires_pipeline',
                    'version_query': discovered.get('version_review'), 'language': 'Chinese',
                    'title': metadata['announcement_title']}
            cache = root / 'backend/runtime/connectivity/sources' / (digest + '.pdf')
            cache.parent.mkdir(parents=True, exist_ok=True)
            if not cache.exists():
                # 同一文件哈希复用一个对象；临时下载不会进入报告目录。
                path.replace(cache)
            else:
                with cache.open('rb') as handle:
                    if hashlib.file_digest(handle, 'sha256').hexdigest() != digest:
                        raise ValueError('已有 PDF 缓存被修改，停止接入')
            documents.append({'document_id': f"D-{company['ticker']}-{year}-{kind}-{digest[:16]}",
                'case_id': 'pending', 'company_id': company['ticker'],
                'company': company.get('company_alias') or company.get('company_name'), 'report_type': kind,
                'period': year, 'report_period': year, 'version': metadata['announcement_title'],
                'version_role': 'correction' if metadata.get('is_revised') else 'original',
                'source_url': url, 'source_kind': 'official', 'disclosure_date': metadata['announcement_date'],
                'retrieved_at': datetime.now(timezone.utc).isoformat(), 'compilation_basis': '待指标核验阶段从原文核对',
                'pages': pages, 'file_sha256': digest, 'available': True})
            cache_document(root, documents[-1])
        identity = hashlib.sha256('|'.join(d['file_sha256'] for d in sorted(documents, key=lambda d: d['report_type'])).encode()).hexdigest()[:16]
        pair_id = f"CONNPAIR-{company['ticker']}-{year}-{identity}"
        previous = next((r for r in records if r['pair_id'] == pair_id), None)
        for document in documents:
            document['case_id'] = pair_id
            # 相同年报可参与两版 ESG 配对；一文档一 case_id 的旧合同要求引用编号也带配对身份。
            old = next((d for d in (previous or {}).get('documents', [])
                if d['report_type'] == document['report_type'] and d['file_sha256'] == document['file_sha256']), None)
            document['document_id'] = old['document_id'] if old else document['document_id'] + '-' + identity[:8]
        record = {'pair_id': pair_id, 'company_id': company['ticker'],
            'company': documents[0]['company'], 'period': year, 'industry': industry,
            'documents': documents, 'download_status': 'complete', 'validation_status': 'verified',
            'parse_status': 'complete', 'inspection': inspections, 'model_status': 'not_run',
            'demo_status': 'not_evaluated', 'created_at': datetime.now(timezone.utc).isoformat(),
            'capabilities': ['registered_pdf_extraction', 'six_rule_candidate_check', 'financial_semantic_mapping', 'three_agents'],
            'limitations': ['原件技术身份通过不等于指标可比；主体、范围、定义和单位须在每条关系中独立验证',
                '资本投入与资产增加不作自动等额映射；模型尚未运行',
                '修订状态基于有界官方标题检索，不保证覆盖所有历史公告']}
        record['limitations'].append('本轮逐页解析文字层；图像内指标未做 OCR，不代表全指标覆盖')
        if previous:
            # 重复准备同一版本不清空它已经取得的程序与模型运行事实。
            for field in ('model_status', 'demo_status', 'last_program_run', 'last_model_run',
                          'demo_evaluation', 'industry', 'industry_profile', 'industry_evidence'):
                if field in previous:
                    record[field] = previous[field]
        emit('registry', 'running', '保存不可变双报告版本与来源')
        return save_pair(root, record)
    finally:
        for path in temporary.glob('*'):
            path.unlink(missing_ok=True)
        if temporary.is_dir():
            temporary.rmdir()
        capacity.__exit__(None, None, None)
