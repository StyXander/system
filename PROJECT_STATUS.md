# 审迹智链单一事实源

更新时间：2026-09-15
统一 AI 声明：**AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。**

> **当前整改发布候选（2026-08-29，唯一当前口径）**：`RELEASE-CANDIDATE-20260828-V1`，模型为 `deepseek-v4-flash`（DeepSeek 官方直连）；15 案由 `backend/competition_demo_cases.json` 冻结清单统一驱动。公开演示任务/结果/质量事件采用 Supabase 服务端台账，当前执行模式是 Render 免费 Web；完成结果可跨刷新和重启读取，运行中实例重启会记为 `interrupted`，不自动续跑，需显式重试。provider probe、真实 B3、签字、评估指针和人工评分分别判定，`configured` 不等于真实可运行，当前 `competition_release_ready=false` 直到新鲜证据和真人批准完成。当前评估指针为 `EVAL-20260828-RELEASE-CANDIDATE-V1`，人工评分保持 pending；可选 Worker 仅见 `render.worker.example.yaml`，未写入当前 Blueprint。

> **2026-09-02 模型口径裁决与本机质量窗口登记**：队长裁决生产目标模型统一为 `deepseek-v4-flash`，AGENTS.md、发布记录、部署配置与方案书口径已同步；`qwen3.5-plus` 的 7/10=70.0% 窗口只作历史证据。DeepSeek 官方直连通道自 2026-08-28 切换以来，本机真实三 Agent 完整链累计 **6/6 案完成、19 次 provider 调用、0 次失败关闭**（2026-08-29 五案 16 次，其中一案含一次内部修正调用；2026-09-02 标准股份演示彩排一案 3 次首过，run `RUN-V7-EB6EAE3B87EB`、task `DEMO-RUN-F9E1BA62F5DC`、`external_live`/`model_success`）。该 100% 指完整链最终完成率而非每案首过率；样本量小，不构成稳定成功证明；Render 生产通道的 provider probe 与新鲜 B3 仍 pending。明细登记于 `PROJECT_STATUS.json` 的 `deepseek_direct_local_window_20260902`。

> 旧 R3/R2/R1 段落、历史模型和历史成功率均保留用于追溯，并标记为 superseded；对外状态以 `/api/health`、`/api/status`、`/api/demo/bootstrap` 和 `backend/release_records/` 的哈希校验结果为准。

## 2026-09-15 全量三轮审查与人工门禁修复（当前工作树，未提交）

- 审查产物：`docs/2026-09-15_全量三轮审查报告_代码方案书对应与部署.md`（第一遍广度扫描、第二遍逐条自验、第三遍反向复核；含推翻子代理 2 条结论与推翻本报告自身 1 条的订正记录）。
- 证据完整性：`outputs/`、`archive/` 共 47 个受控文件此前在本机清理磁盘时被删（约 532K，磁盘不是内存），已 `git restore` 全部恢复，`git ls-files --deleted` 现为 0。`artifacts/` 与 `outputs/**/*.zip` 从未入库（`*.zip` 被 gitignore），git 无法恢复；其中评委包依赖的 `outputs/2026-07-28-v4-closure/审迹智链_标准案例包_V1.zip` 已用仓库自带 `scripts/export_case_template.py` 重建（5,641 字节），`test_delivery_package_build.py` 由红转绿。`artifacts/` 下的截图与 axe 证据未恢复，相关历史主张（如"严格 axe 0 violation"）此刻不可回查。
- 修复的人工门禁（P1）：① `cases.py` 字段重提取会把真人校正值覆盖回机器候选、却继承"已人工确认"留痕，现改为决定/值/页码/定位/复核状态同源继承，候选快照仍保留机器原值；② 本轮又发现同一函数会整表重写 `financial_fields.json`，换年度或 R1↔R2 复跑会抹掉其他年度候选与复核历史，现按 field_id 合并保留；③ `HumanReviewRequest.reviewer_type` 默认值由 `human` 改为 `automation`，自称真人必须填复核人姓名且会话可归属，服务端覆盖式盖章 `reviewer_user_id/reviewer_source`。
- 修复的状态与部署口径：`demo_completed_result_durable` 需凭据齐备才为真；供应商通道判定改为主机名精确匹配（`api.deepseek.com.evil.tld` 不再被标"官方直连"，标签不再可能带出 `user:pass`）；状态页 `human_scoring` 与发布门禁同用 `== "completed"`；`release_evidence` 的 `run_record_status`/`result_hash_verified` 由常量改为按磁盘登记值与重算结果推导；`rag.status()` 未建库时不再一律写 `source_available`；`bootstrap_ready` 不再恒真，改为"至少一个推荐案例 runtime_ready"，并新增 `featured_cases_pending`；`public_catalog_bootstrap` 半发布或客户端建不起来时以退出码 1 中断构建；生产依赖不再安装 pytest。
- 前端真实状态修正：结构化结果徽章由写死的绿色"同源生成"改为按本次是否产出指标驱动（HTML 默认 pending，重跑时复位）；证据轴 output 档不再无条件 complete；知识台账空态区分"已接入但本次未命中"与"尚未接入"；补充资料重跑对 401/403 明确说明需要登录后的真人账号。
- 测试口径修正：`test_signoff.py` 原断言接受签字状态的全部三个合法值（恒真），现钉住当前真实状态 `signoff_stale_requires_reapproval` 并要求 `release.ready_checks.signoff is False` 与 `human_scoring is False`。
- 实测：`pytest backend/tests -q` **508 passed / 1 skipped / 0 failed**（48 个测试文件、509 项收集；跳过项为内部签字原件不随交付包分发）；`check_frontend_contract.mjs` ok（171 ids / 181 引用 / 2 scripts）；`node --check demo-app.js` ok。
- 队长决定并落实：初赛方案书按**实名口径**提交。新增 `02_最终确定方案/28_审迹智链_AuditTrace_初赛方案书_实名提交版_2026-09-15.docx`，由生成器 `scripts/build_realname_submission_copy.py` 从 26 号实名母版还原 29 处身份、删除封面盲审说明行、按母版字节重嵌导师签名图像（SHA-256 `fdf3cf8b…` 与验收记录一致），并把图7那句被改写的"AI生成分析内容"恢复为逐字统一声明；26/27/27b 三份原稿未改动，逐处留痕在 `docs/review-assets/2026-09-15_realname_identity_restore.json`。LibreOffice 渲染复验 15 页与母版一致，封面与第 2 页页面图已人工查看。**封面四项与参赛人员四行在母版里本就是"待填写"，仍需成员本人填真实信息；填完须重新渲染并更新哈希。**
- 仍未处理：`render.yaml` 线上仍装开区间 `requirements.txt`（本机 `.bat` 装 `requirements-lock.txt`），验收版本与线上版本不同源，改动部署安装源风险高，留队长决定；每 IP 额度在免费 Web 共用出口 IP 下可能塌缩（未配 `AUDITTRACE_TRUSTED_PROXY_HOPS/CIDRS`）未做双客户端实测；`agents.py:982/985`、`main.py:4310-4312`、`evidence_fitness.py:127-135`、`release_gate.py` 其余 13 条阻断分支、`_release_fact_snapshot` 仍无测试；`anti_confirmation` 的"已执行反证检索"、`demo_run_tasks` 心跳异常不置失租、`coverage_matrix` 的"计价和分摊"与映射文件"计价分摊"字面不一致、`seed_catalog._DEMO_RETRIEVALS` 无界增长均未改。
- 未越界声明：本轮所有数字均为工程事实，不构成真实年报字段错误率、不构成 B0—B3 专业评分；未 commit/push/部署，provider 调用 0 次，冻结案例、T0、baseline、发布记录与人工评分字段未改。（**该"未 commit/push/部署"已被 2026-09-18 一轮覆盖，见下节；本轮其余声明仍成立。**）

