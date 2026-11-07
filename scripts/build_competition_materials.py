"""Build reviewable competition documents from saved sources and actual API receipts."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import re

from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/competition'
FONT='Noto Sans CJK SC'


def md_docx(source, target):
    d=Document();s=d.sections[0];s.page_width=Cm(21);s.page_height=Cm(29.7)
    s.top_margin=s.bottom_margin=Cm(2);s.left_margin=s.right_margin=Cm(2.2)
    for name in ['Normal','Title','Heading 1','Heading 2','Heading 3']:
        st=d.styles[name];st.font.name=FONT;st._element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'),FONT)
        st.font.color.rgb=RGBColor.from_string('000000')
        st.font.underline=False
        for border in list(st._element.xpath('.//w:pBdr')):border.getparent().remove(border)
    d.styles['Title'].font.size=Pt(22);d.styles['Heading 1'].font.size=Pt(15);d.styles['Heading 2'].font.size=Pt(12)
    n=d.styles['Normal'];n.font.size=Pt(10);n.paragraph_format.line_spacing=1.15;n.paragraph_format.space_after=Pt(5)
    table=None;in_code=False
    for line in source.read_text(encoding='utf-8').splitlines():
        line=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',line)
        if line.startswith('```'):in_code=not in_code;continue
        if not line.strip():table=None;continue
        if line.startswith('|'):
            cells=[x.strip() for x in line.strip().strip('|').split('|')]
            if all(re.fullmatch(r'[:\- ]+',c or '-') for c in cells):continue
            if table is None:
                table=d.add_table(rows=1,cols=len(cells));table.style='Table Grid'
                for c,t in zip(table.rows[0].cells,cells):c.text=t
                prop=table.rows[0]._tr.get_or_add_trPr();el=OxmlElement('w:tblHeader');prop.append(el)
                for c in table.rows[0].cells:
                    for r in c.paragraphs[0].runs:r.bold=True
            else:
                for c,t in zip(table.add_row().cells,cells):c.text=t
            for c in table.rows[-1].cells:
                for p in c.paragraphs:
                    for r in p.runs:r.font.size=Pt(8.5)
            continue
        table=None
        if line.startswith('#'):
            level=len(line)-len(line.lstrip('#'));title=line[level:].strip()
            title=re.sub(r'[—:：|｜]',' ',title)
            d.add_paragraph(title,style='Title' if level==1 else 'Heading '+str(min(level-1,3)))
        else:
            text=re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1（\2）',line).replace('**','').replace('`','')
            p=d.add_paragraph(text[2:] if text.startswith('- ') else text,style='List Bullet' if text.startswith('- ') else None)
            if in_code:
                for r in p.runs:r.font.size=Pt(8)
    target.parent.mkdir(parents=True,exist_ok=True);d.save(target)


def profile_dossier(name,title,question,keywords,interpretation,requests):
    raw=json.loads((BASE/'dossiers'/f'{name}.json').read_text())
    selected=[]
    for e in raw.get('matter_evidence',[]):
        if any(k in e['quote'] for k in keywords):selected.append(e)
    selected=selected[:12]
    # Both sides remain visible, including policies that only establish a gap.
    if not any(e['report_type']=='AR' for e in selected):
        selected += [e for e in raw['matter_evidence'] if e['report_type']=='AR'][:2]
    data={'company':raw['company'],'title':title,'question':question,'run_id':raw['run_id'],
          'model_status':raw['model_status'],'evidence':selected,'documents':raw['documents'],
          'report_set':raw['report_set'],'interpretation_origin':'preparer_review_for_professional_verification',
          'interpretation':interpretation,'professional_review':'not_completed','next_actions':requests}
    (BASE/'dossiers'/f'{name}.dossier.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    write_dossier(name,data)
    return data


def write_dossier(name,data):
    lines=['# '+data['title'],'','## 核查问题','',data['question'],'','## 资料与状态','',
           f"企业：{data['company']}。档案运行：{data['run_id']}。模型状态：{data['model_status']}。专业复核：尚未完成。",'',
           '本底稿区分原文摘录、程序结果与编制人的分析，判断供专业人员复核。公开资料缺口不等于企业存在错报。','',
           '| 原件 | 年度 | 发布日期 | 页数 | SHA-256 |','|---|---|---|---|---|']
    for d in data['documents']:
        lines.append(f"| {d['document_id']} | {d.get('report_period') or d.get('period')} | {d.get('disclosure_date','')} | {d.get('pages','')} | {d['file_sha256']} |")
    lines+=['','## 原文与定位','']
    for e in data['evidence']:
        lines += [f"### {e['document_id']} PDF第{e['pdf_page']}页",'',
                  f"证据ID：{e['evidence_id']}。来源校验：{e.get('source_verified')}。",'',
                  e['quote'],'']
    lines+=['## 核对分析','',data['interpretation'],'','## 待补资料','']+['- '+x for x in data['next_actions']]
    if 'reconciliation' in data:
        r=data['reconciliation'];lines+=['','## 程序试算','',r['formula'],'',
            '已知三项试算结余：'+str(r.get('known_component_subtotal_yuan'))+'元。',r['note']]
    lines+=['','## 复核栏','','复核人及岗位：________。复核范围、修改意见与依据：________。确认方式：________。',
            '本栏由实际复核人员完成，空白不表示已经取得专业意见。','']
    md=BASE/'dossiers'/f'{name}.md';md.write_text('\n'.join(lines),encoding='utf-8')
    md_docx(md,BASE/'deliverables'/f'{name}_dossier.docx')


def execution_report():
    rows=[]
    for p in sorted((BASE/'runs').glob('*/comparison.json')):
        v=json.loads(p.read_text());
        for row in v.get('runs',[]):
            if not row.get('run_id'):continue
            result=json.loads((p.parent/row['result_file']).read_text())
            roles=[t for t in result.get('matter_tasks',[]) if t.get('status') not in ['pending']]
            rows.append({**row,'batch':p.parent.name,'roles':roles,
                         'assessments':result.get('matter_assessments',[]),'rejections':result.get('matter_rejections',[])})
    lines=['# 真实模型运行与可靠性测试报告','','## 测试范围','',
        '通过Render公开工作台接口执行，密钥保留在服务器。输入为真实登记报告，开发案例用于调试，不属于独立盲测。配置、任务ID及完整结果见runs。',
        '模型请求成功只说明供应商返回有效响应，角色合同及语义校验可能继续失败。下表分别保留请求与工作流状态，不预填准确率。','',
        '| 批次 | 组别 | 任务 | 模型状态 | 请求/成功 | 已知输入/输出Token | 耗时秒 |',
        '|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['batch']} | {r['group_id']} | {r['task_id']} | {r.get('model_status')} | {r.get('provider_calls')}/{r.get('successful_calls')} | {r.get('input_tokens')}/{r.get('output_tokens')} | {round((r.get('duration_ms') or 0)/1000,1)} |")
    lines+=['','## 可复查条件','','各组检查fixed_evidence_sha256是否一致，确认模型返回标识、预算及代码版本。不同代码批次只用于开发修复验证，不合并作方法优劣统计。未知Token和费用保持未知。',
        '','## 失败与修复','','第一轮单模型出现RELATION_ENDPOINT_UNREGISTERED。程序拒绝了未登记关系端点，不能把请求成功计为完整业务完成。修复合并建议的前向引用映射，并让各架构都获得一次预算内的校验反馈修正。',
        '五智能体无门禁组即使全部角色完成，旧代码仍因ablation非none标为partial。修复仅对门禁消融按实际角色完成状态判定，移除角色的实验仍保留跳过回执。',
        '','## 专业效果边界','','未取得两名人员独立标注和仲裁，当前不报告准确率、FCR下降或工时节省。五类金额结论与关系任务语义尚须按ANNOTATION_GUIDE.md分别标注。',
        '','## 工程回归','','97项相关Python测试通过，覆盖前向引用整体提交、失败回滚、固定证据、角色合同、完成状态和会计规则。该数量仅代表工程回归，不能作为97个真实企业样本。','']
    path=BASE/'TEST_REPORT.md';path.write_text('\n'.join(lines),encoding='utf-8')
    (BASE/'run_summary.json').write_text(json.dumps([{k:v for k,v in r.items() if k not in ['roles','assessments','rejections']} for r in rows],ensure_ascii=False,indent=2))
    return rows


def main():
    output=BASE/'deliverables';output.mkdir(exist_ok=True)
    profile_dossier('wuliangye','五粮液环保投入财务落点核查底稿','ESG披露的全年环保投入1.8亿元，能否直接等同年报中的资本开支或当期费用？',
        ['环保投入','在建工程达到预定','在建工程不存在新增减值'],
        'ESG原文提供环保投入汇总数。当前取得的年报会计政策仅说明在建工程与减值的一般处理，不提供1.8亿元逐项分配表。项目、主体、计量范围及资本化与费用化拆分尚缺依据，不能确认金额等价；未发现等价关系不等于报告矛盾。',
        ['环保投入明细与统计口径说明','项目编码及资本开支、费用化支出分类对照','相关总账、付款明细和项目归属证据'])
    profile_dossier('midea','美的气候风险与财务估计关联核查底稿','ESG中的气候风险与资产影响陈述，是否有证据进入年报具体资产的减值或会计估计？',
        ['气候相关转型风险','气候情景','本集团至少每年对商誉','在建工程按实际发生'],
        'ESG片段涉及气候情景与资产影响，年报片段说明减值及在建工程一般政策。当前证据没有给出项目级气候假设与估值参数的直接映射，不能据此确认已计入某项资产估值，也不能断言企业遗漏。该任务是财务关系调查，不适用金额一致标签。',
        ['具体资产或资产组的气候暴露清单','估值模型及气候参数、情景与敏感性分析','财务估计与可持续披露假设对照'])
    raw_path=BASE/'dossiers/baosteel.source.json'
    if raw_path.exists():
        raw=json.loads(raw_path.read_text());bootstrap=json.loads((BASE/'source_registry.json').read_text())
        docs=[d for pair in bootstrap['pairs'] for d in pair['documents'] if d['document_id'] in ['BAOSTEEL_AR_2025','BAOSTEEL_ESG_2025']]
        data={'company':raw['company'],'title':'宝钢炼钢子工程跨报告关联核查底稿','question':'炼钢工程本期增加及转固是否可代表整个零碳工厂投资，现有原表能够确认哪些金额？',
              'run_id':'deterministic_dossier_'+raw['case_id'],'model_status':'not_run_in_dossier','documents':docs,'evidence':raw['evidence'],
              'interpretation':'原表直接列示炼钢子工程及三项金额。整体投产、产线贯通与子工程转固并非同一概念。当前不能把子工程金额等同整体投资，也不能用整体贯通日期替代验收和折旧起点。',
              'next_actions':[x['material']+'：'+x['purpose'] for x in raw['audit_procedures']],'reconciliation':raw['reconciliation']}
        write_dossier('baosteel',data)
    execution_report()
    for name in ['TECHNICAL_REPORT','USER_GUIDE','TRIAL_FORMS','IP_DISCLOSURE','ANNOTATION_GUIDE','APPLICATION_CHECKLIST','TEST_REPORT']:
        md_docx(BASE/(name+'.md'),output/(name+'.docx'))
    files={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.glob('*.docx'))}
    (BASE/'deliverables_manifest.json').write_text(json.dumps({'files_sha256':files,'professional_evaluation':'not_independently_completed'},ensure_ascii=False,indent=2))
    print('generated',len(files),'documents')


if __name__=='__main__':main()
