# AI1 核心计算与表格引擎交接

- 日期：2026-10-19
- 角色：AI1（核心计算、PDF 表格、口径条件与确定性复算）
- 分支：`ai/audittrace-core`
- 基线：`origin/main` `541de1b fix(connectivity): search source excerpts and AI opinions`
- 实现提交：`278d63a feat(connectivity): layer scope precision and table evidence`
- 范围：问题 01、02、03、04、05、06、07、20、22；I1、I2、I4、I8 的指标字典侧
- 未改：`connectivity_pipeline.py`、`connectivity_intelligence.py`、`connectivity_api.py`、`connectivity_delivery.py`、`index.html`、前端 JS/CSS、PPT/方案书

## 1. 实际变更文件

| 文件 | 变更 |
|---|---|
| `backend/app/connectivity_schemas.py` | 新增报告边界、范围层级、币种/单位状态、显示精度、舍入方法、内容分类、指标身份、表格行/列身份、结论级别与表内结构字段；全部有默认值，旧 JSON 可读 |
| `backend/app/connectivity_extraction.py` | 表标题/上方短句继承；合并/母公司/分部边界；币种与单位来源；显示精度；宏观/行业背景排除；行名父级恢复；表格行/列角色与 table_id |
| `backend/app/connectivity_engine.py` | 数值/口径/解释分离；显示精度条件区间；合并/母公司及“一侧已知、一侧未证实”闸门；L0/L1/L2 结论级别；成员输入保留原始值、倍率、币种和显示精度 |
| `backend/app/connectivity_conditions.py` | 指标级范围与报告级/表内分组分离；表内结构证据只作 L1，不升级为 supported；直接范围来源可回查 |
| `backend/app/connectivity_rules.py` | 扩充排放、能源、用水首批别名；导出指标身份函数 |
| `backend/app/connectivity_metrics.py`（新增） | 指标身份字典、别名/反例、内容分类、币种识别 |
| `backend/app/connectivity_tables.py`（新增） | 独立表内组成候选生成器：合计行/列、跨行/跨列、可选跨表桥接 |
| `backend/tests/test_at_core_regressions.py`（新增） | 26 项 AI1 回归，覆盖 9 个问题编号与 I1/I2/I4 |
| `scripts/ai1_core_regression.py`（新增） | 5 对登记报告无模型复测脚本，生成真实统计与样例 |
| `docs/ai_handoff/ai1_core_regression_2026-10-19.json`（新增） | 新代码 5 对真实运行结果与分母 |
| `docs/ai_handoff/ai1_core_baseline_2026-10-19.json`（新增） | 同一批原件/缓存在 `origin/main` 旧代码上的前后对照 |

## 2. 数据合同（向后兼容）

### 2.1 `DisclosureOccurrence` 新增字段

> 以下为字段示意；`occurrence_id`、引文与 table_id 以本次 run JSON 的实际值为准，不把示例当运行证据。

```json
{
  "occurrence_id": "<实际 occurrence_id>",
  "report_boundary": "consolidated",
  "report_boundary_source_id": "<实际 occurrence_id>",
  "report_boundary_source_quote": "<逐字原文，如报表标题/单位行>",
  "scope": "合并",
  "scope_level": "report",
  "table_scope": "",
  "scope_source_id": "<实际 occurrence_id>",
  "scope_source_quote": "<逐字原文>",
  "currency": "CNY",
  "currency_status": "table",
  "currency_source_id": "<实际 occurrence_id>",
  "currency_source_quote": "<逐字原文>",
  "unit_status": "table",
  "unit_source_quote": "<逐字原文>",
  "display_precision": 2,
  "rounding_method": "unknown",
  "content_class": "company",
  "metric_id": "研发费用",
  "metric_identity": {
    "metric_id": "研发费用",
    "canonical": "研发费用",
    "topic": "research",
    "dimension": "money",
    "match": "exact",
    "equivalence": "exact",
    "modifier": "",
    "note": "研发费用是会计科目口径，不能自动替代研发投入"
  },
  "table_id": "<实际 table_id>",
  "row_index": 18,
  "column_index": 3,
  "row_role": "detail",
  "column_role": "period",
  "row_parent_label": ""
}
```

