# 审迹智链竞赛演示版 0.10.2 本地启动与验收

> 正式入口：根目录 `index.html`，必须由 FastAPI 提供；不要双击静态文件。  
> 正式范围：审计计划阶段—销售与收款循环。  
> 统一 AI 声明：AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。  

> **当前整改发布候选（2026-08-29，唯一当前口径）**：发布记录为 `RELEASE-CANDIDATE-20260828-V1`，当前模型统一为 `deepseek-v4-flash`（DeepSeek 官方直连）。15 案主入口读取冻结 manifest；公开任务/结果和模型质量事件目标使用 Supabase，执行模式为免费 Web。已完成或降级结果可跨刷新与 Web 重启读取；运行中的 Web 实例重启会诚实结算为 `interrupted`，不会自动重放模型调用，需点击重置后显式创建新任务。`configured` 只表示配置存在，provider probe（无 Token）与真实 B3（付费业务调用）分别记录；当前评估指针为 `EVAL-20260828-RELEASE-CANDIDATE-V1`，人工评分、重新 probe/B3 和最终发布批准仍为 pending，不能写成“正式效果提升”。可选付费 Worker 仅有模板 `render.worker.example.yaml`，当前 `render.yaml` 不部署 Worker。
> 本机已完成一次 DeepSeek 官方只读 provider probe（`paid_probe_performed=false`），证据为 `backend/release_records/provider_probe_20260829_deepseek_local.json`；Render 的 Secret 注入、生产 probe 和新鲜 B3 仍保持 pending，不能把本机结果当作线上发布通过。

> 本段优先于下方历史 R3/R2 记录；历史目录和签字文件保持原样，不作为本候选版本的自动通过依据。每次演示前应读取 `/api/health`、`/api/status`、`/api/demo/bootstrap`，确认模型、Supabase 台账和发布阻断原因；fallback/cache/replay 的 provider call 均应为 0。

> **2026-08-26 R3 历史快照（已由本候选 supersede）**：新评估目录 `outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/` 已追加 9 条当前代码原始记录：B1 3/3 确定性且 provider call=0；B2 0/3 完成、每案一次真实调用并保留 `MODEL_OUTPUT_VALIDATION_FAILED`；B3 3/3 三角色 `model_success`。B2 与 B3 不合并为官方成功率，项目队长正式评分保持空白。qwen3.5-plus 质量窗口为 7/10=70.0%，低于 80% 且 `alert=true`，继续告警、不自动换模型。12 条活跃来源已逐条 HTTP 200 抽查，监管库仍只作“代表性接入”。现场 600436 已完成一次入口与结构化 JSON/CSV/打印 PDF/DOCX 验收，但当时页面终态为需要人工确认/模型链不完整，未冒充成功。该五视口、测试和质量数字均属于 R3 冻结证据，不等于本候选 runtime 窗口。详见 `PROJECT_STATUS.md` 与 `outputs/browser-r3-export-8000/`。
> 当前事实：竞赛演示版把主线收敛为 15 个冻结案例、1 个主运行按钮、6 个过程阶段（证据载入→规则计算→知识检索→三 Agent 协作→证据验证→结构化输出），以及结果/证据/Agent/技术说明抽屉；结果同时提供页面表格、JSON、CSV 和打印/保存 PDF。另有一个受服务端现场开关保护的“评审现场样例接入”次级入口，本机可处理非 15 案的巨潮公开年报，共享站仍为只读。后端审计引擎版本仍为 0.7.1。`PROJECT_AUTHORIZATION.json` 已记录项目所有者对标准股份和杰克科技当前公开来源快照的最小必要模型传输许可；来源哈希变化仍需重新核验，正式案例冻结、全文再分发和专业采用未获自动批准。
>
> 2026-08-24 终版增强（历史快照，已由下方 2026-08-25 R2 追加验收 supersede；执行计划《审迹智链_竞赛终版增强与完整验收_分步执行计划_2026-08-24.md》）：固定案例运行改为后端异步任务分阶段展示（`POST /api/demo/runs` 返回 202，页面轮询真实六阶段与三角色状态，每阶段带时间戳，刷新可从 sessionStorage 恢复同一任务）；新增多源审计知识底座（`backend/knowledge_sources.manifest.json` 已登记 13 条真实官方/公开案源：年报、证监会处罚、深交所/上交所问询、会计准则、审计准则、税收法规、行业报告、新闻、宏观指标；以 2026-08-24 为冻结截止日，处罚与问询按精确近五年窗口过滤，页面只声明 representative）；新增“系统替你完成什么”审计程序映射（`backend/audit_procedure_map.json`，自动执行/辅助判断/人工保留三列）；补充材料重新评估已纳入同一异步六阶段任务台账（父子运行差异可回查，原字段不被覆盖）；JSON/CSV/打印 PDF 与 docx 报告扩展来源快照、检索轨迹、时间线、模型尝试、程序映射、监管证据与补充差异字段；配图改为 5 张精选黑金插画（WebP，台账见 `assets/official-v4/illustrations/illustration-manifest.json`）。

