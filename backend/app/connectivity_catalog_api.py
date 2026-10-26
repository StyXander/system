"""把企业身份发现接入正式双报告工作台，重型准备沿用现有任务存储和权限。

搜索、元数据查询和重型接入使用不同的授权边界。
匿名访客可查询身份和公告元数据，但不能据此无限下载。
公网接入要求真实登录并具备组织写权限。
付费模型新调用另行校验身份，并继续经过原配额账本。
本地模式只接受本机连接的操作员身份，不能用于公网绕过认证。
客户端只能确认官方候选中的版本，不能提交自定义下载地址。
同源限制阻止第三方页面借已登录会话发起接入。
查询共用已有有界限流，不引入第二套身份目录。
后台准备采用既有任务持久化与失败状态。
幂等键绑定操作者和两份官方原件地址。
相同提交返回原任务，不重复创建模型或下载任务。
完成的目录包含报告版本，而准备进度留在任务回执。
读取准备进度也必须校验操作者，任务编号不是授权凭据。
工作台只在登记完成后才向原核验入口传入 pair_id。
失败信息保持明确，不以旧销售收款分析代替双报告结果。
"""
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field

from . import company_discovery as discovery
from .cninfo import CNInfoError, china_today
from .connectivity_catalog import company_cards, remote_enabled
from .connectivity_onboarding import discover_pair, prepare_pair
from .connectivity_schemas import Contract, ReportDocument
from .demo_run_tasks import DemoRunTaskStore, SupabaseDemoRunTaskStore, IdempotencyConflict
from .supabase_adapter import get_demo_task_client, SupabaseError, SupabaseAuthError
from .auth import session_access_token, CASE_WRITE_ROLES, REFRESH_COOKIE_NAME
from .schemas import AuthLoginRequest
from .connectivity_access import single_user_enabled


class ImportRequest(Contract):
    ticker: str = Field(pattern=r'^\d{6}$')
    year: int = Field(ge=2000, le=2100)
    confirmed_identity: bool = False
    annual_url: str = Field(default='', max_length=500)
    sustainability_url: str = Field(default='', max_length=500)


class ReportRangeImportRequest(Contract):
    ticker: str = Field(pattern=r'^\d{6}$')
    years: list[int] = Field(min_length=1, max_length=5)
    confirmed_identity: bool = False


def can_import(request: Request) -> str:
    """公网不以会话 Cookie 代替认证；管理员或审核员才可触发新 PDF 下载。"""
    if single_user_enabled():
        return 'single_user_operator'
    public = os.getenv('AUDITTRACE_PUBLIC_DEMO', '').lower() in {'true', '1', 'yes'}
    if not public and request.client and request.client.host in {'127.0.0.1', '::1', 'testclient'}:
        return 'local_operator'
    token = session_access_token(request)
    if not token:
        raise HTTPException(401, '新报告下载与解析需要登录后的接入权限；已验证案例仍可选择。')
    try:
        client = get_demo_task_client()
        user = client.verify_user(token)
        memberships = client.list_memberships(str(user.get('id') or ''), token=token)
        if not any(row.get('role') in CASE_WRITE_ROLES for row in memberships):
            raise HTTPException(403, '当前账号没有公开报告接入权限。')
        return str(user['id'])
    except SupabaseAuthError as error:
        raise HTTPException(401, '登录状态无效或已过期。') from error
    except SupabaseError as error:
        raise HTTPException(503, '接入身份服务暂不可用，未启动下载。') from error


def authorize_model(request: Request) -> None:
    """公开实例的付费新调用必须有真实登录；原有配额仍在调用前统一预留。"""
    if single_user_enabled() or os.getenv('AUDITTRACE_PUBLIC_DEMO', '').lower() not in {'true', '1', 'yes'}:
        return
    token = session_access_token(request)
    if not token:
        raise HTTPException(401, '真实模型核验需要登录；可选择程序核验或查看已完成任务。')
    try:
        client = get_demo_task_client()
        user = client.verify_user(token)
        if not client.list_memberships(str(user.get('id') or ''), token=token):
            raise HTTPException(403, '当前账号没有核验权限。')
    except SupabaseAuthError as error:
        raise HTTPException(401, '登录状态无效或已过期，未发送模型请求。') from error
    except SupabaseError as error:
        raise HTTPException(503, '模型调用前的身份核验暂不可用，未发送请求。') from error


def failure(error: CNInfoError):
    return HTTPException(429 if error.code == 'DISCOVERY_RATE_LIMITED' else 409 if error.code == 'DISCOVERY_BUSY'
        else 404 if error.code == 'COMPANY_NOT_FOUND' else 422 if error.code == 'REPORT_YEAR_INVALID' or error.code.startswith('COMPANY_') else 503,
        {'code': error.code, 'message': error.message}, headers={'Retry-After': '20'})


