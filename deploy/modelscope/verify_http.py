"""核验魔搭真实接口、内容哈希和直接联网；不发起模型调用。"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "决赛准备" / "ModelScope部署_2026-10-14"
BASE = "https://burgerhaamm-audittrace.ms.show"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--session-file", type=Path)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    audit = {"base": BASE, "direct_without_proxy": args.direct, "requests": [], "provider_calls_created": 0}
    with httpx.Client(base_url=BASE, timeout=90, follow_redirects=True, trust_env=not args.direct, headers={"Referer": "https://www.modelscope.cn/", "User-Agent": "Mozilla/5.0"}) as client:
        # 平台要求先用页面生成的短期 Studio 会话建立 Cookie；不使用账户 API 密钥。
        if args.session_file:
            entry = args.session_file.read_text(encoding="utf-8").strip()
            opened = client.get(entry)
            if opened.status_code != 200:
                raise RuntimeError(f"平台会话入口 HTTP {opened.status_code}")
        for endpoint in ["/", "/api/health", "/api/status", "/api/demo/bootstrap", "/api/evidence-scenarios"]:
            response = client.get(endpoint)
            audit["requests"].append({"path": endpoint, "status": response.status_code})
            if response.status_code != 200:
                raise RuntimeError(f"{endpoint} HTTP {response.status_code}")
            if endpoint == "/":
                audit["index_sha256"] = hashlib.sha256(response.content).hexdigest()
                audit["index_matches_workspace"] = response.content == (ROOT / "index.html").read_bytes()
                for asset in sorted(set(re.findall(r'(?:src|href)="(/assets/[^"?#]+)', response.text))):
                    asset_response = client.get(asset)
                    asset_response.raise_for_status()
                    expected = ROOT / asset.lstrip("/")
                    audit["requests"].append({"path": asset, "status": asset_response.status_code, "matches_workspace": expected.is_file() and expected.read_bytes() == asset_response.content})
                audit["frame_policy"] = response.headers.get("content-security-policy")
            else:
                filename = endpoint.strip("/").replace("/", "_") + ("_direct" if args.direct else "") + ".json"
                (OUT / filename).write_text(json.dumps(response.json(), ensure_ascii=False, indent=2), encoding="utf-8")
                if endpoint == "/api/status":
                    audit["deployment"] = response.json().get("deployment")
    destination = OUT / ("HTTP直接连接验收.json" if args.direct else "HTTP接口验收.json")
    destination.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    assert audit["index_matches_workspace"]
    assert all(row.get("matches_workspace", True) for row in audit["requests"])
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
