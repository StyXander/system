"""汇总实际回执，不填补未完成的模型运行、专业标签或部署证据。"""
from pathlib import Path
import json,shutil,subprocess,hashlib,re
from datetime import datetime,timezone,timedelta
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/financial-impact-acceptance';DOC=ROOT/'docs/financial-impact-acceptance';DOC.mkdir(parents=True,exist_ok=True)
def read(path,default=None):
 p=OUT/path
 return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else default
rule=read(Path('release-rule-experiment/report.json'));sources=read(Path('source-manifest.json'),[]);ci=read(Path('ci-summary.json'),{})
ci_test=next((re.search(r'(\d+) passed, (\d+) skipped',line) for line in ci.get('lines',[]) if re.search(r'(\d+) passed, (\d+) skipped',line)),None)
ci_pass=ci_test.group(1) if ci_test else '未读取';ci_skip=ci_test.group(2) if ci_test else '未读取'
ci_run=ci.get('workflow','unverified')
browser=read(Path('browser/receipt.json'),{});exports=read(Path('browser/export-verification.json'),{})
runs=[]
for directory,arm in [('real-trial','single_model'),('real-trial','multi_agent'),('real-single-repair','single_model'),('remaining-authorized-single','single_model'),('post-fix-three-call','multi_agent')]:
 task=read(Path(directory)/(arm+'-000858-2025.json'))
 if not task:continue
 run=task.get('result') or {};data=run.get('financial_impact') or {};agents=data.get('agents') or {};calls=run.get('provider_calls',[])
 runs.append({'stage':directory,'arm':arm,'task_id':task['task_id'],'run_id':run.get('run_id'),'task_status':task['status'],
  'model_status':run.get('model_status'),'agent_status':agents.get('model_status'),
  'actual_requests':sum(bool(c.get('performed')) for c in calls),'input_tokens':sum(c.get('input_tokens') or 0 for c in calls),
  'output_tokens':sum(c.get('output_tokens') or 0 for c in calls),'verified_judgments':len(agents.get('judgments',[])),
  'rejected_judgments':len(agents.get('rejected',[])),'tools':len(agents.get('tool_receipts',[])),
  'provider_records':calls,'roles':agents.get('roles',[]),'tool_summary':[{'tool':x.get('tool_name'),'role':x.get('requested_by'),'status':x.get('status'),'verified':x.get('verified'),'reason':x.get('reason')} for x in agents.get('tool_receipts',[])],
  'cost_cny':None,'cost_note':'记录真实Token；人民币账单未核对，不虚构费用'})
summary={'generated_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
 'original_trial_requests':sum(r['actual_requests'] for r in runs if r['stage']!='post-fix-three-call'),
 'original_trial_tokens':sum(r['input_tokens']+r['output_tokens'] for r in runs if r['stage']!='post-fix-three-call'),
 'runs':runs,'post_fix_multi_verified':any(r['stage']=='post-fix-three-call' and r['verified_judgments']>0 and r['agent_status']=='completed' for r in runs),
 'professional_labels':'not_completed','accuracy_metrics':None,'vector_status':'degraded_no_vector','expert_rule_review':'pending_human_review',
 'release_gate':'blocked_pending_real_model_acceptance','deployed':False}
