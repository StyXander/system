# 审迹智链单一事实源

更新时间：2026-08-25
统一 AI 声明：**AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。**

## 2026-08-26 R3 缺口修复与真实验收（当前最高优先级事实）

- B1—B3 已在当前代码建立新的追加式合同目录：`outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/`。五粮液、中国海油、标准股份各执行一次，共 9 条原始 JSON；旧 R2 目录和历史目录均未覆盖。
- R3 结果：B1 为 3/3 确定性完成且外部调用 0；B2 为 0/3 完成，每案仅一次真实单模型调用，原始失败码均为 `MODEL_OUTPUT_VALIDATION_FAILED`、校验阶段为 `validation`，且每条均绑定字段证据与 `PROC-R1-2025` 程序证据卡；B3 为 3/3 `model_success`，三角色均完成。`B2_FAILURE_CLASSIFICATION.json/.md` 在不改写原始记录的前提下，将错误文本进一步映射为 `MODEL_FACT_LANGUAGE_VALIDATION_ERROR` / `fact_language`。B2 与 B3 口径不同，不合并为官方成功率。AI 辅助预评分均值分别为 B1 97.7、B2 59.0、B3 98.3；项目队长正式评分栏仍为空。
- 当前 qwen3.5-plus 质量窗口仍为 **7/10=70.0%**，阈值 80%，状态 `below_threshold`、`alert=true`；继续告警，不自动换模型。真实失败码、响应哈希、token、耗时和受控修正次数均保留。
- 12 条活跃知识来源已完成独立可访问性抽查，结果为 12/12 HTTP 200；活跃来源仍是 13 条登记中的 12 条，另 1 条归档。资料范围继续写“代表性接入”，近五年窗口为 2021-08-24 至 2026-08-24，不宣称全量。
- 补充材料父子任务合同测试通过；现场 `600436`（片仔癀）入口已在 8000 当前实例完成一次真实任务，企业解析、公告/文档校验、案例登记、RAG、字段提取和结构化导出均有记录。浏览器现场样例终态为“需要人工确认/模型链不完整”，未写成模型成功；证据与 JSON/CSV/打印 PDF/DOCX 位于 `outputs/browser-r3-export-8000/`。
- 浏览器静态验收 `outputs/browser-r3-static11/static-audit.json` 覆盖 1440×900、1440×1000、1024×768、768×1024、390×844：axe violations/incomplete、console/page/网络错误和横向溢出均为 0。前端契约为 131 unique ids、129 refs、1 script；JavaScript、Python compile、`git diff --check` 均通过。
- 从项目根目录与 `backend` 目录分别运行全量回归，均为 **329 passed、1 warning**；唯一 warning 仍为 Starlette TestClient/httpx 兼容性弃用提示。
- R3 事实快照已冻结：`outputs/final-audit-20260826-r3/`；JSON SHA-256 为 `49739505744686c2510222ae49ae1f531d334f257356fd537e8fd13727c7f5a7`，Markdown SHA-256 为 `7ca8861f2334e3f74704f24c2864e6664abb5cde543fa3732389edd945b08e79`。快照主链哈希范围排除 PROJECT_STATUS、README、快照和浏览器输出；回填状态文档不会改变该主链哈希。当前状态仍不能写成“模型稳定成功率超过 80%”或“任意新企业均自动完成”；现场样例人工确认、B2 失败和质量告警必须保留。

## 2026-08-25 R2 追加验收（当前代码事实）

