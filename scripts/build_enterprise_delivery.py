"""从原始运行、来源指纹与测试回执生成交付；不手填企业数或模型成功数。"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'outputs/enterprise-expansion'
DOCS = ROOT / 'docs/enterprise-expansion'
DOCS.mkdir(parents=True, exist_ok=True)
load = lambda p: json.loads(p.read_text(encoding='utf-8'))
dump = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding='utf-8')
def write(name, text):
    # 按用户的 Markdown 公式约定统一定界符。
    text = text.replace('\\(', '$').replace('\\)', '$').replace('\\[', '$$').replace('\\]', '$$')
    (DOCS / name).write_text(text, encoding='utf-8')
def clean(text, maximum=180):
    return str(text or '').replace('|', '／').replace('\n', ' ').replace('\r', '')[:maximum]

seed = load(ROOT / 'backend/connectivity_reports.json')['documents']
snapshot = load(ROOT / 'backend/connectivity_catalog.snapshot.json')['pairs']
by_pair = {r['pair_id']: r for r in snapshot}
documents = seed + [d for r in snapshot for d in r['documents']]
evaluations = load(OUT / 'case-evaluation.json')
assert all(r['status'] == 'completed' for r in evaluations)
evaluation = {r['pair_id']: r for r in evaluations}
model_task = load(OUT / 'real-model-task.json')
model = model_task['result']
calls = [c for c in model['provider_calls'] if c.get('performed')]
browser = load(OUT / 'browser-company-final.json')
assert not browser['errors'] and browser['switch_preserves_result'] and browser['cross_company_isolated']
regression = load(OUT / '全库回归.json')
assert len(regression['batches']) == 5 and all(b['exit_code'] == 0 for b in regression['batches'])
assert regression['source_unchanged']
for name, digest in regression['source_hashes'].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
counts = Counter()
for i in range(1, 6):
    for suite in ET.parse(OUT / f'回归_{i}.xml').getroot().findall('testsuite'):
        for key in ('tests', 'failures', 'errors', 'skipped'):
            counts[key] += int(suite.get(key, '0'))
counts['passed'] = counts['tests'] - counts['failures'] - counts['errors'] - counts['skipped']
assert counts['failures'] == counts['errors'] == 0
recovery = load(OUT / 'supabase-catalog-recovery.json')
fresh = load(OUT / 'fresh-instance-pair-recovery.json')
ready = load(OUT / 'source-readiness-restart.json')
assert recovery['status'] == fresh['status'] == 'passed' and ready['ready']

inventory = []
for pair_id in sorted({d['case_id'] for d in documents}):
    docs = [d for d in documents if d['case_id'] == pair_id]
    score = evaluation[pair_id]
    raw = load(OUT / score['raw_file'])['run']
    record = by_pair.get(pair_id, {})
    coverage = {c['document_id']: c for c in raw['coverage']}
    inventory.append({'pair_id': pair_id, 'company_id': docs[0]['company_id'], 'company': docs[0]['company'],
        'period': docs[0]['period'], 'industry_context': raw['industry_context'],
        'documents': [{**d, 'extraction_coverage': coverage.get(d['document_id'], {})} for d in docs],
        'source_status': 'verified_by_sha256_and_pdf_pages', 'program_status': 'completed',
        'rules_detected': sorted({c['rule_id'] for c in raw['checks']}), 'checks': len(raw['checks']),
        'formal_consistent': sum(c['conclusion_level'] == 'formal_consistent' for c in raw['checks']),
        'financial_candidate_paths': score['financial_edges'], 'model_status': record.get('model_status', 'not_run'),
        'actual_model_run': record.get('last_model_run'), 'program_run_id': raw['run_id'],
        'limitations': record.get('limitations', ['依实际指标前提判断可比性，不保证全部规则均适用'])})
candidate_history = {}
for name in ('acquisition-first.json', 'acquisition-second.json', 'acquisition.json'):
    if (OUT / name).exists():
        for r in load(OUT / name):
            candidate_history[r['ticker']] = r
discovered = [load(p) for p in OUT.glob('[0-9]*-discovery.json')]
stats = {'original_companies': len({d['company_id'] for d in seed}),
    'new_candidates_considered': len(discovered),
    'new_companies_with_paired_metadata': sum(d['state'] == 'paired' for d in discovered),
    'new_companies_source_verified': len({r['company_id'] for r in snapshot}),
    'total_source_verified_companies': len({r['company_id'] for r in inventory}),
    'total_pairs': len(inventory), 'total_documents': len(documents),
    'program_run_pairs': len(evaluations),
    'companies_with_rule_candidates': len({r['company_id'] for r in inventory if r['rules_detected']}),
    'companies_with_formal_consistent_result': len({r['company_id'] for r in inventory if r['formal_consistent']}),
    'companies_with_real_model_calls_this_round': int(bool(calls)),
    'companies_three_agents_completed_this_round': int(model['model_status'] == 'three_agents_completed'),
    'actual_model_calls': len(calls), 'input_tokens': sum(c.get('input_tokens') or 0 for c in calls),
    'output_tokens': sum(c.get('output_tokens') or 0 for c in calls), 'billed_currency_cost': None}
dump(DOCS / 'B_企业数据清单.json', {'counts': stats, 'verified_pairs': inventory, 'candidate_attempts': list(candidate_history.values())})
with (DOCS / 'B_企业原件清单.csv').open('w', encoding='utf-8-sig', newline='') as stream:
    fields = ['company', 'company_id', 'period', 'pair_id', 'report_type', 'document_id', 'source_url', 'version', 'disclosure_date', 'pages', 'file_sha256', 'program_status', 'rules_detected', 'model_status']
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for row in inventory:
        for d in row['documents']:
            writer.writerow({key: ('、'.join(row[key]) if isinstance(row.get(key), list) else row.get(key, d.get(key, ''))) for key in fields})

deployment = load(DOCS / 'deployment-observation.json') if (DOCS / 'deployment-observation.json').exists() else {}
production_browser = load(OUT / 'production-browser.json') if (OUT / 'production-browser.json').exists() else {}
production_browser_verified = bool(deployment.get('new_version_verified') and production_browser.get('new_entry')
    and production_browser.get('health', {}).get('deployment', {}).get('commit') == deployment.get('runtime_commit')
    and production_browser.get('calculation_status') == 'completed' and production_browser.get('company_isolated')
    and production_browser.get('calculation_model_calls') == 0 and not production_browser.get('errors')
    and production_browser.get('result_visible') and production_browser.get('source_status') == 200
    and all(production_browser.get('exports', {}).get(kind) == 200 for kind in ('json', 'csv', 'docx')))
online_summary = ('线上新版运行时身份、新搜索、17组原件及新增企业程序流水线已验证'
                  if production_browser_verified else '线上新版完整业务流程尚未验证')
facts = {'generated_at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'counts': stats,
    'backend_tests': dict(counts), 'frontend_tests_passed': 29, 'live_model_status': model['model_status'],
    'paid_trial_authorized': {'company': '601012', 'year': 2025, 'model': 'deepseek-flash',
        'destination': 'api.deepseek.com', 'max_calls': 12, 'consumed_token_stop_line': 120000, 'inflight_may_cross_once': True},
    'trial_task_id': model_task['task_id'], 'trial_run_id': model['run_id'],
    'formal_ai_opinions_this_trial': len(model['ai_opinions']), 'model_billing_verified': False,
    'source_recovery': fresh, 'shared_catalog_recovery': recovery,
    'production_deployed': bool(deployment.get('new_version_verified')),
    'production_application_commit': deployment.get('runtime_commit'),
    'production_browser_verified': production_browser_verified,
    'deployment_verification': 'see separate deployment-observation.json and evidence/production-browser.json',
    'synthetic_tests_are_business_evidence': False}
dump(DOCS / 'release_facts.json', facts)
manifest = {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
    for folder in ('backend/app', 'assets/official-v4') for p in (ROOT / folder).glob('*') if p.is_file()}
manifest['index.html'] = hashlib.sha256((ROOT / 'index.html').read_bytes()).hexdigest()
manifest['backend/connectivity_catalog.snapshot.json'] = hashlib.sha256((ROOT / 'backend/connectivity_catalog.snapshot.json').read_bytes()).hexdigest()
dump(DOCS / 'source_manifest.json', manifest)

write('A_代码与接口.md', '''# 正式企业搜索与双报告接入

正式工作台原来只支持预先登记的报告对。本轮把企业身份发现、同年双报告查询、后台原件校验和现有核验任务接成一条流程，保留默认 three_agents 和既有六类规则。原工作目录的未提交改动没有覆盖；开发在独立分支进行。

| 模块 | 实际改动 |
|---|---|
| connectivity_catalog.py | SQLite 本地目录、Supabase cases 元数据主记录、离线镜像、原子部署快照；不可变版本配对；不在公共目录枚举个人任务链接 |
| connectivity_onboarding.py | 复用公司目录与年报适配器，增加官方 ESG 标题查询；逐跳白名单下载、主体与期间、哈希、逐页文字层处理、空间和并发限制 |
| connectivity_catalog_api.py | 正式身份搜索、报告对查询、目录筛选、接入任务及进度、同源登录与权限；复用 Auth、组织成员表和任务存储 |
| connectivity_extraction.py | load_registry 合并动态目录且不覆盖历史 document_id；扩展有原文依据的行业检索重点，不新增数学算子 |
| connectivity_api.py | 公网新模型调用先验证登录并继续使用旧配额；保存实际运行状态，不把未调用当成功 |
| connectivity_app.py | 正式应用挂载企业与会话路由，保持旧销售收款路由未挂载；发布标识 enterprise.1 |
| connectivity-companies.js / connectivity.js / index.html / workbench.css | 企业搜索与分层、版本选择、真实准备进度、行业/年度/状态筛选；切换仅修改下次运行参数，保留当前结果 |
| expand_company_cases / evaluate_company_cases / verify_* | 官方数据接入、真实程序运行、演示适配评分、重启与空实例恢复、真实浏览器复验 |

接口：GET /api/companies/search；GET /api/companies/{ticker}/report-pair；GET /api/connectivity/catalog；POST /api/connectivity/catalog/imports；GET /api/connectivity/catalog/imports/{task_id}；/api/auth/me、login、refresh、logout。接入成功只返回新 pair_id，运行继续使用原 POST /api/connectivity/runs。

共享部署沿用 AUDITTRACE_DEMO_TASK_PERSISTENCE=supabase，目录默认随之使用 Supabase；无需新增数据库表。只写公开 CONNPAIR 命名空间的 cases.metadata.connectivity_pair，其他租户和旧业务结果不进入搜索。可显式设置 AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE。单实例离线目录与任务均用 local，模型关闭。

报告对身份含双方 SHA-256 指纹。修订只追加版本；同一 AR 与新 ESG 配对时，引用编号也绑定配对身份。PDF 以哈希去重，单份上限 100MB、1800 页，准备并发 2、每实例最多 4 项准备任务；默认原件与解析缓存预算 2GB。身份与元数据查询共用既有限流。公网新下载要求真实组织写权限，新付费模型要求登录；令牌留在 HttpOnly Cookie。

parse_status=complete 指全部 PDF 页经过读取、文字层处理完成，不是所有图像内指标均已 OCR；每份提取覆盖与失败页另列。逐条定义、范围、币种、期间和单位仍由原流水线判断。没有把环保投入等同固定资产增加，也没有新增企业风险评分。
''')
table = '\n'.join(f"|{r['company']} {r['company_id']}|{r['period']}|{' / '.join(str(d['pages']) for d in sorted(r['documents'], key=lambda d:d['report_type']))}|{r['checks']}|{r['financial_candidate_paths']}|{r['model_status']}|" for r in inventory)
write('B_企业数据说明.md', f'''# 企业接入与运行口径

本轮考察 {stats['new_candidates_considered']} 家新增候选，其中 {stats['new_companies_with_paired_metadata']} 家找到同年双报告元数据，{stats['new_companies_source_verified']} 家通过原件验证。加上原有 {stats['original_companies']} 家，现有 **{stats['total_source_verified_companies']} 家、{stats['total_pairs']} 对、{stats['total_documents']} 份原件**。

{stats['program_run_pairs']} 对均已真实运行程序链；{stats['companies_with_rule_candidates']} 家至少召回一类规则候选，正式可比与一致仍按前提门禁另算。本轮 1 家发生真实模型调用，完整 three_agents 成功 **{stats['companies_three_agents_completed_this_round']} 家**；不能把部分完成或程序结果计入完整成功。

|企业与代码|年度|AR / ESG页数|程序候选数|有双端原页的财务候选|最近模型状态|
|---|---:|---|---:|---:|---|
{table}

每份原件的官方地址、版本、披露日、SHA-256、document_id、页数与实际提取覆盖见 B_企业数据清单.json 和 B_企业原件清单.csv。候选数量、配对数量、原件验证、规则候选与模型完成分别统计；程序候选不是已证明的披露问题。

万华化学仍未通过 ESG 正文主体核对，未计入有效库。中国神华、长江电力、中国建筑在本轮有界巨潮查询中未形成合格 ESG 配对；这不等于企业没有发布相关报告，也不构成负面评价。紫金原件可读取、主张可抽取，但本轮未形成规则或财务科目路径，明确列为能力受限案例，不推荐作为主演示。

行业配置与正式行业归属分开：只有原文命中行业说明时才显示报告依据；其他显示待核行业。历史版本、不同语言和修订状态依官方公告候选登记，未声称人工穷尽核对全部历史公告。
''')

ranked = sorted([r for r in evaluations if r['pair_id'] in by_pair and r['financial_edges'] >= 3], key=lambda r:(-r['total'],-r['financial_edges'],r['company_id']))
chosen=[];seen_company=set();seen_industry=set()
def demo_group(row):
    profile=by_pair[row['pair_id']].get('industry_profile') or by_pair[row['pair_id']]['industry']
    if profile in ('食品饮料','白酒','乳制品'): return '食品饮料展示组'
    if profile in ('机械制造','装备制造','机械','电力','发电设备'): return '机械装备展示组'
    if profile in ('家电制造','家电','家用电器'): return '家电展示组'
    return profile
longi=next(r for r in ranked if r['company_id']=='601012')
chosen.append(longi);seen_company.add('601012');seen_industry.add(demo_group(longi))
for r in ranked:
    if len(chosen)>=4: break
    group=demo_group(r)
    if r['company_id'] in seen_company or group in seen_industry: continue
    chosen.append(r);seen_company.add(r['company_id']);seen_industry.add(group)
chosen.sort(key=lambda r:({'600019':0,'600887':1,'601012':2}.get(r['company_id'],3),-r['total']))
parts=['# 决赛演示案例筛选\n\n主推荐限本轮新增企业，先要求至少3条有双端原页的财务候选，再按固定演示分数排序；同企业和同展示分组只选一次，保留有本轮真实模型调用的隆基。最终推荐4家，不为凑5家加入证据较薄的路径。原有宝钢和五粮液仍可作既有对照，不算新增成果。\n\n评分表示演示适配，绝不是企业风险、披露质量或专业准确率。原件、计算记录、财务候选、原页解释各20分；完整真实三角色和本次程序时长各10分。分项数量与分母见 demo_selection.json。行业代表性是选择约束：展示分组依据接入配置归并，不冒充官方行业分类；原文业务线索单列。模型真实增量和预算限制照实展示。\n']
for order, score in enumerate(chosen,1):
    raw=load(OUT / score['raw_file'])['run']
    edges=[e for e in raw['financial_edges'] if e.get('financial_document_id') and e.get('claim_document_id')][:2]
    text=[f"## {order} {score['company']} {score['period']}",f"演示适配 {score['total']}/100；程序实跑 {score['elapsed_seconds']} 秒，{score['checks']} 条候选，{score['financial_edges']} 条有双端定位的财务候选。选择理由是存在可解释的披露路径和口径问题，而非发现企业违规。"]
    for edge in edges:
        text.append(f"- ESG PDF第 {edge['claim_page']} 页：{clean(edge.get('claim_text'))}。年报 PDF第 {edge['financial_page']} 页：{clean(edge.get('financial_label'))}。状态 `{edge['status']}`；依据：{clean(edge.get('why'))}。")
    checks=raw['checks'][:2]
    for check in checks:
        calculation=check.get('calculation') or {}
        residual = calculation.get('residual')
        text.append(f"- 程序记录：{clean(check['title'])}；结论 `{check['conclusion_level']}`；输入与过程 `{clean(calculation.get('expression','未形成正式计算'))}`。正式差额：{residual if residual is not None else '未输出（前提未齐），空值不当作零'}。")
    if score['company_id']=='601012':
        text.append(f"本轮真实 A1/A2/A3 共 {len(calls)} 次调用。候选由程序初始 {len(raw['checks'])} 条变为真实运行保存的 {len(model['checks'])} 条，新增或细化了合并/母公司收入、研发费用及研发占比分母的核验线索。最终 AI 意见 {len(model['ai_opinions'])} 条；状态 `{model['model_status']}`。A3 意见未通过年度、原文、数值及专业边界校验，修复请求受 Token 停止线阻止，不能演示成完整成功。")
    else:
        text.append('本轮只验证程序链，未对此企业调用模型；没有可声称的本轮智能体增益。')
    gaps=list(dict.fromkeys(g for c in raw['checks'] for g in c.get('unresolved',[])))[:5]
    text.append('尚未解决：'+('；'.join(clean(g) for g in gaps) if gaps else '仍须按具体关系核对披露范围与财务归属，不作因果推断')+'。')
    text.append('评委可追问：两处是否同一合并范围、投入是资本性还是费用性、是否有具体项目归属、为何金额相近仍未判为等额？答辩回到上述原页和逐条门禁，保留无法量化的状态。')
    text.append('建议操作：选择对应年度 → 程序核验或打开明确标为历史的本轮模型任务 → 点一条财务候选回原页 → 展示缺口及下一步核对。程序运行验收已通过；模型状态按上文单列。')
    parts.append('\n\n'.join(text))
write('D_优质演示案例报告.md','\n\n'.join(parts))
dump(DOCS / 'demo_selection.json', {'selection_rule':'fixed_demo_score_then_company_industry_diversity_plus_one_real_model_case','selected':chosen})

write('C_搜索与运行演示.md', f'''# 搜索与运行实际操作

本机正式入口 http://127.0.0.1:8893 。本轮新增隆基绿能在页面中完成“搜索 → 确认 601012 → 查询 2025 双报告 → 选择公告版本 → 后台校验并登记 → three_agents → 查看结果”。页面复验准备时复用本轮此前已经验证的同版本原件，没有把缓存命中称为重新下载。

真实任务：{model_task['task_id']}；run_id：{model['run_id']}。真实模型调用 {len(calls)} 次，输入 {stats['input_tokens']}、输出 {stats['output_tokens']} Token；状态 `{model['model_status']}`。A3 返回内容包含年度错配及未通过原文、数值和专业边界校验的意见，最终未采纳为有效 AI 意见。A3 返回后越过 12万已消费 Token 停止线，修复请求被阻止；这是一轮部分完成的真实试跑，绝不是完整三角色成功。实际人民币账单未核对，不把未知费用写成0。

![企业身份搜索](evidence/01-企业搜索.png)
![双报告候选](evidence/02-双报告候选.png)
![原件准备完成](evidence/03-原件接入完成.png)
![真实模型结果](evidence/04-真实模型结果与降级.png)

最终浏览器复验覆盖名称、代码、全称、ljln、近似名称、未登记福耀玻璃、不存在的明确合成名称；身份候选需点击确认。中国神华仅找到年报时明确缺 ESG；未来年度返回422。切换企业不清空原任务；原页与 JSON/CSV/DOCX 导出均200，引用均属本企业。另从页面实际启动伊利的 calculation_only，零模型调用并得到程序结果。

1440×1000、1024×768、768×1024、390×844 均无横向溢出。公网登录与权限使用现有 Supabase 组织账号；身份搜索和已完成结果读取不等于拥有新下载或付费模型权限。本轮没有使用真人账号密码执行公网登录，相关 Cookie 和权限边界由隔离合同测试验证。

公网验收：{online_summary}。运行提交 `{deployment.get('runtime_commit')}`；浏览器程序任务 `{production_browser.get('calculation_task_id', '未完成')}`，状态 `{production_browser.get('calculation_status', '未验证')}`。公网没有追加真实模型请求；本轮隆基模型试跑保留为本机运行证据。生产截图与回执见 evidence/production-*。
''')
write('E_验收报告.md', f'''# 企业扩容与正式搜索验收

结论：本轮代码、原件、程序流水线和本地浏览器验收通过；{online_summary}。**完整真实 three_agents 成功门槛尚未通过**，不能把整体任务写成全部完成。

|范围|实际结果|
|---|---|
|最终冻结源码全库|{counts['passed']} passed、{counts['skipped']} skipped、0 failed、0 errors；源码哈希一致|
|前端状态与跨语言口径|29 passed|
|企业与报告|{stats['total_source_verified_companies']} 家、{stats['total_pairs']} 对、{stats['total_documents']} 份；全部原件重新读取就绪|
|真实程序运行|{stats['program_run_pairs']} 对完成；{stats['companies_with_rule_candidates']} 家有规则候选，其他明确限制|
|共享持久化|Supabase恢复 {recovery['recovered_without_local_snapshot']} 对新增登记；无本地快照空实例实际重取隆基 AR/ESG，哈希与页数通过|
|浏览器|七类身份搜索、缺 ESG、未来年度、企业切换保留结果、四屏、原页与三格式导出通过；无页面异常|
|真实付费模型|仅获准一次隆基试跑；{len(calls)} 个真实请求，最终部分完成，完整成功0家|
|生产部署|运行提交 `{deployment.get('runtime_commit')}`；{online_summary}；没有新增付费调用|

自动化负例覆盖：身份/期间错配、摘要及英文版、非白名单与私网 URL、旧版本身份覆盖、同 AR 多版 ESG、重复任务、队列限制、存储预算、离线恢复、坏缓存、公共目录任务链接隐私、匿名付费调用、HttpOnly 会话与同源约束。故障输入和测试 PDF 明确合成，不计入真实企业数量。

所有 pytest 跳过项保留在 JUnit，主要涉及不随仓库分发的全文、封存运行与内部原件；未当作通过。原有六项规则与专业依据索引没有被本轮扩容改写为已验证的专业条款。没有证明专业准确率提升，也没有人工专家或真人可用性评价。

性能与边界：下载、解析有独立后台任务与有界槽位，身份查询不等待整份 PDF 的表格处理；同哈希和同版官方 URL 复用原件。固定演示评分使用本机真实运行耗时，不承诺公网或无缓存90秒完成。共享数据库不可达时，目录可展示已核实离线记录；公网任务写入仍需存储服务，本机离线模式可继续运行已缓存案例。

本轮保留的失败：万华正文身份未通过；三家候选尚缺本轮查询可接入的 ESG；紫金未形成适合展示的财务路径；隆基 A3 意见未通过年度、原文、数值及专业边界校验，修复请求被预算阻止。真实模型试跑之前曾因未明确模型/目的地/预算被自动权限审核拒绝，随后用户明确授权一次，执行范围没有扩大。

代码版本见 source_manifest.json 和本分支 Git 提交，不把旧基线 SHA 当成本轮成果身份。生产观察另见 deployment-observation.json、evidence/production-browser.json 与 F_GitHub与部署.md；推送、部署平台 success 和真实业务完成分别核对。公网同一伊利任务原文状态为 {production_browser.get('source_status', '未验证')}，逐格式导出回执为 {production_browser.get('exports', '未验证')}；本机原文和三格式导出已实测通过。
''')
evidence = DOCS / 'evidence'
evidence.mkdir(exist_ok=True)
for name in ['01-企业搜索.png','02-双报告候选.png','03-原件接入完成.png','04-真实模型结果与降级.png',
             '企业搜索最终_1440x1000.png','企业搜索最终_390x844.png',
             'browser-company-final.json','supabase-catalog-recovery.json','fresh-instance-pair-recovery.json']:
    shutil.copyfile(OUT / name, evidence / name)
for name in ['production-browser.json', 'production-desktop.png', 'production-mobile.png']:
    if (OUT / name).exists():
        shutil.copyfile(OUT / name, evidence / name)
dump(evidence / 'model-trial-receipt.json', {'task_id':model_task['task_id'],'run_id':model['run_id'],
    'model_status':model['model_status'],'provider_calls':model['provider_calls'],'final_ai_opinions':len(model['ai_opinions'])})
dump(evidence / 'test-summary.json', dict(counts))
print(json.dumps({'counts':stats,'tests':dict(counts),'recommended':[r['company'] for r in chosen]},ensure_ascii=False))