## 2026-09-18 Render 两项异常核因与修复（当前工作树）

- 证据目录：`outputs/render-two-issues-20260918-0931/`（`baseline.md`、`acceptance.md`、`storage-upload-checklist.md`、改前 889 行补丁、线上 `health/status/bootstrap` 原始响应、故障注入浏览器验收截图与日志）。
- 版本对齐实测：Render `deployment.commit` 与本地 HEAD 均为 `a4fe995`，线上 `index.html`/`demo-app.js`/`styles.css` 三份资源与 HEAD **逐字节一致**；因此两张截图对应代码可追溯，而 09-15 那批修复因未提交所以从未上线。
- 标准股份 403 根因（已确认）：`*.pdf` 被 gitignore → Render 无原件；`ensure_standard_sources()` 无条件下载全部四个登记年度且任一份失败即整单失败；本机四份原件齐全并命中有效缓存，**运行期根本不发网络请求**，这才是"本地正常"的真实含义。`SUPABASE_PRIVATE_BUCKET` 等配置存在不等于桶里有文件。
- 2022 年依赖经查为比较基期依赖（`PERIODS` 中 2023 的 previous 是 2022，`STD_AR_2022` 是真实字段证据），**予以保留**，未删年度绕过问题。
- 来源修复：`source_cache.py` 改为"本地有效缓存 → Supabase 私有桶 → 官方受控下载"三级顺序；私有桶读取复用同一个 `download_bounded`，PDF 头、50MB 上限、登记 SHA-256 三项检查不放宽，凭据不齐时不猜测而是直接回退。新增 `scripts/upload_standard_sources_to_storage.py`（上传前逐份核对哈希，不符拒绝；`--verify` 读回复验）。官方来源入口仍回巨潮原件，未创建公开全文镜像。
- 任务失败收尾实测：后端本已正确（任务落 `failed`、六阶段收口、`/result` 409）；隔离复现抓到 1/2 次轮询处于"阶段已失败而任务仍 running"的撕裂窗口，前端据此把横幅写成"正在执行完整分析"、后两阶段留"等待开始"。修复在 `demo-app.js`：撕裂读归一化为未执行并给原因，已拒绝时横幅如实改写。新增端到端测试钉住该读路径契约。
- 五粮液提示矛盾：`outcomeFromRun` 五条件合取任一不满足都统称 degraded，而三处文案一律写"本次未完成真实模型调用"，与同屏"三Agent已通过硬校验 · 3/3 角色完成"互斥。新增 `degradedReason()` 分为回放/确定性备用/真实失败/证据不完整四类，阶段条、结果胶囊、顶部通知统一取同一分类。**该次运行属于哪一支仍未定**（原始留痕未取得），线上 `model_quality` 实测 10/10 只可排除通道整体故障。
- 就绪显示：`bootstrap_ready` 不再恒真并新增 `featured_cases_pending`；前端开始横幅按该字段点名未就绪案例，案例卡片对 `runtime_ready=false` 追加纯文字"来源或索引未就绪"行（不只靠颜色）。
- 门禁修复：`scripts/verify_demo_outcome_judge.mjs` 原硬依赖 `artifacts/` 下两个本机文件，而 `artifacts/` 整目录被 gitignore、0 个受控文件，**干净克隆必然 ENOENT 崩溃**；现改为自洽向量 + 缺产物时显式 SKIPPED，共 20 项断言。
- 实测：`pytest backend/tests -q` **514 passed / 1 skipped / 0 failed**（436.73s）；`test_v7_closure.py` 54 passed；`check_frontend_contract.mjs` ok（171 ids / 181 引用）；中文注释 `2617/25430 = 10.29%` PASS；`git diff --check` clean。真实浏览器故障注入 **22 项全过**，覆盖四视口、减少动态、控制台与失败请求；对照克隆证明候选集相对纯 HEAD 净增 6 条通过、失败集合逐条相同。
- 仍未完成：私有桶内四份对象**尚未上传**（本机无 Supabase 凭据，清单已备在 `storage-upload/`）；因此标准股份 `runtime_ready` 在线仍为 false，须待回填后由运行期自动恢复，不需重新部署。每 IP 额度塌缩、`prepare_full_corpus.py` 未加 gitignore 白名单导致干净克隆无法收集两个测试模块，均为既存未处理项。
- 边界：本轮 provider 真实模型调用 **0 次**；未改审计规则、冻结案例、T0、baseline、发布记录、人工评分与签字；`docs/review-assets/2026-09-15_realname_identity_restore.json` 因疑似含个人身份线索**未纳入提交**。

