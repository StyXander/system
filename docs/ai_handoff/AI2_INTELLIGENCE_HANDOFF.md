# AI2 智能推理交接：关系校验、claim 账本与定向补证

日期：2026-10-19  
分支：`ai/audittrace-intelligence`（基于 `origin/main` = `541de1b`）  
实现提交：`61875e9`（本次交接文档另有一次文档提交）  
角色：AI2（关系发现、AI 推理、知识增强）  
边界：只修改 `backend/app/connectivity_pipeline.py`、`backend/app/connectivity_intelligence.py`，新增 `connectivity_claims.py`、`connectivity_retrieval.py`、`connectivity_rule_basis.json`、专项测试和本交接。未改 AI1 的 extraction/conditions/engine/schemas/rules，未改 AI3 的 HTML/CSS/JS，未改 AI4 的 API/交付/README/测试配置。

## 1. 结论先行

- 已实现并通过本地离线测试：错绑/角色/期间/量纲/主体/范围校验、0.66% 变动列识别、派生算式 Decimal 复算、同比幅度复算、竞争解释反证更新、定向检索去重、主题覆盖不足提示、规则依据索引、候选去重与 origin 标记、质量标签与 claim 支持状态分离。
- 未做真实模型复测：本次没有调用 DeepSeek，也没有产生费用。所有“模型意见”测试都是离线注入的 `AIAnalysis`；真实模型是否按新提示词改进，必须在 AI4 集成后按预算复测。
- 本分支没有修改 Schema。新增结构暂存在 `ConnectivityRun.intelligence_trace` 的 `dict` 条目中，保证旧数据可读、API 不因新增字段失败；AI1/AI4 合并时应按第 4 节提升为可选字段并加版本号。
- 真实缓存对照：五粮液 2025 由 8 条候选变 6 条；宝钢 2024 由 11 条变 5 条，新增 1 条列组成勾稽（4.835 = 4.34 + 0.495，残差 0）；宝钢 37.79 亿 vs 12.50 亿的 EQ 提案被拒。

## 2. 问题与实现对照

