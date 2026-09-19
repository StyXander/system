# W24 · 浏览器验收记录（轨 C）

- 日期：2026-09-19　执行轨：轨 C（前端与核验）
- 前端代码：工作副本 `HEAD = e17e007` 之上的轨 C 未提交改动
  （`assets/official-v4/demo-app.js?v=0.10.24`、`styles.css?v=0.13.14`、`index.html`）
- 浏览器：系统已装 **Google Chrome**（Playwright `channel="chrome"`，本机未下载 headless shell）
- 后端：**两个真实 FastAPI 实例**
  - `127.0.0.1:8000`：开工前已在运行的本机实例（模型可用）。本验收对它**只发 GET**
    （`/api/health`、`/api/status`、`/api/demo/bootstrap`、`/api/demo/runs/<id>`），未创建任何任务。
  - `127.0.0.1:8010`：本轨为验收新起，`DEEPSEEK_API_KEY=""` + `AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false`
    + `AUDITTRACE_PROVIDER_PROBE_ENABLED=false`（三重关闭外部调用），`AUDITTRACE_DEMO_MODE=true`。
- **付费模型调用：0 次。** 全部状态由"读取已完成任务台账"与"确定性备用/模型关闭下的真实运行"产生。

## 一、状态覆盖与判据

| 状态 | 达成方式 | 真实 run / task | 结果 |
| --- | --- | --- | --- |
| `success` | 8000 刷新恢复已完成任务 | `DEMO-RUN-66A1B0E52840` / `RUN-V7-BF8D84368D35`（`complete_full_analysis`、`external_live`、3 次调用） | 通过 |
| `incomplete_numeric_claims`（W09 主角） | 8000 刷新恢复 | `DEMO-RUN-F1330AD8EA8B` / `RUN-V7-43AD8C03C3A7` | 通过 |
| `model_failed`（degraded 另一分支） | 8010 刷新恢复 | `DEMO-RUN-33AA25E68BD8` / `RUN-V7-76F994239DE1`（`MODEL_OUTPUT_INVALID`） | 通过 |
| `deterministic_backup` | 8010 现场点「启动确定性备用演示」 | `DEMO-BACKUP-7FB11774EDE5` / `RUN-V7-1FF5B1149044`（0 次调用） | 通过 |
| `data_gap + 抽取诊断`（W16） | 8010 现场点主按钮（模型关闭 → 确定性收口） | `DEMO-RUN-DEA400380695` / `RUN-V7-9791368F7D4D`（R1 `DATA_GAP`） | 通过 |
| **`cache_replay`** | **未达成** | — | **未实测，见第四节** |

四视口：`1440×1000`、`1024×768`、`768×1024`、`390×844`。上表 5 个状态 × 4 视口 = 20 组，逐组实测。

## 二、逐组检查结果（20/20）

| 检查项 | 结果 |
| --- | --- |
| 控制台未捕获异常 / console.error | **0 条**（5 状态 × 4 视口全部为空数组，见 `acceptance.json`、`review-index.json`） |
| 失败网络请求（`requestfailed` 与 HTTP ≥ 400） | **0 条**；所有 `/api/*` 均 200/202 |
| 横向溢出 `scrollWidth - clientWidth` | **全部 0**（含 390×844） |
| 原文证据抽屉可打开 | 通过：12—13 条证据条目 |
| Agent 抽屉可打开且与内联卡同源 | 通过：3 张角色卡 |
| 键盘可达 / 焦点可见 | 通过：Tab 两次后焦点在具名按钮，`outline: 2px` |
| `prefers-reduced-motion: reduce` | 通过：`.demo-stage` 过渡由 `0.24s` 降为 `1e-05s`（动效实际关闭） |
| 文案与技术状态一致 | 逐条核对见下 |

### 关键文案实测（真实渲染，非推断）

- W09 闸门态横幅：**「真实模型分析已完成，但未通过数字可追溯闸门」** +
  「本次已完成 **3 次真实模型调用**、**3/3 角色**结构化输出通过 evidence_id 与禁用词校验；但 AI 草稿中有 **1 个**关键财务数字无法追溯到已登记来源…未通过数字：**41,813,685.32**。确定性计算结果仍可查看。」
  —— 与该 run 的 `provider_call_count=3`、三角色 `completed`、`numeric_claim_trace.key_unverified` 逐项一致；
  旧的假话「没有可核验的调用留痕」已不再出现。状态条为「闸门拒绝发布完整结果 · 已完成 3 次真实模型调用」，未显示为 success。
- W12 三态徽标实测文本：`运行来源：本次真实模型运行 · 3 次调用` / `运行来源：确定性备用链 · 未调用外部模型` /
  `运行来源：模型输出校验失败 · 仅保留已完成程序结果`；另有 `data-mode` 与图形前缀（●/▣/◇/□），不靠颜色单独编码。
- W10：`success` 态总览结论实测为**「需执行额外程序后判断」**（改前会被坍缩成"现有资料不足"）。
- W13：六区在 4 视口下均非空（`zones = [2,1,1,4,1,3]`），②区 `unverified_hypothesis` 渲染为**「待验证解释」**、
  ⑥区在轨 A 字段已挂载的运行上显示**「G 暂不分级（资料或口径受限）」+「E3 未闭合」+「未评价金额重要性」**，
  边界句逐字出现；在字段尚未挂载的历史 run 上如实显示「未提供 · 后端 planning_priority 尚未挂载」。
