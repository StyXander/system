# 审迹智链 0.7.1 本地启动与验收

> 正式入口：根目录 `index.html`，必须由 FastAPI 提供；不要双击静态文件。  
> 正式范围：审计计划阶段—销售与收款循环。  
> 统一 AI 声明：AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。  
> 当前事实：`PROJECT_AUTHORIZATION.json` 已记录项目所有者对标准股份和杰克科技当前公开来源快照的最小必要模型传输许可；来源哈希变化仍需重新核验，正式案例冻结、全文再分发和专业采用未获自动批准。2026-08-16 合并整改后的源码仓库回归为 **213 passed、1 warning**；前端契约为 **240 unique ids、436 refs、9 views**。历史 51 案 `agent_prompt_v3` 外部模型链为技术证据，不是当前修复代码或有效 B3 的专业验收。

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

若第一步显示“巨潮股票清单请求失败”，先查看错误详情：`network_permission_denied` 或 Windows `10013` 表示当前服务进程没有外网权限，并不表示巨潮接口或企业代码无效。关闭旧服务窗口后，双击 `启动审迹智链.bat` 重新启动，再在工作台重试原任务。`dns_resolution_failed` 表示 DNS 或代理异常，`network_timeout` 表示连接超时；三种情况均不会伪装成“未找到企业”。

## 二、当前工作流

1. 在“项目与资料”输入企业名称或股票代码，选择年报数量；
2. 页面调用巨潮自动流程，显示企业确认、公告搜索、全文选择、下载、PDF校验、案例登记、RAG和检索烟测状态；
3. 公开共享站默认选择 `只下载 + RAG`，不猜测财务金额，也不向外部模型传输年报；新企业流程默认 `rag_only`，避免无意消耗模型额度；
4. 只有私有环境、模型就绪且许可完整时才显示并允许 `继续完整分析`；它只形成字段候选，必须在“字段候选真人确认”中逐项确认、修正或拒绝；公开共享站只读并在点击前禁用该写入路径；
5. 只有收入、应收账款等当前规则所需字段全部经过真人确认后，正式采用、缓存或导出才会放行；公开演示仍可运行标注为不完整的仅计算预检；
6. 标准案例 ZIP 仍可用于离线与合成验收：填写 manifest、财务字段、来源页和真实文件哈希，并完成授权/脱敏确认；
7. 完整分析执行计算→固定问题RAG→三Agent→硬校验；失败不会生成最终AI草稿；
8. 在“原文检索”按文档编号和页码回查候选片段；低于 0.50 的 RAG 结果保留但显示“低置信候选，必须回原页复核”；补充资料后的续分析默认不继承旧备用标志；
9. 真实复核人记录保留/降级/暂缓并批准后，才可缓存或导出 `report_v2`。

## 三点一、输入新企业并自动完成巨潮年报到 RAG

网页已经提供正式入口；如需脚本复现，也可以调用 `POST /api/pipelines/cninfo`。请求体至少包含 `company_query`，可选 `years`、`latest_year`、`analysis_mode` 和 `rule_ids`。推荐先使用 `rag_only`：

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
DEEPSEEK_MODEL=实际可用的模型ID
```

公开部署默认只允许同源访问。需要跨域时，只在 `AUDITTRACE_CORS_ORIGINS` 中填写完整且精确的 `http(s)://主机[:端口]`；经反向代理部署时，`AUDITTRACE_TRUSTED_PROXY_HOPS` 与 `AUDITTRACE_TRUSTED_PROXY_CIDRS` 必须成对配置，且不得使用 `/0` 信任网段。`render.yaml` 通过 Render `generateValue: true` 生成至少 32 位的 `AUDITTRACE_PUBLIC_QUOTA_SECRET`，秘密值不写入仓库。

`GET /api/health` 和 `GET /api/status` 的 `model` 对象会返回 `full_analysis_ready`、`full_analysis_reason_code`、`full_analysis_message` 与 `deterministic_backup_available`。`model_status=configured` 只表示 Key 存在；公开模式只有 Key、额度秘密、额度账本和当前额度都可用时才是 `execution_mode=external_live`。缺少条件时页面显示中文原因和可操作路径，不做供应商探测；明确选择备用时始终标注“确定性备用、未调用模型”。

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

2026-08-16 源码仓库当前实际结果为 **213 passed、1 warning、200.11s**；中文说明行检查为 **1758/17545（10.02%）**；前端契约为 240 个唯一 ID、436 个引用、9 个视图。专项覆盖模型就绪组合、额度与账本失败、无 `run_id` 的显式备用、补充续分析备用标志、R2 数据缺口、资料缺口与 evidence ID 去重、RAG 低置信提示、匿名公开 Demo 前后端只读边界和状态中文化。仓库内旧 pytest 临时目录存在 Windows 权限锁，本次改用系统临时目录完成复验；唯一代码层 warning 是 Starlette TestClient / httpx 兼容性弃用提示。历史 2026-08-09 无密钥清洁运行包仍登记为 **171 passed、1 warning**，本轮未重建该交付包。

当前清洁运行包为了保留标准案例的 RAG 与来源复验能力，仍含四份公开年报全文；在真人确认全文再分发边界前，它仅供团队内部技术复验，**禁止外发**。队员 Word/Excel 包和老师方案材料包不含年报全文。

覆盖：R1正反例、净额/重要性/三年趋势；模板导入、真实哈希、危险 ZIP 和案例隔离；杰克科技三年官方年报、余额/准备/净额、公开账龄勾稽与 R1 未触发负向控制；RAG 进入 Agent 证据包、角色专用 Schema、错误引用、分阶段模型失败和确定性事实语言矛盾；四层状态；补充资料父子运行；旧运行只读；精确AI声明、自动化水印和 report_v2。

## 五、实时状态与边界

- `GET /api/status`：版本、案例、RAG、模型就绪状态和 Render 运行时提交/分支/服务信息；历史 `PROJECT_STATUS` 只作状态快照，不冒充当前部署提交；
- `GET /api/cases`：已登记案例；
- `GET /api/cases/template`：标准案例模板；
- `POST /api/runs`：`run_mode=full_analysis|calculation_only`，场景只接受“审计计划”。
- `POST /api/pipelines/cninfo`：输入新企业，自动完成巨潮年报搜索、下载校验、案例登记和 RAG；用 `GET /api/pipelines/{task_id}` 看进度，用 `/result` 看结果；
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