字段语义：

- `report_boundary`：`consolidated / parent / segment / unknown`，只表示报告/表所属边界。
- `scope_level`：`metric / table / report / unknown`。
  - 只有 `metric` 的 `scope` 可以作为指标级统计范围线索；
  - `table` 是钢铁/其他/合计等表内分组；
  - `report` 是合并/母公司等报告层覆盖，**不能替代指标级范围**。
- `currency_status / unit_status`：`explicit / table / report_declaration / assumed / unknown`；无来源不默认 CNY。
- `display_precision`：原文显示小数位；整数为 0，不扩成半个单位。
- `rounding_method`：`unknown / exact / half_up / truncate`，只有原文声明才非 unknown。
- `content_class`：`company / macro / industry / peer / background / unknown`；宏观/行业数值由提取器标 `uncertain` 并进入 `extraction_exclusions`。
- `metric_id / metric_identity`：首批研发、环保、温室气体、综合能源、年度总用水；别名只帮助召回，不证明等价。
- `table_id / row_index / column_index / row_role / column_role`：表内结构自证的坐标身份；旧运行没有这些字段时，`build_table_composition_candidates` 会跳过并提示重新提取。

### 2.2 `RelationshipCheck` 新增字段

```json
{
  "relationship_basis": "table_structure",
  "basis_level": "L1",
  "conclusion_level": "limited_support",
  "comparability": {
    "boundary": {"status": "different", "message": "合并报表与母公司报表属于不同口径，不能直接比较；不认定为企业披露错误"},
    "currency": {"status": "supported"},
    "period": {"status": "unknown", "years": ["2024"]},
    "explanation": {"status": "unsupported", "note": "解释待补依据；不改变数值差额与口径状态"},
    "conditions": {"范围": {"status": "unknown", "evidence_kind": "table_structure"}},
    "numeric": {"assumption_check": {"status": "contains_zero", "residual_interval": {"low": "-316182.505", "high": "683817.505"}}}
  },
  "table_structure": {
    "table_id": "<实际 table_id>",
    "layout": "column_sum",
    "total": {"occurrence_id": "<实际 occurrence_id>", "label": "环保资本化项目投入", "column_header": "2024 年 / 合计"},
    "components": [
      {"occurrence_id": "<实际 occurrence_id>", "label": "环保资本化项目投入", "column_header": "2024 年 / 钢铁"},
      {"occurrence_id": "<实际 occurrence_id>", "label": "环保资本化项目投入", "column_header": "2024 年 / 其他"}
    ],
    "coverage": {"component_count": 2, "total_equals_sum": true, "sum_residual": "0.000"},
    "non_overlap": {"status": "structural_assumption"},
    "limitations": ["表内结构仅支持 L1 有限可比；指标定义、统计范围与期间仍需原文核实"]
  }
}
```

结论级别：

| `basis_level` | `conclusion_level` | 含义 |
|---|---|---|
| L2 | `formal_consistent` | 五项/组成/公式前提均有原文支持，数值正式一致 |
| L2 | `unexplained_difference` | 前提支持但仍有未解释差额；不是企业违规 |
| L1 | `limited_support` | 仅表级/结构证据支持有限比较 |
| L1 | `assumption_compatible` | 显示精度/有据调节假设下相容，不是正式结论 |
| L0 | `insufficient_basis` | 只有数值试算或连试算也不成立 |
| — | `not_applicable` | 叙述关系，无数值算子 |

`calculation` 内同步写入 `conclusion_level / basis_level / numeric_status`，降低 AI3/AI4 读取成本；旧字段 `calculation_status / criteria_status` 保持不变。