| 问题 | 实现位置 | 验收测试/证据 |
|---|---|---|
| 08 候选错绑、角色不全、期间/量纲/主体错误 | `connectivity_pipeline._proposal_problem`，在 `integrate_proposals` 入口逐条校验 | `test_wrong_metric_binding_is_rejected_before_result`、`test_incomplete_composition_roles_are_rejected`、`test_wrong_period_is_rejected` |
| 09 0.66% 变动比例被当年度值 | `connectivity_claims.classify_column_semantics`、`_column_claims`；`semantic_problem` 在提案入口拒绝变动列 | `test_change_ratio_column_cannot_be_used_as_annual_value`、`test_quoted_change_ratio_header_does_not_rescue_annual_misuse`；真实缓存评估 `claim_case` = contradicted |
| 10 派生数未绑定算式 | `connectivity_claims._formula_checks`，支持 `A÷B=C`、`C=A÷B`、“C 由 A÷B 得出” | `test_derived_formula_is_recomputed_and_wrong_input_is_rejected`；正确 26.12÷405.29=0.0644 通过，错误 22.86÷405.29=0.0644 被拒 |
| 21 非同名关系召回 | `_semantic_metric_candidates` + `METRIC_SYNONYMS`；只召回同量纲、同年、AR/ESG 各一处唯一的组合 | `test_non_identical_alias_mapping_recalls_but_expense_is_not_investment`；研发费用不会被并入研发投入 |
| 22 列合计/分项结构 | `_column_composition_candidates`：同一行不同列的“钢铁/其他/合计” | `test_column_composition_balances_and_stays_a_candidate`；真实宝钢 4.835 = 4.34 + 0.495 |
| 23 仅计算模式主题漂移、OCC 堆叠 | `candidate_checks` 增加 `topics` 过滤；宽泛营业收入不再单独成关系；子项 OCC 跳过；同概念 OCC 去重；覆盖不足写入 trace | `test_topic_filter_suppresses_revenue_only_relations`；真实五粮液仅剩 research EQ/INT，intensity/environment 标记覆盖不足 |
| 24 检索 query 过宽、重复 | `connectivity_retrieval.build_query_plan`：公司+期间+成员指标+同义词+缺口条件，支持/反证两路；全局 query 去重并记录共享 | `test_queries_are_metric_specific_and_deduplicated`；五粮液 8 条关系生成 54 个去重 query（共享 8 个） |
| 25 反证驱动解释更新 | `connectivity_claims.hypothesis_ledger`、`apply_hypothesis_updates`；A2/A3 后更新状态并写 trace | `test_counter_evidence_refutes_explanation_and_absence_is_not_verification` |
| 26 引用真实但语义不支持 | claim 账本新增 `causal_explanation`、`direction_claim`；只有引文含因果/范围说明才支持解释 | `test_quoted_change_ratio_header_does_not_rescue_annual_misuse`；因果不足只降为 insufficient_basis，不冒充已验证 |
| 27 文字同比只核方向 | `verify_narrative_magnitude`：解析 claimed_value/精密度，复算 10.8949%→10.89%，方向相反直接 contradicted | `test_narrative_magnitude_108949_and_reverse_direction` |
| 28 目标/结果、总量/强度混淆 | `verify_narrative_magnitude` 增加 `narrative_type`、`target_as_result`、`total_and_intensity_coexist` | `test_target_is_not_treated_as_achieved_result`、`test_total_up_and_intensity_down_are_not_contradictory` |
| 29 缺少具体下一步 | `build_next_evidence` 为每个未决条件给出材料位置、补证动作、升级路径、反证 query；`make_findings` 写入导出 | `test_next_evidence_has_material_and_upgrade_path` |
| 30 知识增强未接主链 | `connectivity_retrieval.rule_basis_for` 接入 A1/A2/A3 payload；`knowledge_enabled` 支持开关；`knowledge_ablation` 记录检索消融 | `test_rule_basis_never_fabricates_unverified_clause`；未做真实模型开/关效果实验 |
| 31 规则编号无定义 | `connectivity_rule_basis.json` 15 条，含内部名称、适用条件、反例、来源、核验状态 | 见第 6 节；未核验条目不允许引用具体条号 |
| 33 模型结果波动/重复 | `_member_key` 去重、`_stable_check_id` 稳定 ID、`candidate_origin` 标记 rule/model；同批重复拒绝 | `test_model_candidates_are_deduplicated_and_deterministic` |
| 34 quality 被当正确率 | `analysis_quality` 只表示论证完整度；claim 支持状态单独记账；0.66 错误直接拒绝 | `test_change_ratio_column_cannot_be_used_as_annual_value`；质量理由明确“不是正确概率” |

## 3. 修改文件

- 修改：`backend/app/connectivity_pipeline.py`（候选过滤、提案校验、检索接线、origin/去重、findings、知识消融）。
- 修改：`backend/app/connectivity_intelligence.py`（claim 账本接入 AI 意见、叙述幅度、反证更新、下一步具体化、质量标签）。
- 新增：`backend/app/connectivity_claims.py`（claim 账本、列语义、派生算式、叙述复算、补证动作、假设更新）。
- 新增：`backend/app/connectivity_retrieval.py`（定向 query、去重、支持/反证检索、规则依据、检索指标、消融）。
- 新增：`backend/app/connectivity_rule_basis.json`（15 条专业规则/来源索引）。
- 新增：`backend/tests/test_at_ai_regressions.py`（24 项专项回归）。
- 新增：`scripts/verify_ai2_offline.py`（真实缓存离线评估）。
- 新增：`docs/ai_handoff/AI2_offline_eval.json`（缓存评估产物）。
- 新增：`docs/ai_handoff/AI2_五粮液_calculation.json`、`docs/ai_handoff/AI2_midea_calculation.json`（真实 calculation_only 运行摘要，0 次模型调用）。

## 4. 新增数据结构（当前以 trace 存放）

### 4.1 claim 账本

`ConnectivityRun.intelligence_trace` 中 `kind="claim_ledger"`：

