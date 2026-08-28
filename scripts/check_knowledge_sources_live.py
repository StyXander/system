"""逐条检查当前活跃知识来源的官方链接并输出追加式验收记录。

只保存状态、最终 URL 和内容哈希，不保存远程正文；网络失败按真实失败记录。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.knowledge_sources import active_source_entries, knowledge_cutoff_date, load_source_manifest


def _hash_response(response) -> tuple[str | None, int]:
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = response.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        digest.update(chunk)
    return digest.hexdigest(), total


def _check(entry: dict) -> dict:
    checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {
        "source_id": entry.get("source_id"),
        "official_url": entry.get("official_url"),
        "checked_at": checked_at,
        "http_status": None,
        "content_type": None,
        "final_url": None,
        "content_sha256": None,
        "content_bytes": None,
        "verified": False,
        "failure_code": None,
    }
    request = Request(
        str(entry.get("official_url") or ""),
        headers={"User-Agent": "AuditTrace-Knowledge-Check/1.0", "Accept": "application/pdf,text/html,*/*"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result["http_status"] = int(getattr(response, "status", 200))
            result["content_type"] = response.headers.get("Content-Type")
            result["final_url"] = response.geturl()
            result["content_sha256"], result["content_bytes"] = _hash_response(response)
            result["verified"] = result["http_status"] == 200 and bool(result["content_sha256"])
            if not result["verified"]:
                result["failure_code"] = "SOURCE_HTTP_NOT_OK"
    except HTTPError as error:
        result["http_status"] = int(error.code)
        result["final_url"] = error.geturl()
        result["content_type"] = error.headers.get("Content-Type") if error.headers else None
        result["failure_code"] = f"SOURCE_HTTP_{error.code}"
    except (URLError, TimeoutError, OSError) as error:
        result["failure_code"] = "SOURCE_NETWORK_ERROR"
        result["failure_detail"] = f"{type(error).__name__}: {str(error)[:240]}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="outputs/knowledge-live-check-20260826.json")
    args = parser.parse_args()
    entries, error = load_source_manifest(ROOT / "backend" / "knowledge_sources.manifest.json")
    cutoff = knowledge_cutoff_date()
    if error:
        raise SystemExit(error)
    active = active_source_entries(entries, cutoff)
    checks = [_check(entry) for entry in active]
    payload = {
        "schema_version": "knowledge_live_check_v1",
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff_date": cutoff,
        "coverage_status": "representative",
        "active_source_count": len(active),
        "verified_count": sum(1 for item in checks if item["verified"]),
        "checks": checks,
        "boundary": "只验证登记官方链接当前可回查；不宣称全量五年覆盖。",
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "active": len(active), "verified": payload["verified_count"]}, ensure_ascii=False))
    return 0 if payload["verified_count"] == len(active) else 2


if __name__ == "__main__":
    raise SystemExit(main())
