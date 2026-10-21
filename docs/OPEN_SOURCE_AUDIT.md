# 开源就绪审计记录

本文件保存本轮开源改造的**审查证据**：内容分级、安全审计、公开范围清单、干净环境复现与浏览器冒烟结果。
许可证选择的分析另见 [LICENSING_DECISION.md](LICENSING_DECISION.md)。

- 审查起点：`origin/main` = `6abd3d7`
- 工作分支：`chore/open-source-readiness`
- 已跟踪文件：661 个，108.03 MB

---

## 1. 内容分级（A–E）

按"能否公开、以什么条件公开"分类。体积为已跟踪文件实测值。

### A. 适合公开的项目源代码

| 路径 | 文件数 | 体积 | 说明 |
|---|---:|---:|---|
| `backend/app/` | 74 | 1.99 MB | FastAPI 应用、关联核对流水线、抽取、RAG、模型调用 |
| `assets/official-v4/` | 48 | 5.73 MB | 前端源码与插图（含 Lucide 图标，MIT） |
| `scripts/` | 93 | 0.84 MB | 验收、冻结、复算脚本 |
| `deploy/`、`supabase/`、`render.yaml` | 9 | 0.06 MB | 部署配置（不含密钥，全部为环境变量占位） |
| 根目录配置 | 8 | <0.01 MB | `requirements*.txt`、`pytest.ini`、`conftest.py`、`.gitignore`、`.gitattributes` |

### B. 允许公开的测试与示例数据

| 路径 | 文件数 | 体积 | 说明 |
|---|---:|---:|---|
| `backend/tests/` | 83 | 1.24 MB | 79 个测试文件 + 3 个 mock 夹具 |
| `tests/` | 4 | 0.45 MB | 前端契约与截图脚本 |

`backend/tests/fixtures/` 只含合成或脱敏的合同样例（`run_contract_mock.json` 等），无真实企业数据。

### C. 需要核实版权或再分发许可的材料

| 路径 | 文件数 | 体积 | 状态 |
|---|---:|---:|---|
| `outputs/` | 123 | 86.78 MB | 运行产物与验收截图。**其中 `outputs/track-c-w24-20260919/` 独占 64 个文件 / 82.15 MB** |
| `决赛准备/` | 78 | 2.79 MB | 竞赛答辩材料，含第三方报告页图（`原文页/*.png`）与讲稿 docx |
| `backend/` 数据文件 | 27 | 4.89 MB | `cache_seed.materialized.json`（2.64 MB）与 `company_directory.snapshot.json`（1.70 MB）为**元数据**，不含 PDF 正文 |

第三方报告 PDF 全文**未入库**（`.gitignore` 阻止 `*.pdf`），运行时下载到 `backend/runtime/`（同样被忽略）。

### D. 不应公开的密钥、私人数据、运行记录

**当前工作树：无。**

- `.env` 从未进入 Git 历史（已核验，0 次 add）。
- 工作树中唯一的环境文件是 `.env.example`，所有值为空。
- 无数据库、无 SQLite 文件、无真实模型调用响应入库。

### E. 已公开但存在潜在风险的历史文件

| 项 | 位置 | 风险等级 | 处理 |
|---|---|---|---|
| 本机绝对路径 | `archive/2026-09-02/历史报告/审迹智链_剩余任务执行计划_2026-08-09.md`、`docs/superpowers/plans/2026-09-03-三AI协作总调度计划.md` | 低（仅路径，无密钥） | 保留，记入 `SECURITY.md` |
| 真实个人邮箱 | Git 提交元数据（`StyXander` 账号，3 个提交） | 低（非密钥，属个人信息） | **未处理**，清除需历史重写，待所有者决定 |
| 竞赛讲稿 docx | 历史提交（`决赛准备/整改_2026-10-11`、`2026-10-12`） | 低（团队自有材料） | 保留 |

---

## 2. 安全审计

### 工具与范围