```json
{
  "kind": "claim_ledger",
  "role": "A3",
  "check_id": "CHECK-0004",
  "schema_version": "claim_ledger_v1",
  "support_status": "contradicted",
  "support_summary": {"supported": 2, "contradicted": 1, "insufficient_basis": 0, "not_verified": 0},
  "claims": [
    {
      "claim_id": "CLM-XXXXXXXXXX",
      "kind": "column_semantics",
      "token": "0.66%",
      "value": "0.66",
      "occurrence_id": "WLY_AR_2025-17-13-2",
      "indicator": "研发投入占营业收入比例",
      "year": "",
      "column_header": "2025 年 2024 年 变动比例",
      "column_semantics": "change_ratio",
      "support_status": "contradicted",
      "material": true,
      "reason": "明确把变动/同比列当作年度值使用"
    }
  ],
  "derived_checks": [
    {
      "formula": "26.12÷405.29",
      "inputs": [{"symbol": "a", "value": "26.12"}, {"symbol": "b", "value": "405.29"}],
      "claimed": "0.0644",
      "computed": "0.0644476794...",
      "computed_at_claim_precision": "0.0644",
      "matches": true,
      "status": "supported"
    }
  ],
  "narrative_test": {
    "status": "supported",
    "direction": "increase",
    "claimed_direction": "increase",
    "actual_change_percent": "10.894899...",
    "claimed_value": "10.89",
    "recomputed_value": "10.89",
    "magnitude_status": "supported"
  },
  "notes": ["引用逐字通过不等于业务含义成立", "未发现反证不等于解释已被证实"]
}
```

### 4.2 定向检索任务与指标

`intelligence_trace` 中 `kind="directed_retrieval"` 与 `kind="retrieval_metrics"`：

```json
{
  "kind": "directed_retrieval",
  "check_id": "CHECK-0003",
  "version": "connectivity_directed_retrieval_v1",
  "query_ids": ["Q-XXXXXXXXXX"],
  "queries": [
    {"query_id": "Q-XXXXXXXXXX", "kind": "support", "terms": ["研发投入金额", "统计范围", "合并报表范围"], "text": "五粮液 2025 研发投入金额 统计范围 合并报表范围", "condition": "范围"}
  ],
  "support_hits": 3,
  "counter_hits": 1,
  "new_evidence_ids": ["WLY_ESG_2025-33-SUP-12"],
  "coverage_note": "只搜索登记版本已解析文字；未命中不等于企业未披露"
}
```

```json
{
  "kind": "retrieval_metrics",
  "role": "A2",
  "round": 1,
  "checks_with_upgraded_conditions": 0,
  "upgraded_conditions": [],
  "supported_conditions_before": 12,
  "supported_conditions_after": 12,
  "new_evidence_used_in_upgrades": 0,
  "citations_checked": 0,
  "invalid_citations": 0,
  "erroneous_citation_rate": 0.0,
  "note": "升级只表示原文条件由 unknown/conflicting 变为 supported；不等于专业结论成立"
}
```

### 4.3 规则依据命中

`intelligence_trace` 中 `kind="rule_basis"`（由 `rule_basis_for` 返回，A1/A2/A3 payload 也会带）：

```json
{
  "basis_id": "CN04",
  "internal_name": "可比性与一致会计政策",
  "statement": "同一企业不同期间、不同企业相同期间的相同或相似项目，应在会计政策、指标定义和统计口径一致时才可直接比较；变更应有附注说明。",
  "source": {
    "publisher": "财政部",
    "title": "企业会计准则——基本准则",
    "document_no": "财政部令第33号（2014年修改）",
    "clause": "第十五条",
    "url": "http://czt.hunan.gov.cn/ztzl/kjxxw/zcfg_1/201408/t20140819_5060476.html",
    "locator": "第十五条（可比性）",
    "url_kind": "政府网站转载"
  },
  "conditions": ["期间", "定义", "范围", "单位"],
  "applicability": ["EQ-001", "RD-001", "ENV-001", "INT-001"],
  "verification_status": "verified_clause_secondary_url",
  "applicability_note": "检索命中仅表示条目相关；须由原文和本条关系条件确认适用"
}
```

### 4.4 假设账本与候选来源

```json
{
  "kind": "hypothesis_ledger",
  "check_id": "CHECK-0003",
  "hypotheses": [
    {
      "hypothesis_id": "H1",
      "testable_condition": "若为范围差异，应找到未纳入子公司的说明",
      "discriminating_evidence": "环保设备投入150万元，未说明是否已包含于环保治理投入",
      "status": "refuted",
      "before_status": "supported",
      "update_reason": "存在指向该解释不成立的原文/反证",
      "unverified_note": ""
    }
  ]
}
```

