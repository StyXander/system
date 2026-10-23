"""原实例重启后读取全部原件；另用空实例恢复一组动态双报告，严格对齐哈希。"""
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')
from backend.app.connectivity_bootstrap import source_readiness
from backend.app.connectivity_extraction import load_registry, ensure_source

OUT = ROOT / 'outputs/enterprise-expansion'
os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE'] = 'local'
ready = source_readiness(ROOT)
(OUT / 'source-readiness-restart.json').write_text(json.dumps(ready, ensure_ascii=False, indent=2), encoding='utf-8')
assert ready['ready'], '有原件未通过重新读取，不宣称就绪'
os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE'] = 'supabase'
with tempfile.TemporaryDirectory(prefix='audittrace-pair-recovery-') as folder:
    fresh = Path(folder)
    documents = [d for d in load_registry(fresh) if d.company_id == '601012']
    assert len(documents) == 2
    for document in documents:
        path = ensure_source(fresh, document)
        with path.open('rb') as handle:
            assert hashlib.file_digest(handle, 'sha256').hexdigest() == document.file_sha256
    pair = source_readiness(fresh, pair_id=documents[0].case_id)
    assert pair['ready']
    receipt = {'status': 'passed', 'backend': 'supabase', 'local_snapshot_present': False,
        'fresh_instance_both_pdfs_downloaded': True, 'pair_id': documents[0].case_id,
        'documents': [{'document_id': d.document_id, 'sha256': d.file_sha256, 'pages': d.pages} for d in documents],
        'readiness': pair}
(OUT / 'fresh-instance-pair-recovery.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'all_local_pairs_ready': True, 'fresh_instance_pair_ready': True}, ensure_ascii=False))