(OUT/'acceptance-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('source-manifest.json','acceptance-summary.json','ci-summary.json','quote-integrity.json','production-observation.json'):
 if (OUT/name).exists():shutil.copyfile(OUT/name,DOC/name)
for name in ('receipt.json','export-verification.json','financial-1440.png','financial-390.png'):
 if (OUT/'browser'/name).exists():shutil.copyfile(OUT/'browser'/name,DOC/name)
rows=rule['rule_only']['results']
table='\n'.join(f"|{r['company']} {r['pair_id']}|{r['events']}|{r['items']}|{r['relations']}|{r['project_level']}|{r['grades']}|" for r in rows)
modeltable='\n'.join(f"|{r['stage']} / {r['arm']}|{r['task_id']}|{r['actual_requests']}|{r['input_tokens']} / {r['output_tokens']}|{r['verified_judgments']}|{r['agent_status']}|" for r in runs)
source_table='\n'.join(f"|{r['company']} {r['type']} {r['year']}|{r['document_id']}|{r['pages']}|[{r['version']}]({r['source_url']})|`{r['actual_sha256']}`|" for r in sources)
report=f'''# 财务穿透任务验收报告

日期：{summary['generated_at']}。应用源码：`{summary['source_commit']}`。草稿PR：[#10](https://github.com/StyXander/system/pull/10)。

**当前结论：工程修复已提交，完整业务验收尚未通过；保持候选分支，不合并main、不发布Render。** 原提交所称“已完成”需要收窄：原先缺少生产模型工具循环、公平实验和真实模型验收。详细逐项状态见[基线与11项验收矩阵](基线与11项验收矩阵.md)。

## 已交付的实际代码

复用原企业发现、16家公司/17组报告对/34份文档登记、原件哈希缓存、任务所有权、模型配额、供应商传输和六项正式程序规则。新增财务模块负责事项、附注结构、候选会计路径、逐边图谱和A/B/C/D证据裁决；模式仍默认three_agents。

- `financial_impact/agents.py`：A1发现及字段补全、A2会计路径、A3反向查证；9个只读工具实际执行并回传下一轮；按真实事件和已定位项目选批次。默认最多6次财务角色请求、18次顶层工具、每事项8次工具和18000字上下文。
- `financial_notes.py`：报告内财务报表、附注和政策段落，行/列/币种/单位/期间/范围与坐标分开。原文引文来自PDF连续文本，结构化数据不再以竖线拼接后冒充原文。最多48个关键词命中页、600条项目；解析异常、无文本页、截断明确留痕。
- `impact_verifier.py`：项目名称、企业、期间、合并范围、币种、单位、金额性质与限定词门禁；预算、余额、现金支付和权责发生额不混算。原文、会计前提和模型假设分开。
- `financial_linker.py` / `impact_graph.py`：BM25、精确匹配、RRF；本地向量可选并明确降级；独立反证、稳定证据身份、去重、四跳路径与逐边核验。相似度不决定成立。
- `connectivity_pipeline.py` / `connectivity_api.py`：生产主链实接财务角色与工具；请求预算可下调；中止前已发生调用仍结算、仍留回执。重试保持原分析范围和预算。一次任务读取不再重复访问远程台账。
- `connectivity-graph.js`：按事项查看真实路径、列语义、九条件、官方依据、当前/预期影响及模型实际回执。明确列出通过校验与拒绝的模型提议数。
- `connectivity_delivery.py`：JSON完整结果、CSV逐事项/项目/处理/关系明细、Word章节和实际角色/工具记录均取本次保存结果。Word正文字体宋体12pt、标题黑体16pt。
- `financial_impact_experiment.py` / `evaluation.py`：规则、单模型、三智能体三臂；模型臂真实调用正式API，不再硬编码not_run。只有来源一致、封闭全集且独立人工复核的标签才计算指标，各臂预测来自各自实际输出。

## 四家真实双报告结果

下列为最终源码的程序实验，均为2025年同年配对；不计为真实模型运行。

|企业与报告对|事项|财务附注项目|候选关系|独立项目级事项|等级分布|
|---|---:|---:|---:|---:|---|
{table}

“附注项目”是带列语义的结构化项目记录，多列会产生多条记录；关系条数不等于独立经济业务数。宝钢达到600条上限，须按截断理解；美的0条表示本次解析器未定位合格附注表，不代表企业没有披露。原文验证清单见[source-manifest.json](source-manifest.json)，逐引文检查见[quote-integrity.json](quote-integrity.json)。

### 建议演示顺序与实际边界

1. **五粮液：主要案例。** ESG PDF第19页提到“配套建设成品酒包装及智能仓储配送一体化项目”；年报PDF第102页“重要在建工程项目本期变动情况”出现同名项目。预算数8,596,655,000.00元、期初899,834,791.90元、本期增加96,752,274.86元、本期转固21,538,979.92元、其他减少174,517.17元、期末974,873,569.67元分别保存，不能互换。该表本身满足期初+增加−转固−其他减少=期末，但这不证明ESG投入与年报支出勾稽。ESG该事项未给金额，范围及会计确认条件尚缺，故保留B级间接业务关联，没有升级A。18条B候选来自同一项目的不同列/会计路径，不是18个独立项目。
2. **宝钢：金额性质和项目身份边界。** 可展示ESG节能改造总投入与年报项目明细的区别；未找到项目级身份闭合时保持C。不能拿别的工程名称或近似金额凑关联。模型专业意见尚未实际通过本轮验收，不宜宣称智能体已发现企业问题。
3. **宁德时代：跨行业与补证问题。** 展示研发/节能活动的会计候选路径和附注检索；当前未形成可确认的项目级财务对应，留存具体材料缺口，不作研发资本化已确认的结论。
4. **美的：解析失败恢复示例。** 原件存在且哈希正确，但当前附注结构化结果为0，不推荐作为核心财务穿透演示案例；可展示系统如何明确说明处理限制。

五粮液的合并范围、项目投入构成、付款与应付款、转固验收、费用/资本化判断及ESG口径仍是评委可提出的有效质疑。没有这些资料，不能把候选财务科目说成真实入账确认，更不能推断舞弊或披露违规。

## 真实模型实验与失败原因

原授权最多12次请求（单模型6次、三智能体6次），实际共{summary['original_trial_requests']}次，已记录Token总量{summary['original_trial_tokens']}。来源窗口曾429拦截一次，未发送供应商请求；窗口自然恢复后才使用剩余单模型额度，未修改配额或更换身份。公网匿名模型请求401拦截也单独留存。本机试验仅监听127.0.0.1，以项目既有本机操作员模式执行，不代表公网登录已通过。

|阶段/实验臂|任务ID|实际请求|输入/输出Token|通过引用校验的模型关联提议|调查状态|
|---|---|---:|---:|---:|---|
{modeltable}

完整调用角色、模型、耗时、请求/响应SHA、实际Token与工具摘要见[acceptance-summary.json](acceptance-summary.json)。人民币费用尚未核对账单，保持空值；不能把未知费用写成0。

实际工具闭环已经运行，但原12次中的有效模型关联提议为0。拒绝不是专业成功。复核原始失败回执发现：程序提供的表格串含`|`，并非PDF连续引文；模型还在缺少参数说明时提交了无效inspect参数。两项已在最终代码修复，原件逐字门禁保持严格，原失败记录没有回填为成功。

追加的修复后三请求验证须单独预算授权；在没有新回执前保持未执行。原单/多模型运行与修复后版本不同，不拼成同版本公平对照。没有独立会计专业人工标签，不计算准确率、Recall/F1或提升比例。测试替身不计为供应商调用。

## 工程验收

- 最终应用提交CI：[{ci_run}](https://github.com/StyXander/system/actions/runs/{ci_run})，完整pytest **{ci_pass} passed / {ci_skip} skipped**，前端 **29 passed**；日志摘要见[ci-summary.json](ci-summary.json)。这些跳过项有材料缺失原因，不计为通过。
- 本地真实报告及主链曾完成113项聚焦检查；后续引用格式及工具合同修复另完成80项相关回归、37项低预算角色合同检查。存在重叠，不相加为总通过数。所有本地JUnit保存在`outputs/financial-impact-acceptance/`。
- 两轮本地分批全库的各批退出码均为0，但执行中继续修复，源指纹发生变化，因此不作为最终冻结版本全库门禁。最终完整回归以对应提交的CI为准。
- 浏览器：真实企业搜索→确认→选择报告对→仅计算任务→按事项筛选→原文/三格式导出，1440/1024/768/390四屏宽检查；实际结果以[receipt.json](receipt.json)为准。模型历史也有独立回放，回放不会发出新模型请求。[桌面截图](financial-1440.png) / [手机截图](financial-390.png)。
- Word重新打开、字体字号和CSV/JSON逐关系一致性结果见[export-verification.json](export-verification.json)。Word布局未按全部页面逐页专业审阅，不能把结构/字体检查写成完整排版审定。
- 新增原件仍只能来自既有登记及官方白名单，模型工具不接受任意URL、路径或自由金额。未注册文档、换版哈希、越页、整句不实、跨企业/期/范围、NaN、预算当支出等有回归。暂存扫描未发现本轮私钥、运行目录或生产.env入库；这不是完整Git历史密钥审计。

## 尚未通过的门禁与部署

- 修复后真实三智能体必须产生经双端证据校验的有用分析，才能宣称专业链路验收通过；旧的角色执行完成标记不能代替它。
- 会计规则12条仍待专业人工复核；已核对官方来源位置不等于专家已审定。CSMAR未接入，向量模型未启用，扫描件未支持。
- 独立专业标签和同版本公平效果实验仍未完成，所有提升指标为空。
- 本轮没有合并main，也没有请求Render部署。当前线上运行时核查遇网络失败，见[production-observation.json](production-observation.json)；不沿用旧记忆宣称线上版本已确认。本地版本可用与线上发布是两种状态。

复现规则实验：`python tools/financial_impact_experiment.py`。模型调用默认关闭，必须显式传`--allow-models`、指定实验臂、次数和Token停止线，并具备实际授权及项目额度。详细原件清单如下。

|原件|document_id|登记页数|官方地址/版本|实测SHA-256|
|---|---|---:|---|---|
{source_table}
'''
(DOC/'验收报告.md').write_text(report,encoding='utf-8')
print('report_written',len(report),'model_requests',summary['original_trial_requests'],'post_fix_verified',summary['post_fix_multi_verified'])