## 2026-09-09 数据链路缺陷修复（当前工作树，未提交）

- 依据 `docs/2026-09-09_代码与运行逻辑审查及开源对照优化方案.md` 与实施计划 `docs/superpowers/plans/2026-09-09_数据链路缺陷修复实施计划.md`，关闭五项实测复现缺陷：C01 字段取错本期列、C02 检索相关性不参与排序、C03 PDF 年度可靠其他命中补分通过、C04 采集适配器不复校重定向落点且伪 PDF 可过、C05 503 不重试；另关闭 4.1（先收完整响应体再判体积）与 4.2（翻页触顶静默返回部分候选）。
- 取值口径变更：本期列由表头期间列与单元格位置确立，金额大小不再参与列选择；列身份不可确立时字段成为资料缺口，不再进入确定性计算。闸门原先"原始值 ≤100 即疑似附注号"与缺陷同源，已限定为列身份未确立时才触发。
- 检索口径变更：问题文本与受控中文问题词先做相关性门禁，零词命中条目与被判定为 `case_fact_prohibited` 的他企业年报一律剔除，权威等级只用于同等相关度定序；`knowledge_no_relevant_evidence` 与"知识库不可用"分离，前者作为资料缺口继续，后者仍失败关闭不调用模型。命中记录新增 `relevance_matches` 与 `retrieval_version=knowledge_retrieval_relevance_gate_v2`。
- 网络口径变更：408/429/502/503/504 与网络瞬断在 60 秒总预算内退避重试，429 读取 `Retry-After`，403 改为 `CNINFO_ACCESS_DENIED` 立即停止并转人工；重试台账记录状态码、次数、计划等待与终止原因。年报下载与标准案例缓存改用同一受控下载组件（逐跳复校、块级限额、增量哈希、原子落盘）。
- 实测证据：`pytest backend/tests -q` **502 passed**（改动前基线 456 passed，新增 46 项缺陷回归，见 `docs/TEST_INVENTORY.md`）；`scripts/check_chinese_comments.py` 2582/25221 = **10.24% ≥ 10%**；`scripts/check_frontend_contract.mjs` ok；复核脚本 `docs/review-assets/20260909_logic_probes.py` 五项输出全部符合期望（C01=80、C02=0 命中、C03=rejected:PDF_REPORT_YEAR_UNCONFIRMED、C04=ok=false/redirect_not_allowed、C05=3 次请求）。
- 知识检索测试集量化：同一 26 题、k=5 下，HEAD `155e3ad` 基线"应拒未拒"11 条、"意外空"0 条；修复后分别 **6 条 / 0 条**。基线为当日重建产物 `artifacts/competition-improvement-20260908/retrieval-test/results_baseline_head_155e3ad.json`（原 9/8 产物在实施中被中间态运行覆盖）。剩余 6 条属"登记条目是类比/背景入口"，需真人标注相关/不相关后才能继续收紧。
- **仍未证明**：以上全部是离线夹具与真实清单上的工程事实，不构成真实年报字段错误率、不构成检索质量评分、不构成 B0—B3 任何专业结论。真实年报解析对照（含 Docling）与 AKShare 适配器均未实施。
- **未触碰的人工门禁**：未 commit/push/部署，未调用付费模型（provider 调用 0），未改动 `backend/competition_demo_cases.json`、冻结案例数据、T0、baseline、发布记录与任何签字或人工评分。`knowledge_ingest.py` 仍未被任何路由调用，其边界修复只表示"接入前已具备条件"，不得写成入库链已可用。

## 2026-09-08 竞赛要求逐项整改（当前工作树）