```json
{"kind": "candidate_origin", "check_id": "CHECK-0003", "origin": "rule", "rule_id": "EQ-001"}
{"kind": "candidate_origin", "check_id": "CHECK-8F3A2C1D09", "origin": "model", "rule_id": "NAR-001", "producer_role": "A1"}
{"kind": "candidate_dedupe", "rule_id": "EQ-001", "member_ids": ["A", "B"], "reason": "与已有确定性候选成员集合相同"}
```

### 4.5 主题覆盖不足

```json
{
  "kind": "topic_coverage",
  "topic": "intensity",
  "status": "insufficient_coverage",
  "located_rows": 49,
  "note": "本报告对当前事项覆盖不足；不从其他主题借关系凑数"
}
```

## 5. AI1 接入要求

AI1 合并后，pipeline 会优先调用以下可选钩子（不存在时使用本分支兜底）：

```python
# backend/app/connectivity_extraction.py（AI1 文件，AI2 不修改）
def classify_disclosure_scope(row: DisclosureOccurrence) -> str:
    """返回“合并”“母公司”或其他可读范围；无法判断返回空串。"""

def validate_row_identity(row: DisclosureOccurrence) -> bool | str:
    """True/空串表示可独立表达指标；False 或原因字符串表示应拒绝。"""

def is_macro_context(row: DisclosureOccurrence) -> bool | str:
    """True 或原因字符串表示宏观/行业统计，应排除。"""

def build_table_composition_candidates(run: ConnectivityRun, period: str) -> list[RelationshipCheck]:
    """高置信表内组成候选；也兼容 (rows, period, run) 签名。"""
```

必须保留/新增的 occurrence 字段（向后兼容默认值）：

- `scope`、`scope_source_id`、`scope_source_quote`：范围证据必须能回到表标题/表头。
- `currency_source_id`、`currency_source_quote`：币种必须能回到原文。
- `column_header` 中的多年度/变动列语义：本分支已通过 `classify_column_semantics` 兜底，但 AI1 最好在提取时直接标记 `column_semantics`。
- 列合计/分项候选：建议 AI1 在 `build_table_composition_candidates` 中返回 `relationship_basis="auto_label_match"` 或新增 `table_structure` 证据类型；不要把“刚好加平”写成条件已支持。

合并注意：

1. AI1 的 extraction 新增 scope/currency 字段后，`_proposed_problem`/`candidate_checks` 会自动使用；不要删除本分支的 `_ai1_scope` 兜底。
2. AI1 的 `build_table_composition_candidates` 若存在，会与 `_column_composition_candidates` 同时运行，`_member_key` 会去重；请确保两者成员集合一致时只保留一条。
3. 两份分支都改 `connectivity_pipeline.py` 时，以 AI2 的候选校验/检索接线为主，AI1 的 hooks 以函数形式接入，不要回退 `integrate_proposals` 的硬校验。
4. `run.intelligence_trace` 新增条目均为可选；旧运行 JSON 不含这些条目也能正常读取。

## 6. AI3/AI4 读取要求

### AI3 前端

- 结果页“AI 意见”旁必须分开展示：`run.intelligence_trace` 中 `claim_ledger.support_status`（supported/contradicted/insufficient_basis/not_verified），不要只显示 `analysis_quality`。
- `analysis_quality` 已改为“论证完整度”，不得显示为正确率或“高可靠”。0.66% 错误在 `integrate_analyses` 阶段被拒绝，不会进入正式意见；若历史任务仍有旧意见，UI 应显示“待重新分析”。
- `kind="scope_gate"` 或关系 `mapping_type="different_metric"` 时显示“不同口径，不直接比较”，不要显示为“未解释差异”。
- `kind="topic_coverage"` 显示“本报告对当前事项覆盖不足”，不要用其他主题关系凑数。
- 规则依据：`basis_id` 可点击；`verification_status` 为 `unverified` 时显示“未核验”，不得展示具体条号或“已符合准则”文案。
- 列组成候选显示“表内合计列与分项列（候选）”，并同时显示 `calculation_status="not_comparable"` 与假设残差 0；不要把试算 0 写成正式一致。
- 检索指标放在“运行记录/专业详情”抽屉，不要在首屏堆叠。

