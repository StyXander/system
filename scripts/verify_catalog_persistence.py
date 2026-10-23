"""把已验证目录同步至现有共享元数据存储，并用无本地快照的新根读取证明恢复。"""
from pathlib import Path
import json
import os
import sys
import tempfile
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from backend.app.connectivity_catalog import list_pairs, save_pair, export_snapshot

out = ROOT / 'outputs/enterprise-expansion'
out.mkdir(parents=True, exist_ok=True)
os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE'] = 'local'
records, _ = list_pairs(ROOT)
os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE'] = 'supabase'
for record in records:
    save_pair(ROOT, record)
export_snapshot(ROOT, records, 'supabase_verified_snapshot')
with tempfile.TemporaryDirectory(prefix='audittrace-catalog-recovery-') as folder:
    recovered, mode = list_pairs(Path(folder), refresh=True)
assert mode == 'supabase'
expected = {r['pair_id']: r for r in records}
actual = {r['pair_id']: r for r in recovered}
assert expected.keys() <= actual.keys()
assert all(actual[key]['documents'] == value['documents'] for key, value in expected.items())
receipt = {'status': 'passed', 'backend': mode, 'written_pairs': len(records),
    'recovered_without_local_snapshot': len(recovered), 'hashes_unchanged': True,
    'stores_pdf_bytes': False, 'recovery': 'registered_official_url_plus_sha256',
    'boundary': '数据库恢复已实测；远端原件仍须按登记 URL 和哈希恢复，官方删除时明确失败'}
(out / 'supabase-catalog-recovery.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(receipt, ensure_ascii=False))
