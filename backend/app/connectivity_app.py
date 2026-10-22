"""正式发布入口仅公开年报与可持续报告核验。

旧主模块暂作为额度、代理与安全响应头的公共依赖保留。
这里不挂载旧审计、案例管理、RAG和行业规则路由。
后续拆出公共模块前不可直接删除其传递依赖。
"""
from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.gzip import GZipMiddleware

from .main import _enforce_public_model_quota, _public_model_ledger, security_headers
from .connectivity_api import build_router
from .connectivity_facts import project_facts

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title='审迹智链 跨报告自主核验', version='2026.10.22')
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.middleware('http')(security_headers)
app.mount('/assets', StaticFiles(directory=ROOT/'assets'), name='assets')
app.include_router(build_router(ROOT, lambda request: _enforce_public_model_quota(request, force=True), _public_model_ledger))


@app.get('/', include_in_schema=False)
def home():
    """首页仍使用既有根文件，不创建另一套展示页。"""
    return FileResponse(ROOT/'index.html')


@app.get('/api/health')
def health():
    """配置存在只报告 configured，不等同真实模型验收。"""
    return {'service_status': 'ready', 'product': 'connectivity',
        'model_status': 'configured' if os.getenv('DEEPSEEK_API_KEY', '').strip() else 'config_missing',
        'model_id': os.getenv('DEEPSEEK_MODEL', 'deepseek-flash'),
        'default_mode': 'three_agents', 'project_facts': project_facts(ROOT)}