### AI4 导出与集成

- 导出 JSON/Word/CSV 时读取 `intelligence_trace` 的 `claim_ledger`、`rule_basis`、`retrieval_metrics`、`topic_coverage`、`scope_gate`、`hypothesis_ledger`；版本号写 `claim_ledger_v1`、`connectivity_rule_basis_v1`、`connectivity_directed_retrieval_v1`。
- 导出声明继续使用 `NOTICE`，不得把 claim 账本写成审计/鉴证结论。
- 固定任务需要重新生成：本分支改变了候选数量、ID 和排除日志（五粮液 8→6、宝钢 11→5），旧固定任务不能代表新逻辑。
- 63 项矩阵建议状态：08–10、21、23–31、33、34 标“已实现并离线验证”；真实模型复测、线上 E2E、人工确认仍为未完成/外部依赖，不能自动勾成“已验收”。

## 7. 规则依据索引核验状态

共 15 条。`verification_status` 的含义：

- `verified_clause_secondary_url`：条款文字在政府网站转载页核对，正式引用仍应回财政部原件。
- `verified_clause_primary_url`：财政部官网页面核对。
- `verified_url` / `verified_url_clause_unverified`：文件/URL 已核，具体条款号未逐条核对。
- `unverified`：只登记准则名称/适用边界，**禁止**在回答或界面补写条号/原文。

| basis_id | 内部名称 | 来源 | 状态 |
|---|---|---|---|
| CN01 | 会计主体与报告期间同一性 | 企业会计准则——基本准则 第五/十五条 | verified_clause_secondary_url |
| CN03 | 披露可验证性与可靠性 | 基本准则 第十二条 | verified_clause_secondary_url |
| CN04 | 可比性与一致会计政策 | 基本准则 第十五条 | verified_clause_secondary_url |
| CN05 | 实质重于形式 | 基本准则 第十六条 | verified_clause_secondary_url |
| CN06 | 重要性与披露完整性 | 基本准则 第十七条 | verified_clause_secondary_url |
| CN07 | 列报、合并范围与单位一致性 | 第30号、第33号 | **unverified**（未取得可核验原文链接，不写条号） |
| CN08 | 审计证据充分适当性 | 审计准则第1301号（2022应用指南） | verified_url |
| AS02 | 分析程序与异常波动 | 审计准则第1313号（财政部官网） | verified_clause_primary_url |
| AS04 | 职业怀疑与反证 | 审计准则第1301号应用指南（2022） | verified_url |
| ESG01 | 可持续披露主体/期间/范围 | 财政部《企业可持续披露准则——基本准则（试行）》财会〔2024〕17号 | verified_url_clause_unverified |
| ESG02 | 温室气体范围与强度分母 | GHG Protocol Corporate Standard / Scope 2 Guidance | verified_url_clause_unverified |
| ESG03 | 能源消耗与折标系数 | GRI 302；GB/T 2589 | **unverified**（GB/T 条款未核） |
| ESG04 | 取水/耗水/循环用水 | GRI 303 | **unverified**（条款未核） |
| ESG05 | 研发投入/费用/资本化 | 企业会计准则第6号——无形资产 | **unverified**（未取得可核验链接） |
| ESG06 | 重述、更正与版本 | 第28号、第30号 | **unverified**（未取得可核验链接） |

来源 URL 详见 `connectivity_rule_basis.json`。`ESG02` 的案例正是五粮液 22.86/26.12/405.29 的口径区分；本分支只做“不能混用”的约束，不宣称已确认企业实际折标系数。

## 8. 真实缓存评估

产物：`docs/ai_handoff/AI2_offline_eval.json`。  
数据：主工作区 `backend/runtime/connectivity/tasks` 中 2026-10-17 的五粮液/宝钢 calculation_only 运行缓存；不是新模型运行。

| 案例 | 旧候选 | 新候选 | 规则分布 | 关键结果 |
|---|---|---|---|---|
| 五粮液 2025 | 8 | 6 | EQ 3、OCC 1、INT 2 | 0.66% 变动列 claim = contradicted；intensity/environment 标记覆盖不足；无营业收入独立关系 |
| 宝钢 2024 | 11 | 5 | OCC 4、ENV 1 | 新增环保资本化列组成：4.835 = 4.34 + 0.495，残差 0；37.79 亿 vs 12.50 亿 EQ 提案被拒；6 条宏观、3 条无意义行名、24 条多年混列被记录排除 |