- 依据 `docs/2026-09-08_AuditTrace竞赛要求逐项达成审查与全面改进计划.md` 执行 M02/M03/M04/M05/M06/M08/M09，逐任务状态见 `docs/2026-09-08_竞赛改进任务执行台账.md`，机器可读索引见 `PROJECT_STATUS.json.competition_improvement_20260908`。HEAD 仍为 `26059cfc…`，工作树未提交，未部署，未代发任何外部消息。
- **M02 初赛方案书**：26 号候选稿渲染为 15 页（`artifacts/competition-improvement-20260908/proposal-render-v5/`），15 张页面图逐页人工查看；正文最小字号 8.0pt、第 8 页来源 URL 段 7.5pt，右边界未越可打印区。数字实测核对：384 项测试（截至 2026-09-07）、15 案、45 份登记年报（15×3 年，全部带 SHA-256，本地不驻留全文）、`deepseek-v4-flash`、B2 `EVAL-B2-2F8BE053630D` 失败事实均一致。发现并修正 1 处：表 10 “浏览器记录”行原写“最近记录”，与列标题“带日期的已有证据”矛盾，已改为 2026-09-07 记录。逐页记录见 `docs/2026-09-08_26号初赛方案书PDF逐页核验记录.md`。封面与参赛人员仍为“待填写”，第 2 页含导师真实手机号与手写签名，匿名口径未确认前不得作为提交版。
- **H04/M05 真实模型运行（经队长授权 1 次）**：`RUN-V7-30E58BC730C6` / task `DEMO-RUN-75A7591A4E22`，案例五粮液 `CNINFO_000858_T0_20260430` 2025 年度，`external_live`、`deepseek-v4-flash`、`agent_prompt_v3`，3 次 provider 调用、三个可追踪调用 ID、`cache_hit=false`、13,847 ms、35,220/1,861 tokens，三角色全部 `completed` 且各带输入/响应哈希，磁盘原件 207,492 字节、SHA-256 `09f7d306…c824`。终态 `candidate` / `complete_public_prescreen`，**不是**正式生产 B3。留痕见 `docs/2026-09-08_当前工作树真实完整链运行留痕.md`。
- **M03 六类案例独立复算**：`scripts/build_case_independent_recomputation.py` 对 15 案各跑一次 `calculation_only`（provider 调用 0），按 `field_kind` 取收入与应收族原值独立复算并与程序逐项比对。结果：**8 案一致、1 案指标暴露矛盾、6 案因资料缺口 N/A**。**当日更正**：本项首版曾报“9 项登记冲突、标准股份应收三年为负值（−212,351,971.28 等）、中国石油/中国石化详情值约为来源值 1/126 与 1/311”，经复核是脚本把所有非营业收入字段误当应收所致（那三个负数实为标准股份**净利润**，公司确实亏损），属误报，已作废并重跑。修正后的真实疑点：紫金矿业 2023/2024 应收登记为 **4.00 元 / 1.00 元**，长江电力 2024、立讯精密 2023/2024、万华化学 2023/2025 出现 **1.00/5.00 元**，形似页码或位数；中国石油、中国石化应收三年恒定（9,000,000 / 7,000,000）且与同案例并存的 `accounts_receivable_net`、`accounts_receivable_allowance` 相差 1—3 个数量级；中国海油程序报出 `growth_gap=0.0377176610` 却把 `ar_growth` 置 null，两者不能同时成立。这 6 案引擎均返回 `DATA_GAP`，没有用可疑值编造增速或风险卡。裁决项见 `docs/2026-09-08_案例登记值裁决建议单.md`（AD-1—AD-4），核对表见 `docs/2026-09-08_六类代表案例独立复算核对表.md`，复核人与日期一律留空。另：六类中“行业不适用”无法演示——15 案 `industry_gate.fit_level` 全为 `direct`。
- **M04 知识库**：26 问测试集实跑（`scripts/run_knowledge_retrieval_test_set.py`）。13 条来源中 5 条页码或行号级定位、4 条描述性、4 条写明“页码以原件为准”，**0 条含可回查原文短引**，6 条带 `query_terms`。12 问期望拒答中 11 问仍有命中，说明台账检索缺相关性下限（零相关问题也会返回权威材料）；跨公司提问时年报会被标 `case_fact_prohibited`，但同公司提问下的无关问题仍标 `case_fact`。未做真人相关性标注，因此不报告 Recall@k 或 Precision@k。见 `docs/2026-09-08_知识库来源分栏与检索测试集实测.md`。
- **M05/M06 工具与台本**：`docs/2026-09-08_B0-B3同案对照冻结合同模板.md`（S1—S12 门禁顺序、2.1—2.12 待真人冻结字段、11 项指标逐条分子分母）、两份盲评表与逐案对照记录表（UTF-8 BOM）、`scripts/compute_b0_b3_metrics.py`（缺人工评分时 fail closed，实测对今天的运行只报 N/A 与 1/1 完整链，不编造效果数字）；`docs/2026-09-08_初赛五分钟视频录制台本与画面清单.md`（计划 290 秒、口播 1200 字、S01—S20 画面清单、33 项录后自检空勾选）。真人出镜、录制与评分均未执行。
- **M08 实现独立重算与外置绑定（当日更正：未关闭 F02/F03）**：新增 `backend/app/release_evidence.py` 从磁盘原件重算结果哈希、按尝试哈希重派生调用 ID、重跑确定性事实语言闸门，并只从独立人工评分台账推导评分完成状态；`_load_fresh_b3_evidence` 不再读取发布记录内联的自报字典。新增外置版本绑定（锚点必须在工作区之外，绑定真人批准 → 内容哈希 → 源码与运行原件哈希 → 门禁），`evaluate_release_ready` 未获 `verified` 绑定一律阻断。调用 ID 派生规则抽到 `backend/app/provider_calls.py` 供在线与离线共用。当时实测：`test_release_evidence` 36 项、`test_release_gate_contracts` 20 项、全量 **420 passed / 1 warning in 96.40s**（同日另一次为 238.49s，联网用例耗时不同，项数一致）；`verify_release_evidence.py` 对今天的运行重算一致，仅因人工评分未完成而 FAIL；改写锚点后报“疑似被改写”。中文说明 2486/24471=10.16%。**当日更正**：段首原写“关闭 F02/F03”不成立。独立验收用负向夹具复现出两处当时没有测试覆盖的缺口——评分行改分不改摘要仍被接受（A02），锚点可不绑任何文件与运行仍判 `verified`、且预期版本被补作运行事实（A03）。本轮返工后：读取端整行重算摘要并按真人冻结标准核对维度/区间/有限性；绑定 schema 升 `v2`，拒绝空清单与必需文件缺项、要求覆盖门禁选用运行与登记台账；`source_commit/deployment_commit/manifest_sha256` 只从运行原件读取。专项四文件合并 92 passed（新增 `test_release_evidence_hardening.py` 31 项、`test_blind_submission_anonymity.py` 5 项），F02/F03 在复核通过前保持开放。
- **M09 交付面**：`scripts/check_delivery_surface.py` 首测扫 173 个交付面文件，生成 173 项 SHA-256 清单；固定依赖 41 项，`THIRD_PARTY_NOTICES.md` 补登记 14 项后覆盖 41/41（其中 `axe-playwright-python`、`pillow`、`pypdf`、`pypdfium2` 的许可证仍待核验，本机未安装或元数据未声明）；敏感形态必须处理 0 处、待判定 0 处，28 处为测试夹具、28 处为亿元级金额形态；既有 `scripts/scan_working_tree_secrets.py` 报 `no_secret_hits`。**返工后重跑**：180 个文件、41/41 覆盖、必须处理 0、RESULT `PASS`。同日实测确认一处既存依赖不一致：`pypdf` 已在许可清单中登记但本机虚拟环境**未安装**，而 `scripts/audit_proposal_v4.py` 直接 `from pypdf import PdfReader`；本轮新增的 PDF 校验因此改用已安装的 PyMuPDF，未擅自改装或改技术栈。
- **同日续（第 1—3 项）**：① 登记值诊断完成，产出 `docs/2026-09-08_案例登记值裁决建议单.md`（AD-1—AD-4 待真人裁决），并更正本日上午的误报；② 匿名口径产出 `02_最终确定方案/27_..._盲审提交候选_2026-09-08.docx`，实名母版 26 号未改动，两份并存供队长选择，见 `docs/2026-09-08_初赛匿名口径与两份提交版说明.md`。**当日更正（A01）**：该条原文写“身份字段与导师签名图像已移除，全文身份残留扫描 0 处”只对文本层成立；首版盲审件仍在包内保留 `word/media/image1.jpeg`（与母版导师签名逐字节一致，SHA-256 `fdf3cf8b…75c68`），因为脚本只删显示节点、未清除 `word/_rels` 里的 image 关系。现 `_strip_drawings` 收集被删节点引用的关系 ID，保存前删除已无人引用的关系，保存后按 ZIP 逐部件复验：媒体 8→7、孤立媒体 0、悬空 image 关系 0、页眉页脚与 `docProps` 身份命中 0；有缺陷的旧件留档于 `artifacts/independent-plan-acceptance-20260908/A01-defective-blind-copy-27.docx`，新哈希 docx `2887ec5c…`、PDF `294cd589…`（15 页）。③ 人工评分台账已建立并接线到发布记录（`backend/release_records/human_scores/`，含 README 与 `scripts/record_human_score.py`），**台账当前为空**。原写“两名真人写入后 `verify_release_evidence.py` 即报 PASS”是临时合成夹具下的结果，不构成人工评分完成，且当时读取端还不重算行摘要（A02）。返工后读写两端共用 `human_score_row_digest`，并要求 `rubrics/<版本>.json` 里有**真人已冻结**的评分标准；标准缺失时评分门禁按设计失败关闭，`rubrics/` 目前为空。
- **第 4 项：clean tree 冻结与绑定（结论已被独立验收推翻）**：提交 `d5ff829` 使工作树转为 clean，随后在该提交代码上跑通队长授权的第 2 次真实完整链 `RUN-V7-0351B4C6950D`（task `DEMO-RUN-6565C61D7C66`，3 次 provider 调用、`cache_hit=false`、14,623 ms、35,481/2,073 tokens，磁盘原件 209,780 字节、SHA-256 `6f01d33d…532ec`）。锚点 `release-20260908-d5ff829.json` 与后继 `release-20260908-1c9f1db.json` 均为 `v1`、批准人为空。**当日更正（A03/A04）**：原文“复验只剩两项…其余全部通过”不成立——v1 锚点允许文件表与运行表为空仍判 `verified`，且运行原件 `context` 根本没登记 `source_commit/deployment_commit/manifest_sha256`，这些字段此前由调用方期望值补写成运行事实。绑定 schema 已升 `v2`（必需 9 个文件、拒绝空清单、要求覆盖门禁选用运行与登记台账），实测 `verify_release_evidence.py` 对该运行与 v1 锚点退出码 1，失败项为“人工评分未完成或未绑定独立台账”与“外置绑定版本不受支持，当前只接受 `audittrace_release_binding_v2`”。三份 v1 锚点全部作废，须由真人在最终代码冻结后重建。该运行仍是 `complete_public_prescreen` 且非 production，未登记为生产 B3。
- **2026-09-08 独立验收与 A01—A04 返工**：验收报告 `docs/2026-09-08_Qwen交付独立验收报告.md` 判定“整体暂不通过、部分交付可保留”，M08 不通过。返工计划 `docs/2026-09-08_Qwen验收报告返工计划.md`，执行留痕 `docs/2026-09-08_A01-A04返工执行留痕.md`。本轮修 A01（匿名媒体部件）、A02（评分整行重算 + 真人冻结标准）、A03（绑定非空、必需清单、运行与台账交叉绑定、版本期望不再补作运行事实）和 A04（状态表述），专项测试 92 passed（36/31/20/5）。M03 原件回页、M04 检索整改与 26 问判据修订、M07 独立目录冷启动、M05/M06/M10 真人项**本轮未做**，仍按台账逐项开放；`competition_release_ready` 保持 `false`。
- 一次全量回归中出现 1 次 `test_all_seed_cases_enter_three_role_external_route` 失败，当时本机 8000 端口服务在运行并向 `backend/runtime` 追加记录；停服务后单文件与全量复跑均绿。根因未定位，按间歇性风险保留，不写成稳定全绿。

