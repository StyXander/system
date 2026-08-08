# 审迹智链 AuditTrace

审迹智链是北京市大学生数智会计创新应用竞赛项目，面向会计师事务所审计项目组，在审计计划阶段对销售与收款循环进行证据约束型预筛查。

统一 AI 声明：AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

## 项目边界

- 正式场景：审计计划阶段—销售与收款循环。
- 主要输出：预审风险备忘录、最多 5 项待核查事项、资料索取清单。
- 主链：确定性计算 → 案例隔离 RAG → 质疑/反证/复核 Agent → Schema 与事实语言硬校验 → 人工处理。
- 不做：舞弊认定、重大错报认定、审计意见、业务承接决定、续聘决定、投资建议和全市场实时扫描。
- 项目所有者已于 2026-08-07 对合法公开案例授予完整分析与最小必要模型传输许可；许可记录保存在 `PROJECT_AUTHORIZATION.json`，新来源快照仍按哈希重新核验。

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

若第一步提示“巨潮股票清单请求失败”并包含 `network_permission_denied` 或 Windows `10013`，说明启动服务的进程没有外网访问权限，并非企业不存在。请先关闭旧服务窗口，再双击根目录 `启动审迹智链.bat`；失败任务可在工作台保留并重新执行。系统会把当前步骤同步标为失败，不再停留在“进行中”。

若需要复现实测版本，可使用 `backend\requirements-lock.txt`。真实 Key 只能写入本机 `.env`，不得写入网页、日志、压缩包或聊天消息；对外包只允许携带空的 `.env.example`。

## 演示路径

1. 打开“项目与资料”，输入企业名称或股票代码，默认执行巨潮公开年报预筛；
2. 系统自动搜索、下载、校验、建立 RAG 并运行可用规则；缺失字段只影响对应规则或趋势，不会猜测金额；
3. 查看分析截止年度、已运行规则、跳过规则、缺失字段、RAG 片段和资料索取清单；
4. 在“原文检索”按文档编号和页码回查原文片段；
5. 取得补充资料后，先完成授权/脱敏，再以独立证据绑定原运行续分析；补充资料不会静默覆盖公开年报原字段；
6. 字段人工复核是正式采用、证据冻结、缓存或导出前的步骤，不是首次公开预筛的前置门槛；
7. 真人复核并批准后，才可缓存或导出 `report_v2`。

## 巨潮新企业自动流程

已新增基于[巨潮资讯网](https://www.cninfo.com.cn/)公开来源的自动流程：输入股票代码或企业名称后，系统依次完成企业确认、年度报告公告搜索、全文版本选择、PDF 文件头/页数/企业/年度校验、SHA-256 记录、独立案例登记、案例隔离 RAG 建库和固定问题检索烟测。

网页和 API 默认使用 `full_analysis`；API 调用者仍可显式选择 `rag_only`，只完成下载、校验与本地 RAG。启动服务后，可以在 PowerShell 中执行：

```powershell
$body = @{
    company_query = "603337"
    years = 3
    latest_year = 2024
    analysis_mode = "full_analysis"
    rule_ids = @("R1")
} | ConvertTo-Json

$job = Invoke-RestMethod http://127.0.0.1:8000/api/pipelines/cninfo `
    -Method Post -ContentType "application/json" -Body $body
$job.task_id
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)/result"
```

公开预筛采用规则级、年度级优雅降级：最近两年具备 R1 所需字段时直接计算；第三年缺失只关闭三年趋势；最新年度不完整时使用最近一组完整连续年度并显示分析截止年度；单条规则缺字段时只跳过该规则，其余规则和 RAG 继续。所有缺失金额保持空缺，不估算、不补造。项目所有者许可只允许公开来源的最小必要证据进入已配置模型；新企业、新报告或来源哈希变化后，字段页码、单位和合并口径仍生成新的核验状态，不能沿用旧快照结论。

### 行业闸门与 50 家热缓存

系统现在在规则前增加 `industry_gate_v1`：普通工商企业直接进入 R1/R2，房地产/建筑等条件适用企业保留口径限制，银行/保险/证券等金融企业返回 `NOT_APPLICABLE` 并保留公开年报 RAG，行业元数据不足时返回 `INDUSTRY_UNKNOWN`，不猜测行业。中国海油按能源类直接适配；中国人寿按金融类跳过当前 R1/R2，二者都不会再被混成“字段缺失”。

常用企业可以进入 SQLite 热缓存目录。数据库保存企业、年报年度、官方 URL、SHA-256、页码证据、结构化字段、行业闸门和 RAG 指纹；PDF 通过内容寻址保存到 `backend/runtime/pdf_store/<SHA256>.pdf`，案例目录只保留稳定的案例链接，不把二进制文件提交到 GitHub。`backend\cache_seed.example.json` 是可重复预热的 50 家白名单；`backend\cache_seed.lock.json` 是从已校验目录导出的最终元数据锁定清单，不含 PDF/FAISS。2026-08-07 已完成真实联网校验，白名单去重后 **50/50 条目为 `ready`**，每家均具备 2025/2024/2023 快照。新企业仍走巨潮实时路径，成功后自动进入目录。

```text
POST /api/cache/resolve          查询是否命中已校验快照
GET  /api/cache/status            查看目录条目和版本
POST /api/cache/prewarm           批量排队预热白名单
GET  /api/cache/prewarm/{batch_id}  查看批次成功、缺报、不适用、字段缺口和耗时
POST /api/cache/refresh/{ticker}  强制刷新一家企业
GET  /api/cache/companies/{ticker}
GET  /api/industry-gates/{case_id}
```

命中热缓存时，巨潮任务会明确显示“已复用本地已校验 PDF；本次未重复下载”，然后直接进入 RAG 烟测、字段校验和分析；需要追踪最新公告时提交 `force_refresh`，不能把旧快照伪装成现场搜索。`prefer_cache` 会命中新鲜快照；`refresh_if_stale` 会把过期快照标成待刷新；`force_refresh` 才会重新搜索和下载。服务重启会把遗留的预热任务标记为 `needs_human/SERVICE_RESTART_RECOVERY`，预热并发限制为 2 家，运行目录默认配额为 5GB。

2026-08-05 真实烟测以 603337 杰克科技为例完成 2022—2024 年报搜索、下载、校验和 RAG 建库，共生成 1103 个检索片段；公开预筛允许候选继续进入规则链，但 `passed_technical_pending_human` 只代表字段仍建议回查，不代表正式专业定稿。正式缓存与导出仍由真人复核闸门控制。

## 自动化验证

源码仓库当前一次性复验结果（2026-08-07）：**84 passed、1 warning**；定向巨潮回归：**16 passed、1 warning**；`node --check assets/official-v4/app.js` 和 `git diff --check` 通过。中文说明性行检查：**676/6670 = 10.13%**。

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe scripts\check_chinese_comments.py
backend\.venv\Scripts\python.exe scripts\export_cninfo_cache_manifest.py --output backend\cache_seed.lock.json
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
- 公开阶段只处理巨潮等公开来源；内部客户资料默认不上传公共网站。产品化部署应优先采用审计师本机、事务所内网或私有部署，并执行最小化传输、脱敏、短期留存、访问审计和可审计删除。
- 竞赛演示只使用公开年报与合成补充资料；真实内部文件如需续分析，应由资料所有者确认授权和脱敏后进入受控环境。
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
