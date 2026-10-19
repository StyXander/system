# AI3 前端交接说明（工作台 / 结果页 / UX）

> 分支：`ai/audittrace-frontend`（独立 worktree `audittrace-frontend`）
> 基线：`541de1b` + 主工作区已有的未提交前端改动（`index.html`、`connectivity.js`）
> 本次提交：`5576171`（前端代码与测试）、`af959c4`（交接文档与截图）
> 自测时间：2026-10-19；本地 `uvicorn 127.0.0.1:8011`，真实任务 `CONNJOB-D8796D38B3EC`（8 项关系）

---

## 一、改了什么（按文件）

| 文件 | 改动 | 未改动 |
|---|---|---|
| `assets/official-v4/connectivity-status.js`（新增） | 状态分类唯一来源：程序级别、矛盾三态、AI 倾向、计数摘要、关系类型、结论句 | 纯函数，无 DOM、无网络 |
| `assets/official-v4/connectivity.js` | 结果页信息层级、结论句、分级计数、三条证据线、关系图语义、AI/程序分离、导出命名、深链错误处理 | 未改计算、schema、pipeline、AI 调用 |
| `assets/official-v4/connectivity-workspace.js` | 状态路由（进入工作台收起 hero）、历史 5 条+状态、任务号高级入口、首页真实样例入口 | 未改任务提交与轮询逻辑 |
| `assets/official-v4/connectivity-results.css` | 新增结果页层次样式、语义色、折叠区、390px 压缩；原有样式全部保留（追加而非重写） | 未删原规则 |
| `index.html` | 首页定位文案、场景标签、静态数字改占位、任务条、阅读深度开关、全部关系折叠 | 未删 PDF 定位/画框/弹窗/更正/导出入口 |
| `tests/frontend/connectivity-status.test.mjs`（新增） | 13 例分类单测（含 `insufficient_basis`、`not_comparable`、条件试算负例） | — |
| `tests/frontend/ui_flow_test.py`（新增） | Playwright 真实浏览器 E2E，四尺寸 + AI 四状态 | 需本地服务 |
| `tests/frontend/capture_screens.py`（新增） | 截图采集（改造前/后） | — |
| `tests/fixtures/ai_state_fixture.json`（新增） | AI 四状态合成夹具，`dataset_role: synthetic_ui_fixture` | **非企业结论，禁止引用** |

`/docs`、`/scripts` 在 `.gitignore` 中被整体忽略，测试脚本改放 `tests/frontend/` 才可提交；`docs/ai_handoff/` 下的交接文档与关键截图用 `git add -f` 强制加入，其余截图留在本地。

## 二、结果页信息层级（旧 → 新）

旧版首屏同时出现：四问卡、关系列表、当前关系图、AI 倾向横幅、程序状态、成员表，同一关系重复三次以上，且“依据不足”会落到绿色“暂未见矛盾”。

新版顺序（自上而下）：

1. **任务条**：任务号、公司/期间、运行方式、状态、结果版本；复制任务链接。
2. **一句话结论**：如“本次共 8 项关系；2 项在前提支持下完成复算且未见差异；4 项依据不足或不可比……”。由 `verdictSentence()` 生成，只陈述计数，不给“没问题”判断。
3. **六个分级计数卡**：每个卡带定义、分母、是否互斥；六个级别互斥，合计等于关系总数。
4. **最值得先看的 2–3 条关系**：按程序级别与优先提示排序，每条可直接打开原页 PDF 或进入条件与计算。
5. **三条证据线**（互不替代）：左为关系图（披露成员 → 关系与前提 → 结果），右为程序事实 / AI 意见 / 条件缺口三块。
6. **`<details>全部关系与专业明细`**：默认收起，展开后才是原来的列表+详情主从布局、未决原因、优先清单、运行诊断、历史 AI 汇总。

导出区写明内容与运行方式：`Word 核对报告` / `CSV 关系明细` / `JSON 全部结果` + 运行方式标签（仅计算 / 三角色核对等）。

## 三、状态语义（唯一来源）

`connectivity-status.js` 只做翻译，不做判断。六个程序级别互斥：