- W16：长江电力实测显示**「自动抽取字段待人工回页确认，暂不评级」**并逐条列出诊断原文
  （含「同字段连续年度金额相差 1450369507.8 倍…」「自动提取金额的原始值仅为 6元…」），
  与泛化"资料不足"文案区分；`blocked_candidate_count=6` 同步透传。
- 命名红线：`document.body.textContent` 中不含「无风险 / 风险评级 / 信用等级 / 企业风险等级」。

## 三、验收中发现并修复的两个真实缺陷

1. **窄屏结果区被压成 30px（既有缺陷，非本轮引入）**
   `styles.css:5779` 的 `.demo-analysis-layout { grid-template-columns: minmax(0,65fr) minmax(300px,35fr); }`
   在源码顺序上晚于 `@media (max-width:1024px){ … grid-template-columns: 1fr }`（原 4596 行），
   同特异度下后者被覆盖 → 390px 时主列实测仅 **30px 宽**（审计关注卡 30×16436、总览卡 32px、30 秒证据挑战 38px），
   整个结果区在手机端不可读。修复：给该规则加 `@media (min-width: 1025px)` 条件，保留桌面 65:35 意图。
   修复后实测主列宽：390→280px、768→618px、1024→858px、1440→786px，四档均无横向溢出。
   证据：`review/*__mobile__attentioncard.png`（修复前该元素截图为 30×16436，已删除）。
2. **⑤ 区在总览无效时为空**
   `deriveAttentionCard` 原先只取 `overview.procedures`，而总览 `valid=false`（如闸门拒绝、仅计算预检）时该数组为空，
   但同一 run 的 `context.audit_procedures` 实际登记了 AP-01…AP-06 共 6 条。
   修复：无效时如实退回"本次运行登记的程序映射"，并加一行边界说明
   「本次未形成有效结论，以下只是本次运行登记的程序映射，不代表系统已选定追加程序。」

另把证据回链字号从 9.5px 提到 10.5px（移动端可读性）。

## 四、未达成项与原因

- **`cache_replay` 态未实测。** 本机不成立：`_replay_remote_cache_payload`（`main.py:1858-1920`）要求
  Supabase 缓存行 + `human_review.reviewer_type=="human"` + `export_approved`，本机未启用 Supabase，
  且 `/api/demo/bootstrap` 的 `task_continuity` 走本地文件台账。前端 `executionBadgeForRun` 的
  cache_replay 分支已由合同测试断言文案（`已验证历史结果回放 · 本次新增 0 次调用`），
  但**"真实浏览器 + 真实后端"这一条对该状态尚未满足，不得计入通过**。
  需要：启用 Supabase 的实例，或队长指定的经批准回放通道。
- **`success` 态用的是今日 13:24 的历史真实 live run**（轨 A 的 W01 闸门修复之后未再产生新的 live 运行）。
  它验证的是渲染通路，不验证"当前 HEAD 能否再次成功"——那属 W21/W23，需队长授权付费调用。

## 五、本目录文件

- `w24_browser_acceptance.py` — 5 状态 × 4 视口主验收（可重跑）
- `acceptance.json` — 逐视口检查值、控制台/网络记录、`/api` 调用清单
- `w24_probe_copy_and_motion.py` + `probe.json` — 文案与 reduced-motion 专项探针
- `w24_review_shots.py` + `review/`（40 张）+ `review-index.json` — 目视复核截图（元素与首屏取景）
- `screenshots/` — 5 张桌面端整页截图（移动端整页高达 6 万像素，不可用于目视，已删除）
- `mock_run_w00_contract.json` 见 `../track-c-w13-mock-20260919/`

## 六、重跑命令

```bash
# 1) 模型硬关闭的验收实例（不会发起任何外部模型调用）
DEEPSEEK_API_KEY="" AUDITTRACE_DEMO_MODE=true \
AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false AUDITTRACE_PROVIDER_PROBE_ENABLED=false \
backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010

# 2) 主验收 / 文案探针 / 复核截图
DEEPSEEK_API_KEY="" backend/.venv/Scripts/python.exe -X utf8 outputs/track-c-w24-20260919/w24_browser_acceptance.py
DEEPSEEK_API_KEY="" backend/.venv/Scripts/python.exe -X utf8 outputs/track-c-w24-20260919/w24_probe_copy_and_motion.py
DEEPSEEK_API_KEY="" backend/.venv/Scripts/python.exe -X utf8 outputs/track-c-w24-20260919/w24_review_shots.py
```

## 七、验收期间由后端新建的文件（本轨未改写任何既有文件）

```
backend/runtime/runs/RUN-V7-1FF5B1149044.json   五粮液 确定性备用（含 planning_priority P2 / evidence_state E2）
backend/runtime/runs/RUN-V7-6D499B96BA72.json   五粮液 确定性备用
backend/runtime/runs/RUN-V7-0C30A9046093.json   五粮液 确定性备用
backend/runtime/runs/RUN-V7-9791368F7D4D.json   长江电力 DATA_GAP（W16 证据）
runtime/demo-run-tasks/DEMO-RUN-DEA400380695.json
runtime/demo-backup-tasks/DEMO-BACKUP-{7FB11774EDE5,91B45422486A,D6C83E66F71D}.json
```

`backend/runtime/runs/` 下 2342 个历史 run、`competition_demo_cases.json`、`release_records/` 均未改动；
8000 端口上队长的实例未被写入。
