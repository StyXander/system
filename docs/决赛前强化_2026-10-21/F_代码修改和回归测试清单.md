# 交付物 F：代码修改和回归测试清单

**分支**：`codex/finals-hardening-20261021`（基于 `origin/main` `6abd3d7`）
**位置**：`C:\Users\86135\Desktop\大学\大三上\数智竞赛\worktrees\hardening`
**未推送、未部署、未提交到生产分支。**

---

## 一、修改文件总表

| # | 文件 | 修改内容 | 对应问题 | 风险 |
|---|---|---|---|---|
| 1 | `backend/app/connectivity_extraction.py` | ① 年度列"槽位"绑定：数值多于年度列时不再绑定年度；坐标绑定后列头只记具体年度（合并表头另存追溯）。② 报告级币种声明扫描（`DOCUMENT_CURRENCY` + `_document_currency_declaration`），只认明确记账/列示句，状态 `report_declaration`。③ 指令性文本隔离（`INJECTION_PATTERN`），写入 `extraction_exclusions`。④ `_exclusions` 支持附加排除项。 | P0-2 / P0-3 / P0-5 | 中：抽取行为变化会影响所有真实报告；已用 5 对真实报告复验 |
| 2 | `backend/app/connectivity_pipeline.py` | ① 模型自封前提降级（`condition_demoted` 轨迹）。② `_identity_concept` 用于跨报告映射召回，`_semantic_concept` 保持原语义。③ 比例分子分母允许跨报告唯一取值。④ 跨报告同值关系按"受控身份字典 / 直接指标 / 自动配对"分级设置 `relationship_basis`。 | P0-1 / P1-8 / 能力强化 | 中：改变候选生成与条件整合 |
| 3 | `backend/app/connectivity_conditions.py` | ① 范围依据允许"AI 提出 + 程序逐成员复核"后采纳。② 定义句允许 6 字以内限定语。③ 组成关系允许"其中："行名。④ "互不重叠"依据在整段定义中定位。 | P1-7 / P1-8 | 低—中 |
| 4 | `backend/app/connectivity_engine.py` | ① 新增 `metric_identity` 关系依据分支（不整体否决，仍受五项前提约束）。② 调节项同一原文数值不得重复扣减。③ 比例显示精度判定舍入相容（仅 `ratio`）。 | P0-4 / P1-9 / 能力强化 | 中：涉及结论级别 |
| 5 | `backend/app/connectivity_schemas.py` | `relationship_basis` 增加 `metric_identity` 取值 | 支撑 #2/#4 | 低 |
| 6 | `backend/tests/test_finals_hardening_20261021.py` | 新增 8 项回归测试 | 覆盖 #1—#4 | 无 |
| 7 | `backend/tests/test_connectivity_review2_20261017.py` | ① 原"自动配对"用例改用未登记指标。② 新增"受控身份字典关系可确认"用例。 | 政策变更记录 | 无 |
| 8 | `tools/hardening/*.py` | 复现工具：5 对报告批量、对抗样本、币种统计、前后对照 | 证据可复现 | 无（不进入生产导入链） |

**未修改**：前端 `index.html`/`assets`、`main.py` 路由、部署配置、Supabase 台账、历史审计链。原因：本轮聚焦专业判定与证据层；前端"实时/历史"三态与冷启动提示不涉及专业结论，且无法在本机完成真实浏览器验收。

---

## 二、逐项验收标准与结果

| 验收项 | 方法 | 结果 |
|---|---|---|
| 多年度表头不再误杀 | `000333-2025` 纯规则运行 | 候选 **0 → 1**；拒绝 **41 → 20**；拒绝原因从 100% "多年度表头"降为混合原因 |
| 币种证据补齐 | `currency_stats.py` 全量 10 份报告 | 未知 **139/1043 (13.3%) → 8/1043 (0.77%)** |
| AI 自封前提被降级 | 对抗样本 C3（走 `integrate_proposals`） | 修改前 `unexplained_difference`（错误结论）→ 修改后 `insufficient_basis` |
| 同一原文不得重复扣减 | 新增单测 `test_same_source_cannot_be_deducted_twice` | 通过，第二条调节被拒并写明"重复扣减" |
| 比例舍入不误报 | 对抗 E1/E2 + 单测 `test_ratio_display_precision_is_not_a_difference` | 由"未建立关系"变为 `assumption_compatible`，金额同值关系口径不变 |
| 组成关系可确认 | 对抗 E3/E4 + 单测 `test_composition_accepts_qizhong_component_labels` | E3 `formal_consistent`，E4 `unexplained_difference` |
| 注入文本不进证据池 | 单测 `test_injection_text_is_detected`；`_exclusions` 支持附加项 | 通过（未用真实 PDF 端到端复验） |
| 原安全策略不回退 | `test_auto_pair_is_candidate_not_conclusion`（改为未登记指标）、`test_multi_location_basis_never_confirmed` | 通过 |
| 24 个对抗样本 | `adversarial_suite.py` 前后各跑一次 | **15/24 → 22/24**；剩余 G1/G2 为多位置政策所致 |
| 新增回归测试 | `pytest tests/test_finals_hardening_20261021.py` | **8 passed** |

---

## 三、测试命令与结果

