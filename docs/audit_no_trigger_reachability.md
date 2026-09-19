# W11 · `no_trigger_confirmed` 可达性审计（只读）

- 日期：2026-09-19　执行轨：轨 C（前端与核验）
- 代码状态：工作副本 `HEAD = e17e007`（分支名实测为 `main`，见"边界"一节）
- 性质：**纯只读审计**。未修改任何代码、未改写任何 run、未为了让该结论出现而伪造结果。
- 问题来源：全库 2342 次运行中 `no_trigger_confirmed` 出现 **0 次**，而 `additional_procedure_required` 出现 **107 次**。

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。

---

## 一、结论（一句话）

`no_trigger_confirmed` 在 schema、Agent 合同、前端三处都已备好接口，
**但在 `main.py` 的路由选择器上被结构性堵死：R1 每次返回 `RULE_NOT_TRIGGERED` 时，
它的 `risk_card.data_gaps` 恒含 4 条常设资料请求（`main.py:2371`），
而路由选择器把"任何非空 `risk_card.data_gaps`"判为证据缺口路线（`main.py:3135-3140`），
于是永远先落到 `evidence_gap_review`，`negative_confirmation` 分支不可能被选中。**

按方案 W11 的二分法，本次结论为 **(b) 应当可达**：三处接口都在等它，
只是 R2 没有这 4 条常设缺口、R1 有，导致唯一出口被自己写死。
**是否修、怎么修属队长决定（D6），本审计不实施。**

---

## 二、逐问回答

### Q1 `main.py` 的 `negative_confirmation` 分支何时才可达？

`_select_ai_analysis_route()`（`main.py:3124-3142`）四条按序判定，`negative_confirmation` 是第 4 条兜底，
必须同时满足：

1. **无任何** `result.status == "candidate"`（`main.py:3131-3132`）；
2. **无** `specialized_rule`，且 `industry_gate.fit_level` ∉ `{conditional, not_applicable, unknown}`（`3133-3134`）；
3. **每一条**规则结果都满足：`status != "DATA_GAP"` ∧ `source_validation.issues` 为空 ∧ `risk_card.data_gaps` 为空（`3135-3140`）；
4. 以上全部不成立时才 `return "negative_confirmation"`（`3142`）。

阻断点在第 3 条的最后一个析取项 `(result.risk_card or {}).get("data_gaps")`。
`_r1_result()` 的最后一个 return（`main.py:2344-2375`）对 `candidate` 与 `RULE_NOT_TRIGGERED`
**共用同一张卡片**，其中 `main.py:2371` 逐字写死：

```python
"data_gaps": ["账龄结构", "期后回款", "信用政策变动", "主要客户合同结算条款"],
```

也就是说：**只要 R1 完成了一次正常计算（无论触发与否），`risk_card.data_gaps` 必非空**，
路由必然停在 `evidence_gap_review`。对照 `R2`：其未触发卡片（`main.py:2485-2493`）**不含 `data_gaps` 键**，
所以 R2 单独不构成阻断——阻断是 R1 特有的。

其余分支同样不指向 `negative_confirmation`：
`SOURCE_INCOMPLETE`（`2224-2231`）带 `source_validation.issues` → 第 3 条命中；
字段缺失的 `DATA_GAP`（`2236-2254`、`2260-2274`）→ 第 3 条命中；
行业不适用/未知 → 第 2 条先行命中 `industry_review`。

### Q2 `agents.py` 是否允许该 route 产出 `no_trigger_confirmed`？

**允许，接口齐备**（`agents.py`，行号为当前 HEAD 实测）：

- `ROUTE_CONCLUSIONS["negative_confirmation"] = "no_trigger_confirmed"`（`146`）；
- `ROUTE_ALLOWED_CONCLUSIONS["negative_confirmation"] = ["no_trigger_confirmed", "additional_procedure_required"]`（`152`）；
- 该路线的角色状态白名单被收紧为 `challenge: ["defer"]`、`counter: ["defer"]`、`review: ["retain", "defer"]`（`111-117`）——
  即**走上这条路线后质疑/反证 Agent 不得再输出 `candidate`**；
- 复核角色任务描述逐字为「复核规则未触发结果，主动检查阈值边缘、异常趋势、漏判可能和原文中的反向迹象；不得把未触发改写成已触发。」（`227`）；
- 反证检索问题集 `negative_confirmation → RAG-Q1/Q2/Q5/Q6`（`anti_confirmation.py:20`、`main.py:3181`）；
- `schemas.py` 的 `analysis_conclusion` 五档枚举含 `no_trigger_confirmed`（`AgentOutput.analysis_conclusion`，当前 HEAD 位于 `schemas.py:178-184`）。

