# 审迹智链 AuditTrace

**基于年度报告与可持续发展报告的智能关联核对与证据追踪工具。**

AI-assisted annual report and sustainability disclosure verification with evidence tracing.

> CI 徽章暂不展示：`main` 分支上尚未产生该工作流的成功运行记录，此时挂徽章会显示为失败状态。待本分支合并、`main` 首次运行通过后再加。

> AI 生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，**不构成审计结论、鉴证结论或鉴证意见**。

---

## 1. 项目解决什么问题

同一家上市公司的年度报告与可持续发展报告（ESG 报告）经常在**两份不同文档**里披露同一件事：研发投入、员工人数、碳排放、环保投入、分红金额。两份报告的口径未必一致——合并范围、统计期间、单位（元/万元/亿元）、指标定义、统计边界都可能不同。

人工核对的难点不是"找到两个数字"，而是**判断这两个数字在什么前提下才可以比较**。直接让通用大模型读两份 PDF 并"比对数字"，通常得到的是看起来合理、但无法回溯到原文、也无法复算的结论。

AuditTrace 把这件事拆成四层：

| 层 | 做什么 | 由谁做 |
|---|---|---|
| 确定性计算 | 数值归一、单位换算、精度区间、差异判定 | 代码（`Decimal`，不含浮点） |
| 语义解释 | 判断两个指标是否指向同一概念 | 大模型（可选，可关闭） |
| 证据定位 | 每个数字必须回到"哪份文档、哪一页、哪一句" | 代码强制校验 |
| 专业判断 | 是否构成披露问题、是否需要追加程序 | **人**（系统只给线索） |

## 2. 主要能力

- **跨报告披露关系识别**：从两份报告的结构化表格中生成候选关系——合计与分项的组合关系、比例关系、同一指标跨报告配对、语义相近指标配对。
- **口径可追溯**：每条披露记录带 `report_boundary`（合并/母公司/分部）、`scope_level`（报表/表格/指标）、`currency_status`、`unit_status`、`rounding_method`、`content_class`（企业自身/宏观/行业/同业）等字段。数据不足时字段保持 `unknown`，**不推定**。
- **确定性核对**：按显示精度计算区间，差异落在舍入边界内不判为不一致；合并报表与母公司报表的差额不会被当成披露错误。
- **AI 辅助语义解释**：三种角色——A1 质疑、A2 反证、A3 复核；也支持单模型模式。模型只输出结构化提案，**引用必须能逐字回到原文**，否则整条丢弃。
- **证据定位与溯源**：`/api/connectivity/sources/{document_id}/pages/{page}.png` 可直接渲染原始页，供人工回查。
- **可复算**：核对的输入（字段、页码、哈希）与计算过程全部落盘，同一输入可重算出同一结论。
- **专业判断与 AI 意见分离**：结论层（`consistent` / `inconsistent` / `unknown` / `not_comparable`）由代码给出；AI 意见单独存储，不能覆盖结论。

## 3. 系统架构

```text
                     ┌──────────────────────────────┐
   浏览器  ────────▶ │  index.html + assets/official-v4  │  静态前端（同一 FastAPI 进程托管）
                     └──────────────┬───────────────┘
                                    │ /api/*
                     ┌──────────────▼───────────────┐
                     │      backend/app/main.py      │  FastAPI 应用
                     └──┬──────────┬────────────┬────┘
                        │          │            │
          ┌─────────────▼──┐  ┌────▼─────┐  ┌───▼──────────────┐
          │ connectivity_* │  │ rag.py   │  │ cninfo.py        │  巨潮公开年报抓取
          │ 关联核对流水线  │  │ FAISS 检索│  │ secure_download  │  逐跳校验/哈希/限额
          └───┬────────┬───┘  └────┬─────┘  └──────────────────┘
              │        │           │
     ┌────────▼──┐  ┌──▼────────┐  │
     │ engine.py │  │pipeline.py│◀─┘
     │ 确定性计算 │  │ 候选生成+AI│
     └────┬──────┘  └─────┬─────┘
          │               │
     ┌────▼───────────────▼────┐     ┌────────────────────┐
     │ connectivity_extraction │────▶│ PyMuPDF 文本/页图   │
     └─────────────────────────┘     └────────────────────┘
```

关联核对流水线的阶段（`backend/app/connectivity_pipeline.py`）：

```text
登记报告 → 抽取披露记录（带口径字段）→ 生成候选关系 → 确定性计算
        → [可选] AI 语义提案 → 引用逐字校验 → 结论分层 → 人工复核 → 导出
```

## 4. 技术栈

- **后端**：Python 3.12、FastAPI、Uvicorn、Pydantic v2
- **数据**：SQLite（本地台账）、FAISS（本地向量索引）、JSON 合同文件
- **文档解析**：PyMuPDF（PDF 文本与页图）、python-docx、openpyxl
- **前端**：原生 HTML/CSS/JS，无构建步骤
- **模型**：任何 OpenAI 兼容接口（默认 DeepSeek 官方直连），**可完全关闭**
- **测试**：pytest（79 个测试文件）、Node 内置测试运行器