> 后续模型选择专项修复（历史快照，已由 R2 supersede）新增 1 项台账隔离测试，最终全量回归更新为 **289 passed, 1 warning**；当时默认模型为 `deepseek-v4-flash`，历史记录不会充当当前质量口径的实时成功率。

> 真实模型复验（历史快照，已由 R2 当前窗口 supersede）：本机私有演示实例已完成 `RUN-V7-5666A45FCAA7`，执行方式为 `external_live`，三角色均完成，6 次 provider 调用、29278/13889 tokens、8 条知识命中。Challenge 的首次输出触发语义校验后，经一次受控修正通过；Counter 与 Review 首次通过。当时质量窗口为 8/10=80%。

> **2026-08-25 R2 历史快照（已由本候选 supersede）**：队长追加签字记录为 `outputs/professional-signoff/R1-v0.4-captain-signoff-20260825-r2.json`，状态 `captain_approved_for_competition_demo`；签字后事实快照为 `outputs/final-audit-20260825-r2/`。当时模型 ID 为 `qwen3.5-plus`，冻结质量窗口为 **7/10=70.0%**，低于 80% 且 `alert=true`，不得写成稳定成功，现场保留真实失败码与降级。R2 B1/B2/B3 网络合同目录为 `outputs/evaluation_v5/EVAL-20260825-B1B3-CURRENT-R2-NETWORK/`：B1 3/3、B2 0/3（`MODEL_OUTPUT_VALIDATION_FAILED`）、B3 3/3 三角色 `model_success`；旧评估目录不被覆盖。R2 的测试、视口和 axe 数字仅作历史证据；当前候选以 release pointer 和 runtime quality window 为准。

## 一、最省事的启动方法

双击根目录 `启动审迹智链.bat`。第一次会创建 `backend\.venv` 并按 `backend\requirements.txt` 安装依赖；服务窗口保持打开，然后访问：

`http://127.0.0.1:8000`

手动启动：

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

复现实测依赖可改用 `backend\requirements-lock.txt`。密钥只写入本机 `.env`；发送包只包含 `.env.example`。

启动器会同时检查 `/api/health` 与 `/api/demo/bootstrap`。如果 8000 端口上是旧后端或不兼容进程，启动器会明确阻断并要求关闭旧服务窗口，不会把单独的健康检查 200 误报成当前演示版已经就绪。若模型链显示 `network_permission_denied` 或 Windows `10013`，说明当前服务进程没有外网权限；关闭旧服务窗口并用正式启动器重启。`dns_resolution_failed` 表示 DNS 或代理异常，`network_timeout` 表示连接超时，这些状态都不会伪装成模型成功。

## 二、竞赛演示工作流

1. 首先看到“证据地平线”项目首页，进入旧版视觉恢复的“证据先行”产品定位页，再点击“进入证据工作台”；工作台默认选中标准股份，也可从 3 个精选案例或“查看全部 15 个案例”切换公司；
2. 点击唯一主按钮“开始审计预筛”；后端创建异步任务（202），页面每 1 秒轮询真实状态，刷新页面从 sessionStorage 恢复同一任务，不重新发起运行；
3. 页面依次显示读取证据、规则计算、知识检索、Agent 协作、证据验证和结构化输出六个阶段；每个阶段的状态与备注来自后端任务台账（含 updated_at 时间戳），前端定时器不推进业务阶段；
4. 结果区展示结构化待核查事项、证据追踪轴、语义表格和“系统替你完成什么”程序映射，可下载 JSON/CSV、打印或保存 PDF，也可打开原文证据和三 Agent 过程抽屉；结果后提供“补充证据并重新评估”次级按钮（内置样例→父子运行→前后差异，原字段不被覆盖）；
5. 点击“一键重置演示”即可回到当前案例的初始状态，重新演示不需要输入公司代码、规则、run_id 或 cache_id；
6. 只有当次真实模型调用、三角色和硬校验全部完成时才显示模型成功；Provider 失败、确定性备用和缓存回放分别如实标注，不冒充新模型成功。