| key | 显示 | 触发（摘要） | 色调 |
|---|---|---|---|
| `formal` | 正式复算 | 前提齐备且计算状态属于 `consistent` / `precision_explained` / `adjustment_explained` | 绿（已核实） |
| `conditional` | 条件试算 | 仅写明假设时相容（`assumption_check.contains_zero`、假设试算、条件调节） | 琥珀 |
| `limited` | 有限支持 | 口径支持但算式不可执行，或多位置比对 | 琥珀偏灰 |
| `insufficient` | 依据不足·不可比 | 关键前提缺原文依据，程序不输出正式差额 | 中性灰 |
| `conflict` | 潜在矛盾 | 明确冲突前提，或同口径下仍有未解释差额 | 铜红 |
| `not_applicable` | 不适用数值计算 | 叙述类关系 | 中性灰 |

矛盾三态独立命名：`potential` / `none` / `unknown`。**`none` 只在本级为 `formal` 时出现**；`insufficient`、`not_comparable` 一律归 `unknown`，不显示绿色。

AI 倾向使用独立命名空间与独立色板（`ai` / `ai-warn` / `ai-none`），代码中不出现 `tone:'ok'`，任何 AI 徽标都不可能显示为程序确认绿。AI 与程序冲突时额外输出“以程序为准”的分歧提示。列表与详情共用 `levelChip()` + `tendencyChip()`，不会出现两处说法不一致。

计数口径：级别互斥求和 = 关系总数；AI 意见数为独立一行（有意见/总关系）；未决原因可一关系多类，条形图注明“分母为全部关系，不可相加”。

## 四、路由与深链

- 首页与工作台同页：`#connectivity-root` 触发 `setRoute('workspace')`，以 `body[data-route]` 收起超长 hero，工作台顶部即任务身份。
- `?connectivity_task=<ID>`：先 `bootstrap` 建会话，再 `GET /runs/{id}`；成功后直接进入结果视图。
  - `404` → “该任务不存在，或当前浏览器无权读取”，给“开始新运行”。
  - `410` → “该任务已过期，服务端不再保留结果”。
  - `403` → “当前浏览器无权读取该任务；请用创建任务的浏览器打开”。
  - 任何失败都不清空用户已选报告对，错误面板在结果区之外。
- 刷新、前进/后退：`hashchange` + 路由状态恢复；刷新后仍停在结果视图，不回到新建。
- 返回首页：恢复 hero，保留 `#connectivity-root` 链接，不残留任务参数。
- 历史：`localStorage['audittrace-connectivity-history-v2']`，默认展示 5 条，按 `completed / failed / expired|interrupted / running` 区分状态；任务号输入框保留为高级入口；仅记录本浏览器实际访问过的任务，不读取他人会话。

## 五、字段兼容（缺失时不编造）

| 字段 | 存在时 | 缺失时 |
|---|---|---|
| `overview.confirmable / unconfirmable / unexplained` | 直接展示后端计数 | 由 `checks` 经同一 `summarize()` 推导，并标注“由关系记录推导” |
| `overview.priority_checks` | 优先清单与“优先核查”徽标 | 不显示优先级，仅按程序级别排序 |
| `ai_analyses` / `ai_opinions` | AI 证据线与倾向徽标 | “本次未生成 AI 意见；程序结果与原文仍可查看” |
| `program_hints[].priority_reason` | 关键关系的一句理由 | 退回该级别定义，不写推测性理由 |
| `candidate_rejections` | “系统数据问题 / 运行诊断”独立区块 | 该区块整体隐藏 |
| `scenario_adjustment.applied` / `hypothetical` | 条件试算与假设说明 | “未登记条件试算”，不显示 0 差额 |
| `execution_mode` | 任务条与导出区显示运行方式 | “运行方式未登记” |
| `result_revision` | 版本号 | 不显示 `vundefined` |
| `findings` / `next_evidence` | 补证任务列表 | “待提供”，不生成空任务 |
| `versions.rules` | 规则版本；旧版本加“历史规则结果”提示 | 不显示版本比较 |

## 六、真实测试记录

环境：Chrome（headless，Playwright）＋ 本地 `uvicorn`；数据为真实任务 `CONNJOB-D8796D38B3EC`（五粮液 2025，8 项关系）。

