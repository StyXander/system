"""每批独立进程完成全库回归，保留退出码、清单与JUnit，不串接历史日志。"""
from pathlib import Path
import subprocess
import sys
import os
import json
import hashlib
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/enterprise-expansion'
OUT.mkdir(parents=True,exist_ok=True)
FILES = sorted((ROOT/'backend/tests').glob('test_*.py'))
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
           AUDITTRACE_DEMO_USE_EXTERNAL_MODEL='false', DEEPSEEK_API_KEY='')
manifest = {'started_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'test_files':len(FILES),'provider_calls':0,'batches':[],
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (ROOT/'backend/app').glob('*.py')}}
for index in range(5):
    files = FILES[index::5]
    arguments = [sys.executable,'-m','pytest','-q','-p','no:cacheprovider',
                 *[str(p.relative_to(ROOT)) for p in files],
                 '--junitxml='+str(OUT/f'回归_{index+1}.xml')]
    log = OUT/f'回归_{index+1}.log'
    print(f'batch {index+1}: {len(files)} files',flush=True)
    with log.open('w',encoding='utf-8') as stream:
        result = subprocess.run(arguments,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT)
    manifest['batches'].append({'index':index+1,'files':[str(p.relative_to(ROOT)) for p in files],
                                'exit_code':result.returncode,'log':log.name})
    (OUT/'全库回归.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'batch {index+1}: exit {result.returncode}',flush=True)
manifest['source_unchanged'] = all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value
                                 for name,value in manifest['source_hashes'].items())
(OUT/'全库回归.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
raise SystemExit(0 if manifest['source_unchanged'] and all(batch['exit_code']==0 for batch in manifest['batches']) else 1)