## 2026-09-07 概览复核与门禁整改（上一轮工作树）

- 当前复核对象为 HEAD `26059cfc79643f05b37d706393ebbb851dc32f80`。按复核结论完成 R01-R03、R05-R06 修改，尚未提交、部署或调用付费生产模型；`RELEASE-CANDIDATE-20260828-V1` 仍保持 `competition_release_ready=false`。
- 发布门禁继续使用固定的 `challenge/counter/review` 角色集合；供应商调用 ID 和真人评分记录 ID 必须为非空、唯一字符串，调用 ID 数量必须等于真实调用次数；最终批准只接受布尔值 `true`。每次尝试只能使用自身的输入/响应哈希，重试缺哈希或历史数量不一致时失败关闭。新请求、文件和远程缓存回放均清空本次 `provider_call_ids`，嵌套 Agent 步骤的来源调用明细也会清空，旧运行编号只在缓存来源上下文回查。相关代码为 `backend/app/release_gate.py`、`backend/app/main.py`、`backend/app/delivery.py`、`backend/app/schemas.py`。
- 源码最后一次全量回归为 **384 passed、1 warning（224.05 秒）**；发布门禁契约 **20 passed**；故障/恢复相关子集仍为 **33 passed、1 warning**。`docs/TEST_INVENTORY.md` 已更新为 37 个测试文件、384 项、10 个需联网文件；中文说明比例为 **2434/24072=10.11%**；前端契约为 166 个唯一 ID、175 个引用、1 个脚本。
- 真实本地运行验收：15 个冻结案例执行 90 次 `calculation_only`，90/90 通过且 provider 调用为 0；15 案详情与 RAG 共 30 项通过；公开写入边界 3 项均返回 HTTP 403。真实模型不可达时记录 `incomplete_model_chain_failed/unavailable`，显式备用入口生成带 `parent_run_id` 的 `complete_demo_fallback/deterministic_backup` 子运行。
- 四视口（1440×1000、1024×768、768×1024、390×844）均完成真实页面选择→分阶段运行→结果→证据抽屉→Agent 抽屉→补充证据父子差异→打印→JSON/CSV 下载。每个视口 9 个状态的 axe 均真实执行且 violations=0；console/page/失败请求/HTTP error=0；横向溢出=0；Enter/Esc/Space 焦点与折叠状态、打印强制展开均通过。截图和 JSON 位于 `artifacts/review-plan-20260907/browser-final/`。生产 CSP 未修改；一次通用静态审计工具因内联 axe 被 CSP 阻止，不能把该工具的空结果当作无障碍通过，本轮以同源注入版本的真实结果为准。
- 2026-09-04 评委包独立解压复跑为 **346 passed、19 skipped、1 warning**。旧包与当前源码收集项相差 19 项；原差异清单记录了其中 18 项，当前新增的 1 项为验收脚本失败汇总反例测试。差异构成为 8 项仓库交付/取证/杰克案例测试、9 项门禁参数化反例、1 项调用 ID 派生测试、1 项验收脚本失败汇总测试。19 项 skip 均是缺年报全文或内部签字原件的显式边界。
- 未闭合门禁仍有：fresh B3 证据需独立重算运行记录、结果文件和人工评分记录；发布记录与代码同仓的非循环外置证据绑定流程；生产 provider、专业签字、B0—B3 真人评分；标准股份净额/账面余额口径的专业确认。历史状态、历史模型样本和旧报告继续保留，不能代替这些当前证据。
- 验收脚本的必要断言漏报已修复，并有隔离反例证明失败会返回非零退出码；缓存轨迹归属修复也已完成。本次修复尚未随当前评委 ZIP 重新打包，旧包不能证明包含 R01-R03、R05-R06 修复。
- 修复后在真实本地服务上运行验收脚本（跳过运行与 RAG）完成 15 案详情和 3 项只读边界检查，失败 0 项；原始结果位于 `artifacts/review-plan-20260907/acceptance-script-postfix.json`。