- 分类单测：`node --test tests/frontend/connectivity-status.test.mjs` → **13/13 通过**。
- 全流程 E2E：`python tests/frontend/ui_flow_test.py docs/ai_handoff/screens/after` → **96/96 通过**，覆盖 390 / 768 / 1024 / 1440 四档：
  首页 10 秒内可见用途句 → 入口在首屏且未被浮层遮挡 → 进入工作台 hero 收起 → 新建视图 → 深链直达结果 → 一句话结论与分级计数（2/4/0，分母 8）→ 不可比不显绿 → AI 计数独立 → 三条证据线 → 原文阅读器开关 → 全部关系展开 → 刷新仍在结果 → 历史 ≤5 条且有状态 → 失效链接给出可读错误 → 返回首页 hero 恢复 → 无横向溢出 → 无 JS 运行时错误。
- AI 四状态（**合成夹具**，`tests/fixtures/ai_state_fixture.json`，非企业结论）：
  1. 程序不可比 + AI 倾向一致 → 显示“依据不足·不可比”，并提示“以程序为准”；
  2. 程序条件相容 → “条件试算”，不进入正式复算统计；
  3. 程序差异未解释 → “潜在矛盾”；
  4. 系统候选失败 → 进入“运行诊断”，不计入企业待查。
- 改造前后截图：`docs/ai_handoff/screens/before/`（基线 `541de1b`）与 `after/`（本提交）。已随分支提交 5 张关键图 + `e2e-report.json`。
- **未做**：真人 5–10 秒理解与 3 分钟任务测试。仅交付脚本与记录模板：`docs/ai_handoff/AI3_可用性测试脚本与记录模板.md`，结果栏留空，标注“待人工验收”。

复现：

```bash
# 1) 起服务（本机虚拟环境）
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8011
# 2) 单测
node --test tests/frontend/connectivity-status.test.mjs
# 3) E2E（TMP 指向工作区内目录，避免 Windows 临时目录权限问题）
TMP="$PWD/tmp" TEMP="$PWD/tmp" TMPDIR="$PWD/tmp" python tests/frontend/ui_flow_test.py docs/ai_handoff/screens/after
```

## 七、需要 AI4 补充或确认

1. **导出命名与内容**：前端已标“Word 核对报告 / CSV 关系明细 / JSON 全部结果”，请确认 `export/docx` 是否区分运行方式（仅计算 vs 三角色）；若 Word 内含关系统计，请与 `ST.summarize()` 的口径一致（六级互斥、分母为关系总数），否则页面与文档会打架。
2. **AI 声明文本**：结果页默认展示“AI 生成内容，仅供关联核对参考，不构成审计结论、鉴证结论或鉴证意见”。若 AI4 在 API 或 Word 中使用不同措辞，请统一，避免同一产品两种声明。
3. **错误码语义**：前端把 `404` 视作“不存在或无权限”、`403` 视作“无权限”、`410` 视作“已过期”。若后端改为统一 `404` 防探测，请保留 `message` 可读文案。
4. **任务列表**：历史目前基于 `localStorage`。若提供 `GET /runs?owner=me&limit=5`，前端可替换为服务端列表（需带过期状态字段）。
5. **字段补齐**：`next_evidence`、`claim` 证据状态、L0/L1/L2 级别若在 AI1/AI2 落地，请给字段名与取值枚举；前端已留兼容位，缺字段时显示“待提供”。
6. **单位与计数**：结果页已把“处 / 页 / 项”分开显示；Word 导出若合并统计，请勿相加不同单位。

## 八、已知限制

- 390px 首屏以静态机制图替代 3D 场景（CSS 媒体查询降级），未做 WebGL 关闭开关。
- 首页“查看最近一次真实记录”只在当前浏览器有历史时出现；无历史则只保留“开始核对”，不编造样例数字。
- 历史仅本浏览器可见，跨设备需依赖服务端任务列表（见上）。
- 已用真实浏览器验证四档尺寸与键盘可达性基础项，但未做 200% 缩放、读屏软件与真人可用性验收。
- 本地截图与夹具来自真实任务，仅用于版式与状态测试；对外演示不得引用夹具中的数字。