| 项 | 内容 |
|---|---|
| 密钥扫描 | 环境无 `gitleaks` / `trufflehog`，改用正则扫描（`sk-`、`ghp_`、`gho_`、`AKIA`、PEM 私钥、JWT、赋值型密钥字面量） |
| 依赖漏洞 | `pip-audit 2.10.1`（安装于隔离 venv） |
| 覆盖范围 | ① 当前工作树 ② 已跟踪文件 ③ **全部 192 个提交** |
| 个人信息 | 邮箱（qq/163/126/gmail/outlook/foxmail/sina）、手机号、绝对路径 |

### 结果

| 层 | 命中 | 说明 |
|---|---:|---|
| 工作树 | 0 | 无密钥、无 `.env` 实体、无个人信息 |
| 已跟踪文件 | 0 | 同上 |
| 全部 192 个提交 | 0 | 逐提交 `git grep`，含私钥与 JWT 模式 |
| 依赖漏洞（runtime） | 0 | `pip-audit -r requirements.txt` |
| 依赖漏洞（dev） | 0 | 修复后复扫通过（详见下） |

**一次必须记录的扫描失误**：首次用 `git log --all -p` 扫描历史，在某个 `.docx` 二进制 diff 处 `fatal: unable to read files to diff` 中断，**192 个提交实际只扫了 39 个**，却输出了"零命中"。改用逐提交 `git grep`（192/192）并做阳性对照——`DEEPSEEK_API_KEY` 在 174 个提交中命中——才确认扫描真的覆盖了全部历史。

### 依赖供应链修复

两条问题同源：**版本上限把修复版挡在门外**。

| 依赖 | 原约束 | 问题 | 处理 |
|---|---|---|---|
| `pytest` | `>=8,<9` | 8.x 存在 PYSEC-2026-1845，修复版 9.0.3 | 抬至 `>=9,<10`；906 项回归已在 9.1.1 实测通过 |
| `pillow` | `>=10,<12` | 11.3.0 有多个 CVE，修复版 12.3.0+；且全仓库无 `from PIL` / `import PIL` | 移除该未使用依赖 |

### 运行期风险（已在代码中缓解，非阻断）

| 风险 | 现有措施 | 位置 |
|---|---|---|
| 下载任意地址（SSRF） | 只允许巨潮 / 深交所 / 新浪公告镜像三类官方域名 | `connectivity_extraction.py::ensure_source` |
| 报告被替换 | 下载后比对登记 SHA-256，不符即 409 | 同上 |
| 重定向滥用 / 超大响应 | 逐跳复校、限制跳数、接收中限额、文件头校验 | `secure_download.py` |
| 模型编造证据 | 模型提案引用须逐字回溯，否则整条丢弃 | `connectivity_engine.py::validate_refs` |
| 越权读他人任务 | 历史列表只返回当前会话任务，无会话返回 409 | `connectivity_api.py` |

---

## 3. 公开范围与清理清单（文件级）

### 结论：本轮**删除 0 个文件**

所有者已明确选择"历史材料全部保留"。以下是据此做出的逐项判断与依据。

### 大体积文件（> 500 KB，共 30 个 / 84.0 MB）

| 目录 | 文件数 | 体积 | 是否被引用 | 判断 |
|---|---:|---:|---|---|
| `outputs/track-c-w24-20260919/screenshots/` | 25 | 76.40 MB | **是**，被 `2026-09-19_W19-W25_执行计划与授权登记.md` 与 `outputs/track-c-w24-20260919/report.md` 引用 | 保留：删除会断链 |
| `backend/cache_seed.materialized.json` | 1 | 2.64 MB | 是，热缓存预热清单 | 保留：功能依赖 |
| `backend/company_directory.snapshot.json` | 1 | 1.70 MB | 是，企业目录快照 | 保留：功能依赖 |
| `assets/official-v4/illustrations/` | 30 | 3.74 MB | 是，首页插图（单文件最大 1.30 MB） | 保留：页面使用 |

如果将来确定要瘦身，**唯一安全做法**是同时改掉引用它们的两个 Markdown 文件，而不是单独删图。

### 根目录的 17 个 Markdown

其中 9 个是 2026-09-18 至 2026-09-20 的过程日志（`2026-09-1x_*.md`），从首页看确实杂乱，但**不能移动**——已逐个查过引用：