## 3. AI2 需要接的函数

### 3.1 表内组成候选

```python
from .connectivity_tables import build_table_composition_candidates

for extra in build_table_composition_candidates(run.occurrences, run.period):
    extra.check_id = f"CHECK-{len(checks)+1:04d}"
    checks.append(extra)
```

- 签名：`build_table_composition_candidates(occurrences, period, *, include_cross_table=False) -> list[RelationshipCheck]`
- 返回 `relationship_basis="table_structure"`、`check_id="TABLE-..."`、完整 `table_structure`。
- 只读取 `quality=="located"`、`content_class=="company"`、有 `table_id/row/column` 的单元格。
- 结构候选仍必须经过 `upgrade_conditions(check, run, period)` 和 `calculate(check, run.occurrences)`；**不能直接把结构候选写入企业异常、优先级或正式计数**。
- 当前只覆盖 `research/environment`（规则卡 RD-001/ENV-001）；排放、能源、用水没有组成规则卡，不能硬套。
- `include_cross_table=True` 只生成 L1 线索，`non_overlap.status="unknown"`；默认关闭。

### 3.2 指标身份

```python
from .connectivity_metrics import metric_identity, content_classification

metric_identity("研发投入金额（亿元）")
# {"metric_id": "研发投入金额", "canonical": "研发投入金额", "topic": "research",
#  "dimension": "money", "match": "exact", "equivalence": "exact", "modifier": "", ...}

metric_identity("研发费用")["metric_id"]  # "研发费用"，不是"研发投入金额"
content_classification("我国粗钢产量", "2025年全国粗钢产量统计")  # ("macro", "...")
```

- 别名只作召回；`equivalence="limited"` 时仍须原文定义、范围、期间支持。
- 研发投入/研发费用、总量/强度、范围一/范围二、取水/用水不自动等同。
- AI2 在 `candidate_checks` 分组时可使用 `metric_id`，但不得把别名直接升级为 `text_statement`。

### 3.3 计算辅助函数

```python
from .connectivity_engine import (display_interval, display_precision_assumption,
    member_boundary, boundary_comparison, explanation_state)

display_interval(occurrence)                 # 单侧显示精度区间，整数返回 None
display_precision_assumption(check, rows)     # 双侧条件区间，不改正式差额
member_boundary(occurrence)                  # consolidated/parent/segment/unknown
boundary_comparison(check, rows)             # same/different/undetermined/unknown/not_applicable
explanation_state(check, rows)               # supported/unsupported/not_provided
```

AI2 在候选生成前应过滤：

- `row.content_class in {"macro","industry"}`；
- 报告边界 `boundary_comparison(...).status in {"different","undetermined"}` 的同值/比例候选；
- 无效行名（提取器已把 `quality` 降为 `uncertain`）。

AI2 不要修改 `connectivity_extraction.py / engine.py / conditions.py / schemas.py / rules.py / metrics.py / tables.py`；如需新增字段，在交接文档中列出并由 AI4 集成时统一处理。

## 4. AI3 展示语义

| 字段/状态 | 展示建议 |
|---|---|
| `report_boundary` | “合并报表 / 母公司报表 / 分部 / 未证实”；不要显示成指标统计范围 |
| `scope_level` | `metric` 才能作为范围依据；`report`/`table` 用灰色“报告级/表内分组，非指标级范围” |
| `table_scope` | “钢铁/其他/合计”等表内分组；参与组成关系时可显示，不得当作统计边界 |
| `conclusion_level` | 绿色仅 `formal_consistent`；`assumption_compatible`/`limited_support` 用琥珀色并带“假设/有限”；`insufficient_basis` 灰色；`unexplained_difference` 红色但注明“不是违规” |
| `assumption_check` | 显示区间、假设、限制；不得显示为“程序已给正式区间” |
| `boundary.status` | `different` / `undetermined` 灰色“不可直接比较”；不要显示“企业披露错误” |
| `explanation.status` | `unsupported` 单独标“解释待补”；不得改写数值差额或口径状态 |
| `display_precision` | “显示 2 位” |
| `rounding_method` | `unknown` 显示“舍入方法未声明”，不得显示“已按四舍五入” |
| `content_class` | `macro/industry` 放“已排除背景”，不能进入企业异常列表 |
| `table_structure` | 显示 total/components/coverage/non_overlap/limitations；`limited_support` 不显示为正式一致 |

