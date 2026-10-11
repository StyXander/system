"""汇总真实验收与未执行项目，不替代专业签字或付费实验。"""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '决赛准备/整改_2026-10-11'

def main():
    # 修复写入时产生的控制字符，运行说明引用完整历史入口。
    p=ROOT/'README_RUN.md'
    text=p.read_text(encoding='utf-8').replace('\nemediation/finals-20261011','remediation/finals-20261011').replace('\x1b29c175','e29c175')
    p.write_text(text,encoding='utf-8')
    p=ROOT/'README.md';text=p.read_text(encoding='utf-8').replace('当前唯一发布候选为','该历史快照发布候选为');p.write_text(text,encoding='utf-8')
    facts=json.loads((OUT/'当前答辩事实表.json').read_text(encoding='utf-8'))
    live=json.loads((OUT/'线上状态只读.json').read_text(encoding='utf-8'))
    facts['deployment_live']={'read_only_observation':'2026-10-11','deployment':live.get('deployment'),'local_changes_deployed':False}
    facts['checks']={'focused_pytest_passed':31,'warnings':1,'browser_record':'outputs/finals-20261011-browser/browser-record.json','source_check':'outputs/finals-20261011-browser/source-check.json','external_model_calls_this_round':0,'word_pages_rendered_and_reviewed':3,'chinese_comment_ratio':'2931/27547=10.64%','diff_check':'passed','python_compile':'passed','frontend_syntax':'passed'}
    rows=list(csv.DictReader((OUT/'R1零模型敏感性.csv').open(encoding='utf-8-sig')))
    counts=[sum(r[k]=='candidate' for r in rows) for k in ['10个百分点','15个百分点','20个百分点']]
    facts['sensitivity']={'included':len(rows),'excluded':50-len(rows),'candidate_counts_10_15_20pp':counts,'scope':'本机有效可比期间，一般销售与收款；混合金融东方财富单列排除'}
    (OUT/'当前答辩事实表.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
    # 授权表默认不批准，不能把历史密钥或旧项目许可当成本次新增预算。
    auth={'experiment_id':'EXP-FINALS-20261011-AB-01','approved':False,'approved_by':None,'max_calls':30,'max_tokens':500000,'model_id':'deepseek-v4-flash','endpoint':'https://api.deepseek.com/v1','note':'建议上限，包含修正；需用户明确预算授权和实际模型ID。价格未知，不声称金额上限；密钥仅从环境读取。'}
    (OUT/'探索对照/预算授权_待确认.json').write_text(json.dumps(auth,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'探索对照/执行与评分说明.md').write_text('''# 探索对照执行与独立评分
当前只完成输入冻结和零模型合同预演，真实尝试0、调用0、失败0，评分未开展。零失败不代表成功率。三类案例为五粮液触发、中国海油未触发、万华化学截止日资料缺口，不人为制造缺口。

A是一次完整草稿，B是当前三角色链，双方读取同一冻结输入与全部证据，接受相同最终数字和用途校验。计划每类每条件重复两次，共12份结果、24次基础调用；交替顺序见manifest。实际模型、源码与授权哈希在执行时冻结。调用数不同且角色合同不同，不能称成本相同。失败、受控修正、延时和实际token保留，费用未知。

确认预算后，在项目Python环境运行 scripts/run_finals_ab_20261011.py --execute --authorization 决赛准备/整改_2026-10-11/探索对照/预算授权_待确认.json；将批准、批准人及真实模型写入授权文件，并从环境提供密钥。默认运行不触网。上限30调用、500000保守预留token是建议，未获批准。不能以改为true代替用户授权。

独立参考清单由原文与规则建立，不能拿B作为标准答案：五粮液核对四金额、净额及收入核算调整；中国海油按冻结可比2024/2023期间复算，未触发不写成无风险；万华化学按原截止日资料缺口给出补取程序，不能编出2025完整金额。所有案例需保留期间、范围、单位、证据用途、未解决资料和具体程序，不能认定舞弊或出具审计意见。细节查inputs和主案例原文核对包，参考清单本身也待独立专业确认。

两名评价者分别记录：逐条计数不受支持断言、引用错配、参考遗漏；程序可执行性0=仅泛化提醒，1=资料或目的不完整，2=明确事项/资料/核对目的/未解决条件。边界遵守单列文字意见。先独立评分再保留原表和分歧，不合并为虚构专家共识。

真实结果未生成，因此匿名结果包尚未生成。取得结果后对最终输出随机编号、移除A/B与角色提示、保持全文和失败状态；映射单独保管，仅原始映射保留模型身份。不得把空模板写成匿名结果已完成。正式评价指针不改。

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。
''',encoding='utf-8')
    # 正式通知作为基线备份，年报与历史任务保留原位并用字段哈希索引。
    notice=ROOT/'关于开展2026年北京市大学生数智会计创新应用竞赛决赛的通知.pdf'
    backup=OUT/'基线原件';backup.mkdir(exist_ok=True)
    target=backup/notice.name
    if not target.exists(): target.write_bytes(notice.read_bytes())
    report=f'''# 决赛整改总记录（2026-10-11）

## 基线与范围
项目根目录为数智竞赛，分支 remediation/finals-20261011，源码与远端main基线7f83b52564aa2a10a21191d20d49ab44a5df3fa3。本轮没有提交、推送或部署。原有四份9月19/20日文件删除、身份恢复记录、tmp_pdf文件和决赛准备目录保持原状态，不混入提交。本轮代码与证据都留在原仓库。历史运行、年报原件和正式评价指针未修改。运行说明原文保存在docs/history/README_RUN_20261011整改前.md。

## 已完成并留证
1. P1：六字段逐项原文核对，四金额差异0，2025/2024净额口径保持；2023比较数也回查。年报截图、哈希、净额与准备关系、官方差错更正范围、复算均留存。真人字段采用确认仍待进行。
2. P2：仅在副本做10/15/20个百分点阈值敏感性；纳入{len(rows)}案、排除{50-len(rows)}案，候选数{counts[0]}/{counts[1]}/{counts[2]}。不改15/30默认参数，不证明准确率。东方财富2024年报第10页的混合金融业务独立排除；生产简称行业识别存在局限，本轮不扩张为行业路由改造。
3. P3：修复正常解释未经过证据用途校验的遗漏，与claims共用校验；所有主张增加semantic_support_status=not_verified。前端和交付标签为“已绑定引用，支持关系待复核”，CSV明确记录未验证状态。合法ID不等于文本获原文支持。扩展用途违规容量以容纳两组各5项。
4. P4：冻结三类真实案、A/B、两次重复、12次计划尝试和受控预算入口；当前只是零模型预演，真实尝试0、调用0、失败0、质量评分未开展。无匿名真实结果包。执行脚本、参考清单、空评分表和待授权预算表齐备。
5. P5：核对标准股份真实父子运行，原字段相同、补充证据及原始哈希留存；补证是公开演示账龄样例，父子均defer，无无补证控制，不能归因为改善。五粮液具体任务卡单独标记本轮编辑补充，非历史模型原文。陌生使用者任务和空记录表已备，实际试用未开展。
6. P6/P7：更新事实表、README运行入口与历史标注；已只读取得线上部署状态，线上7f83b52不包含本地修改。原七分钟PPT和原讲稿不在工作区，未修改原PPT；提供15页替换稿和新3页Word讲稿。Word正文宋体小四、标题黑体三号，已渲染逐页检查，视觉验收证据见outputs/finals-20261011-docx-render。
7. P8：历史同源备用HTML、原文截图、角色原始输出、故障切换句、超时删减和上场清单齐备。未生成短录屏，未真人彩排，不声称90—120秒实测完成。

## 实际验证与限制
聚焦pytest：31 passed、1 Starlette弃用警告；覆盖证据反例、原有创新控制、数字归属和导出合同。不是全仓回归。沙箱首次FAISS原生句柄失败，换获准本机执行后通过，不隐去环境失败。
真实FastAPI隔离服务读取原始历史完成任务，外网与供应商连接封禁；真实Edge四视口1440×1000、1024×768、768×1024、390×844无页面错误、失败请求或横向溢出，读取身份一致，无POST新任务。桌面JSON/CSV导出、刷新同一任务、键盘焦点和断网本地三张原文图检查通过。恢复耗时约1.5—2.7秒，只是读取恢复，不是模型时长或现场完整演示时间。证据在outputs/finals-20261011-browser。
补充实测：界面展开引用和三角色详情，点击同源原文链接，新窗口实际打开PDF，返回内容以%PDF开头；新增语义待复核提示可见，截图与日志见source-check.json。第一次测试脚本未把相对URL转成绝对URL而失败，修复测试脚本后通过；不改产品来适应测试。A/B共用最终闸门对越界引用的离线反例通过，未调用供应商。中文说明2931/27547=10.64%、Python编译、前端语法和差异空白检查通过。
语义蕴含未实现通用自动验证；字段口径、金额重要性及专业采用未由真人确认。本轮未重审历史48调用，不把15案模型工程记录与8案零模型预检合成23案模型成功。LibreOffice输出日志存在GBK解码线程警告，但PDF与三张页面已实际生成并检查，无遮挡或溢出，标题继承蓝线已去除。

## 最小真人动作
补交原PPT和原讲稿，才能执行原件15页替换、学校信息核查及PPT逐页渲染；现有替换稿可直接迁入。
明确本实验模型与预算（建议最多30调用、500000预留token，费用未核价），才能真实执行并生成匿名结果；随后两名评价者分别评分。
对六字段CSV回查官方原文并记录真实身份、意见与时间；复核R1用途；请陌生使用者按任务实际操作并记错误与求助；使用讲稿和备用页实测彩排时间。所有空表不代填。

## 回退与发布
本轮未发布，公网无本轮变更可回退。工作区回退须只针对本轮列出的6个生产文件（schemas.py、evidence_fitness.py、main.py、delivery.py、demo-app.js、index.html）及README、.gitignore改动；先保存差异，再按基线选择性恢复，不能整仓重置或恢复用户已有删除。新增脚本与交付包可保留供审核。正式发布需另行明确授权；现有签字状态为signoff_stale_requires_reapproval，必须按现有签字机制重新核对，不自动批准。正式通知备份见基线原件，原PPT缺失无法备份。隔离验收服务已结束，不在后台继续运行。

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。
'''
    (OUT/'整改总记录.md').write_text(report,encoding='utf-8')
    # 索引仅列本轮成果，原始文件内容不因索引而重写。
    entries=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='交付文件哈希.json']
    (OUT/'交付文件哈希.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Final records: {len(entries)} artifacts; sensitivity {counts}')

if __name__=='__main__':
    main()