- 队长追加签字已完成：`outputs/professional-signoff/R1-v0.4-captain-signoff-20260825-r2.json/.md`；状态为 `captain_approved_for_competition_demo`，姓名字段空白，旧签字记录保持可追溯。签字后事实快照位于 `outputs/final-audit-20260825-r2/`。
- 当前代码 B1—B3 合同目录为 `outputs/evaluation_v5/EVAL-20260825-B1B3-CURRENT-R2-NETWORK/`：五粮液、中国海油、标准股份各执行 B1/B2/B3 一次，共 9 条原始记录；B1 3/3、B2 0/3（均为 `MODEL_OUTPUT_VALIDATION_FAILED`）、B3 3/3 三角色 `model_success`。旧 `EVAL-20260825-B1B3-AI-PRESCORE-V1` 目录不被覆盖，仅作历史证据。
- 当前 `qwen3.5-plus` 真实外部三 Agent 质量窗口为 **7/10=70.0%**，阈值 80%，`below_threshold`、`alert=true`；这已构成对队长的低于 80% 告警。不得宣称稳定成功，不自动切换模型。
- 真实 B3 结果均写入知识检索轨迹、来源台账、认定—证据—程序矩阵、证据适配度、数字回查和反确认记录；失败/降级运行保留真实失败码，不冒充成功。
- 四视口静态/动态浏览器链、键盘抽屉、重置、JSON/CSV/打印入口均已验收；真实 B3 `RUN-V7-DB751326FFAC` 的 API JSON 与 Word/PDF 报告也已核对并记录在 `outputs/final-audit-20260825-r2/real-export-audit.json`。自动阻断项、console/page/网络错误和横向溢出为 0。axe `color-contrast` 因渐变/伪元素无法自动判定，保留人工复核项。
- 最新回归：后端 **321 passed、1 warning**；前端契约 **131 unique ids、129 refs、1 script**；JavaScript、Python compile、`git diff --check` 和中文说明比例 **2198/21676=10.14%** 均通过。快照 JSON/Markdown 哈希分别为 `fa352bf3fbe15f2c92c3f2136e4fc8a6ec9cb4491a36abb65446f806466eeda8`、`d82df2122b0e7c33a7f1f4481780e34aaecafcc3c1ec3e115ac7bd39f652299f`。

## 2026-08-25 当前主方案、创新增强与 B1—B3 评估状态

- 当前主文档已切换为 `02_最终确定方案/15_审迹智链_项目方案书_V4_竞赛提交版_2026-08-25.md` 与 `02_最终确定方案/16_审迹智链_详细项目计划书_V3_提交冲刺版_2026-08-25.md`；V3.3/V2.4.6 仅保留为历史版本链。
- 四项审计专属增强已接入运行上下文、前端结果区和结构化导出：确定性路由、认定—证据—程序覆盖矩阵、证据适配度主张边界、数字主张回查与反确认偏差记录。
- 历史评估目录中的 9 条记录仍原样保留；当前代码结果以 R2 网络合同和上方追加验收为准。AI 辅助预评分均值 85.2/100，正式人工评分仍为空。
- 历史 5/7=71.4% 只作为旧窗口记录；当前质量窗口已更新为 7/10=70.0%，不得混用。
- 当前汇总与逐条评分入口：`outputs/evaluation_v5/EVAL-20260825-B1B3-CURRENT-R2-NETWORK/B1_B2_B3_SUMMARY.md`、`B1_B2_B3_RUN_LEDGER.md`。视频本周期暂缓，不关机。

## 2026-08-24 可信修复计划实施状态

- 已落地：以 `2026-08-24` 为冻结截止日的 13 条代表性来源台账与本地可检索最小片段；覆盖年报、证监会处罚、上/深交所问询、会计准则、审计准则、税收法规、行业报告、新闻、宏观指标。处罚与问询按 `2021-08-24`—`2026-08-24` 精确窗口过滤，未来及过期条目不进入检索或导出。
- 已落地：知识检索在 Agent 调用前执行，运行上下文记录命中、来源类别、定位、内容哈希、快照和“可支持何种主张”的边界；规范只支持程序依据，处罚/问询/行业/新闻/宏观只作待验证背景。
- 已落地：固定案例和补充材料续分析共用 `demo_task_v2` 六阶段台账（证据载入→规则计算→知识检索→三 Agent 协作→证据验证→结构化输出），支持刷新恢复、重启中断、阶段边界取消和失败/取消结果拒绝导出。
- 已实测（2026-08-24 历史快照，R2 已更新当前口径）：真实模型尝试保留原响应哈希、修正调用、token、失败码；成功率窗口按当前模型最近 10 次真实外部三 Agent 完整运行统计，低于 80% 时页面 toast、事实栏和运行记录同时告警。`deepseek-v4-flash` 于 `RUN-V7-5666A45FCAA7` 完成真实 `external_live` 三 Agent 链；R2 当前 `qwen3.5-plus` 窗口为 7/10=70.0%，以追加验收段为准。

## 2026-08-24 竞赛终版增强与完整验收快照