AI3 不得用 `criteria_status` 单独决定颜色；以 `conclusion_level` 和 `basis_level` 为准。旧数据没有这些字段时显示“—/历史结果未分级”，不要回填推断。

## 5. AI4 导出与统计

建议 Word/JSON 增加：

- occurrence 级：`report_boundary`、`scope_level`、`table_scope`、`currency_status`、`unit_status`、`display_precision`、`rounding_method`、`content_class`、`metric_id`、`row_role/column_role`、`table_id`。
- check 级：`basis_level`、`conclusion_level`、`comparability`、`table_structure`、`calculation.assumption_check`。
- 统计拆分（禁止混合单位/分母）：
  - `formal_calculations`：`calculation.residual is not None`；
  - `formal_consistent`：`basis_level=="L2" and conclusion_level=="formal_consistent"`；
  - `assumption_compatible` / `limited_support`：L1，不得并入“正式一致”；
  - `insufficient_basis`：L0；
  - `unexplained_difference`：前提支持但差额未解释；
  - `boundary_blocked`：`comparability.boundary.status in {"different","undetermined"}`；
  - `table_structure_candidates`：结构候选数，不能当作企业异常数。
- Word 首屏按“可确认/有限支持/条件试算/不可比/待查”分段；显示真实 0，同时说明原因。
- 导出中保留 `assumption_check.limitations` 和 `table_structure.limitations`，不得只留一个“区间含 0”。

## 6. 测试与真实结果

### 6.1 自动测试

```bash
cd backend
DEEPSEEK_API_KEY= python -m pytest tests/test_at_core_regressions.py -q
# 26 passed

DEEPSEEK_API_KEY= python -m pytest \
  tests/test_connectivity_engine.py tests/test_connectivity_extraction.py \
  tests/test_connectivity_conditions_20261017.py tests/test_connectivity_direct_metrics.py \
  tests/test_connectivity_review_fixes.py tests/test_connectivity_review2_20261017.py \
  tests/test_connectivity_acceptance_fixes_20261017.py tests/test_connectivity_remediation_20261017.py \
  tests/test_connectivity_proposals.py tests/test_connectivity_hybrid.py \
  tests/test_connectivity_hybrid_upgrade.py tests/test_connectivity_reviews.py \
  tests/test_at_core_regressions.py -q --basetemp=tmp/pytest-ai1-final
# 144 passed, 1 warning；固定 basetemp 避免并发进程清理临时目录造成 FileNotFoundError

DEEPSEEK_API_KEY= python -m pytest \
  tests/test_finals_ab_20261012.py tests/test_finals_remediation.py \
  tests/test_finals_support_boundaries.py tests/test_at_core_regressions.py -q \
  --basetemp=tmp/pytest-ai1-finals
# 56 passed, 4 skipped（缺登记 PDF 原件全文的既有跳过）
```

### 6.2 五对登记报告无模型复测

```bash
cd <repo>
DEEPSEEK_API_KEY= python scripts/ai1_core_regression.py
# 输出：docs/ai_handoff/ai1_core_regression_2026-10-19.json
```

同一批原件与解析缓存，旧代码基线：`ai1_core_baseline_2026-10-19.json`。

