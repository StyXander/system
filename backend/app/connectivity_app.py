"""正式发布入口仅公开年报与可持续报告核验。

旧主模块暂作为额度、代理与安全响应头的公共依赖保留。
这里不挂载旧审计、案例管理、RAG和行业规则路由。
后续拆出公共模块前不可直接删除其传递依赖。
"""
from pathlib import Path
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware

from .main import (_enforce_public_model_quota, _public_model_ledger, security_headers,
                   _validate_trusted_proxy_configuration, _configured_cors_origins)
from .connectivity_api import build_router
from .connectivity_facts import project_facts
from .connectivity_catalog_api import build_catalog_router
from .connectivity_matter_schemas import matter_enabled
from .connectivity_access import access_policy

ROOT = Path(__file__).resolve().parents[2]
@asynccontextmanager
async def lifespan(_app):
    """沿用代理配置的失败关闭检查，不恢复旧业务任务。"""
    _validate_trusted_proxy_configuration()
    yield


app = FastAPI(title='审迹智链 跨报告自主核验', version='2026.10.26.matter.1', lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(CORSMiddleware, allow_origins=_configured_cors_origins(), allow_credentials=True,
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Authorization', 'Idempotency-Key'])
app.middleware('http')(security_headers)
app.mount('/assets', StaticFiles(directory=ROOT/'assets'), name='assets')
app.include_router(build_router(ROOT, lambda request: _enforce_public_model_quota(request, force=True), _public_model_ledger))
app.include_router(build_catalog_router(ROOT))


@app.get('/', include_in_schema=False)
def home():
    """首页仍使用既有根文件，不创建另一套展示页。"""
    return FileResponse(ROOT/'index.html')


@app.get('/api/health')
def health():
    """配置存在只报告 configured，不等同真实模型验收。"""
    return {'service_status': 'ready', 'product': 'connectivity',
        **access_policy(),
        'model_status': 'configured' if os.getenv('DEEPSEEK_API_KEY', '').strip() else 'config_missing',
        'model_id': os.getenv('DEEPSEEK_MODEL', 'deepseek-flash'),
        'default_mode': 'five_agents' if matter_enabled() else 'three_agents', 'matter_schema_version': 'matter_connectivity_v1', 'frontend_release': '2026.10.27.planning.1', 'project_facts': project_facts(ROOT),
        'deployment': {'commit': os.getenv('RENDER_GIT_COMMIT') or os.getenv('GIT_COMMIT') or None,
            'platform': os.getenv('AUDITTRACE_DEPLOYMENT_PLATFORM') or ('render' if os.getenv('RENDER_GIT_COMMIT') else 'local'),
            'source_baseline_commit': os.getenv('AUDITTRACE_SOURCE_BASELINE_COMMIT') or None,
            'source_snapshot_sha256': os.getenv('AUDITTRACE_SOURCE_SNAPSHOT_SHA256') or None,
            'entry': 'backend.app.connectivity_app:app', 'release': '2026.10.26.matter.1',
            'identity_source': 'runtime_environment' if os.getenv('RENDER_GIT_COMMIT') or os.getenv('GIT_COMMIT') else 'unverified'}}