竞赛演示页不暴露上传、字段确认、缓存管理、补充资料和正式复核写入入口。顶部“现场样例接入”是次级入口，不参与首屏请求；只有本地启动器设置 `AUDITTRACE_ONSITE_LIVE_SAMPLE=true` 时才允许创建非内置巨潮任务，云端共享部署默认关闭。

## 三点一、输入新企业并自动完成巨潮年报到 RAG

网页“现场样例接入”已经提供本机入口；这不是竞赛手册规定的“企业搜索”功能，而是用来证明现场可处理真实新样例。手册硬性项是“实时处理样例数据并输出结构化结果”，没有规定输入必须是搜索、上传或新企业。如需脚本复现，也可以调用 `POST /api/pipelines/cninfo`。请求体至少包含 `company_query`，可选 `years`、`latest_year`、`analysis_mode` 和 `rule_ids`。推荐先使用 `rag_only`：

```powershell
$body = @{
    company_query = "603337"
    years = 3
    latest_year = 2024
    analysis_mode = "rag_only"
    rule_ids = @("R1")
} | ConvertTo-Json
$job = Invoke-RestMethod http://127.0.0.1:8000/api/pipelines/cninfo -Method Post -ContentType "application/json" -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/pipelines/$($job.task_id)/result"
```

流程只访问巨潮公开页面和静态 PDF 原件，步骤日志会保存公告候选、最终 URL、页数、SHA-256、案例编号、RAG 片段数和检索编号。`full_analysis` 会继续提取财务字段候选；当前保守质量闸门会把疑似附注号、页码、期限或阈值误识别的候选排除在规则与模型证据之外，字段页码/单位/口径仍须真人复核。只有案例自身具备完整许可记录、运行开关允许且隐私扫描通过时才会调用外部模型。字段确认接口为 `POST /api/cases/{case_id}/fields/confirm`，支持 `confirm`、`correct`、`reject`，修正前的自动候选会保留在 `candidate` 和 `human_review_history` 中。

2026-08-05 的 603337 真实烟测结果：2022—2024 三份年报通过搜索、下载和 PDF 硬校验，RAG 生成 1103 个检索片段；字段候选技术通过但仍是 `passed_technical_pending_human`。

## 三、模型配置

```ini
DEEPSEEK_API_KEY=团队自己的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
AUDITTRACE_PROVIDER_PROBE_ENABLED=true
AUDITTRACE_DEMO_TASK_PERSISTENCE=supabase
AUDITTRACE_DEMO_EXECUTOR_MODE=web
```

公开部署默认只允许同源访问。需要跨域时，只在 `AUDITTRACE_CORS_ORIGINS` 中填写完整且精确的 `http(s)://主机[:端口]`；经反向代理部署时，`AUDITTRACE_TRUSTED_PROXY_HOPS` 与 `AUDITTRACE_TRUSTED_PROXY_CIDRS` 必须成对配置，且不得使用 `/0` 信任网段。`render.yaml` 通过 Render `generateValue: true` 生成至少 32 位的 `AUDITTRACE_PUBLIC_QUOTA_SECRET`，秘密值不写入仓库。

`GET /api/health` 和 `GET /api/status` 的 `model` 对象会返回 `full_analysis_ready`、`full_analysis_reason_code`、`full_analysis_message` 与 `deterministic_backup_available`。`model_status=configured` 只表示 Key 存在；provider probe（无 Token 的通道探测）、模型执行就绪和真实 B3 是三层独立门禁。公开生产只有 Supabase 台账、Key、额度秘密、DeepSeek 直连通道和真实探测均满足时才允许 `external_live`；明确选择备用时始终标注“确定性备用、未调用模型”。

