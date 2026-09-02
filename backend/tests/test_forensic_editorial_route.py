"""独立 Forensic Editorial 页面保留兼容入口，根页由正式 V4 工作台提供。"""

from fastapi.testclient import TestClient

from backend.app.main import WORKSPACE_ROOT, app


client = TestClient(app)


def test_forensic_editorial_page_is_served() -> None:
    response = client.get("/forensic-editorial/")
    assert response.status_code == 200
    assert "审迹智链 · Forensic Editorial Workspace" in response.text
    assert 'data-view-panel="analysis"' in response.text


def test_forensic_editorial_assets_are_served() -> None:
    css = client.get("/forensic-editorial/styles.css")
    script = client.get("/forensic-editorial/app.js")
    icons = client.get("/forensic-editorial/assets/icons.svg")
    assert css.status_code == 200
    assert "--bg-primary: #090b0f" in css.text
    assert "--accent-primary: #7c9fd2" in css.text
    assert script.status_code == 200 and 'const API_BASE' in script.text
    assert icons.status_code == 200 and 'id="search"' in icons.text


def test_root_page_still_returns_the_original_file() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.content == (WORKSPACE_ROOT / "index.html").read_bytes()


def test_root_index_contains_the_current_main_workbench() -> None:
    """主页面是竞赛演示版工作台：单一主按钮、抽屉式证据/Agent 明细，不含旧控制台控件。"""
    text = (WORKSPACE_ROOT / "index.html").read_text(encoding="utf-8")
    assert "上市公司年报风险预筛" in text
    assert 'id="demo-start"' in text
    assert 'id="demo-open-all-cases"' in text
    assert 'id="demo-open-evidence"' in text
    assert 'id="demo-open-agents"' in text
    assert 'id="demo-tech-drawer"' in text
    assert 'id="case-import-form"' not in text
    # 0.10.0 增加由本机现场开关保护的巨潮公开样例入口，但仍不恢复旧上传/导入控制台。
    assert 'id="demo-live-sample-form"' in text
    assert 'type="file"' not in text