本轮详细执行记录见 `docs/superpowers/plans/2026-09-07-AuditTrace概览复核与审查修改计划.md`；机器可读索引见 `PROJECT_STATUS.json.latest_review_20260907`。

## 2026-08-26 R3 缺口修复与真实验收（历史冻结窗口，已由 2026-08-28 整改候选 supersede）

- B1—B3 已在当前代码建立新的追加式合同目录：`outputs/evaluation_v5/EVAL-20260826-B1B3-CURRENT-R3/`。五粮液、中国海油、标准股份各执行一次，共 9 条原始 JSON；旧 R2 目录和历史目录均未覆盖。
- R3 结果：B1 为 3/3 确定性完成且外部调用 0；B2 为 0/3 完成，每案仅一次真实单模型调用，原始失败码均为 `MODEL_OUTPUT_VALIDATION_FAILED`、校验阶段为 `validation`，且每条均绑定字段证据与 `PROC-R1-2025` 程序证据卡；B3 为 3/3 `model_success`，三角色均完成。`B2_FAILURE_CLASSIFICATION.json/.md` 在不改写原始记录的前提下，将错误文本进一步映射为 `MODEL_FACT_LANGUAGE_VALIDATION_ERROR` / `fact_language`。B2 与 B3 口径不同，不合并为官方成功率。AI 辅助预评分均值分别为 B1 97.7、B2 59.0、B3 98.3；项目队长正式评分栏仍为空。
- R3 冻结的 qwen3.5-plus 质量窗口为 **7/10=70.0%**，阈值 80%，状态 `below_threshold`、`alert=true`；该数字只作历史告警证据，不等于当前候选的 runtime 窗口。真实失败码、响应哈希、token、耗时和受控修正次数均保留。
- 12 条活跃知识来源已完成独立可访问性抽查，结果为 12/12 HTTP 200；活跃来源仍是 13 条登记中的 12 条，另 1 条归档。资料范围继续写“代表性接入”，近五年窗口为 2021-08-24 至 2026-08-24，不宣称全量。
- 补充材料父子任务合同测试通过；现场 `600436`（片仔癀）入口已在 8000 当前实例完成一次真实任务，企业解析、公告/文档校验、案例登记、RAG、字段提取和结构化导出均有记录。浏览器现场样例终态为“需要人工确认/模型链不完整”，未写成模型成功；证据与 JSON/CSV/打印 PDF/DOCX 位于 `outputs/browser-r3-export-8000/`。
- 浏览器静态验收 `outputs/browser-r3-static11/static-audit.json` 覆盖 1440×900、1440×1000、1024×768、768×1024、390×844：axe violations/incomplete、console/page/网络错误和横向溢出均为 0。前端契约为 131 unique ids、129 refs、1 script；JavaScript、Python compile、`git diff --check` 均通过。
- 从项目根目录与 `backend` 目录分别运行全量回归，均为 **329 passed、1 warning**；唯一 warning 仍为 Starlette TestClient/httpx 兼容性弃用提示。
- R3 事实快照已冻结：`outputs/final-audit-20260826-r3/`；JSON SHA-256 为 `49739505744686c2510222ae49ae1f531d334f257356fd537e8fd13727c7f5a7`，Markdown SHA-256 为 `7ca8861f2334e3f74704f24c2864e6664abb5cde543fa3732389edd945b08e79`。快照主链哈希范围排除 PROJECT_STATUS、README、快照和浏览器输出；回填状态文档不会改变该主链哈希。当前状态仍不能写成“模型稳定成功率超过 80%”或“任意新企业均自动完成”；现场样例人工确认、B2 失败和质量告警必须保留。