模型配置存在不等于完整链通过。0.7.1 已为质疑、反证、复核角色分别生成工具 Schema，并增加确定性事实语言一致性闸门。历史 `RUN-V7-00ED00962F34` 虽曾完成三个角色并形成草稿，但新增闸门发现其把未达到的强阈值写成已达到，因此不再是有效 B3。B2 `EVAL-B2-2F8BE053630D` 的一次实际调用因返回5条claims超过最多4条而失败，原始响应和哈希已留档，未裁剪或再次调用；该调用发生于本轮合规失败关闭补丁前，不具备正式比较资格。没有 Key、合法样例未确认或案例禁止模型传输时，系统只提供本地预检并如实标记不完整；最新结论见 `PROJECT_STATUS.json`。

## 四、自动化验证

源码仓库与清洁包分开验收：

```powershell
# 源码仓库（含交付包、旧路由和杰克科技公开案例检查）
backend\.venv\Scripts\python.exe -m pytest backend\tests -q

# 中文注释与独立说明性 docstring
backend\.venv\Scripts\python.exe scripts\check_chinese_comments.py

# 清洁包：解压后在包根目录运行
backend\.venv\Scripts\python.exe -m pytest -q
```

2026-08-24 竞赛演示版 0.10.0 最终源码回归为 **259 passed、1 warning**；中文说明行检查沿用本轮基线 **1918/18628（10.30%）**；前端演示契约为 **89 个唯一 ID、77 个引用、1 个脚本**，结果判定 6 个向量通过。专项覆盖 15 案 bootstrap、现场新企业任务、JSON/表格/CSV/打印 PDF、真实模型/确定性备用/缓存回放的诚实状态、供应商超时边界、证据 ID、禁用词、启动器旧后端识别和评委演示状态机。唯一代码层 warning 是 Starlette TestClient / httpx 兼容性弃用提示。历史 2026-08-09 无密钥清洁运行包仍登记为 **171 passed、1 warning**，本轮未重建该交付包。

0.10.0 在“证据地平线”视觉首页与工作台之间恢复了上一版“证据先行的销售收款预审”产品定位页，工作台统一为旧版深青黑、细线分栏、数字账页和右侧证据追踪轴。关键指标按百分比、百分点、万元或亿元突出显示，不再是一整排同权文字。四视口（1440×1000、1024×768、768×1024、390×844）均无横向溢出、重复 ID、控制台错误、页面错误、失败请求或 HTTP 错误；axe 无 violation，渐变背景产生的对比度 incomplete 已结合四张长截图人工复核，最终源码证据位于 `artifacts/competition-demo-v010-audit-20260824/static-exact-final/`。

结构化成果已做真实浏览器下载验收：标准案例与现场企业均可同源生成表格、JSON、CSV 和打印 PDF，文件可解析、运行/任务编号匹配且含 AI 边界声明。未登记企业 `600436` 首次任务 `CNINFO-3BC9823B4708` 从巨潮真实取得并硬校验 3 份年报、建立 1207 块案例隔离 RAG、提取 6 条字段；修复 `indexing` 与 `ready_for_analysis → analyzing` 轮询竞态并清理英文内部枚举后，最终热缓存复验 `CNINFO-86256D86978E` 形成运行 `RUN-V7-55F34B22A43C`、12 行结构化指标和三类可下载文件，严格审计见 `artifacts/competition-demo-v010-audit-20260824/structured-output-label-final/structured-output-audit.json`。当前最终源码的供应商探测仍返回 `provider_temporarily_unavailable`，所以本轮没有伪造新的真实模型成功；此前批次 7 的 `RUN-V7-B655B4D7EAEE` 仍只作为既有三 Agent 真实模型准入证据。

当前清洁运行包为了保留标准案例的 RAG 与来源复验能力，仍含四份公开年报全文；在真人确认全文再分发边界前，它仅供团队内部技术复验，**禁止外发**。队员 Word/Excel 包和老师方案材料包不含年报全文。

覆盖：R1正反例、净额/重要性/三年趋势；模板导入、真实哈希、危险 ZIP 和案例隔离；杰克科技三年官方年报、余额/准备/净额、公开账龄勾稽与 R1 未触发负向控制；RAG 进入 Agent 证据包、角色专用 Schema、错误引用、分阶段模型失败和确定性事实语言矛盾；四层状态；补充资料父子运行；旧运行只读；精确AI声明、自动化水印和 report_v2。

