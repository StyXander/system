"""Prepare source-bound, unlabelled tasks. Never generate human answers or trial results."""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def prepare(source_root,output,as_of,remote_base=None):
    os.environ['AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE']='local'
    os.environ['AUDITTRACE_DEMO_TASK_PERSISTENCE']='local'
    from backend.app.connectivity_extraction import load_registry
    from backend.app.connectivity_matter_extraction import read_corpus,relevant_evidence
    from backend.app.connectivity_matters import seed_matters
    from backend.app.connectivity_report_sets import create_report_set
    from backend.app.connectivity_matter_schemas import ReportSetRequest
    import httpx
    output.mkdir(parents=True,exist_ok=True)
    documents=load_registry(source_root);companies=sorted({d.company_id for d in documents})
    scenarios=[];sources=[];coverage=[]
    with httpx.Client(base_url=remote_base or 'https://example.invalid',timeout=120) as client:
        if remote_base:client.get('/api/connectivity/bootstrap').raise_for_status()
        for company in companies:
            print(company,'preparing source selection',flush=True)
            docs=[d for d in documents if d.company_id==company]
            request=ReportSetRequest(document_ids=[d.document_id for d in docs],as_of_date=as_of)
            report_set=create_report_set(source_root,request)
            if remote_base:
                print(company,'verifying remote source set',flush=True)
                response=client.post('/api/connectivity/report-sets',json=request.model_dump(mode='json'));response.raise_for_status()
                if response.json()['report_set_id']!=report_set.report_set_id:raise ValueError('Local/remote report set identity mismatch')
            print(company,'indexing verified local originals',flush=True)
            corpus,cov=read_corpus(source_root,docs)
            evidence,_=relevant_evidence(corpus)
            matters=seed_matters(evidence,['climate_risk','transition_project','commitment','resource_efficiency','other'])
            byid={e.evidence_id:e for e in corpus}
            heldout=company not in {'600019','000858','000333'}
            kinds=['transition_project','climate_risk','commitment','resource_efficiency'] if heldout else ['transition_project','climate_risk']
            company_dir=output/company;company_dir.mkdir(exist_ok=True)
            for i,kind in enumerate(kinds,1):
                pool=[m for m in matters if m.matter_type==kind]
                if not pool:
                    coverage.append({'company_id':company,'kind':kind,'status':'no_candidate'});continue
                def score(m):
                    text=' '.join(byid[k].quote for k in m.evidence_ids)
                    return (not ('PDF ' in m.name),sum(t in text for t in ['项目','在建工程','投资','环保投入','万元','承诺','目标','气候']),len(text))
                matter=sorted(pool,key=score,reverse=True)[0]
                target_refs=set(matter.evidence_ids)
                # Query-independent common pack, with the chosen identity sources retained.
                pack_ids={e.evidence_id for e in evidence[:12]}|target_refs
                for typ in ('AR','ESG'):
                    target=next((e for e in evidence if e.report_type==typ),None)
                    if target:pack_ids.add(target.evidence_id)
                case_id=f'{company}-CAND-{i:02d}'
                question={
                    'transition_project':f'对于“{matter.name}”，公开报告能否直接支持与具体财务项目的关联？逐段列出已证实关系和仍需补证的环节。',
                    'climate_risk':f'对于“{matter.name}”，是否有证据表明风险已进入具体会计估计或财务项目？区分一般风险叙述与直接证据。',
                    'commitment':f'对于“{matter.name}”，哪些年份属于目标期、报告期或已发生事件？哪些承诺进展得到原文支持，哪些尚不能判断？',
                    'resource_efficiency':f'对于“{matter.name}”，节能减排或资源效率披露是否能直接关联具体财务金额？请说明口径和证据边界。'}[kind]
                scenario={'case_id':case_id,'question_id':case_id+'-Q','question':question,'research_task_type':'relation_tracing',
                    'company_id':company,'company':report_set.company,'report_set_id':report_set.report_set_id,
                    'matter_id':matter.matter_id,'matter_name':matter.name,'as_of_date':str(as_of),
                    'source_document_ids':report_set.document_ids,'source_fingerprints':report_set.document_fingerprints,
                    'source_links':{d.document_id:d.source_url for d in docs},
                    'split':'candidate_holdout' if heldout else 'development','annotation_status':'pending','annotations':[],
                    'adjudication':None,'gold_evidence_ids':[],'source_pages':[{'document_id':byid[k].document_id,'pdf_page':byid[k].pdf_page} for k in matter.evidence_ids],
                    'evidence_ids_file':f'{company}/{case_id}.evidence-ids.json'}
                (company_dir/f'{case_id}.evidence-ids.json').write_text(json.dumps(sorted(pack_ids),indent=2))
                scenarios.append(scenario)
            coverage.extend(cov)
            sources.extend([d.model_dump(mode='json') for d in docs])
            print(company,report_set.company,len(matters),'source candidates',flush=True)
    manifest={'dataset_version':'candidate-validation-v1','independent_test_completed':False,
        'sampling_note':'Source-bound candidate tasks selected before labels. Holdout status must be revised if used for debugging; no target labels are generated.',
        'scenarios':scenarios}
    raw=json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'
    (output/'cases.json').write_text(raw)
    (output/'freeze.json').write_text(json.dumps({'manifest_sha256':hashlib.sha256(raw.encode()).hexdigest(),
        'cases':len(scenarios),'companies':len(companies),'human_annotations':0,'code_commit':os.getenv('GIT_COMMIT','working_tree_before_release')},indent=2))
    (output/'sources.json').write_text(json.dumps({'documents':sources,'coverage':coverage},ensure_ascii=False,indent=2))
    for participant in ['annotator-A','annotator-B']:
        packet=json.loads(raw)
        packet['instructions']='独立查看问题与原报告作答，勿查看系统输出或其他标注者答案。填写真实匿名编号、verdict、证据与理由；空白不算已完成。关系标签为supported/limited/pending/conflicting/not_comparable/invalid。'
        packet['assigned_packet']=participant
        (output/f'{participant}.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2))
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--as-of',type=date.fromisoformat,required=True)
    p.add_argument('--remote-base')
    a=p.parse_args();prepare(a.source_root,a.output,a.as_of,a.remote_base)
