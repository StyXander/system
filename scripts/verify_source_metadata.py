"""核读已找到的官方替代源，保留原镜像登记身份，不悄悄替换历史哈希。"""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
import httpx
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.secure_download import download_bounded

url = 'https://static.cninfo.com.cn/finalpage/2025-04-26/1223329096.PDF'
target = ROOT / 'backend/runtime/connectivity/provenance/BAO24_ESG_official.pdf'
target.parent.mkdir(parents=True, exist_ok=True)
if not target.is_file() or target.stat().st_size < 100:
    with httpx.Client(timeout=90, trust_env=False, headers={'User-Agent': 'Mozilla/5.0'}) as client:
        download_bounded(url, target, client=client, max_bytes=120*1024*1024,
                         require_pdf=True, is_allowed_url=lambda candidate: candidate == url)
with pymupdf.open(target) as pdf:
    pages = len(pdf)
    text = '\n'.join(pdf[i].get_text() for i in range(min(4, pages)))
assert '2024' in text and '宝山钢铁' in text
registry = json.loads((ROOT / 'backend/connectivity_reports.json').read_text(encoding='utf-8'))
mirror = next(d for d in registry['documents'] if d['document_id'] == 'BAO24_ESG')
digest = hashlib.sha256(target.read_bytes()).hexdigest()
record = {'document_id': 'BAO24_ESG', 'official_alternative_url': url,
          'official_sha256': digest, 'pages': pages, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
          'publication_path_date': '2025-04-26', 'publication_date_basis': 'official_source_url_path',
          'registered_mirror_sha256': mirror['file_sha256'], 'byte_identical': digest == mirror['file_sha256'],
          'registry_replaced': False, 'version_role': 'unknown',
          'note': '官方与镜像分别登记身份；未以相同标题推定字节相同，也未覆盖旧运行来源'}
output = ROOT / 'outputs/ai4/official-source-verification.json'
output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