## 2026-08-25 R2 追加验收（历史冻结窗口，已由 2026-08-28 整改候选 supersede）

- 队长追加签字已完成：`outputs/professional-signoff/R1-v0.4-captain-signoff-20260825-r2.json/.md`；状态为 `captain_approved_for_competition_demo`，姓名字段空白，旧签字记录保持可追溯。签字后事实快照位于 `outputs/final-audit-20260825-r2/`。
- 当前代码 B1—B3 合同目录为 `outputs/evaluation_v5/EVAL-20260825-B1B3-CURRENT-R2-NETWORK/`：五粮液、中国海油、标准股份各执行 B1/B2/B3 一次，共 9 条原始记录；B1 3/3、B2 0/3（均为 `MODEL_OUTPUT_VALIDATION_FAILED`）、B3 3/3 三角色 `model_success`。旧 `EVAL-20260825-B1B3-AI-PRESCORE-V1` 目录不被覆盖，仅作历史证据。
- R2 冻结的 `qwen3.5-plus` 真实外部三 Agent 质量窗口为 **7/10=70.0%**，阈值 80%，`below_threshold`、`alert=true`；该数字只作历史告警证据。不得宣称稳定成功，不自动切换模型。
- 真实 B3 结果均写入知识检索轨迹、来源台账、认定—证据—程序矩阵、证据适配度、数字回查和反确认记录；失败/降级运行保留真实失败码，不冒充成功。
- 四视口静态/动态浏览器链、键盘抽屉、重置、JSON/CSV/打印入口均已验收；真实 B3 `RUN-V7-DB751326FFAC` 的 API JSON 与 Word/PDF 报告也已核对并记录在 `outputs/final-audit-20260825-r2/real-export-audit.json`。自动阻断项、console/page/网络错误和横向溢出为 0。axe `color-contrast` 因渐变/伪元素无法自动判定，保留人工复核项。
- 最新回归：后端 **321 passed、1 warning**；前端契约 **131 unique ids、129 refs、1 script**；JavaScript、Python compile、`git diff --check` 和中文说明比例 **2198/21676=10.14%** 均通过。快照 JSON/Markdown 哈希分别为 `fa352bf3fbe15f2c92c3f2136e4fc8a6ec9cb4491a36abb65446f806466eeda8`、`d82df2122b0e7c33a7f1f4481780e34aaecafcc3c1ec3e115ac7bd39f652299f`。

## 2026-08-25 主方案、创新增强与 B1—B3 评估状态（历史快照，已由整改候选 supersede）

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

详细记录见 `archive/2026-09-02/历史报告/审迹智链_51案例AI全链复核与Bug修复报告_2026-08-13.md`；8 月 9 日报告保留为历史快照。

## 当前正式口径

- 正式业务范围：审计计划阶段的销售与收款循环风险预筛。
- 正式入口：根目录 `index.html`，采用 V4“证据地平线”设计；旧 `09_官网V4_融合增强实验版` 已移入本机历史材料归档，仅作整改前基线。
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

## 2026-09-19 队长裁决登记与赛后欠账

- **当日裁决 R1—R5** 全文见 `docs/CONTRACT_2026-09-19.md` §九：R1 分支与检查点提交授权；R2 PlanningPriority 不设 `reasons`；R3 `evidence_state` 扁平/嵌套键名裁定为永久分层；R4（对应开工基线 D6）W11 `no_trigger_confirmed` 可达性选 (a)；R5 授权轨 A 生成 `run_contract_mock_degraded.json`。
- **赛后欠账（不得遗忘）**：W11 的 (a) 是呈现层措辞兜底，不是根治。R1 正常计算时 `risk_card.data_gaps` 恒含 4 条常设资料缺口，路由选择器因此结构性不进入 `negative_confirmation`。赛后须实施 (b) 路由最小修复，并配完整回归；实施前任何“未触发已确认可达”的表述均不成立。依据：`docs/audit_no_trigger_reachability.md`（轨 C 只读审查）与 2026-09-19 两轮独立磁盘复核。
- **当日受控评估事实不变**：B0 未执行；B1 `RUN-V7-0BDE5060FBED` 已执行；B2 `EVAL-B2-2F8BE053630D` 校验失败；历史 B3 `RUN-V7-00ED00962F34` 经事实闸门复核失败；人工评分全部空白。本轮工程改造不等于竞赛验收通过。

## 2026-09-19 W19—W25 集成、真实验收与录制基线（当前工作树）

- **W19 三端一致性**：后端 run JSON ↔ Word 导出对五条真实 live 运行逐字段比对，
  六个契约字段与状态行 **58/60 字面一致**；两处差异经复核为核验脚本的**误报**
  （中国海油段落含模型自撰的「未形成程序候选不等于企业无风险」，长江电力段落含 RAG 引出的年报原文「风险评级」字样，
  均非系统自撰标签）。把红线核对范围修正为"系统自撰的标题与行标签"后 **5/5 通过**。
  前端腿经真实浏览器实测确认（见下）。
- **W21 稳定性**：五粮液连续 **3 次 fresh `external_live`** 完整分析（`RUN-V7-A923212497D0` /
  `RUN-V7-CD12FD56306C` / `RUN-V7-901E91444479`），三次全部 `cache_hit=false`、3 次 provider 调用、
  三角色完成、`numeric_gate.passed=true`、`key_unverified=[]`、`run_completeness=complete_public_prescreen`、
  `growth_gap=0.55619794099056` 逐位相同、三轴 `P2 / E2 / retain` 三次一致。
  其中 2 次 `analysis_conclusion=additional_procedure_required`、1 次 `risk_candidate`；
  自然语言层允许差异，程序事实层稳定。**D1 数字闸门误杀已在真实 live 路径上确认修复**
  （当日 13:09—13:13 曾三次全败于同一数字）。