说明：

- 五粮液 0.66% 的 claim 账本使用**真实 occurrence** + 离线构造的 AIAnalysis（缓存没有 AI 意见），因此证明的是“账本会拒绝该列义”，不是“线上模型已经改好”。
- 宝钢 EQ 拒绝使用真实 occurrence 和 `_proposal_problem`；不是模型提案的真实输出。
- 列组成残差 0 只是假设试算；`calculation_status=not_comparable`，不能写成正式一致。

### 8.1 新代码真实 calculation_only 运行（0 次模型调用）

| 案例 | occurrences | 候选 | 规则分布 | 关键观察 |
|---|---|---|---|---|
| 五粮液 2025 | 217 | 6 | EQ 3、OCC 1、INT 2 | 0.66% 未进入任何成员；`449,183,817.50 − 4.49亿元 = 183,817.50` 只在假设试算；所有关系仍为 `not_comparable`，未越过范围门禁 |
| 美的 2025 | 305 | **0** | 无 | research 15 条 located、intensity 31 条 located，但没有形成跨报告同值/组成/比例关系；三个主题均输出“覆盖不足”。用 `topics=None` 重跑同样为 **0**，说明不是本次主题过滤误删，而是当前抽取结果没有可配对的跨报告关系 |

五粮液 6 条候选的表达式和状态保存在 `AI2_五粮液_calculation.json`。  
美的“0 条”是本次最重要的诚实结论：不能为了凑数把营业收入 OCC 当研发/环保关系；需要 AI1 继续修抽取/表格结构或人工确认可用的双报告指标。

## 9. 测试与复现

已运行：

```bash
DEEPSEEK_API_KEY= PYTHONPATH=backend ../审迹智链系统/backend/.venv/Scripts/python.exe -m pytest backend/tests/test_at_ai_regressions.py -q
# 24 passed

DEEPSEEK_API_KEY= PYTHONPATH=backend ../审迹智链系统/backend/.venv/Scripts/python.exe -m pytest \
  backend/tests/test_connectivity_acceptance_fixes_20261017.py \
  backend/tests/test_connectivity_conditions_20261017.py backend/tests/test_connectivity_direct_metrics.py \
  backend/tests/test_connectivity_engine.py backend/tests/test_connectivity_extraction.py \
  backend/tests/test_connectivity_hybrid.py backend/tests/test_connectivity_hybrid_upgrade.py \
  backend/tests/test_connectivity_proposals.py backend/tests/test_connectivity_remediation_20261017.py \
  backend/tests/test_connectivity_review2_20261017.py backend/tests/test_connectivity_review_fixes.py \
  backend/tests/test_connectivity_reviews.py backend/tests/test_at_ai_regressions.py -q
# 142 passed

PYTHONPATH=backend ../审迹智链系统/backend/.venv/Scripts/python.exe scripts/check_chinese_comments.py
# TOTAL 10.01%；PASS

PYTHONPATH=backend ../审迹智链系统/backend/.venv/Scripts/python.exe scripts/verify_ai2_offline.py
# 写出 docs/ai_handoff/AI2_offline_eval.json
```

全量 `pytest backend/tests`：

- 首次在干净 worktree 收集失败：`scripts/build_blind_submission_copy.py`、`scripts/prepare_full_corpus.py` 被 `.gitignore:71 /scripts/*` 忽略，干净分支没有这两个文件。已从主工作区复制（未提交，仍受忽略规则约束），随后重跑。
- 最终：**859 passed, 28 skipped, 8 failed（651.73s）**。
- 8 个失败：`test_batch4_persistence` 1、`test_competition_demo_plan` 1、`test_delivery_package_build` 2、`test_forensic_editorial_route` 2、`test_jack_case_package` 1、`test_release_gate_contracts` 1。均不涉及 connectivity/AI2 代码。
- 为排除本次改动影响，在 `origin/main` 的干净 worktree 重跑同样 8 项：**同样 8 failed, 3 passed**。因此这些失败是基线/环境/被忽略交付物问题，不是 AI2 引入。典型案例：`test_release_gate_contracts` 的 dashboard SHA-256 与登记不符；`test_forensic_editorial_route`/`test_delivery_package_build` 依赖未进干净分支的静态/交付物。