## 5. 快速开始

### 环境要求

- Python **3.12**（CI 与本次验收实测版本；更低版本未验证）
- 无需 Node.js 即可运行主程序

### 安装与启动

```bash
git clone https://github.com/StyXander/system.git
cd system

python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

python -m pip install -r requirements.txt
cp .env.example .env            # Windows: copy .env.example .env

python -m backend.app.connectivity_bootstrap --allow-missing-sources
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。健康检查：<http://127.0.0.1:8000/api/health>。

> 不要直接双击 `index.html`。页面必须由 FastAPI 提供，否则接口全部 404。

### 不配置模型 Key 也能跑

`.env` 中的 `DEEPSEEK_API_KEY` 留空即可。如需**强制**不发起任何外部模型请求：

```bash
# macOS/Linux
export AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false
# Windows PowerShell
$env:AUDITTRACE_DEMO_USE_EXTERNAL_MODEL="false"
```

此时仍可完成抽取、候选生成、确定性计算与证据定位，只是没有 AI 语义提案。

### 关于年报 PDF

仓库**不提交**任何第三方报告全文（版权与体积原因，`.gitignore` 已阻止 `*.pdf` 入库）。但干净克隆**仍然可以完整复现**：

上面的 `connectivity_bootstrap --allow-missing-sources` 会按 `backend/connectivity_reports.json` 的登记，从白名单官方域名（巨潮 `static.cninfo.com.cn`、深交所 `disc.static.szse.cn`、或明确标注的新浪公告镜像）下载已登记的 10 份报告，并逐份校验 SHA-256、页数与逐页解析结果。

- 官方来源不可达时返回 **503，不会用其他版本替代**，也不会用旧快照冒充本次下载；
- 登记地址不在白名单内的，直接拒绝获取，不做"尽力尝试"；
- 要新增企业，用 `scripts/register_connectivity_sources.py` 登记（同样要求白名单域名 + 固定哈希）。

## 6. 公开示例与演示

- **线上演示站**：<https://audittrace-demo.onrender.com>（Render 免费实例，冷启动约 15–60 秒；本次审查时 `/api/health` 与首页均返回 HTTP 200）。
- **本地无模型演示**：`python scripts/prepare_release_demo.py`（要求原件已缓存，不会把历史模型记录改写成本次调用）。
- **冻结合成对照**：`python scripts/eval_release_contract.py`（不联网、不调用模型）。

部署配置见 `render.yaml`；线上地址必须重新部署并通过真实 HTTP 验收后才可对外宣称可用。

## 7. 自动化测试

```bash
python -m pytest backend/tests/test_release_contract.py -q   # 快速契约，约 6 秒
python -m pytest -q                                          # 完整回归
node --test tests/frontend/connectivity-status.test.mjs      # 前端状态契约
```

**本仓库 `main` 分支（提交 `6abd3d7`）实测结果**：

| 项目 | 结果 |
|---|---|
| 快速契约测试 | 13 passed / 5.84s |
| 完整回归 | **906 passed, 29 skipped, 0 failed, 1 warning / 336.71s** |
| 前端状态契约 | 14 passed |

29 项 skipped **不是通过**，原因是缺少不随仓库分发的材料：标准股份年报全文、封存运行记录（`runtime/`）、内部签字原件。补齐后对应用例会自动恢复，未补齐前不得声称这些能力已复验。

CI 在 `.github/workflows/tests.yml` 中运行上述三组测试，采用 `permissions: contents: read`，且**不引用任何仓库 Secret**，因此外部 Fork 的 PR 不会获得凭据。

### 干净环境复现验收

上面三个数字是在开发机上跑出来的，还不足以证明"别人克隆下来也能跑"。因此在**全新目录 + 全新虚拟环境**里完整走了一遍：

```text
git clone → python -m venv .venv → pip install -r requirements.txt
         → connectivity_bootstrap --allow-missing-sources
         → uvicorn backend.app.main:app