- 实施《审迹智链_竞赛终版增强与完整验收_分步执行计划_2026-08-24.md》全部批次（G0—G9）：固定案例运行改为后端异步任务真实六阶段（证据载入→规则计算→知识检索→三 Agent 协作→证据验证→结构化输出；`backend/app/demo_run_tasks.py` + `/api/demo/runs` 系列端点 + 前端轮询与 sessionStorage 刷新恢复，六阶段与三角色状态由业务节点写入并带时间戳）；新增多源审计知识底座（`knowledge_sources.py / knowledge_ingest.py / knowledge_rag.py` 与 `backend/knowledge_sources.manifest.json`，13 条真实官方/公开案源覆盖年报、证监会处罚、深交所/上交所问询、会计准则、审计准则、税收法规、行业报告、新闻、宏观指标；按 2026-08-24 截止日和 2021-08-24—2026-08-24 近五年窗口过滤，页面标注 representative）；新增审计程序映射（`backend/audit_procedure_map.json` 6 项，页面“系统替你完成什么”三列）；补充材料重跑使用同一异步六阶段任务（父子运行差异可回查，原字段不被覆盖）；扩展 JSON/CSV/打印 PDF 与 docx 报告字段（knowledge_snapshot_id、source_coverage_summary、knowledge_retrieval_trace、model_attempt_history、audit_procedures、regulatory_evidence、supplement_delta、provider_readiness_snapshot、progress_task_id）。
- 供应商通道（2026-08-24 历史快照）：基础地址形状校验（`provider_base_url_error`，失败码 `MODEL_PROVIDER_BASE_URL_INVALID` 提示填写基础地址而非完整请求地址）；`/models` 探测增加一次网络层重试与 8 秒超时；启动打印通道/模型/开关但绝不打印 Key；新增离线备用启动器 `启动审迹智链_离线备用.bat`。R2 当前模型 ID 与质量窗口以追加验收段和 `PROJECT_STATUS.json.latest_r2_20260825` 为准。
- 真实模型单案例：最小工具合同烟测曾验证 vision-exp 与 v4-flash 均 HTTP 200、参数合法；vision-exp 的历史三次实时尝试在确定性事实语言闸门失败关闭。切换为 `deepseek-v4-flash`、修正基础地址并允许本机服务网络访问后，`RUN-V7-5666A45FCAA7` 已完成新代码真实三 Agent `model_success`；模型成功率台账只统计当前质量口径（`demo_model_quality_v2`）的真实外部运行，旧记录不再被换模型后误显示为新代码实时成功率。
- 全量回归：**289 passed、1 warning、163.21s**（基线 259 passed；新增知识、任务状态、模型质量及接口契约测试）；前端契约 **119 unique ids、113 refs、1 script**；JavaScript 语法、compileall、`git diff --check` 通过；最终扫描未发现 20 位以上 token 格式密钥。
- 真实浏览器四视口（1440×1000、1024×768、768×1024、390×844，Chrome + Playwright）：四档均完成选择→运行→结果→证据抽屉→Agent 抽屉→重置，console/page error/failed request/HTTP error=0，横向溢出=0，重复 ID=0；axe violations=0，只有渐变背景触发的 `color-contrast` incomplete，保留为人工复核项；静态与交互证据目录 `outputs/browser-final-20260824/`。
- 本轮未完成且不得宣称的事项：旧 OpenCode Key 撤销确认（人工）；插图文字与 B0—B3 专业评分、人工复核/报告批准等既有门槛不变；未执行系统关机。

## 2026-08-22 OpenCode 通道化就绪状态与提交收尾快照

- 实施《审迹智链_OpenCode调用与前端体验缺陷整改计划_2026-08-20》阶段 1/2 的核心整改：供应商通道分类（DeepSeek 官方直连 / OpenCode Go / OpenCode Zen / 其他 OpenAI 兼容网关）与按 HTTP 401/402/403/429/5xx 的通道化中文引导、稳定 `next_action_code`；未开启主动探测时不再映射为 ready，显示"真实模型可运行性尚未验证"；`live_run`/`circuit_breaker` 快照优先于 TTL 缓存；后台探测加锁防并发雷群；readiness 成功/失败反馈按 `base_url` 通道登记且只由 `failure_stage=provider` 触发；Agent 工具参数协议错误结构化（`ToolArgumentsError` 与稳定失败映射）。
- 前端状态与错误闭环：全局 toast（错误不自动消失）+ 隐藏面板消息镜像；校验与 HTTP 错误全文中文化；字段核对收敛为折叠单行+逐条展开+一键确认（仍强制真实复核人，不代填）；`skipped` 角色页脚显示"未运行 / 未调用模型"，不再补造 `demo-deterministic-v1`；运行深链失败在分析页显示可见错误面板与返回入口；运行按钮禁用原因增加常驻提示文本。
- Word 报告在存在主张时新增"Top 5 待核查事项与事实依据"标题；Agent 输出合同 `claims` 上限与 Top 5 对齐（4→5）；后端增加通用异常兜底处理器。
- 本工作树最终收尾回归（2026-08-22）：**241 passed、1 warning、149.94s**，退出码 0；中文说明比例 **1861/18393=10.12%**；前端契约 **246 unique ids、441 refs、9 views**（08-19 快照后导航与结构继续收敛的实测值，旧值 294/504 仅作历史）；JavaScript 语法与 `git diff --check` 通过；提交前秘密扫描仅命中测试夹具假值（`sk-test-*`），无真实密钥。
- `assets/official-v4/refine.css` 经全库检索无任何引用，按整改计划指令移入本地 `backups/refine-unreferenced-20260822.css`，不进入发布提交；`runtime/`（本地浏览器验收产物）与 `backups/`（本地回滚备份）加入 `.gitignore`。
- 本轮未完成且不得宣称的事项：OpenCode 单案例真实完整链复测（OP-A4）未执行，需付费调用与团队授权后另行完成；390px 几何门槛与四视口真实浏览器验收未在本轮重跑；E2E 验收器重建（整改计划阶段 4）未实施。当前准确口径仍是：OpenCode Go 端点与基础工具协议已实测可用，复杂三 Agent 完整链待新的单案例真实运行验收。