**注意副作用**：路线一旦翻转，同时改变三件事——Agent 提示词、角色状态白名单（challenge/counter 只能 `defer`）、
RAG 检索问题集。这不是"改个标签"，是切换到一条从未被任何一次运行走过的执行路径。

### Q3 前端 `routeFallbackAllowed` 是否把它挡掉？

**不挡。**（`assets/official-v4/demo-app.js`，当前 HEAD）

- `ROUTE_CONCLUSION_FALLBACKS.negative_confirmation = "no_trigger_confirmed"`（`demo-app.js:142-147`）；
- `routeFallbackAllowed`（`817-819`）在 `deterministicBackup ∥ modelStatus === "model_success" ∥ (not_applicable ∧ industry)` 时为真，
  `no_trigger_confirmed` 与其余三类享受同一条件，**没有被额外排除**；
- `explicitConclusion`（`809-815`）用 `AUDIT_OVERVIEW_META[value] || value === "additional_procedure_required"` 过滤，
  而 `AUDIT_OVERVIEW_META` 有 `no_trigger_confirmed` 条目（`115-120`，label「暂未发现需提升关注的程序信号，维持常规核查」），
  所以后端只要真的产出该结论，前端两条通路（显式结论 / 路线兜底）都能命中。

### Q4 `valid` 判定是否是第二道闸门？

**是，这是独立的第二道阻断，但它不是主因。**
`completeRuleChain`（`demo-app.js:834-837`）要求：有规则结果 ∧ 无 `source_validation.issues` ∧
`run_completeness` 不以 `incomplete` 开头 ∧ 有字段/检索/知识证据。
`valid`（`838`）再加 `outcome !== "failed_run"` 与结论在 META 中。

因此即便 Q1 的路由被打通，仍有一批运行会被 `valid` 挡下——见下节量化。

---

## 三、全库量化证据（2342 个 run，只读扫描）

**A. 路线分布（`ai_analysis_route`）**

| route | 次数 |
| --- | --- |
| `not_requested` | 1053 |
| `evidence_gap_review` | 488 |
| `industry_review` | 290 |
| `risk_candidate` | 111 |
| `None` | 400 |
| **`negative_confirmation`** | **0** |

**B. 结论分布（`ai_analysis_conclusion`）**：`None` 1507、`data_gap` 439、`industry_boundary` 179、
`additional_procedure_required` 107、`risk_candidate` 110、**`no_trigger_confirmed` 0**。

**C. 用当前 HEAD 的判定谓词逐条重放 2342 次运行**（非只看历史 route，而是拿本次代码重新算一遍）：
满足 `negative_confirmation` 条件的运行 **0 条**。即"按今天的代码重跑历史输入，也一次都到不了"。

**D. 归因**：R1 为 `RULE_NOT_TRIGGERED` 的运行共 **1197** 条，其中 **960** 条的 `risk_card.data_gaps` 非空。
按（行业 fit、是否专用规则、各规则 data_gaps 条数、source issues 条数）归因，Top 组合：

| fit_level | specialized | 各规则 data_gaps 条数 | source issues | 运行数 | 结果 route |
| --- | --- | --- | --- | --- | --- |
| `direct` | 否 | `(4,)` | `(0,)` | **590** | `evidence_gap_review`（被 R1 的 4 条常设缺口挡下） |
| `direct` | 否 | `(4, 0)` | `(0, 0)` | **213** | 同上 |
| `direct` | 是 | `(0,)` | `(0,)` | 124 | `industry_review`（第 2 条先行） |
| `direct` | 否 | `(4, 0)` | `(0, 1)` | 64 | `evidence_gap_review` |
| `not_applicable` | 是 | `(0,)` | `(0,)` | 61 | `industry_review` |
| `direct` | 否 | `(4, 1)` | `(0, 0)` | 52 | `evidence_gap_review` |

803 条（590+213）是"纯粹被 R1 常设 data_gaps 挡下"的量——**这就是 `negative_confirmation` 零次的直接机制**。

**E. 若删去路由第 3 条中的 `risk_card.data_gaps` 析取项，会有多少运行翻转到 `negative_confirmation`？**

- 会翻转：**858** 条；仍留在 `evidence_gap_review`（因真实 `DATA_GAP` 或来源校验问题）：**247** 条；
- 翻转集按完整性：`incomplete_calculation_only` 361、`complete_demo_fallback` 225、
  `incomplete_model_chain_failed` 76、`incomplete_persistence_unavailable` 54、
  `complete_public_prescreen` 42、`complete_full_analysis` 39；
