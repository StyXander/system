# 审迹智链 AuditTrace

审迹智链是北京市大学生数智会计创新应用竞赛项目，面向会计师事务所审计项目组，在审计计划阶段对销售与收款循环进行证据约束型预筛查。

统一 AI 声明：AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

## 项目边界

- 正式场景：审计计划阶段—销售与收款循环。
- 主要输出：预审风险备忘录、最多 5 项待核查事项、资料索取清单。
- 主链：确定性计算 → 案例隔离 RAG → 质疑/反证/复核 Agent → Schema 与事实语言硬校验 → 人工处理。
- 不做：舞弊认定、重大错报认定、审计意见、业务承接决定、续聘决定、投资建议和全市场实时扫描。
- 当前两个真实公开案例均为 `model_transfer_allowed=false`，在真人确认合法样例、保存期限、再分发和模型传输边界前，只允许本地计算预检。

## 运行要求

- Windows 10/11；
- Python **3.10 或更高版本**；
- 首次安装需要访问 Python 包源；
- 需要本地浏览器查看页面；
- 模型 Key 可选。没有 Key 或案例禁止模型传输时，仍可运行仅计算预检。

## 安装与启动

推荐双击根目录的 `启动审迹智链.bat`。也可以在 PowerShell 中执行：

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

然后访问 `http://127.0.0.1:8000`。不要直接双击 `index.html`，正式网页必须由 FastAPI 提供。

若需要复现实测版本，可使用 `backend\requirements-lock.txt`。真实 Key 只能写入本机 `.env`，不得写入网页、日志、压缩包或聊天消息；对外包只允许携带空的 `.env.example`。

## 演示路径

1. 打开“项目与资料”，下载或导入模板化案例；
2. 检查字段、来源页、T0 和文件哈希；
3. 在“候选指标”保留 R1，R2 仅作辅助；R3—R8 是路线图；
4. 在“分析工作台”选择“仅计算预检”，查看程序筛查、资料缺口和运行完整性；
5. 在“原文检索”按文档编号和页码回查原文片段；
6. 只有经过真人许可并满足模型传输条件后，才可考虑完整分析；
7. 真人复核并批准后，才可缓存或导出 `report_v2`。

## 巨潮新企业自动流程

已新增基于[巨潮资讯网](https://www.cninfo.com.cn/)公开来源的自动流程：输入股票代码或企业名称后，系统依次完成企业确认、年度报告公告搜索、全文版本选择、PDF 文件头/页数/企业/年度校验、SHA-256 记录、独立案例登记、案例隔离 RAG 建库和固定问题检索烟测。

默认使用 `rag_only`，不会把年报发送给外部模型。启动服务后，可以在 PowerShell 中执行：

```powershell
$body = @{
    company_query = "603337"
    years = 3
    latest_year = 2024
    analysis_mode = "rag_only"
    rule_ids = @("R1")
} | ConvertTo-Json

$job = Invoke-RestMethod http://127.0.0.1:8000/api/pipelines/cninfo `
    -Method Post -ContentType "application/json" -Body $body
$job.task_id
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)/result"
```

需要查看完整分析编排时，将 `analysis_mode` 改为 `full_analysis`。系统仍会先做字段候选和技术校验；字段页码、单位、合并口径需要真人确认，`model_transfer_allowed=false` 时只返回本地计算和“模型传输未许可”的不完整状态，不会暗中调用外部模型。

2026-08-05 真实烟测以 603337 杰克科技为例完成 2022—2024 年报搜索、下载、校验和 RAG 建库，共生成 1103 个检索片段；R1 营业收入/应收账款候选已提取，但仍标记为 `passed_technical_pending_human`，不能直接当作专业定稿。

## 自动化验证

源码仓库当前一次性复验结果（2026-08-05）：**71 passed、1 warning**；中文说明性行检查：**613/6121 = 10.01%**。

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe scripts\check_chinese_comments.py
```

若 Windows 系统临时目录权限导致 `pytest` 在夹具初始化阶段报 `PermissionError`，可使用项目内一次性临时目录：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q --basetemp tmp\pytest-local
```

当前无密钥清洁运行包的历史独立复验结果为 **57 passed、1 warning**（2026-07-30）。它与源码仓库测试分开登记，不代表新的清洁包已经重新构建。

## 真实状态与人工门槛

`PROJECT_STATUS.json` 是机器可读单一事实源，`PROJECT_STATUS.md` 是人工阅读版，`GET /api/status` 会在此基础上叠加实时案例、RAG 和模型配置状态。

当前 B0—B3 事实：B0 未执行；B1 已完成确定性计算；B2 因 5 条 claims 超过最多 4 条而失败；历史 B3 因确定性事实语言闸门失败，不具备正式比较资格。R1 专业签字、第二案例冻结、合法样例确认、新 B3、真人报告批准和 B0—B3 人工评分仍必须由真人完成。

## 资料和许可边界

- 根目录年报全文仅用于本地开发和受控技术复验；真人确认全文再分发边界前，不得放入对外包。
- 官方来源 URL、公告标题和 SHA-256 记录在 `PROJECT_STATUS.json` 和案例注册表中。
- Python 依赖和网页图标的许可说明见 `THIRD_PARTY_NOTICES.md`。
- 项目自身授权边界见 `PROJECT_LICENSE.md`。
- 公开部署说明仅是部署前检查清单；线上地址必须重新部署并通过真实 HTTP 验收后才能对外宣称可用。

## 主要文件

- `index.html`：正式网页入口；
- `backend/app/`：FastAPI、案例、RAG、Agent 和报告链；
- `02_最终确定方案/`：方案书、详细计划、分工和案例说明；
- `14_审迹智链_全项目审批与AI修改指令_2026-08-04.md`：本轮审批结论和后续整改指令；
- `README_RUN.md`：较完整的本地启动与验收说明。