| 报告对 | 旧：occurrences / checks / 正式 | 新：occurrences / checks / 正式 | 旧 scope 非空 | 新 scope 非空（report/table/metric） | 旧 money 币种已知 | 新 money 币种已知 | 新表内候选 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 五粮液 2025 | 217 / 8 / 0 | 225 / 8 / 0 | 0/217 | 10/225（10/0/0） | 35/93 | 36/90 | 0 |
| 美的 2025 | 305 / 4 / 0 | 317 / 4 / 0 | 0/305 | 20/317（20/0/0） | 149/194 | 149/194 | 0 |
| 宁德时代 2025 | 246 / 7 / 0 | 243 / 7 / 0 | 0/246 | 32/243（32/0/0） | 2/49 | 2/42 | 0 |
| 宝钢 2025 | 614 / 9 / 0 | 691 / 14 / 0 | 15/614 | 92/691（66/26/0） | 379/381 | 354/354 | 0 |
| 宝钢 2024 | 618 / 11 / 0 | 708 / 15 / 0 | 33/618 | 132/708（75/57/0） | 370/370 | 363/363 | 1 |

说明：

- **正式结论仍为 0**。这不是回退，而是没有为了演示放松范围、定义、期间和币种门禁；旧代码同样为 0。
- 新代码的 3 条 `assumption_compatible`（L0）来自五粮液 2 条、宁德时代 1 条；1 条 `limited_support`（L1）来自宝钢 2024 表内组成。
- 新 `scope` 非空来自报告/表级继承；**指标级 `scope_metric` 在 5 对中仍为 0**。五粮液 AR/ESG 原件中没有“研发投入统计范围/合并范围”这类指标级原句，未把报告边界冒充指标范围。01 的字段分层已实现，L2 指标级范围仍缺原文证据。
- 新代码 occurrence 数变化来自表内行/列身份和行名恢复；前后分母不同，不能把绝对数直接当作召回率。
- 五粮液 money 币种 36/90：其余 54 处金额上下文没有明确人民币/币种声明；未用“元”字推定。
- 宁德时代 money 币种仅 2/42：原件未提供可回查的报告级人民币声明；保留 unknown，不默认 CNY。
- 宝钢 money 币种 354/354、363/363：表标题/报告声明已继承。
- 实时抽取的 `rounding_method` 基本为 unknown（五对中仅宁德时代 1 处 half_up）；没有从显示位数推定舍入方法。

门禁原因（检查项数，非互斥）：五粮液 范围 8、主体 5、定义 4、期间 2、单位 1、关系依据 1；美的 范围 4、主体 4、单位 3、关系依据 2、定义 2、期间 2；宁德 范围 7、主体 5、定义 4、关系依据 3、期间 1、单位 1；宝钢 2025 范围 14、主体 14、关系依据 13、期间 1、单位 1；宝钢 2024 范围 15、主体 15、关系依据 15。

### 6.3 关键真实样例

**五粮液 449,183,817.50 元 vs 4.49 亿元**

- 左：`WLY_AR_2025-56-T0-R18-C3`，第 56 页，`located`，合并边界，单位元，显示 2 位；
- 右：`WLY_ESG_2025-54-T3-R2-C4`，第 54 页，`located`，单位亿元，显示 2 位；
- 差额：`183817.50` 元；
- 显示精度条件区间：`[-316182.505, 683817.505]`，含 0；
- 结论：`assumption_compatible` / L0 / `not_comparable`；正式残差为 `null`；
- 限制：未确认企业实际舍入方法；报告边界/指标范围/定义仍未齐备，**不宣称正式一致或业务可比**。

**宝钢 2024 合并/母公司**

- 母公司：`BAO24_AR-120-T0-R6-C2`，第 120 页，`1,249,616,010.99` 元，`report_boundary=parent`；
- 合并：`BAO24_AR-118-T0-R12-C2`，第 118 页，`3,779,320,686.31` 元，`report_boundary=consolidated`；
- 两者直接比较：`not_comparable`，`boundary.status=different`，提示“合并报表与母公司报表属于不同口径，不能直接比较；不认定为企业披露错误”；
- 母公司 vs ESG 37.79 亿元：`boundary.status=undetermined`，提示“一侧为母公司报表口径，另一侧报告边界未证实；不能直接比较”；
- 两种探针的正式残差均为 `null`，不再把两数当未解释差额。