## 2026-08-19 视觉收口与整改验收快照

- 源码仓库全量回归：**234 passed、1 warning、130.28s**，退出码 0；唯一 warning 为 Starlette TestClient/httpx 兼容性弃用提示。
- 前端契约：**294 unique ids、504 refs、9 views**；Python compileall、JavaScript 语法、中文说明比例 **1855/18337=10.12%** 和 `git diff --check` 零告警通过。
- 评委工作台完成深浅主题衔接与导航收敛：深色品牌框架（`#0F151D`）+ 暖灰底稿背景（`#F1EFE9`）+ 近白底稿卡片（`#FCFBF8`），顶栏增加 1px 深审计绿（`#1F5B4D`）过渡细线。
- 顶部导航实装 4 项完整结构（演示工作台、证据详情、竞赛材料下拉、高级功能下拉）；左侧侧栏收敛为 68px 收缩图标轨道，hover/:focus-within/.is-pinned 展开为 240px 浮层（零内容跳动）；`overview` 自动隐藏五步步骤条以聚焦四阶段指示器。
- 真实 FastAPI 与 Playwright 真实浏览器完成 1440×1000、1024×768、768×1024、390×844 四档视口验收，控制台错误 0、横向溢出 0；标准股份（主演示）与杰克科技（负向对照）双业务链路回归通过。

## 2026-08-15 两份 Bug 清单合并整改快照

- 已合并两份 Bug 与人工操作盘点中的确认问题，原始盘点文件保持不变，继续作为整改前证据；本轮未把密钥、运行缓存或原始盘点文件加入发布提交。
- 源码仓库最终全量回归：**213 passed、1 warning、200.11s**，退出码 0；唯一 warning 为 Starlette TestClient/httpx 兼容性弃用提示。仓库内旧临时目录存在 Windows 权限锁，本次以系统临时目录复验并通过；该环境问题不计为代码失败。
- 前端契约：**240 unique ids、436 refs、9 views**；Python compileall、JavaScript 语法、中文说明比例 **1758/17545=10.02%** 和 `git diff --check` 已通过。
- `/api/health`、`/api/status.model` 现在同时返回 `full_analysis_ready`、稳定 `full_analysis_reason_code`、中文 `full_analysis_message` 与 `deterministic_backup_available`；`model_status=configured` 只表示 Key 存在，不再冒充真实模型已就绪。公开模式只有 Key、32 位额度秘密、额度账本和当前额度都可用时才标记 `external_live`，不做供应商探测。
- 公开共享站已收口为只读演示：内置案例、RAG、仅计算和内置补充样例保留；自定义案例/资料、非内置企业抓取、强制刷新、字段确认、正式复核批准和案例 ZIP 均在页面点击前禁用，后端继续以 403 双重拦截。人工字段判断区仍可见，并明确标注“此处是人工字段判断位置”；私有模式保留确认、更正、拒绝和导出能力。
- 新企业流程默认“只下载 + RAG”，不无意消耗模型额度。RAG 候选不因低分被删除；低于 `0.50` 时列表与原文阅读器同时显示“低置信候选，必须回原页复核”。R2 字段缺失进入 `DATA_GAP/risk_card.data_gaps`，资料缺口统一为中文短句并去重，证据包按 evidence ID 去重。
- 补充续分析默认清除父运行遗留的备用标志；只有用户明确选择“确定性备用、未调用模型”才沿用备用链。没有 `run_id` 的失败也可用当前案例参数显式创建备用运行。
- 修复已推送 GitHub `main`（功能提交 `0342ccf`，案例来源契约补丁 `9cb9531`）并由 Render 自动部署。线上运行时 `/api/status.deployment.commit` 在功能验收时为 `9cb953128c2125628c0b4b95ea62f8a4dfe1d956`；Render 已自动生成额度签名密钥，健康与状态接口均返回 `full_analysis_ready=true`、`reason_code=ready`。
- 最新线上站已完成 9 个页面 × 1440×1000、1024×768、768×1024、390×844 四档视口共 36 项真实浏览器复验：控制台错误 0、页面横向溢出 0；公开只读控件、人工字段判断区、动态评估编号、确定性备用实际运行方式以及 RAG 列表/原文阅读器低置信警告均已实际操作验证。
- 上汽集团 `RUN-V7-75962367DF2A` 只发起一次真实完整分析；供应商返回 `MODEL_PROVIDER_AUTH_FAILED`，后续反证/复核角色均标为 `skipped/PREVIOUS_ROLE_FAILED`，未自动重试、未形成 AI 草稿、未冒充成功。就绪接口按设计不消耗额度探测供应商，因此该鉴权问题必须由团队在 Render 更换有效 DeepSeek Key 后再做一次单案例复验。
- 同一线上案例的仅计算、显式备用、RAG 与内置账龄补充样例均通过：显式备用 `RUN-V7-DB0820F6819A` 为 `deterministic_backup`、provider call 0；RAG 返回 5 条，其中 3 条低于 0.50 并显示回页警告；补充续分析含 1 条独立补充证据。公开写入边界继续以 403 拒绝。