```powershell
# 新增回归测试（8 项）
cd worktrees\hardening\backend
$env:PYTHONPATH = "..\..\..\worktrees\hardening\backend"   # 实际使用绝对路径
python -m pytest tests\test_finals_hardening_20261021.py -q -p no:cacheprovider --basetemp ..\tmp\pt-regression
# 结果：8 passed

# 关键既有用例（关系依据策略 + 引擎 + 条件补证）
python -m pytest tests\test_connectivity_review2_20261017.py tests\test_connectivity_engine.py `
  tests\test_connectivity_conditions_20261017.py tests\test_connectivity_hybrid.py tests\test_connectivity_hybrid_upgrade.py -q
# 结果：除 5 项环境性 ERROR 外全部通过（详见下）

# 全量套件（两棵树各跑一次，junit 输出）
python -m pytest tests -q --junitxml=..\outputs\hardening\junit_after2.xml
```

### 全量套件前后对照（junit XML 统计）

| 指标 | 基线 `origin/main` | 修改后 | 说明 |
|---|---|---|---|
| 用例总数 | 935 | **944**（935 + 9 新增/改写） | 新增 8 项机制回归 + 1 项政策用例 |
| 失败 failures | 6 | **6** | **失败集合逐项完全相同**（`failure_diff.txt`：only_after=[]、only_before=[]），均为网络/PDF 环境用例 |
| 错误 errors | **247** | **247** | **两棵树完全一致 → 环境性问题**（pytest 临时目录权限），与修改无关 |
| 跳过 skipped | 29 | 29 | 缺标准股份年报全文 |
| 通过 passed | 653 | **662** | 944−6−247−29 = 662（比基线多 9 项通过） |

> 复跑方法：本机沙箱会在 pytest 会话结束清理临时目录时抛 `PermissionError` 并挂起，因此加了一个本地插件 `tools/hardening/no_cleanup_plugin.py`（只把 `cleanup_dead_symlinks` 置空，不改任何用例逻辑），命令为
> `python -m pytest tests -q -p no:cacheprovider -p no_cleanup_plugin --basetemp ..\tmp\fin --junitxml=..\outputs\hardening\junit_final2.xml`。
> 上表数字取自 `junit_before.xml` 与 `junit_final2.xml`，不依赖终端输出。**247 个 error 是环境问题，不等于"全绿"**，对外只能报"失败集合与基线一致，新增用例全部通过"。

> **注**：本机沙箱对 pytest 创建的临时目录存在枚举权限问题，会话结束清理时会抛 `PermissionError`，导致终端汇总行可能被截断；上表数字取自 `--junitxml` 产物，不依赖终端输出。失败用例名已导出到 `outputs/hardening/junit_failures.txt`。**不得**把 247 个 error 说成"零失败全绿"。

---

## 四、回滚办法

**方案 A（推荐，最小影响）**：整个改动在独立 worktree/分支中，主工作区未动。

```powershell
cd "C:\Users\86135\Desktop\大学\大三上\数智竞赛\审迹智链系统"
git worktree remove "C:\Users\86135\Desktop\大学\大三上\数智竞赛\worktrees\hardening" --force
git branch -D codex/finals-hardening-20261021
```

**方案 B（只回退某个修复）**：文件级回退。

```powershell
cd worktrees\hardening
git checkout origin/main -- backend/app/connectivity_engine.py   # 例：只回退引擎改动
```

**方案 C（合并到主分支后回退）**：

```powershell
git revert <commit>     # 保留历史，可追溯
```

**注意**：`connectivity_schemas.py` 的 `metric_identity` 枚举与 `connectivity_engine.py`、`connectivity_pipeline.py` 必须同进退；单独回退其中一个会导致旧数据校验失败。

---

## 五、尚未解决的风险

| 风险 | 影响 | 建议 |
|---|---|---|
| 真实报告 formal=0 | 无法在真实案例上演示"确认差异" | 答辩改为演示"证据链 + 缺口"；不要伪造结论 |
| `multi_location` 永不确认 | 同报告前后不一致无法升级为结论（G1/G2） | 若决定放开，需同步修改 `test_multi_location_basis_never_confirmed` 并在答辩中说明政策变化 |
| 注入隔离未做真实 PDF 端到端验证 | 可能漏检变形注入 | 用一份真实报告副本插入注入句后再跑一次 |
| 全量套件 247 个环境性 error | 无法声称"全绿" | 在干净环境（非本机沙箱）重跑一次再对外报数 |
| 前端未改 | 实时/历史仍不可区分 | 答辩只演示当场新任务 |
| 未调用真实模型 | AI 层行为只做了静态与契约验证 | 有 Key 后跑一次三角色并保存原始 JSON |

---

## 六、合并到主分支的方法

```powershell
cd "C:\Users\86135\Desktop\大学\大三上\数智竞赛\审迹智链系统"
git fetch origin
git checkout -b finals-hardening origin/main          # 从线上同源开分支
git cherry-pick d1f035a                               # 应用本轮提交
# 或：git am < outputs\hardening\finals-hardening-20261021.patch
python -m pytest backend\tests -q                     # 在干净环境复跑
git push -u origin finals-hardening                   # 需要时再开 PR
```

> `审迹智链系统` 当前在 `codex/finals-evidence-decisions` 分支且有未提交的删除项；**不要**直接在该工作区 cherry-pick，先按上面命令从 `origin/main` 开新分支，避免把旧分支的差异带进来。

## 七、提交建议

1. 先在有网络的干净机器上重跑：`pytest tests -q`，确认 failures/errors 数量与基线一致。
2. 把 `tools/hardening/` 与 `docs/决赛前强化_2026-10-21/` 一起提交，证据与代码同源。
3. 提交信息建议：`fix(connectivity): bind year columns, recognise report-level currency, demote AI-asserted premises`
4. **不要**在未复验的情况下直接部署到 Render。
