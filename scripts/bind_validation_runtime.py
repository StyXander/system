"""Bind a local frozen pack to exact same-source runtime fragments, never fuzzy evidence.

Splitting one source block into several blocks is allowed only when normalized text
matches in full and document hash/page match. Unknown text causes a hard failure.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def compact(text):return re.sub(r'\s+','',text)


def bind_ids(local,remote,ids):
    source={e['evidence_id']:e for e in local};runtime={e['evidence_id']:e for e in remote}
    bound=[];mapping={}
    for eid in ids:
        if eid not in source:raise ValueError('LOCAL_EVIDENCE_MISSING')
        original=source[eid]
        if eid in runtime:
            candidate=runtime[eid]
            if any(original.get(k)!=candidate.get(k) for k in ['document_id','source_sha256','pdf_page']) or compact(original['quote'])!=compact(candidate['quote']):
                raise ValueError('EVIDENCE_IDENTITY_COLLISION')
            mapped=[eid]
        else:
            text=compact(original['quote']);position=0;mapped=[]
            candidates=[e for e in remote if e.get('source_verified') and not e.get('invalid_reason')
                and all(e.get(k)==original.get(k) for k in ['document_id','source_sha256','pdf_page'])]
            while position<len(text):
                fits=[e for e in candidates if compact(e['quote']) and text.startswith(compact(e['quote']),position)]
                if not fits:raise ValueError('EXACT_RUNTIME_FRAGMENT_BINDING_UNAVAILABLE: '+eid)
                e=max(fits,key=lambda x:len(compact(x['quote'])));mapped.append(e['evidence_id']);position+=len(compact(e['quote']))
        mapping[eid]=mapped;bound.extend(mapped)
    return sorted(set(bound)),mapping


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--case-id',required=True)
    p.add_argument('--source-root',type=Path,required=True);p.add_argument('--server-screen',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE']='local'
    from backend.app.connectivity_extraction import load_registry
    from backend.app.connectivity_matter_extraction import read_corpus
    manifest=json.loads(a.manifest.read_text());case=deepcopy(next(c for c in manifest['scenarios'] if c['case_id']==a.case_id))
    task=json.loads(a.server_screen.read_text());run=task['result']
    if task['status']!='completed' or run['execution_mode']!='calculation_only':raise ValueError('COMPLETED_RULE_ONLY_SOURCE_SNAPSHOT_REQUIRED')
    if run['report_set']['document_fingerprints']!=case['source_fingerprints']:raise ValueError('SOURCE_SET_CHANGED')
    docs=[d for d in load_registry(a.source_root) if d.document_id in case['source_document_ids']]
    corpus,_=read_corpus(a.source_root,docs)
    original_ids=json.loads((a.manifest.parent/case['evidence_ids_file']).read_text())
    ids,mapping=bind_ids([e.model_dump() for e in corpus],run['matter_evidence'],original_ids)
    if not any(m['matter_id']==case['matter_id'] for m in run['matters']):raise ValueError('MATTER_BINDING_REQUIRES_REVIEW')
    target=next(m for m in run['matters'] if m['matter_id']==case['matter_id'])
    if not set(target['evidence_ids'])<=set(ids):raise ValueError('SELECTED_MATTER_IDENTITY_EVIDENCE_MISSING')
    case['evidence_ids_file']='evidence-ids.json'
    case['split']='engineering_validation'
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'evidence-ids.json').write_text(json.dumps(ids,indent=2)+'\n')
    binding={'server_screen_task':task['task_id'],'server_run_id':run['run_id'],'source_fingerprints':case['source_fingerprints'],
             'parser_coverage':run.get('matter_coverage',[]),'original_to_runtime_evidence_ids':mapping,
             'matching_rule':'same document hash and PDF page; exact full text after whitespace normalization; no deletion or paraphrase',
             'professional_labels_generated':False}
    (a.output/'binding.json').write_text(json.dumps(binding,ensure_ascii=False,indent=2)+'\n')
    (a.output/'manifest.json').write_text(json.dumps({'dataset_version':'runtime-bound-v1','scenarios':[case]},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'input_fragments':len(original_ids),'runtime_fragments':len(ids),'split_mappings':sum(len(v)>1 for v in mapping.values())}))