## 2026-08-13 本轮复核快照

- 源码仓库全量回归：**201 passed、1 warning、146.22s**，退出码 0；唯一 warning 为 Starlette TestClient/httpx 兼容性弃用提示。针对本轮边界的合同测试另为 **21 passed**。
- 前端契约：**210 unique ids、369 refs、9 views**；JavaScript 语法、CSS 对比度、Python compileall 和差异卫生检查通过；中文说明比例 **1737/17325=10.03%**。
- 真实 FastAPI 与本机浏览器完成 1440×1000、1024×768、768×1024、390×844 四档视口和 9 个视图验收；HTTP 200、console error、失败请求、文档级横向溢出和 axe violation 均为 0。桌面与手机均完成标准样例字段、RAG prepare/retrieve（1167 块、返回 5 条）和仅计算运行，provider 调用为 0。证据位于 `artifacts/review-2026-08-13-browser/current-audit/` 与 `artifacts/review-2026-08-13-browser/current-interactions/`。
- 历史 `agent_prompt_v3` 外部模型批次严格复核为 51/51 HTTP 200、51/51 `external_live`、51/51 `model_success`、153 次 provider call；实际重试结构为 **45 次首轮成功 + 3 次批内重试成功 + 3 次后续定向补跑成功**。冻结清单为 `outputs/external_model_acceptance/current.json`。
- 上述 51 案只能证明当时的真实模型传输、三角色 Schema 和运行留痕链；它使用了本轮字段质量闸门上线前的候选，不证明字段正确、风险识别准确率或有效 B3，也不是当前修复代码的外部模型复验。
- 当前物化种子共 50 家、394 条字段候选；新保守闸门拦截 **128 条、涉及 30 家**，其中 72 条为启发式提取的跨年数量级异常。这些候选仍展示给人回页核对，但不会进入确定性规则或模型证据。确定性演示分布因此变为 `DATA_GAP=30`、`RULE_NOT_TRIGGERED=17`、`candidate=3`。
- 本轮未重新调用付费外部模型、未部署、未重新验收 Render/Supabase/RLS，也未完成专业签字或 B0—B3 真人评分。

详细记录见 `审迹智链_51案例AI全链复核与Bug修复报告_2026-08-13.md`；8 月 9 日报告保留为历史快照。

## 当前正式口径

- 正式业务范围：审计计划阶段的销售与收款循环风险预筛。
- 正式入口：根目录 `index.html`，采用 V4“证据地平线”设计；`09_官网V4_融合增强实验版` 仅作整改前基线。
- 工程版本：0.7.1；运行结构：`run_output_v2`；R1：v0.4，当前状态 `captain_approved_for_competition_demo`；R2：辅助工程草案；R3—R8：路线图。
- 完整分析：确定性计算 → 固定问题集 RAG → 质疑 / 反证 / 复核 Agent → Schema、引用与确定性事实语言一致性硬校验 → 人工处理。
- 仅计算预检允许使用，但必须标为不完整运行。JSON、网页草稿和 Word 报告必须逐字保留统一 AI 声明。
- 运行方式优先显示实际 `execution_mode`；真实模型、模型已配置、后端可用和确定性备用彼此分开。真实模型不可用时，页面显示原因码对应的中文操作说明，并只允许用户明确选择确定性备用。
- 公开共享站是安全只读演示：只保留内置案例、RAG、仅计算和内置补充样例；新企业默认 `rag_only`。私有环境才开放自定义资料、字段确认、更正、拒绝、正式复核批准和导出。