- **W22 Demo Case Matrix**：在当前 HEAD 上取三条 fresh live，四条路线给出**四种不同结果**，
  全部可回查 `outputs/w21-w23-live-verification-20260919/w22_matrix.json`：
  五粮液 `P2 优先核查 / E2 / retain`（risk_candidate，+55.62pp strong）；
  标准股份 `G 暂不分级 / E2 / defer`（R1 未触发 −13.20pp，R2 `DATA_NOT_COMPARABLE`）；
  中国海油 `S 暂缓判断 / E3 / defer`（industry_review）；
  长江电力 `G 暂不分级 / E3 / defer`（R1 `DATA_GAP`，`blocked_candidate_count=6`）。
  **严格落 `P4` 的 live 案例本轮未取到**——`S` 优先于 `P4` 是已裁定的保守顺序，非缺陷。
- **W17 在 live 路径上再次确认**：长江电力 `growth_gap=null`，不再出现历史 1.45e9 量级；
  抽取诊断原文（"同字段连续年度金额相差 1450369507.8 倍，可能存在错列、单位或表内子项误取，须人工回页确认"）
  已在 `prescreen_plan.candidate_quality_issues` 中供前端 W16 直接读取。
- **W23 Golden Demo Run 已冻结**：`RUN-V7-901E91444479`（task `DEMO-RUN-9ABA77BB1D68`），
  基线 commit `13f25549f9b0`，原件 224,226 字节、SHA-256 `04F5E3E146042685…`，
  闸门 `validation_mode=claim_scoped`、已追溯年报原文来源 `RAG-…-2025-P0089-C00`（第 89 页）。
  记录 `outputs/w21-w23-live-verification-20260919/golden_demo_run.json`。
  **它是录制前的对照基线，不是缓存回放的借口。**
- **W24 增量验收**：`3 状态 × 4 视口 = 12 组`在**带契约字段的真实 live 运行**上实测，
  控制台错误 0、失败请求 0、横向溢出 0、⑥ 三徽标与两条边界句全部在场，390 宽下关注卡 280px 未塌。
  证据 `outputs/w21-w23-live-verification-20260919/w24_live_acceptance.json`。
- **发现并如实登记的录制阻塞**：`:8000` 本地实例启动于 12:56:59，早于契约字段挂载落地（20:47—20:52），
  且启动器默认不带 `--reload`，**该进程冻结在旧代码上**；不重启就录制，三徽标与六区关注卡不会出现。
  已在台本 §0.1 给出重启与自检步骤。
- **口播事实修正**：备用链下的五粮液 `ai_recommendation=defer`（`RUN-V7-1FF5B1149044` 实测），
  故"defer 只出现在标准股份"一句不成立，已改为按运行来源分档表述。角色名统一为
  质疑 / 反证 / 复核 Agent，系统内无 Arbiter。
- **W25 台本**：`2026-09-19_演示录制台本与画面清单_V2_实测校准版.md`（含九条口播红线、五幕结构、
  S01—S14 画面清单、五项已知瑕疵如实登记）。
- **W05 补齐**：Word 备忘录「运行来源」行此前只写代码未提交、零测试覆盖；
  已提交 `13f2554`，新增 `backend/tests/test_delivery_contract_fields.py` 9 项，
  并按 R5 生成 `backend/tests/fixtures/run_contract_mock_degraded.json`
  （同底座只翻闸门结果 → `incomplete_numeric_claims` + `E3`，而 `P2 / retain / 徽标` 逐字不变，
  以钉死"闸门不参与定级"的双轴性质）。
- **实测**：`pytest backend/tests -q` **586 passed / 1 skipped / 0 failed**（142.43s；
  原基线 577，+9 为 W05 补齐项）；`scripts/check_chinese_comments.py` **2813/26641 = 10.56%** PASS；
  `node scripts/verify_demo_outcome_judge.mjs` **75 项通过**；`git diff --check` 退出码 0；
  `scripts/scan_working_tree_secrets.py` `no_secret_hits`。
- **付费调用**：本轮经队长授权执行 **6 次真实完整链运行 / 18 次 provider 调用**
  （W21 三次 + W22 三次），全部 `external_live`、`cache_hit=false`；
  所有测试与只读探针一律前缀 `DEEPSEEK_API_KEY=`，未提交、未推送、未部署。
- **间歇项触发条件已复现定位**（升级 2026-09-15 段"根因未定位"的登记）：
  `test_all_seed_cases_enter_three_role_external_route` 在**有第二个 uvicorn 实例运行并写同一份
  `backend/runtime`** 时全量失败、单独运行时通过；停掉该实例后全量 **586 passed / 1 skipped / 0 failed**（157.77s）。
  本轮实测两次：`:8011` 在跑时全量 FAILED，`taskkill` 停掉后全量绿。
  失败现场伴随多条 `ResourceWarning: unclosed database in <sqlite3.Connection>` 指向案例台账 sqlite，
  说明测试的 `TestClient(app)` 与在线实例共用同一份磁盘台账状态而被干扰。
  **精确失效路径仍未定位**，但触发条件可复现，故按"跑全量回归前必须停掉所有 uvicorn 实例"作为操作规程执行。
- **未闭合项**：`cache_replay` 态仍未在真实浏览器实测（本机需 Supabase 缓存行 + 真人 `export_approved`），
  **不得计入验收通过**；④ 区存在「应收账款账龄明细表 / 账龄明细表」近似重复条目（呈现层瑕疵）；
  `PROC-R1-*` 程序结果证据无 PDF 页码，回链如实显示"原文入口未提供"；
  W11 的 (b) 路由根治、128 条被拦截候选的真人回页、B0—B3 真人评分与 R1 重新签字均仍开放。

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
