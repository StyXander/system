"""Build reproducible first/last source extracts without padding or deleting code.

This is preparation material, not a registration or a determination of ownership.
The manifest records the original file and line for every displayed source line.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import unicodedata

from docx import Document
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]


def wrap_source(text, limit=112):
    """Display-only wrapping. Original bytes and line numbers remain in the map."""
    text=text.expandtabs(4)
    if not text:return ['']
    pieces=[];piece='';width=0
    for char in text:
        size=2 if unicodedata.east_asian_width(char) in {'W','F'} else 1
        if width+size>limit:
            pieces.append(piece);piece='';width=0
        piece+=char;width+=size
    if piece:pieces.append(piece)
    return pieces


def source_listing():
    first=['backend/app/connectivity_app.py','backend/app/connectivity_api.py',
           'backend/app/connectivity_matter_schemas.py','backend/app/connectivity_matter_pipeline.py']
    rest=[str(p.relative_to(ROOT)) for p in sorted((ROOT/'backend/app').glob('connectivity_*.py')) if str(p.relative_to(ROOT)) not in first]
    paths=first+rest
    lines=[];files={}
    for name in paths:
        raw=(ROOT/name).read_bytes();files[name]=hashlib.sha256(raw).hexdigest()
        for no,text in enumerate(raw.decode('utf-8').splitlines(),1):
            for segment,part in enumerate(wrap_source(text),1):
                lines.append({'file':name,'source_line':no,'segment':segment,'text':part})
    return lines,files


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=ROOT/'docs/copyright/current')
    p.add_argument('--name',default='审迹智链跨报告财务关联证据核验系统')
    p.add_argument('--version',default='V1.1')
    args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    listing,files=source_listing()
    # This ordering defines a complete reproducible program listing. Nothing is
    # trimmed within either continuous extract to force a particular last line.
    selected=listing if len(listing)<=3000 else listing[:1500]+listing[-1500:]
    count=(len(selected)+49)//50
    d=Document();s=d.sections[0];s.page_width=Cm(21);s.page_height=Cm(29.7)
    s.top_margin=s.bottom_margin=Cm(2);s.left_margin=s.right_margin=Cm(1.8)
    h=s.header.paragraphs[0];h.text=f'{args.name} {args.version}    '
    f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');h._p.append(f)
    for r in h.runs:r.font.name='Noto Sans CJK SC';r.font.size=Pt(8)
    for i,line in enumerate(selected):
        if i and i%50==0:d.add_page_break()
        para=d.add_paragraph();para.paragraph_format.space_before=Pt(0);para.paragraph_format.space_after=Pt(0)
        para.paragraph_format.line_spacing=Pt(12.5)
        run=para.add_run(line['text'] or ' ');run.font.name='DejaVu Sans Mono';run.font.size=Pt(6.5)
        run._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),'Noto Sans CJK SC')
    docx_path=args.output_dir/'AuditTrace_source_extract.docx';d.save(docx_path)
    (args.output_dir/'AuditTrace_source_extract.txt').write_text('\n'.join(x['text'] for x in selected)+'\n',encoding='utf-8')
    with (args.output_dir/'source_line_map.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['page','display_line','file','source_line','wrapped_segment'])
        for i,line in enumerate(selected):w.writerow([i//50+1,i%50+1,line['file'],line['source_line'],line['segment']])
    manifest={'software_name':args.name,'version':args.version,'registration_status':'not_submitted',
              'listing_order':list(files),'files_sha256':files,'complete_display_lines':len(listing),
              'selected_display_lines':len(selected),'intended_pages':count,'display_wrap_columns':112,
              'code_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
              'note':'名称、版本、权属及鉴别要求由申请人核定；原始代码未通过删除空行或补造注释凑页。排版折行映射见CSV。',
              'docx_sha256':hashlib.sha256(docx_path.read_bytes()).hexdigest()}
    (args.output_dir/'source_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ['complete_display_lines','selected_display_lines','intended_pages']},ensure_ascii=False))


if __name__=='__main__':main()