## 当前已经实现并通过的工程能力

- 标准案例 ZIP 下载、安全导入、真实哈希校验、路径穿越 / 危险压缩 / 高风险个人信息 / 跨案例串包拦截。
- 新案例如开启模型传输，必须登记确认人、日期、许可依据、供应商、最小传输范围和记录编号；缺项即拒绝导入，且该记录仍须独立真人复核。
- 标准股份与导入案例共用案例注册表；字段、来源与 RAG 按案例隔离。
- R1 两年基本计算、三年持续期间及周转趋势、净额过渡口径、计划重要性缺失状态。
- RAG 候选原文进入本次 Agent 证据包；错误引用、无命中和模型失败均关闭完整性。
- 四层状态、补充证据续分析、旧运行只读兼容、人工批准缓存与 `report_v2`。
- 三角色专用 Tool Schema、稳定失败码和确定性事实语言一致性闸门。
- 自动字段候选增加保守质量闸门：疑似把附注号、页码、期限或阈值当金额/比例的行失败关闭；真人确认或修正后才重新进入规则与模型证据。
- 全案例模式的 RAG、隐私检查和模型许可均失败关闭；比赛演示不再绕过 RAG/隐私失败，也不再自动替案例开启模型传输。
- 外部模型载荷删除文件名、文档 ID、定位器和哈希等非必要技术标识；补充资料正文同样进入传输前隐私扫描。
- 模型缓存键已覆盖规则/引擎版本、阈值、路线、确定性结果和实际证据；缓存响应重绑当前运行 ID，并记录来源运行 ID。
- 缓存命中和历史回放不再冒充本次外部调用：当前运行的 token、耗时与 provider call 均归零，来源用量只作为上下文留痕；并发缓存占位增加 TTL、所有者身份和原子重获，配额拒绝也会释放占位。
- provider 调用审计按真实 HTTP 尝试计数，覆盖瞬时重试、Schema 失败和输出策略失败；调用前拒绝与后续跳过角色保持 0，不再把已发生的失败调用写成未调用。
- 外部模型输入先最小化并扫描，模型输出在保存和对外返回前再次扫描；命中高风险内容时只保留失败类别和字段路径，不保存敏感原文。
- 公开部署默认同源；CORS 只接受精确 HTTP(S) origin。反向代理身份信任要求跳数与可信 CIDR 成对配置并拒绝 `/0`，公开真实模型配额密钥不得短于 32 个字符。
- 匿名本地公开 Demo 只允许内置样例，拒绝任意案例 ZIP、非内置企业抓取、强制刷新和补充资料上传；内置补充样例不再重复登记两份相同证据。页面在点击前禁用写入控件，后端继续以 403 双重边界保护。
- 公开模型就绪判断只读配置、Render 生成的额度秘密和额度账本，不做消耗额度的供应商探测；缺 Key、缺秘密、秘密长度不足、账本异常和额度耗尽均返回稳定原因码。`render.yaml` 使用 Render `generateValue: true` 生成 `AUDITTRACE_PUBLIC_QUOTA_SECRET`，秘密值不进入仓库。
- RAG 返回项包含 `low_confidence` 和 `confidence_note`；低于 0.50 只提示回原页复核，不硬过滤召回。R2 字段缺失写入 `DATA_GAP/risk_card.data_gaps`，资料缺口和 evidence ID 均按统一规则去重。
- 精确 AI 声明已作为新生成及对外 API JSON、网页草稿和 Word 报告的不变式接入；历史封存 JSON 原字节不改写，读取时由当前 API 追加声明。
- 巨潮新企业自动流程已实现：输入股票代码/名称后，自动搜索巨潮年度报告公告、选择最新有效全文、下载并校验 PDF 文件头/页数/企业/年度/SHA-256，再登记独立案例、建立案例隔离 RAG、执行固定问题检索烟测并默认进入 `rag_only`；只有私有环境和已确认许可才继续完整分析。
- 公开预筛已接入规则级与年度级优雅降级：最近两年字段完整时运行 R1；第三年缺失只关闭三年趋势；最新年度不完整时选最近完整连续年度并标出分析截止年度；单条规则缺字段只返回 `DATA_GAP` 或跳过该规则，其他规则与 RAG 不被阻断；缺失金额不估算、不补造。
- 巨潮流程 API 已提供 `POST /api/pipelines/cninfo`、任务进度/结果查询、失败重试和候选公司确认；字段技术校验不再把逐字段人工确认作为首次预筛前置门槛。结果会列出已运行规则、跳过规则、缺失字段、分析截止年度、置信度和资料索取方向；正式采用、证据冻结、缓存或导出仍由真人复核闸门控制。
- 正式网页已接入巨潮入口：页面可输入企业、轮询 11 步任务、展示官方原件 URL、页数、SHA-256、案例编号、RAG 块数和检索编号；公开预筛完成状态与 `needs_human`（企业歧义、硬失败或人工处置）分开显示，重试文案不再暗示“确认字段后才能首次分析”。
- 巨潮字段确认闭环已实现：`POST /api/cases/{case_id}/fields/confirm` 支持 `confirm`、`correct`、`reject`，自动候选原值、修正前值、复核人、时间、原因和历史记录追加保存；该接口用于正式采用/导出前复核，不阻断公开预筛。
- 历史 2026-08-07 源码仓库回归为 **76 passed、1 warning**；2026-08-13 源码快照为 **201 passed、1 warning**，2026-08-16 合并整改后的当前源码快照为 **213 passed、1 warning**，历史数字保留用于追溯。
- 2026-08-09 无密钥清洁运行包独立解包回归登记为 **171 passed、1 warning**；本轮未重建该交付包，两套测试口径分开登记。
- 无密钥清洁运行包为保留标准案例复验能力而包含四份公开年报全文；在真人确认全文再分发边界前，它只允许团队内部技术复验，禁止外发。队员 Word/Excel 包和老师方案材料包不含年报全文。
- 根目录正式网页已用真实 FastAPI 和浏览器完成四视口复核：控制台错误、失败请求、HTTP 错误、文档级横向溢出和 axe violation 均为 0；当前证据位于 `artifacts/review-2026-08-13-browser/`。
- 当前 8 份正式 Word 共 77 页，逐页、无障碍和表格几何均通过；12 页提交版 PDF 逐页通过。终验记录位于 `artifacts/review-2026-07-30/docx-render-final/`、`artifacts/review-2026-07-30/docx-audits-final/` 与 `artifacts/review-2026-07-30/proposal-pdf-final/`。
- 当前 8 份 Word 已通过真实 Word 渲染逐页检查、表格几何检查及无障碍检查；方案书 PDF 为 12 页并完成逐页复核。

