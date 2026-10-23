"""双报告目录：复用服务端 Supabase 元数据；本地 SQLite 与部署快照可恢复。

目录不保存分析结果。内容指纹参与 pair_id，换版只追加，不覆盖历史任务身份。
公开查询只返回上市公司公开报告元数据，不读取租户资料、模型密钥或全文。

目录有三种来源，但只有一套报告合同。
种子登记保留旧 document_id，历史任务无需迁移。
运行接入写入 SQLite 或共享 Postgres，写入失败不能降级为成功。
部署快照由接入脚本从已验证目录生成，不人工填写预期指标。
快照只承担已知来源的恢复，不证明本机已经缓存原件。
远端读取失败时返回明确的 snapshot_only 状态。
本地缓存存在和哈希正确是两个不同条件。
搜索卡片只有命中登记指纹后才标为可运行。
同年度修订报告得到新 pair_id，不替换旧配对。
共享数据库只查询公开 CONNPAIR 命名空间。
私人租户的案例和字段不进入企业搜索。
元数据更新只记录执行情况，分析意见仍保存在原任务。
企业卡片不会因为另一企业运行成功而改变模型状态。
PDF 原件按哈希保存，目录本身只保存出处与版本。
因此目录恢复和原件恢复分别验收。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from functools import lru_cache
from pathlib import Path
from threading import RLock

from .connectivity_schemas import ReportDocument

_lock = RLock()
_remote_cache: dict[str, tuple[float, list[dict]]] = {}
_remote_failures: dict[str, float] = {}


@lru_cache(maxsize=256)
def _cache_matches(path: str, size: int, modified: int, expected: str) -> bool:
    """只在缓存文件变化后重算哈希，搜索无需反复读取数百 MB 原件。"""
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest() == expected


def remote_enabled() -> bool:
    mode = os.getenv('AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE', '').strip()
    return (mode or os.getenv('AUDITTRACE_DEMO_TASK_PERSISTENCE', 'local')) == 'supabase'


def _database(root: Path):
    path = root / 'backend/runtime/connectivity/catalog.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS pairs (pair_id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS source_cache (url TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return db


def cached_documents(root: Path) -> list[dict]:
    """未组成双报告的已验证原件也可复用；该索引不赋予分析就绪资格。"""
    with _lock, _database(root) as db:
        return [json.loads(row[0]) for row in db.execute('SELECT payload FROM source_cache')]


def cache_document(root: Path, document: dict) -> None:
    with _lock, _database(root) as db:
        db.execute('INSERT INTO source_cache VALUES (?,?) ON CONFLICT(url) DO UPDATE SET payload=excluded.payload',
            (document['source_url'], json.dumps(document, ensure_ascii=False)))


def _snapshots(root: Path) -> list[dict]:
    path = root / 'backend/connectivity_catalog.snapshot.json'
    return json.loads(path.read_text(encoding='utf-8')).get('pairs', []) if path.exists() else []


def _offline_records(root: Path) -> list[dict]:
    """共享目录不可达时读取上次落盘的公开登记，不依赖进程内缓存存活。"""
    with _lock, _database(root) as db:
        return [json.loads(value) for (value,) in db.execute('SELECT payload FROM pairs')]


def export_snapshot(root: Path, records: list[dict], persistence: str) -> None:
    """部署快照原子替换，导出中断不会截断仍在被工作台读取的旧快照。"""
    path = root / 'backend/connectivity_catalog.snapshot.json'
    temporary = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(json.dumps({'schema_version': 'connectivity_catalog_v1',
            'generated_from': persistence, 'pairs': records}, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def list_pairs(root: Path, *, refresh: bool = False) -> tuple[list[dict], str]:
    """远端短缓存避免每个图谱节点一次数据库查询；故障仅回退已冻结快照。"""
    rows = {row['pair_id']: row for row in _snapshots(root)}
    status = 'local_sqlite'
    if remote_enabled():
        from .supabase_adapter import get_demo_task_client, SupabaseError
        key = str(root.resolve())
        if not refresh and time.monotonic() < _remote_failures.get(key, 0):
            rows.update({r['pair_id']: r for r in _offline_records(root)})
            rows.update({r['pair_id']: r for r in _remote_cache.get(key, (0, []))[1]})
            return list(rows.values()), 'snapshot_only_remote_unavailable'
        try:
            cached = _remote_cache.get(key)
            if refresh or not cached or time.monotonic() - cached[0] > 15:
                values = get_demo_task_client().select_table('cases',
                    filters={'case_id': 'like.CONNPAIR-*', 'tenant_id': 'is.null', 'sample_type': 'eq.public'},
                    select='case_id,metadata', service=True)
                records = [v['metadata']['connectivity_pair'] for v in values
                    if isinstance(v.get('metadata'), dict) and v['metadata'].get('product') == 'connectivity'
                    and isinstance(v['metadata'].get('connectivity_pair'), dict)]
                _remote_cache[key] = time.monotonic(), records
                _remote_failures.pop(key, None)
            rows.update({r['pair_id']: r for r in _remote_cache[key][1]})
            status = 'supabase'
        except SupabaseError:
            status = 'snapshot_only_remote_unavailable'
            _remote_failures[key] = time.monotonic() + 30
            rows.update({r['pair_id']: r for r in _offline_records(root)})
            rows.update({r['pair_id']: r for r in _remote_cache.get(key, (0, []))[1]})
    else:
        with _lock, _database(root) as db:
            rows.update({key: json.loads(value) for key, value in db.execute('SELECT pair_id,payload FROM pairs')})
    return sorted(rows.values(), key=lambda r: (r.get('company_id', ''), str(r.get('period', '')))), status


def save_pair(root: Path, record: dict) -> dict:
    """先完整校验合同再持久化；任何后端写入失败均不宣称成功。"""
    documents = [ReportDocument.model_validate(d) for d in record['documents']]
    if len(documents) != 2 or {d.report_type for d in documents} != {'AR', 'ESG'}:
        raise ValueError('必须是同公司同年度的 AR/ESG 双报告')
    if len({(d.company_id, d.period, d.case_id) for d in documents}) != 1:
        raise ValueError('企业、期间或报告对身份不一致')
    identity = hashlib.sha256('|'.join(d.file_sha256 for d in sorted(documents, key=lambda d: d.report_type)).encode()).hexdigest()[:16]
    expected = f"CONNPAIR-{documents[0].company_id}-{documents[0].period}-{identity}"
    if record['pair_id'] != expected or documents[0].case_id != expected:
        raise ValueError('报告对标识必须绑定双方版本指纹')
    if record.get('validation_status') != 'verified' or record.get('parse_status') != 'complete':
        raise ValueError('未完成来源与解析校验，不能登记为就绪报告对')
    # 全局案例可公开，但用户任务历史不能由目录枚举；只保留不可逆的关联指纹。
    for field in ('last_execution', 'last_model_run', 'last_model_attempt', 'last_program_run'):
        event = record.get(field)
        if isinstance(event, dict) and event.get('task_id'):
            event['task_reference_sha256'] = hashlib.sha256(event.pop('task_id').encode()).hexdigest()
    if remote_enabled():
        from .supabase_adapter import get_demo_task_client
        # 复用现有案例元数据表；单行事务发布完整双报告，没有中间半对可见状态。
        get_demo_task_client().insert_table('cases', [{
            'case_id': record['pair_id'], 'tenant_id': None, 'sample_type': 'public',
            'company_name': record['company'], 'ticker': record['company_id'],
            'source_snapshot_id': identity, 't0': f"{record['period']}-12-31", 'import_status': 'ready',
            'metadata': {'product': 'connectivity', 'connectivity_pair': record},
        }], service=True, upsert=True, on_conflict='case_scope')
        _remote_cache.pop(str(root.resolve()), None)
        _remote_failures.pop(str(root.resolve()), None)
    # 共享数据库是多实例主记录；成功写入后保留一份 SQLite 离线镜像。
    # 网络失效和服务重启同时发生时，也能找到本实例已核实原件的登记身份。
    with _lock, _database(root) as db:
        db.execute('INSERT INTO pairs VALUES (?,?) ON CONFLICT(pair_id) DO UPDATE SET payload=excluded.payload',
            (record['pair_id'], json.dumps(record, ensure_ascii=False)))
    return record


def registered_documents(root: Path) -> list[ReportDocument]:
    records, _ = list_pairs(root)
    return [ReportDocument.model_validate(d) for record in records
        if record.get('validation_status') == 'verified' and record.get('parse_status') == 'complete'
        for d in record.get('documents', [])]


def record_execution(root: Path, run, task_id: str) -> dict:
    """运行事实独立登记；没有真实调用就不增加模型完成数量。"""
    pair_id = run.versions.get('pair_id')
    records, _ = list_pairs(root)
    record = next((r for r in records if r['pair_id'] == pair_id), None)
    if record is None:
        return {'status': 'seed_unchanged'}
    expected = {(d['document_id'], d['file_sha256']) for d in record['documents']}
    if expected != {(d.document_id, d.file_sha256) for d in run.documents}:
        raise ValueError('运行原件不属于当前目录版本')
    calls = [c for c in run.provider_calls if c.get('performed')]
    event = {'task_reference_sha256': hashlib.sha256(task_id.encode()).hexdigest(), 'run_id': run.run_id, 'mode': run.execution_mode,
        'model_status': run.model_status, 'actual_provider_calls': len(calls),
        'input_tokens': sum(c.get('input_tokens') or 0 for c in calls),
        'output_tokens': sum(c.get('output_tokens') or 0 for c in calls),
        'actual_opinion_count': len(run.ai_opinions), 'rules_detected': sorted({c.rule_id for c in run.checks})}
    record['last_execution'] = event
    record['runnable_rules'] = event['rules_detected']
    if run.execution_mode == 'calculation_only':
        record['last_program_run'] = event
    else:
        record['last_model_attempt'] = event
        if calls:
            record['last_model_run'] = event
            record['model_status'] = run.model_status
    save_pair(root, record)
    return {'status': 'recorded', 'actual_provider_calls': len(calls)}


def company_cards(root: Path) -> tuple[list[dict], str]:
    """种子与动态目录共用可见状态；本地缓存缺失时保留待处理状态而非虚报可运行。"""
    from .connectivity_extraction import load_registry, source_path
    records, persistence = list_pairs(root)
    metadata = {r['pair_id']: r for r in records}
    grouped = {}
    for document in load_registry(root):
        row = grouped.setdefault(document.case_id, {'pair_id': document.case_id,
            'company_id': document.company_id, 'company': document.company, 'period': document.period,
            'industry': metadata.get(document.case_id, {}).get('industry', '待核行业'), 'documents': [],
            'model_status': metadata.get(document.case_id, {}).get('model_status', 'not_run')})
        path = source_path(root, document)
        stat = path.stat() if path.is_file() else None
        valid = bool(stat and _cache_matches(str(path), stat.st_size, stat.st_mtime_ns, document.file_sha256))
        row['documents'].append({'document_id': document.document_id, 'report_type': document.report_type,
            'source_url': document.source_url, 'file_sha256': document.file_sha256, 'pages': document.pages,
            'local_available': valid, 'cache_invalid': bool(stat and not valid)})
    for row in grouped.values():
        paired = {d['report_type'] for d in row['documents']} == {'AR', 'ESG'}
        # 种子报告已登记哈希但本机未缓存时，运行仍能按原 URL 恢复；展示为待准备。
        invalid = any(d['cache_invalid'] for d in row['documents'])
        row['state'] = 'partial' if invalid else 'ready' if paired and all(d['local_available'] for d in row['documents']) else 'paired' if paired else 'partial'
        row['can_run'] = paired and not invalid
        row['next_action'] = 'select_pair' if row['state'] == 'ready' else 'prepare_registered_sources' if paired else 'discover_reports'
        row['rules'] = metadata.get(row['pair_id'], {}).get('runnable_rules', [])
        row['rule_capability'] = ['EQ-001', 'RD-001', 'ENV-001', 'INT-001', 'OCC-001', 'NAR-001']
        row['limitations'] = metadata.get(row['pair_id'], {}).get('limitations', ['规则能否适用取决于实际披露与比较前提；模型状态独立记录'])
    return list(grouped.values()), persistence