**宝钢 2024 表内结构**

- `TABLE-22829D2F56`，ENV-001，`column_sum`；
- 合计列 `2024 年 / 合计`，分项列 `2024 年 / 钢铁`、`2024 年 / 其他`；
- `coverage.component_count=2`，`total_equals_sum=true`，`sum_residual=0.000`；
- 结论 `limited_support` / L1；正式残差 `null`，条件试算残差 `0`；
- 结构只支持 L1，指标定义、统计范围与期间仍需原文，未升级为正式一致。

**0.66% 列义**

- 五粮液 `WLY_AR_2025-17-13-2`：`0.66`、单位 `%`、年度为空、`quality=uncertain`；
- 不再作为年度绝对值进入候选；这是 09 的证据基础，AI2 仍需在 claim 层继续校验。

**宏观/行业排除**

- 五粮液 1 处 macro、宁德 2 处 macro、宝钢 2024 1 处 industry + 1 处 macro 被标 `uncertain` 并进入 `extraction_exclusions`；
- 宝钢“公司粗钢产量”仍为 `company/located`，未因关键词误删。

## 7. 当前阻断与未验证

1. **指标级范围（01 的 L2）**：5 对报告中没有可回查的指标级统计范围原句；`scope_metric=0`。报告/表级 scope 已填充，但未冒充指标级。需要补充报告脚注/定义页或人工标注后才能升级。
2. **币种（02）**：宁德时代等报告没有明确报告级人民币声明；money 币种 2/42，保持 unknown。不能用“元”字推定 CNY。
3. **舍入方法（03）**：原件几乎不声明舍入方法；`rounding_method` 仅 1 处 half_up。显示精度区间只作 L0，不升级正式。
4. **表内组成（22）**：五对中只找到 1 条高置信结构候选（宝钢 2024 钢铁+其他=合计），五粮液 0；跨表桥接未在真实数据中启用。排放/能源/用水没有 RD/ENV 规则卡，不能硬套组成关系。
5. **指标覆盖（20）**：新增字典覆盖研发、环保、温室气体、综合能源、年度总用水；实际 `metric_id` 覆盖率为 35.65%–64.2%（按报告对），不代表全指标平台。
6. **模型侧未验证**：本次只做无模型复算；AI opinion/claim ledger、检索、反证、导出与前端展示由 AI2/AI3/AI4 完成。所有 L0/L1 结果不得被模型意见覆盖。
7. **本地主工作区未提交改动**：主工作区 `审迹智链系统` 仍有用户/前序会话未提交的 `connectivity_engine.py`、`connectivity_extraction.py`、`connectivity_schemas.py`、`connectivity_pipeline.py`、`connectivity_delivery.py`、`tests/test_connectivity_engine.py`、`assets/official-v4/connectivity.js`、`index.html` 等改动。本分支从 `origin/main` 独立建立，未覆盖它们；AI4 合并时必须逐项对比，不能直接丢弃。

## 8. 结论

AI1 交付的是可复核的数据事实与门禁，不是“正式结论数量”。本次真实 5 对复测仍为 0 正式，但：

- 字段分层和来源链已落地；
- 五粮液 449,183,817.50 vs 4.49 亿元可复算出 183,817.50 元差额与条件区间；
- 宝钢合并/母公司不再被当作未解释差额；
- 宝钢 2024 找到 1 条钢铁+其他=合计的表内结构候选（L1）；
- 0.66% 错列 / 宏观排除 / 无效行名有回归覆盖；
- 所有未达标项均按真实数据阻断记录，没有伪造达成指标。