## 标准股份四份年报官方来源

| 年度 | 巨潮资讯官方全文 URL | 登记 SHA-256 |
|---|---|---|
| 2022 | https://static.cninfo.com.cn/finalpage/2023-04-19/1216455382.PDF | `9A466F987E16948A06F3E6222E139E707A7D9F6C35A60DE7074C8545B02E7DE8` |
| 2023 | https://static.cninfo.com.cn/finalpage/2024-04-18/1219646140.PDF | `6BFF4D4084010EAB55FED5447CFFDC8DA14AD842064F072E83ACB811FD909C87` |
| 2024修订版 | https://static.cninfo.com.cn/finalpage/2025-04-29/1223359539.PDF | `4665665125EBA8B83504D1A2DA59A4083CD3E2FE158EC2B9466983EAB4C65A09` |
| 2025 | https://static.cninfo.com.cn/finalpage/2026-04-30/1225266733.PDF | `CC52826B24EB54AC09784BAA31DCDC2F8E7B0FD165D0EA559E707124F219ED35` |

在线文件与本地 PDF 的 SHA-256 已完成技术核对；字段口径与页码仍须真人专业复核。

标准股份当前由 `PROJECT_AUTHORIZATION.json` 记录项目所有者对公开来源最小必要字段和 RAG 片段的模型传输许可；该许可不等于全文再分发许可，也不替代专业复核或正式报告批准。来源快照变化后必须重新核验。

## 第二案例当前边界

- 杰克科技 `JACK_603337_T0_20250415` 已完成三份官方年报导入、字段/公开账龄技术核对、案例隔离 RAG 和本地计算预检。
- 当前计算运行：`RUN-V7-B1EB77EDB151`，程序状态 `RULE_NOT_TRIGGERED`。这只表示当前 R1 增长错配条件未命中，不等于无风险。
- 项目所有者已在 `PROJECT_AUTHORIZATION.json` 登记对公开来源的最小必要模型传输许可（2026-08-07）；正式案例冻结、双人独立复核与全文再分发许可仍待真人完成，在此之前该案例的模型传输开关保持关闭（`model_transfer_allowed=false`）。公开预筛结果不等于正式案例结论。

