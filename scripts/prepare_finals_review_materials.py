"""准备工程事实、专业确认与同任务评估草案，不冻结或填写真人人工记录。"""
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")
from backend.app.seed_catalog import load_seed_cases
from backend.app.signoff import current_r1_config, load_signoff_status

NOTICE = "AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"


def write_md(path, text):
    path.write_text(text.strip() + "\n\n" + NOTICE + "\n", encoding="utf-8")


def main():
    out = ROOT / "决赛准备/整改_2026-10-09"
    out.mkdir(parents=True, exist_ok=True)
    config = current_r1_config()
    signoff = load_signoff_status()
    files = ["backend/app/cases.py", "backend/app/schemas.py", "backend/app/field_extraction.py", "backend/app/main.py", "backend/app/source_corrections.py", "backend/app/rag.py", "backend/app/seed_catalog.py", "backend/app/pipeline.py", "backend/app/agents.py", "backend/source_corrections_20261009.json", "backend/source_date_verifications_20261009.json"]
    binding = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    (out / "当前配置与源文件绑定_待真人确认.json").write_text(json.dumps({"status": "prepared_pending_human", "current_config": config, "existing_signoff_status": signoff, "source_file_hashes": binding, "signed_by": None, "signed_at": None, "decision": None, "ai_generated_content_notice": NOTICE}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(out / "01_当前规则与原文更正确认单.md", f"""
# 当前规则与原文更正确认单

状态：准备完成，待项目队长和负责原表核对的成员实际填写。本单不是新批准记录。

本次保持R1筛查参数：增速差{config['r1_gap_threshold']:.0%}、强线索{config['r1_strong_gap_threshold']:.0%}、绝对金额门槛{config['r1_absolute_threshold']:g}元。参数为演示筛查配置，不能宣称为准则阈值。专业目标应收口径为账面余额；自动读取报表列示额时标为净额，保留限制，不自动转换为余额。

工程改动：按科目行和年度列取值，拒绝说明句、邻行金额和未知单位；八案候选更正绑定原字段与PDF哈希；保留原候选；发现登记日期与原件链接日期冲突时不改T0，可能跨越截止日的字段暂不参与当前计算。原文年度、口径与专业采用仍待真人核验。

历史签字当前状态：{signoff['signoff_status']}。原因：{signoff.get('reason')}。源文件绑定见同目录JSON；任何后续代码改动都应重新核对绑定。

| 确认事项 | 真人意见 / 证据 |
| --- | --- |
| 主演示案例、分析年度和T0是否接受 | 待填写 |
| 每个采用字段的科目、年度、金额、单位、合并口径和页码 | 待填写 |
| 日期冲突对应官方公告记录；是否另建新T0案例 | 待填写，不沿用旧批准 |
| 净额限制、重要性参数、阈值适用范围 | 待填写 |
| 同意 / 要求修改 / 拒绝及理由 | 待填写 |
| 实际确认人、角色、时间 | 待填写 |
""")
    methods = {"B0": "人工使用同一冻结R1资料与任务", "B1": "确定性计算", "B2": "确定性计算＋单次草稿（原定义，不增加RAG）", "B3": "确定性计算＋RAG＋质疑/反证/复核＋硬校验", "A1": "拟议强对照：单模型＋同一RAG＋同样硬校验", "A2": "拟议消融：完整系统去掉反证角色"}
    contract = {"evaluation_id": "FINALS-EVAL-PROPOSAL-20261009", "status": "draft_not_frozen", "task": "仅使用同一冻结T0资料，判断R1收入应收错配是否需要进一步核查，并列支持来源、限制、下一步资料及程序；不作舞弊认定", "methods": methods, "case_ids": [], "reference_decisions": None, "two_reviewers": [], "model_id": "deepseek-v4-flash", "budget_cny": None, "maximum_provider_calls": None, "repeats": None, "stopping_policy": "预算和停止条件由真人冻结后执行；超额、来源冲突或保护闸门失败则停止并登记", "human_frozen_at": None, "ai_generated_content_notice": NOTICE}
    (out / "02_同任务评估合同_未冻结.json").write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(out / "02_同任务盲评与消融执行说明.md", """
# 同任务盲评与消融执行说明

这是准备材料；尚未冻结案例、参考处理意见、模型预算或正式执行。不能将空表、自动分数或历史三案评分计为本轮效果。

选5类任务：普通企业规则触发、未触发、有证据支持的正常解释、资料缺口、行业边界。先逐字段回页核验，真人接受T0与资料包；正常解释必须有真实来源，不因期望五类齐全而编造。边界与缺口的正确拒绝单列，不混入适用任务完成率。

B0、B1、B2、B3保持原定义。A1（单模型＋RAG＋相同硬校验）和A2（去反证角色）是拟议消融；执行器和同预算设置仍需在冻结合同后专门验收，不能把A1冒充B2。所有方法使用相同资料指纹、任务与输出格式：处理建议、引用、限制、材料清单、程序。每条真实尝试保留，首次通过与修正后通过分开。

协调人把结果分配随机编号，方法映射单独保管。B0人员先完成任务，不能预先看到AI输出。两名真实复核者独立填写相同编号表，意见互不传阅；有分歧则登记各自理由。输出为空、失败或拒绝均保留状态，不能以删掉坏样本提高均值。

评分维度：科目/年度/金额/单位/口径正确性；引用支持度；可执行事项与资料范围；边界与正确拒绝；反证是否实际纠正或限制主张。每项0–4分并附原文依据，未核验写未评价。字段漏取另报覆盖率，空输出另报数量。小样本只支持当前若干任务的结论。

效率必须计入人工整理、系统等待、人工修正和有效交付数量。用量记录每次调用的输入输出Token、修正次数、费用依据及时间；没有实际账单或当期价格依据时费用留空，不能从“0模型预检”推断三角色成本优势。

当前不具备真正行业独立认证；团队复核应明确为内部复核。正式发盲包前，合同中的案例、T0、参考处理意见、预算、重复次数和停止条件都必须由真人填写并冻结。
""")
    for reviewer in ("复核者A", "复核者B"):
        with (out / f"03_{reviewer}_独立评分空表.csv").open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["匿名结果编号", "真实复核者", "开始时间", "结束时间", "字段正确性0至4", "引用支持0至4", "事项可执行性0至4", "边界处理0至4", "反证贡献0至4", "需补资料", "原文依据与理由", "是否采用", "分歧理由"])
    with (out / "04_运行成本与人工时间空表.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerow(["结果编号", "案例包指纹", "任务指纹", "模型", "开始结束时间", "首次通过", "最终通过", "调用数", "修正数", "输入Token", "输出Token", "费用", "费用依据", "人工整理秒", "人工修正秒", "有效交付数量", "失败或拒绝理由"])
    write_md(out / "05_真实业务过程与陌生用户试用记录.md", """
# 真实业务过程与陌生用户试用记录

请两名未参与制作的真实使用者各自完成一次任务：确认企业、找到指定年度公告、理解可用处理方式、运行一个可用样例、证明一个金额、找到下一步材料、导出结果。观察人不要代点按钮。记录真实开始结束时间、卡住的位置、求助次数、返工和最终交付；不填写预计耗时作为成绩。

| 使用者 / 身份 / 日期 | 待真实填写 |
| --- | --- |
| 企业与任务、使用本机或云端 | 待填写 |
| 开始 / 结束 / 等待 / 人工修正时间 | 待填写 |
| 卡点、求助、返工次数、原话 | 待填写 |
| 是否完成、交付编号与文件 | 待填写 |
| 认为可节省哪项工作、依据 | 待填写 |

业务过程只演示真实发生的处理：原表科目→计算→具体质疑→正常解释查证→哪条主张改变或保持→索取资料→真人实际采用/拒绝→批准交付。金额确认、事项采用、交付批准分别记录身份与时间。没有真实反证变化时说明限制或保持原因，不制作假反转。自动技术更正不当作真人修改。

每份索取资料记录：对应事项与认定、所需期间、最小字段范围、解决的问题、责任人及优先顺序。尚未实际取得的合同、函证和回款记录标为待取得，不能把年报引用当作这些证据已齐备。
""")
    cases = load_seed_cases(ROOT)
    conflicts = [{"case_id": c["case_id"], "engineering_snapshot": c.get("engineering_snapshot")} for c in cases if c.get("engineering_snapshot")]
    (out / "来源日期冲突与工程更正登记.json").write_text(json.dumps(conflicts, ensure_ascii=False, indent=2), encoding="utf-8")
    write_md(out / "06_现场演示异常与当前事实口径.md", """
# 现场演示异常与当前事实口径

主演示使用已核验的本机案例；云端提前唤醒并核对代码版本。先检查启动状态、来源、任务台账、模型通道和案例年度，再运行。PPT及口头表达统一使用本轮验收结果；不重复旧的“100%准确”。完成率要同时报样本量与是否含修正。

来源查询超时：说明官方查询尚未完成，稍后重试或打开登记原件；不宣称无企业或无年报。来源日期冲突：展示旧日期与链接日期，待官方公告确认；不悄悄改T0复用旧批准。字段缺口：展示错误被拦及需要回查哪一行；不要宣称完整成功。

模型失败、额度或并发限制：使用页面明确提供的确定性备用；说明本次零模型调用。Web重启：运行中断如实展示，不能声称线程自动续跑；已完成结果按真实台账读取。缓存复用：说明复用旧经校验结果，本次没有新的模型调用。取消：等待服务端终态，不把关掉窗口称为已取消。

备用材料使用本轮实际截图、同源JSON/CSV/PDF与录屏；每个文件绑定运行编号及版本。记录真实团队分工，每人能解释一条规则、一份原文、一次失败及修复。没有真实合作、采用或收入证据的内容不写进答辩。
""")
    print(out)


if __name__ == "__main__":
    main()