```

实测结果：

| 检查项 | 结果 |
|---|---|
| 依赖安装（仅 `requirements.txt`） | 成功，PyMuPDF 1.28.2 / FastAPI 0.156.8 / faiss-cpu 1.15.1 |
| 报告引导 | 10/10 文档 `available`，自动下载并校验 SHA-256 |
| 服务启动 | `uvicorn` 启动后约 4 秒 `/api/health` 返回 200 |
| 首页 `/` | HTTP 200，72348 字节，标题「审迹智链 · 双报告关联核对」 |
| `/api/connectivity/readiness` | `ready: true`，逐份核验哈希、页数与逐页解析（如五粮液年报 141 页 / ESG 59 页） |
| 证据页 `/api/connectivity/sources/WLY_AR_2025/pages/7.png` | HTTP 200，195766 字节 `image/png` |
| 未建立会话时 `/api/connectivity/runs` | HTTP 409（按设计拒绝，不返回他人任务） |
| 未配置模型 Key 时 `/api/health` | `model_status: config_missing`，`deterministic_backup_available: true` |

**未配置模型 Key 不会导致服务不可用**，这是设计意图，也已被实测确认。

## 8. 能力边界与专业判断

这一节是项目的一部分，不是免责声明。

- **不做**：舞弊认定、重大错报认定、审计意见、鉴证结论、投资建议。
- **"数字相符"不等于"披露真实"**：只说明在给定精度和口径内两个数一致。
- **"依据不足"与"不可比"不等于"未发现问题"**：可能是数据缺失、口径不可达，也可能是确实存在披露问题。
- **多 Agent 并非已被证明优于单模型**：A1/A2/A3 三角色与单模型两条路径都已实现，但本项目的实测中**没有取得三角色稳定优于单模型的证据**，因此不以此作为卖点。
- **指标级统计边界大量不可达**：`scope_level` 为 `metric` 的细粒度边界在公开报告中经常无法确证，系统会保持 `unknown` 而不是猜测。
- **规则索引不等于准则原文**：`backend/app/connectivity_rule_basis.json` 的 15 条规则（CN/AS/ESG 编号）是对公开准则与指引的可追溯索引，无法回到权威原文的条款标为未核验。
- **模型可靠性不是主要风险**：逐字引用校验、无来源数字拦截、提示注入识别均已实现并有测试覆盖；主要限制来自**候选为空**时模型无题可答。

## 9. 仓库结构与历史材料

```text
backend/app/          FastAPI 应用、关联核对流水线、抽取、RAG、模型调用
backend/tests/        79 个测试文件（pytest）
assets/official-v4/   前端源码（工作台、结果页、样式、图标）
scripts/              验收、冻结、复算与部署脚本
docs/                 设计与验收记录、测试清单、历史交接材料
outputs/              历次运行产物与评估记录（历史证据）
决赛准备/              竞赛阶段的答辩材料与整改记录
archive/              早期历史归档
```

`决赛准备/` 与 `archive/` 是**竞赛阶段的历史材料**，保留用于溯源，不代表当前产品定位。当前定位以本 README 与 `docs/` 中的近期记录为准。较完整的本地启动与验收说明见 [README_RUN.md](README_RUN.md)，测试清单见 [docs/TEST_INVENTORY.md](docs/TEST_INVENTORY.md)。

**第三方材料边界**：根目录与 `决赛准备/` 中的 PDF 为公开披露的第三方报告，仅用于本地开发与受控技术复验，**不在本仓库的再分发范围内**。`.gitignore` 已阻止 `*.pdf` 入库。

## 10. 许可证与贡献

### 许可证

本项目以 **GNU Affero General Public License v3.0（AGPL-3.0）** 发布。

```text
Copyright (C) 2026 The AuditTrace Authors

本程序是自由软件：你可以依据自由软件基金会发布的 GNU Affero 通用公共许可证
第 3 版（或你选择的任何更新版本）条款重新分发和/或修改它。
本程序按「无任何担保」分发，详见 LICENSE。
```

完整条款见 [LICENSE](LICENSE)，授权范围与不覆盖的材料见 [PROJECT_LICENSE.md](PROJECT_LICENSE.md)。

**AGPL-3.0 的关键点，请在使用前确认你能接受：**

- 分发本项目或其衍生作品，必须以 AGPL-3.0 提供完整对应源码；
- **通过网络提供服务也触发源码提供义务**（第 13 条）。把修改版部署成对外服务，就要向使用者提供对应源码；
- 如果你的组织不允许 AGPL 类许可证，请不要直接使用本仓库代码。

**许可证不覆盖的部分**：第三方年报与 ESG 报告 PDF 全文不在授权范围内，仅可依原发布条款使用，`LICENSE` 不对其产生任何许可。

> 为什么是 AGPL 而不是 MIT：核心链路依赖 PyMuPDF（AGPL-3.0 / 商业双许可），被 8 个后端模块直接 `import`。在这条依赖不变的前提下，标 MIT 会与依赖冲突。若要改用宽松许可证，需要先把 PDF 处理层替换为 `pypdfium2` + `pdfplumber`。完整分析见 [docs/LICENSING_DECISION.md](docs/LICENSING_DECISION.md)。

### 贡献

- 贡献流程、代码风格与不得提交的内容：[CONTRIBUTING.md](CONTRIBUTING.md)
- 漏洞披露与安全边界：[SECURITY.md](SECURITY.md)
- 内容分级、安全审计与公开范围清单：[docs/OPEN_SOURCE_AUDIT.md](docs/OPEN_SOURCE_AUDIT.md)

提交 PR 前请至少跑通快速契约测试与完整回归。测试被跳过不等于通过。

> 提交贡献即表示你同意以 AGPL-3.0 授权你的贡献。本项目未采用 CLA。

---

*审迹智链 AuditTrace — 北京市大学生数智会计创新应用竞赛参赛项目。*
