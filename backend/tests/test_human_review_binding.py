"""人工复核必须能归属到真人：默认不得是 human，自称真人要校验并由服务端盖章。

覆盖 2026-09-15 审查 R-04：`HumanReviewRequest.reviewer_type` 旧默认值为
"human"，任何拿到合法写权限的自动化调用方都能一次 POST 解锁正式缓存与导出。
"""
from __future__ import annotations

import io
import re
import zipfile

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import HumanReviewRequest


client = TestClient(app)


def _create_run() -> dict:
    response = client.post(
        "/api/runs",
        json={"current_year": 2023, "rule_ids": ["R1", "R2"], "check_model": False},
    )
    assert response.status_code == 200
    return response.json()


def test_reviewer_type_defaults_to_automation() -> None:
    """缺省值必须是 automation：真人身份要显式声明，不能靠不填蒙过去。"""

    assert HumanReviewRequest(status="暂缓").reviewer_type == "automation"


def test_automation_review_cannot_unlock_formal_cache_but_report_is_watermarked() -> None:
    """自动化不能写正式缓存；自动化产出的报告必须自带"未经真人复核"水印。"""

    run = _create_run()
    reviewed = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={"status": "保留为待核查候选", "reviewer": "流水线", "export_approved": True},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["human_review"]["reviewer_type"] == "automation"
    assert client.post(f"/api/runs/{run['run_id']}/cache").status_code == 409
    report = client.get(f"/api/runs/{run['run_id']}/report.docx")
    assert report.status_code == 200
    with zipfile.ZipFile(io.BytesIO(report.content)) as archive:
        body = re.sub(r"<[^>]+>", " ", archive.read("word/document.xml").decode("utf-8"))
    assert "自动化" in body
    assert "未经真人" in body or "尚未经真人" in body or "不构成审计结论" in body


def test_human_claim_without_a_name_is_rejected() -> None:
    run = _create_run()
    reviewed = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={"status": "保留为待核查候选", "reviewer": "   ", "reviewer_type": "human", "export_approved": True},
    )
    assert reviewed.status_code == 422
    assert "复核人姓名" in reviewed.text


def test_human_claim_is_stamped_with_server_side_identity() -> None:
    run = _create_run()
    reviewed = client.post(
        f"/api/runs/{run['run_id']}/review",
        json={
            "status": "保留为待核查候选",
            "reviewer": "张复核",
            "reviewer_type": "human",
            "export_approved": True,
            # 客户端自报归属字段必须被服务端覆盖。
            "reviewer_user_id": "伪造身份",
            "reviewer_source": "伪造来源",
        },
    )
    assert reviewed.status_code == 200
    stored = reviewed.json()["human_review"]
    assert stored["reviewer_user_id"] == "local-dev"
    assert stored["reviewer_source"] == "local"
    assert client.post(f"/api/runs/{run['run_id']}/cache").status_code == 200