## B0—B3 当前真实状态

| 组别 | 固定定义 | 当前事实 | 人工评分 |
|---|---|---|---|
| B0 | 真人人工基线 | 未执行，系统不得代填 | 空白 |
| B1 | 确定性计算 | `RUN-V7-0BDE5060FBED` 已执行；`incomplete_calculation_only` | 空白 |
| B2 | 确定性计算 + 一次单模型草稿 | `EVAL-B2-2F8BE053630D` 返回5条claims，超过最多4条，校验失败；原始响应与哈希留档；调用发生于合规失败关闭补丁前，不具备正式比较资格 | 空白 |
| B3 | 确定性计算 + RAG + 三Agent + 硬校验 | 历史 `RUN-V7-00ED00962F34` 经新增事实闸门复核失败，不具备正式比较资格 | 空白 |

受控记录位于 `outputs/2026-07-29-controlled-evaluation/retry-01/`，已有文件拒绝覆盖。当前没有 B0—B3 效果结论，也没有可用于正式评分的有效 B3。

## 尚未验收或必须由人完成

- R1 专业签字；
- 回原页确认或修正当前闸门拦截的 128 条候选，优先覆盖受影响的 30 家公司；
- 第二公开案例两名真人独立复核和全组冻结；
- 标准股份与第二案例的合法样例、保存期限、外部模型传输和再分发边界确认；
- 在真人冻结合同与合法样例后，通过一次当前事实闸门下的 B3，并由真人复核及批准正式报告；
- B0—B3 真人评分、姓名、日期和原始记录快照。
- 当前工作区未找到可逐条核对的主办方最新正式竞赛手册原件；正式提交前必须补齐原件并按规则优先级复核。

## 可证明的新增创新

- 确定性事实语言一致性闸门；
- 杰克科技负向控制与拒绝过度预警；
- JSON、网页草稿、Word报告的精确 AI 声明不变式；
- 拒绝覆盖、保留失败响应与哈希的追加式原始评估账本。

机器可读版本见 `PROJECT_STATUS.json`，网页 `/api/status` 在此基础上叠加实时案例、RAG 和模型配置状态。
## 2026-08-13 全案例 AI 路线收尾更新

- 完整分析模式已取消“只有 candidate 才调用模型”的门槛；四条 AI 路线分别覆盖候选风险、未触发复核、行业口径和数据缺口。
- 当前案例级链固定为一次 Challenge、一次 Counter、一次 Review；R1/R2 及行业结果合并进入同一证据包，不按规则重复调用。
- 历史 51 案真实外部模型回归已完成：51/51 请求 HTTP 200，最终 51/51 为 `model_success`，每案最终均完成 Challenge/Counter/Review 三角色、3 次 provider call；45 案首轮成功、3 案批内重试成功、3 案后续定向补跑成功。
- 当前全量后端回归为 201 passed、1 warning（146.22s）；前端合同为 210 unique ids、369 refs、9 views。
- 模型链失败状态已补齐：失败角色保留真实 failure_code，后续角色明确记录为 skipped，不计入 provider_call_count，也不伪造完成。
- 空证据案例也会进入三角色链；模型只能返回 data_gap/industry_boundary 缺口说明，不得编造主张或 evidence_id。51 案验收脚本对瞬时失败自动重试一次，对余额/鉴权等永久失败保留原始失败记录并停止重试。
- 2026-08-13 工作区已开启中国托管模型；OpenCode Go `deepseek-v4-flash` 最小调用返回 200，项目真实案例和 51 案批量均通过三 Agent 结构化链。Key 只在临时环境变量中使用，没有写入源码、配置示例或 Git。
- 历史 51 案路线摘要：风险候选 15、行业口径复核 19、数据缺口复核 17；其技术验收不等于当前字段质量闸门下的路线或专业内容结论。
- 可提交的严格验收清单为 `outputs/external_model_acceptance/current.json`；原始摘要保存在忽略目录 `tmp/external-opencode-go-51.json` 与 `tmp/external-opencode-go-failures-retry.json`，每案运行 JSON 保存在 `backend/runtime/external-51-20260812/runs/`。
- 当前代码下尚未重新付费运行 51 案；在 128 条拦截候选完成真人回页复核前，不建议把历史输出用于专业评分。