def build_catalog_router(root: Path) -> APIRouter:
    router = APIRouter(tags=['connectivity-company-discovery'])
    stores = {}
    pending = {}
    pending_lock = RLock()

    def runtime():
        mode = 'supabase' if remote_enabled() else 'local'
        if mode not in stores:
            stores[mode] = SupabaseDemoRunTaskStore(get_demo_task_client()) if mode == 'supabase' else DemoRunTaskStore(
                root / 'backend/runtime/connectivity/import_tasks', task_id_prefix='CIMPORT')
        return stores[mode]

    def quota(request: Request):
        # 与已有企业身份查询共用限流账本，不再新建匿名网络配额系统。
        discovery.enforce_discovery_quota(request.client.host if request.client else 'unknown')

    def same_origin(request: Request):
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, '会话请求必须来自当前工作台。')

    def signed_user(token: str):
        """沿用原 Auth 适配器和成员表，只返回身份摘要，令牌不进入 JSON。"""
        client = get_demo_task_client()
        user = client.verify_user(token)
        rows = client.list_memberships(str(user.get('id') or ''), token=token)
        if not rows:
            raise HTTPException(403, '当前账号没有有效组织成员身份。')
        return {'authenticated': True, 'user': {'user_id': user['id'], 'role': rows[0]['role']},
            'can_import': any(r.get('role') in CASE_WRITE_ROLES for r in rows), 'http_only': True}

    @router.get('/api/auth/me')
    def me(request: Request):
        if single_user_enabled():
            return {'authenticated': False, 'authentication_required': False,
                    'single_user': True, 'local_operator': True, 'can_import': True}
        required = os.getenv('AUDITTRACE_PUBLIC_DEMO', '').lower() in {'true', '1', 'yes'}
        token = session_access_token(request)
        if not token:
            return {'authenticated': False, 'authentication_required': required, 'local_operator': not required}
        try:
            return {**signed_user(token), 'authentication_required': required}
        except SupabaseAuthError as error:
            raise HTTPException(401, '会话已过期，请重新登录。') from error
        except SupabaseError as error:
            raise HTTPException(503, '身份服务暂不可用。') from error

    @router.post('/api/auth/login')
    def login(body: AuthLoginRequest, request: Request, response: Response):
        same_origin(request)
        quota(request)
        from .main import _set_session_cookies
        try:
            session = get_demo_task_client().sign_in_with_password(email=body.email, password=body.password.get_secret_value())
            result = signed_user(session['access_token'])
            _set_session_cookies(response, session)
            return result
        except SupabaseAuthError as error:
            raise HTTPException(401, '邮箱或密码无效。') from error
        except SupabaseError as error:
            raise HTTPException(503, '身份服务暂不可用。') from error

    @router.post('/api/auth/refresh')
    def refresh_session(request: Request, response: Response):
        same_origin(request)
        quota(request)
        token = request.cookies.get(REFRESH_COOKIE_NAME)
        if not token:
            raise HTTPException(401, '请先登录。')
        from .main import _set_session_cookies
        try:
            session = get_demo_task_client().refresh_session(refresh_token=token)
            result = signed_user(session['access_token'])
            _set_session_cookies(response, session)
            return result
        except SupabaseAuthError as error:
            raise HTTPException(401, '会话已过期，请重新登录。') from error
        except SupabaseError as error:
            raise HTTPException(503, '身份服务暂不可用。') from error

    @router.post('/api/auth/logout')
    def logout(request: Request, response: Response):
        same_origin(request)
        from .main import _clear_session_cookies
        _clear_session_cookies(response)
        return {'authenticated': False}

    @router.get('/api/connectivity/catalog')
    def catalog(request: Request, q: str = Query('', max_length=120), industry: str = Query('', max_length=60),
                year: str = Query('', pattern=r'^\d{4}$|^$'), state: str = Query('', pattern=r'^(ready|paired|partial)?$')):
        rows, persistence = company_cards(root)
        needle = q.strip().lower()
        rows = [r for r in rows if (not needle or needle in (r['company'] + r['company_id']).lower())
                and (not industry or r['industry'] == industry) and (not year or r['period'] == year)
                and (not state or r['state'] == state)]
        try:
            allowed = bool(can_import(request))
        except HTTPException:
            allowed = False
        return {'items': rows, 'persistence': persistence, 'can_import': allowed,
            'boundary': '可运行表示已登记双报告；模型参与状态须查看本次运行回执。'}

    @router.get('/api/companies/search')
    def search(request: Request, q: str = Query(min_length=1, max_length=120)):
        quota(request)
        try:
            result = discovery.search(root, q)
        except CNInfoError as error:
            raise failure(error) from error
        cards, _ = company_cards(root)
        for row in result['candidates']:
            pairs = [r for r in cards if r['company_id'] == row['ticker']]
            row['report_pairs'] = pairs
            row['state'] = 'ready' if any(p['state'] == 'ready' for p in pairs) else 'paired' if any(p['state'] == 'paired' for p in pairs) else 'partial' if pairs else 'identity_only'
            row['next_action'] = 'confirm_identity'
        return result

    @router.get('/api/companies/{ticker}/report-pair')
    def reports(ticker: str, request: Request, year: int = Query(ge=2000, le=2100)):
        quota(request)
        try:
            return discover_pair(root, ticker, year)
        except CNInfoError as error:
            raise failure(error) from error

    @router.post('/api/connectivity/catalog/imports', status_code=202)
    def start(body: ImportRequest, request: Request):
        user = can_import(request)
        if not body.confirmed_identity:
            raise HTTPException(422, '请先确认企业身份。')
        origin = request.headers.get('origin')
        if origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, '接入请求必须来自当前工作台。')
        quota(request)
        try:
            discovered = discover_pair(root, body.ticker, body.year)
        except CNInfoError as error:
            raise failure(error) from error
        for field, supplied, candidates in [('annual', body.annual_url, 'annual_candidates'),
                ('sustainability', body.sustainability_url, 'sustainability_candidates')]:
            if supplied:
                selected = next((r for r in discovered[candidates] if r['source_url'] == supplied), None)
                if selected is None:
                    raise HTTPException(422, '所选报告不在本次官方候选池中。')
                discovered[field] = {**selected, 'report_type': 'AR' if field == 'annual' else 'ESG'}
        if discovered['state'] != 'paired':
            raise HTTPException(422, '尚未形成完整且查询无截断的同年度双报告。')
        store = runtime()
        fingerprint = hashlib.sha256('|'.join(discovered[k]['source_url'] for k in ('annual', 'sustainability')).encode()).hexdigest()
        owner = hashlib.sha256(user.encode()).hexdigest()
        run_body = {'kind': 'connectivity_import', 'owner': owner, 'ticker': body.ticker, 'year': body.year,
            'source_fingerprint': fingerprint}

        def execute(item):
            events = []
            def progress(stage, state, detail):
                event = {'stage': stage, 'status': state, 'detail': detail,
                    'updated_at': datetime.now(timezone.utc).isoformat()}
                events.append(event)
                # 通用任务的六个核验阶段不用于下载准备，进度通过原有 result 字段持久化。
                store.update_task(item['task_id'], result={'import_progress': event, 'import_events': list(events), 'model_status': 'not_run'})
            try:
                record = prepare_pair(root, discovered, progress=progress)
                store.update_task(item['task_id'], status='completed', result={'pair_id': record['pair_id'],
                    'company': record['company'], 'validation_status': record['validation_status'],
                    'import_events': events, 'model_status': 'not_run'})
            finally:
                with pending_lock:
                    pending.pop(item['task_id'], None)
        with pending_lock:
            for key in list(pending):
                row = store.get(key)
                if not row or row['status'] not in {'queued', 'running'}:
                    pending.pop(key, None)
                elif row.get('run_body', {}).get('owner') == owner and row['run_body'].get('source_fingerprint') == fingerprint:
                    return {'task_id': row['task_id'], 'status': row['status']}
            if len(pending) >= 4:
                raise HTTPException(429, '本实例已有四项报告准备任务，请稍后再试。', headers={'Retry-After': '30'})
            try:
                item = store.create('IMPORT-' + body.ticker + '-' + str(body.year), run_body, execute,
                    idempotency_key=request.headers.get('idempotency-key'))
                if item['status'] in {'queued', 'running'}:
                    pending[item['task_id']] = True
            except IdempotencyConflict as error:
                raise HTTPException(409, str(error)) from error
        return {'task_id': item['task_id'], 'status': item['status']}

    @router.get('/api/connectivity/catalog/imports/{task_id}')
    def read_import(task_id: str, request: Request):
        user = can_import(request)
        item = runtime().get(task_id)
        if not item or item.get('run_body', {}).get('kind') != 'connectivity_import':
            raise HTTPException(404, '报告接入任务不存在。')
        if not hmac.compare_digest(item['run_body'].get('owner', ''), hashlib.sha256(user.encode()).hexdigest()):
            raise HTTPException(403, '只能查看当前账号创建的接入任务。')
        snapshot = runtime().snapshot(task_id) or {}
        return {k: snapshot.get(k) for k in ('task_id', 'status', 'stages', 'result', 'error', 'failure_code', 'updated_at')}

    @router.post('/api/connectivity/catalog/report-set-imports', status_code=202)
    def start_range(body: ReportRangeImportRequest, request: Request):
        user = can_import(request)
        same_origin(request)
        quota(request)
        if not body.confirmed_identity or any(year < 2000 or year > china_today().year for year in body.years):
            raise HTTPException(422, '请确认企业身份并选择有效年度')
        years = sorted(set(body.years))
        store = runtime()
        owner = hashlib.sha256(user.encode()).hexdigest()
        def execute(item):
            documents = []
            gaps = []
            events=[]
            def save_progress(year, status, message):
                from .connectivity_schemas import now_iso
                events.append({'year':year,'status':status,'message':message,'updated_at':now_iso()})
                store.update_task(item['task_id'], result={'import_progress':events[-1], 'import_events':list(events),
                    'documents':[d.model_dump(mode='json') for d in documents], 'coverage_gaps':list(gaps),'model_status':'not_run'})
            for year in years:
                save_progress(year,'source_candidates','正在查询官方公告；此前年度资料保留')
                try:
                    discovered = discover_pair(root, body.ticker, year)
                except CNInfoError as error:
                    # 主体与参数错误仍是硬门禁；仅官方临时失败不取消其他年份。
                    if any(marker in error.code for marker in ('TIMEOUT','NETWORK','HTTP','RATE','BUSY','UNAVAILABLE')):
                        gaps.append(f'{year}年官方源暂不可达（{error.code}），不代表企业未披露')
                        save_progress(year,'source_unavailable',gaps[-1]);continue
                    raise
                if not discovered.get('query_complete'):
                    gaps.append(f'{year}年官方查询被截断，需补查后再纳入')
                    save_progress(year,'source_unavailable',gaps[-1]);continue
                if not discovered.get('annual') and not discovered.get('sustainability'):
                    gaps.append(f'{year}年本次查询未检索到报告候选，不等于企业未披露')
                    save_progress(year,'unsupported_or_missing',gaps[-1]);continue
                prepared = prepare_pair(root, discovered, allow_partial=True,
                    progress=lambda stage,status,message:save_progress(year,stage,message))
                candidates=[ReportDocument.model_validate(d) for d in prepared['documents']]
                from .disclosure_dates import document_date_issue
                for document in candidates:
                    issue=document_date_issue(document,china_today())
                    if issue:
                        gaps.append(f"{document.document_id}：{issue['code']}；{issue['message']}")
                    else:documents.append(document)
                gaps.extend(f'{year}年本次资料缺少{kind}' for kind in discovered.get('missing', []))
                if prepared.get('state')=='partial_readable':
                    gaps.append(f'{year}年部分页面需OCR，仅对可读证据有限调查')
                # 每年立即保存合格资料集合，下一年硬错误也不会丢失已核实年度。
                if documents:
                    from .connectivity_report_sets import canonical_documents, make_report_set, save_report_set
                    partial_docs=canonical_documents(documents)
                    partial_set=make_report_set(partial_docs,china_today())
                    save_report_set(root,partial_set,partial_docs)
                save_progress(year,'needs_ocr' if prepared.get('state')=='partial_readable' else 'documents_partial' if discovered.get('missing') else 'documents_ready',f'{year}年已保存{len(candidates)}份原件；本次累计{len(documents)}份日期合格资料')
            if not documents:
                raise ValueError('所选年度没有通过原件核验的资料')
            from .connectivity_report_sets import canonical_documents, make_report_set, save_report_set
            documents = canonical_documents(documents)
            report_set = make_report_set(documents, china_today())
            save_report_set(root, report_set, documents)
            store.update_task(item['task_id'], status='completed', result={'report_set': report_set.model_dump(mode='json'), 'coverage_gaps': gaps, 'import_events':events,'model_status': 'not_run'})
        with pending_lock:
            for key in list(pending):
                row=store.get(key)
                if not row or row['status'] not in {'queued','running'}:pending.pop(key,None)
            active = [store.get(key) for key in pending]
            if len(active) >= 4:
                raise HTTPException(429, '报告准备任务已满，请稍后重试')
            try:
                item = store.create('IMPORT-SET-' + body.ticker, {'kind': 'connectivity_import', 'owner': owner, 'ticker': body.ticker, 'years': years},
                    execute, idempotency_key=request.headers.get('idempotency-key'))
            except IdempotencyConflict as error:
                raise HTTPException(409,str(error)) from error
            pending[item['task_id']] = True
        return {'task_id': item['task_id'], 'status': item['status']}
    return router