## 五、实时状态与边界

- `GET /api/status`：版本、案例、RAG、模型就绪状态和 Render 运行时提交/分支/服务信息；历史 `PROJECT_STATUS` 只作状态快照，不冒充当前部署提交；
- `GET /api/cases`：已登记案例；
- `GET /api/cases/template`：标准案例模板；
- `POST /api/runs`：`run_mode=full_analysis|calculation_only`，场景只接受“审计计划”。
- `POST /api/pipelines/cninfo`：本机现场模式输入新企业，自动完成巨潮年报检索、下载校验、案例登记、RAG、字段候选与分析主链；用 `GET /api/pipelines/{task_id}` 看进度，用 `/result` 看结果。竞赛手册要求的是现场处理新样例和结构化成果，并未要求建设泛企业搜索；这里的企业输入是证据接入入口，不作为独立创新点夸大；
- `POST /api/cases/{case_id}/fields/confirm`：逐项保存真人字段确认、修正或拒绝；未通过真人确认的巨潮字段不能进入 `/api/runs`。

公开共享站只允许内置案例、RAG、仅计算和内置补充样例；自定义上传、非内置企业、强制刷新、字段确认、正式复核批准和案例 ZIP 在前端点击前禁用，后端继续返回 403。人工字段判断区仍会显示“此处是人工字段判断位置”；私有环境才开放完整写入能力。完整版本和人工门槛见根目录 `PROJECT_STATUS.md`。系统不得替代：R1专业签字、第二公开案例冻结、合法样例确认、真人复核和B0—B3评分。

当前公开站已部署 `9cb9531` 功能版本并由 `/api/status.deployment.commit` 实时证明；Render 自动额度秘密已生效。上汽集团只执行过一次当前版本真实完整分析 `RUN-V7-75962367DF2A`，供应商返回 `MODEL_PROVIDER_AUTH_FAILED`，系统保留首角色失败码并跳过后续角色，没有形成或伪造 AI 草稿。请在 Render 更换有效的 DeepSeek Key 后只复验一个案例；不要因此重新运行 51 案付费批量。

## 六、B0—B3 与当前受控记录

- B0：真人仅看冻结资料的人工基线，当前未执行；
- B1：确定性计算，`RUN-V7-0BDE5060FBED` 已执行；
- B2：确定性计算加一次单模型草稿，`EVAL-B2-2F8BE053630D` 因5条claims超过最多4条而失败；
- B3：确定性计算、RAG、三Agent和硬校验；历史 `RUN-V7-00ED00962F34` 经新增事实闸门复核失败。

原始记录位于 `outputs/2026-07-29-controlled-evaluation/retry-01/`，已有JSON拒绝覆盖，所有人工评分为空白。不要编辑JSON来“修复”失败结果；后续真人评分应另存原始工作簿快照并记录SHA-256。

标准股份和杰克科技当前公开来源快照已由项目所有者登记最小必要模型传输许可，但这不等于全文再分发、正式案例冻结或专业采用许可；来源哈希变化必须重新核验。新导入案例若把 `model_transfer_allowed` 设为 `true`，还必须提供确认人、日期、许可依据、模型供应商、最小传输范围和许可记录编号，缺一项系统即拒绝导入；运行开关、隐私扫描与 manifest 记录仍须分别通过。

所有新生成及对外API JSON、网页草稿和Word报告都携带精确AI声明。已封存的历史原始JSON为保全字节和SHA-256不重写；使用当前API读取时会追加声明。

## 七、标准股份四份年报官方来源

| 年度 | 巨潮资讯官方全文URL |
|---|---|
| 2022 | https://static.cninfo.com.cn/finalpage/2023-04-19/1216455382.PDF |
| 2023 | https://static.cninfo.com.cn/finalpage/2024-04-18/1219646140.PDF |
| 2024修订版 | https://static.cninfo.com.cn/finalpage/2025-04-29/1223359539.PDF |
| 2025 | https://static.cninfo.com.cn/finalpage/2026-04-30/1225266733.PDF |

运行 `backend\.venv\Scripts\python.exe scripts\verify_standard_annual_report_sources.py` 可重新下载并校验登记SHA-256；网络失败应记为待核验，不得用本地文件冒充在线验证。