## 10. 已知限制与未验证项

1. **没有真实模型调用**：未验证 DeepSeek 在新增提示词/claim 约束下的实际输出质量；未做开/关知识的真实模型消融；未证明“减少错误率/提升召回率”的具体百分比。
2. **Schema 未提升**：claim 账本、规则依据、检索指标目前放在 `intelligence_trace`；AI1/AI4 合并时应加可选字段、版本化导出，并保留旧数据回退。不要直接删 trace。
3. **AI1 钩子未实际合入**：本分支的 `_ai1_scope`/`_row_identity_problem`/`_macro_reason` 是保守兜底；AI1 的显式 scope/currency/组成候选接入后，需要重新跑五粮液/宝钢/美的并检查字段兼容。
4. **规则来源不是全部已核**：CN07、ESG03–ESG06 标未核验；ESG01/ESG02 只核到文件/URL，未逐条核条款；回答中不得补写条号。
5. **宝钢范围判断是启发式**：37.79 vs 12.50 的拒绝依赖“同一报告存在与另一侧同值的同名披露”；若企业只披露一处或同名不同口径无同值锚点，仍可能漏检，需 AI1 的显式 scope 证据补充。
6. **主题过滤可能降低召回**：营业收入不再独立成 EQ/OCC；若需要“营业收入本身异常”的场景，应在后续单独增加规则，不能恢复成强度主题的默认关系。美的 2025 在 `topics=None` 时同样为 0 条，说明当前 0 条主要来自抽取没有跨报告可配对关系，不是过滤器单独造成；不能把“0 条”包装成“过滤有效”。
7. **OCC 仍然存在**：宝钢 5 条中 4 条是 OCC；已去重子项和同概念重复，但“多位置披露”本身不是异常，前端应放在“专业详情/待补证据”，不要放企业异常首屏。
8. **检索效果指标只统计条件升级**：`retrieval_effect` 的错误引用率分母只是本次升级条件所带引文；不是全量检索准确率。
9. **真实缓存是 2026-10-17 的 calculation_only**：不能代表当前分支新跑的任务；AI4 必须重新生成固定任务和 E2E 证据。

## 11. 合并检查清单（给 AI4）

- [ ] 合并 AI1 `ai/audittrace-core`：确认 `classify_disclosure_scope`、`validate_row_identity`、`is_macro_context`、`build_table_composition_candidates` 四个钩子存在；不存在时保留本分支兜底。
- [ ] 合并 AI3 `ai/audittrace-frontend`：前端读取 `intelligence_trace` 的新条目；不要把 `analysis_quality` 当正确率。
- [ ] 合并本分支 `ai/audittrace-intelligence`：解决 `connectivity_pipeline.py`/`connectivity_intelligence.py` 冲突时保留 `_proposal_problem`、claim 账本接入、定向检索和 origin/去重。
- [ ] 重新生成固定任务；用五粮液/宝钢/美的重跑 calculation_only，确认 0.66 不再是年度值、37.79/12.50 不再是 EQ 异常、列组成残差可回查。
- [ ] 在授权预算内跑一次真实模型任务；记录任务 ID、模型、token、耗时；没有这一步就写“真实模型未复测”。
- [ ] 更新 `docs/ai_handoff/63项最终验收矩阵.md`，把“已实现并离线验证”和“真实模型/E2E 未验证”分开。
- [ ] 导出 JSON/Word/CSV 增加 claim 账本与规则依据版本；确认声明仍逐字使用 `NOTICE`。
- [ ] 提交前扫描 `.env`、密钥、个人信息；不要把本次复制的忽略脚本提交进仓库。

## 12. 全量测试补记

- 全量：`859 passed, 28 skipped, 8 failed`，耗时 651.73s；8 个失败均可用干净 `origin/main` 复现（同样 8 failed），不属于 AI2 引入。
- connectivity + AI2 专项：`142 passed`；AI2 单独：`24 passed`；中文注释：`10.01% PASS`。
- 未测：真实模型调用、线上 E2E、人工双人标注、20 条人工解释错接纳率、5 名陌生用户任务测试。以上均不得写成已通过。