| 文件 | 被谁引用 | 可否移动 |
|---|---|---|
| `2026-09-19_口径签字与开工基线.md` | **`backend/app/evidence_closure.py`、`backend/app/planning_priority.py`**（生产代码） | ❌ 不可 |
| `2026-09-19_综合执行方案_多AI并行.md` | 3 个同级文档 | ❌ 不可 |
| `2026-09-19_三份AI建议评审与24小时改进计划.md` | 2 个同级文档 | ❌ 不可 |
| `2026-09-19_录视频前突击修复与演示方案.md` | 3 个同级文档 | ❌ 不可 |
| `2026-09-18_Render两项异常…`、`2026-09-19_演示录制台本…`、`2026-09-20_三项任务…`、`opus修改建议 .md` | 各 1 处引用 | ❌ 不可 |
| `2026-09-19_W19-W25_执行计划与授权登记.md`、`2026-09-19_新修改计划完成度_独立复核.md` | 0 处引用 | 理论可移，但会破坏与前者的引用链，暂不动 |

**这里有一个容易踩的坑**：仅按"文件名看着像过程日志"就批量移走，会直接改坏 `evidence_closure.py` 与 `planning_priority.py` 的引用。所以本轮只做记录，不做移动。

### 已确认保留、不进 `.gitignore` 的例外

`/outputs/` 在 `.gitignore` 中被忽略用于**新增**产物，但已跟踪的 123 个文件保持跟踪状态，`git status` 不会因新规则出现删除。

---

## 4. 干净环境复现

在中文路径之外的全新目录、全新 venv 中执行（详见 `README.md` 第 7 节）：

| 检查项 | 结果 |
|---|---|
| `pip install -r requirements.txt` | 成功（PyMuPDF 1.28.2 / FastAPI 0.156.8 / faiss-cpu 1.15.1） |
| `connectivity_bootstrap --allow-missing-sources` | 10/10 文档 `available`，从白名单官方域名下载并校验 SHA-256 |
| 服务启动 | `uvicorn` 约 4 秒后 `/api/health` 返回 200 |
| 首页 `/` | 200，72348 字节 |
| `/api/connectivity/readiness` | `ready: true`，逐份核验哈希与页数（五粮液年报 141 页 / ESG 59 页） |
| 证据页 `/api/connectivity/sources/WLY_AR_2025/pages/7.png` | 200，195766 字节 `image/png` |
| 未建会话时 `/api/connectivity/runs` | 409（按设计拒绝） |
| 无模型 Key | `model_status: config_missing`，`deterministic_backup_available: true` |

---

## 5. 浏览器冒烟测试

环境：Chromium 151（Playwright headless），本地 `uvicorn` 实例，**未配置模型 Key、未预下载 PDF**。

| 视口 | 标题 | 横向溢出 | 导航项 | 视图切换 | console 错误 | 页面异常 | 失败请求 | ≥400 响应 |
|---|---|---:|---:|---|---:|---:|---:|---:|
| 1440×900 | 审迹智链 · 双报告关联核对 | 0 px | 9 | ✅ 跳转 `#connectivity-root` | 0 | 0 | 0 | 0 |
| 390×844 | 同上 | 0 px | 9 | ✅ 同上 | 0 | 0 | 0 | 0 |

服务端日志同步确认：全部 CSS / JS / 图标 / `/api/evidence-scenarios` / `/api/connectivity/bootstrap` 均返回 200，无 404。

**说明**：这是**页面可用性**冒烟，不等于业务链路验证。未下载 PDF 时不会产生真实核对结果，那部分由第 4 节的干净克隆验收覆盖。

---

## 6. 剩余不确定项

| 项 | 状态 | 原因 |
|---|---|---|
| GitHub 首页识别为 AGPL-3.0 | **待复核** | 许可证分类取自默认分支，`main` 尚无 `LICENSE`；合并后自动生效 |
| 著作权归属 | **待确认** | 仓库无贡献者名单、无学校/指导教师授权文件；当前用集体署名 |
| 历史提交个人邮箱 | **未处理** | 需历史重写，未经授权不得执行 |
| 三角色 AI 是否优于单模型 | **未证明** | 本项目实测未取得该证据，README 已如实标注 |
