"""历史书签进入正式工作台，不再依赖未入库的旧页面资源。"""

from fastapi.testclient import TestClient
import pytest

from backend.app.main import WORKSPACE_ROOT, app


pytestmark = pytest.mark.repository_only

client = TestClient(app)


def test_forensic_editorial_bookmark_redirects_to_current_workspace() -> None:
    for path in ("/forensic-editorial", "/forensic-editorial/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 308
        assert response.headers["location"] == "/"
        assert client.get(path).content == (WORKSPACE_ROOT / "index.html").read_bytes()


def test_retired_assets_are_not_silently_served_from_local_untracked_files() -> None:
    css = client.get("/forensic-editorial/styles.css")
    script = client.get("/forensic-editorial/app.js")
    icons = client.get("/forensic-editorial/assets/icons.svg")
    assert css.status_code == script.status_code == icons.status_code == 404


def test_root_page_still_returns_the_original_file() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == (WORKSPACE_ROOT / "index.html").read_bytes()


def test_root_index_contains_the_current_main_workbench() -> None:
    """主页面是竞赛演示版工作台：单一主按钮、抽屉式证据/Agent 明细，不含旧控制台控件。"""
    text = (WORKSPACE_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="connectivity-root"' in text
    assert 'id="cn-form"' in text
    assert 'id="cn-collaboration"' in text
    assert 'id="legacy-workspace"' not in text
    assert 'demo-app.js' not in text
    assert 'id="case-import-form"' not in text
    # 0.10.0 增加由本机现场开关保护的巨潮公开样例入口，但仍不恢复旧上传/导入控制台。
    assert 'id="cn-pair"' in text
    assert 'type="file"' not in text