- 案例集中度：`STD_DEV_T0` 370、其余分散在 12+ 个案例（最多 54）。

**含义**：翻转后真正能穿过前端 `valid`（Q4）显示"维持常规核查"的，只有完整性为 `complete_*`
且无来源问题、且有证据的那部分（粗估 ≤ 约 300 条，其中 `complete_public_prescreen` / `complete_full_analysis` 仅 81 条）。
**所以"修路由"只解决第一道阻断，不修完整性口径仍然看不到这个结论。**

---

## 四、交给队长的两个选项（本审计不实施）

### 选项 (a)：设计上不由 AI 宣称"未触发即维持常规程序"

- 口径：系统只在真实形成程序信号时才给结论，`no_trigger_confirmed` 保留为枚举但不追求可达；
- 前端要做（不依赖后端）：把 `evidence_gap_review` + R1 `RULE_NOT_TRIGGERED` 的组合显示为
  「当前规则未形成需提升关注的程序信号，维持常规审计程序」，并让 W10 的
  `additional_procedure_required` 承接"常设资料请求"这一层，避免它被读成"资料不足"；
- 代价：页面仍不出现 META 里那条 `no_trigger_confirmed` 文案，评委问"能不能说这家没问题"时，
  答案只能是"当前设计不出这个结论"；
- 禁止事项：任何情况下都不得写「无风险」「风险评级」（`AGENTS.md §3`、签字记录 D1 命名红线）。

### 选项 (b)：认定其应可达，批准最小修复（按侵入性从小到大三选一）

1. **最小、语义最准（推荐评估）**：`main.py:2371` 只在 `candidate` 为真时输出那 4 条常设 `data_gaps`；
   `RULE_NOT_TRIGGERED` 分支改为 `data_gaps: []`，常设清单继续由 `requested_materials`（`2372`）承载。
   影响面：R1 未触发的运行 route 由 `evidence_gap_review` 变 `negative_confirmation`；
   同时会改变这些运行的 Agent 提示词与角色状态白名单（见 Q2 副作用）。
2. **路由侧**：删除 `_select_ai_analysis_route` 第 3 条里的 `(result.risk_card or {}).get("data_gaps")` 析取项，
   只以 `status == "DATA_GAP"` 与 `source_validation.issues` 作为硬缺口依据。
   量化：858 条历史运行在新谓词下会翻route（见 E）。
3. **前端侧兜底（不改后端行为）**：把 R1 `RULE_NOT_TRIGGERED` ∧ 无硬缺口的组合在 `deriveAuditOverview`
   里显示为"维持常规审计程序"。**这只是呈现层，不使后端结论变为 `no_trigger_confirmed`，
   不能对外说"系统已能给出未触发结论"。**

三个选项都需：真实 run 复验 + `backend/tests/` 回归 + 若触 `schemas.py` 则 R1 signoff 继续 stale（D7）。
**共同代价**：这条路线在 2342 次运行中从未被走过，任何选择都等于首次启用一条新执行路径，
必须用真实 run（含模型调用）验收，需 D9 授权。

---

## 五、本审计的边界与未核验项

- 分支名实测为 `main`（`git rev-parse --abbrev-ref HEAD`），SHA `e17e007` 与回滚基线一致；
  方案假设的 `remediation-2026-09-19` 在本轨开工时不存在。轨 C 无权执行 `git checkout / switch / branch`（D-ISO 硬规则），
  故未自行建分支。
- run JSON 内无 `created_at` 字段，时间归因用文件 mtime，只称"文件时间"不称"运行时刻"。
- 未核验：`negative_confirmation` 路线的实际模型输出质量（0 条历史样本可查）；
  翻转后 `challenge/counter` 被限制为 `defer` 是否会让草稿失去内容——只能靠真实 run 验证。
- 未核验：`complete_demo_fallback`（225 条）走 `deterministic_backup` 时的 `valid` 通过率，
  需按 W24 逐状态实测，不在本审计范围。
- 本审计只读，未产生任何写入 `backend/` 的文件。

## 六、核验命令（可复跑）

```
# 路线/结论分布 + 用当前 HEAD 谓词重放 2342 次运行
backend/.venv/Scripts/python.exe -X utf8 -c "<见本文三节 A—E 的谓词重放脚本>"
```

重放脚本与本报告同批产出物：`outputs/blocked-field-verification-20260919-154427/verification.json`
（W17 语料扫描），两者使用同一 `backend/runtime/runs/` 只读目录。
