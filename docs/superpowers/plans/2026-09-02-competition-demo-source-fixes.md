# 初赛演示源码问题修复实施计划（2026-09-02 审查产出）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除初赛演示链路上的真实缺陷与失败风险（模型口径漂移、备用入口不可达、轮询放大、文档/页面事实不一致），并完成录视频与现场演示所需的全链真实验收。

**Architecture:** 只改根目录正式站点（`index.html` + `assets/official-v4/`）与 `backend/app` 既有模块，不新建页面、不改技术栈；所有结论以真实后端 + 真实浏览器验收为准，人工门禁（模型调用授权、提交、签字、评分）一律由真人完成。

**Tech Stack:** FastAPI + Uvicorn（backend/app）、SQLite/Supabase 台账、原生 HTML/CSS/JS 前端、pytest、Playwright/Chrome 验收脚本。

---

## 执行者必读规则（来自根目录 AGENTS.md，全程生效）

1. 只在本目录内工作；唯一正式站点是根目录 `index.html` 与根目录 `assets/`。不得新建第二个展示网页，不得改写 `03_第一周任务与成果/audittrace-local-static/` 早期原型。
2. 不删除任何用户文件；只改本计划列出的落点。不动 `../../../project/`（无关旧 FINTEL 项目）。
3. 未经用户明确要求，不 commit、不 push、不部署。标记 `[需用户批准]` 的步骤必须先停下来问。
4. 不得伪造或夸大：Mock 成功不得写成真实模型成功；provider probe、真实 B3、签字、人工评分是独立门禁；"R1 未触发"不等于"无风险"。
5. 统一 AI 声明逐字使用："AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。"
6. `backend/app` 中文注释与独立 docstring 行占非空行比例不得低于 10%（当前实测 10.03%，余量很小）。本计划新增/修改的后端代码必须自带中文注释；每步完成后运行 `backend/.venv/Scripts/python.exe scripts/check_chinese_comments.py` 复核。
7. 真人在环事项（标记 `[真人]`）：模型调用预算授权、Render Secret 操作、git 提交批准、方案书口径裁决、视频出镜与旁白决定。执行者准备好命令与证据格式，但由真人按下按钮。
8. 每个 Task 完成后把命令、退出码、产物路径追加登记到 `artifacts/source-fix-20260902/执行台账.md`（不存在则创建）。数字必须有产物与日志支撑；推算值不得写成实测。

## 审查发现总览（问题 → 任务映射）

| # | 严重度 | 发现（已核实，源码证据） | 处理任务 |
|---|--------|--------------------------|----------|
| 1 | **高** | 生产模型口径三方不一致：AGENTS.md 写统一 `qwen3.5-plus`；`backend/release_records/current_release.json:6`、`render.yaml:53`、本机 `.env`、`main.py:548` 默认值全为 `deepseek-v4-flash`；17/18 号初赛方案书候选已写"生产统一 DeepSeek 直连"。 | Task 1 `[真人]` |
| 2 | **高** | 模型链失败/额度耗尽后，页面**没有**"启动确定性备用演示"入口：`demo-app.js:416-419` `canStartBackup` 要求 `!taskStoreReady || taskCreationBlocked`，而供应商失败时台账可用、任务创建成功（202 后异步失败），按钮永不出现；后端就绪接口却给 `next_action_code=use_deterministic_backup`（`main.py:674`）。前后端合同不一致。 | Task 2 |
| 3 | **高** | 真实模型成功率历史：qwen3.5-plus 最近窗口 7/10=70%（<80% 阈值，`PROJECT_STATUS.json` alert=true）；deepseek-v4-flash 仅本机 15 案中的五案 5/5 烟测，**生产 probe 与新鲜 B3 均 pending**（`current_release.json:40-47`）。演示日失败概率未量化。 | Task 4、5 |
| 4 | 中 | 每访客模型额度 `AUDITTRACE_MODEL_RUN_LIMIT=2`/15 分钟（`public_model.py:69`、`render.yaml:34`）：彩排+正式演示同一 IP 连点即被限流，且叠加问题 2 后无备用出口。 | Task 2、6 |
| 5 | 中 | `/api/demo/bootstrap` 一次请求调用 `_runtime_quality_snapshot` 两遍（`main.py:4881` 与 `main.py:4908`），每遍 1 次 Supabase RPC，拖慢首屏且浪费免费层配额。 | Task 3 |
| 6 | 中 | `SupabaseDemoRunTaskStore.get()` 每次任务轮询都执行 `interrupt_expired_demo_run_tasks()` RPC（`demo_run_tasks.py:640-642`）；前端每 1.5s 轮询一次，多人观看时放大到免费 Postgres。 | Task 3 |
| 7 | 低 | JSON 导出对象含两个 `supplement_delta` 键（`demo-app.js:2005` 与 `:2023`），后者静默覆盖前者。 | Task 2 |
| 8 | 低 | 死常量 `RUN_TIMEOUT_MS`（`demo-app.js:20`）定义后从未使用。 | Task 2 |
| 9 | 低 | 版本徽章不一致：`index.html:29` "0.10.2 · DEMO"，而资源指纹已是 `styles.css?v=0.10.7` / `demo-app.js?v=0.10.13`；`index.html:33` 遥测条硬编码 "45 REPORTS"，真实值由 JS 按 manifest 计算覆盖定位页计数但**不覆盖该条**。 | Task 2、8 |
| 10 | 高（流程） | 源码基线 347 passed 登记于 2026-09-01，但工作区又有 ~1000 行未提交改动（含 `agents.py`、`main.py`、`demo_run_tasks.py`、前端）；本轮审查会话的 Bash 分类器故障导致**未能在本会话复跑测试**。另外约 28 个测试文件从未 `git add`。 | Task 0、9 |
| 11 | 高（流程） | 视频未录制（`PROJECT_STATUS.json` 多处 `"video": "deferred"`）；5 分钟演示脚本（2026-08-24）未对照 0.10.13 前端逐步骤实测；键盘可达性证据在 09-01 被明确判"未取得有效证据，须按 Task 11 专项复验"。 | Task 4、7 |
| 12 | 中（流程） | Render 免费 Web 冷启动/休眠：任务运行中实例回收 → `interrupted`（诚实但难看）；共享站现场样例已正确关闭（`main.py:4869-4871`），但演示 runbook 未写成可执行清单。 | Task 6 |
| 13 | 低（存疑） | `renderProcedureMap`（`demo-app.js:1189-1200`）把每条程序同时写入 自动/辅助 与"人工保留"列——疑似有意（每条程序都有人工保留段），但视觉重复，需人工看图定案。 | Task 8 |
| 14 | 登记不改 | `main.py` 375KB 巨型单文件、`cases.py` 110KB；赛前重构风险大于收益。评委包线用户已裁决砍掉，但 `PROJECT_STATUS.json` 仍挂 `remediation_required` 与作废口径并存。B0—B3 真人评分、R1 正式签字、双人冻结仍是人工门。 | Task 10 |

> 关于"老师提到的问题都改了"：本审查只覆盖源代码；两份老师批改版 `.docx` 的修订点落实核对是文档线，列为 Task 8，结论以对照报告为准，不得口头宣称完成。

---

## Task 0: 基线证据复跑（本会话未能执行，必须最先补）

**Files:** 无修改；产出写入 `artifacts/source-fix-20260902/`

- [ ] **Step 1: 复跑全量测试**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q 2>&1 | Tee-Object artifacts\source-fix-20260902\pytest-baseline.txt
```
Expected: `347 passed, 1 warning`（warning 为 Starlette TestClient/httpx 弃用提示）。若数字不同或出现失败：**停止后续所有 Task**，先按失败清单逐项定位（不得放宽任何测试或硬校验来"过线"），把根因写进执行台账。

- [ ] **Step 2: 中文注释门槛**

```powershell
backend\.venv\Scripts\python.exe scripts\check_chinese_comments.py
```
Expected: PASS（当前登记 2368/23604 = 10.03%）。

- [ ] **Step 3: 前端 JS 语法**

```powershell
node --check assets\official-v4\demo-app.js
```
Expected: 无输出、退出码 0。

- [ ] **Step 4: 工作区快照登记**

```powershell
git status --short > artifacts\source-fix-20260902\git-status-start.txt
git stash list >> artifacts\source-fix-20260902\git-status-start.txt
```
确认未跟踪/已修改清单与本计划开头一致（main.py、agents.py、demo_run_tasks.py、前端、约 28 个测试文件）。**不要**执行任何 stash/checkout/reset。

---

## Task 1: 生产模型口径统一 `[真人裁决]`

**背景（裁决记录）：** 原 AGENTS.md 写"生产目标模型统一为 `qwen3.5-plus`"，而 2026-08-28/29 的发布记录、README_RUN、render.yaml、初赛方案书候选与本机 `.env` 全部指向 `deepseek-v4-flash`。**2026-09-02 队长裁决：统一 `deepseek-v4-flash`（DeepSeek 官方直连）；qwen3.5-plus 只作历史冻结证据。**

- [x] **Step 1: 向用户提出二选一并等待答复** — 已答复：选 A（deepseek-v4-flash）。

- [x] **Step 2A（裁决 A）：已执行。** 修改清单：`AGENTS.md:9`（写入裁决与历史限定）；`backend/app/provider_readiness.py` OpenCode Go 402 指引去除硬编码模型名；`render.worker.example.yaml` 模板默认值 → `deepseek-v4-flash`；`scripts/freeze_evaluation_v4.py:199`、`scripts/run_controlled_b1_b3_prescore.py:615` env 兜底默认 → `deepseek-v4-flash`；`scripts/summarize_b1_b3_evaluation.py:75` 摘要文案改为模型无关口径；`02_最终确定方案/15_..V4..md:14`、`16_..V3..md:18`、`22_..老师终稿最终修改计划..md` P0-5 的 qwen 段落全部改为"历史冻结证据"表述。发布记录/`render.yaml`/`.env` 本就是 `deepseek-v4-flash`，未动；`PROJECT_STATUS.json/.md` 与 `README_RUN.md` 中的 qwen 数字均在已标 superseded 的历史段，保持不改写历史。

- [ ] **Step 2B（作废）**：裁决为 A，本节不再执行。保留原文供追溯：

1. `.env` 与 `render.yaml` 将 `DEEPSEEK_BASE_URL` 切到支持 `qwen3.5-plus` 的通道（历史上是 OpenCode Go：`https://opencode.ai/zen/go/v1`，见 `provider_readiness.py:102-109`），`DEEPSEEK_MODEL=qwen3.5-plus`；
2. `main.py:548` 与 `auth.py:41` 的默认值同步改为裁决模型；
3. `backend/release_records/current_release.json`、`current_evaluation.json` 追加新窗口定义（不覆盖旧文件，按追加式记录惯例新建 `provider_probe_*` 证据文件）；
4. 裁决后必须重做 Task 5 的新鲜 B3（qwen 通道历史成功率仅 70%，风险更高，须向用户明示）。

- [ ] **Step 3: 一致性自检脚本化**

```powershell
backend\.venv\Scripts\python.exe -c "import json,os,re,pathlib; m=os.getenv('DEEPSEEK_MODEL') or re.search(r'DEEPSEEK_MODEL=(\S+)', pathlib.Path('.env').read_text(encoding='utf-8')).group(1); r=json.loads(pathlib.Path('backend/release_records/current_release.json').read_text(encoding='utf-8')); y=pathlib.Path('render.yaml').read_text(encoding='utf-8'); print('env',m); print('release',r['model']['model_id']); print('yaml', 'MATCH' if m in y else 'CHECK')"
```
Expected: 三处输出同一模型 ID；不一致即本 Task 未完成。把输出贴进执行台账。

---

## Task 2: 前端修复（备用入口 + 三处小缺陷）

**Files:**
- Modify: `assets/official-v4/demo-app.js:404-441`（`renderControls`）、`:1431-1433`（`startDemoRun` 相位门槛）、`:20`（死常量）、`:2023`（重复键）
- Modify: `index.html:13-14,29,33`（版本徽章/遥测条/资源指纹）

### 2a. 失败/降级后暴露"启动确定性备用演示"（核心）

- [ ] **Step 1: 修改 `renderControls` 的备份按钮门槛**

`demo-app.js` 现状（约 411-419 行）：

```js
    const continuity = demoState.bootstrap?.task_continuity || {};
    const taskStoreReady = continuity.availability ? continuity.availability === "ready" : true;
    const deterministicAvailable = Boolean(demoState.bootstrap?.model_readiness?.deterministic_backup_available);
    const canStartBackup = deterministicAvailable
      && (phase === "ready" || phase === "failed_run")
      && (!taskStoreReady || demoState.taskCreationBlocked)
      && Boolean(demoState.caseId);
```

改为（保持既有注释风格，新增中文注释说明为什么）：

```js
    const continuity = demoState.bootstrap?.task_continuity || {};
    const taskStoreReady = continuity.availability ? continuity.availability === "ready" : true;
    const deterministicAvailable = Boolean(demoState.bootstrap?.model_readiness?.deterministic_backup_available);
    const modelReady = Boolean(demoState.bootstrap?.model_readiness?.full_analysis_ready);
    // 供应商链失败后任务已进终态，但台账可用、创建未受阻：
    // 此时后端就绪合同给出 use_deterministic_backup，前端必须同步露出备用入口，
    // 否则演示会卡在"只能反复重试真实模型"的死路上。
    const outcomeFailed = ["failed_run", "failed", "degraded", "expired", "interrupted", "cancelled"].includes(phase);
    const canStartBackup = deterministicAvailable
      && (phase === "ready" || outcomeFailed)
      && (!taskStoreReady || demoState.taskCreationBlocked || outcomeFailed || !modelReady)
      && Boolean(demoState.caseId);
```

- [ ] **Step 2: 放开 `startDemoRun` 的备份相位门槛**

现状（约 1432 行）：

```js
    const allowedPhase = backup ? new Set(["ready", "failed_run"]) : new Set(["ready"]);
```

改为：

```js
    const allowedPhase = backup
      ? new Set(["ready", "failed_run", "failed", "degraded", "expired", "interrupted", "cancelled"])
      : new Set(["ready"]);
```

- [ ] **Step 3: 语法检查 + 真实浏览器验证（不得用静态打开替代）**

```powershell
node --check assets\official-v4\demo-app.js
```
Expected: 退出码 0。随后（配合 Task 4 的服务）在真实浏览器复现路径：以 `AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=true` 但临时置错 `DEEPSEEK_API_KEY=sk-invalid` 启动，跑 STD_DEV_T0 至首角色 `provider_unreachable` 终态 `failed`，确认"启动确定性备用演示"按钮出现在"一键重置演示"旁，点击进入备用任务并如实标注"确定性备用 · 未调用外部模型"；再把 Key 恢复正常复跑一次确认成功路径不出现备用按钮闪烁误导。截图存入 `artifacts/source-fix-20260902/backup-entry-*.png`。同时把 `demo-app.js?v=` 与 `styles.css?v=` 指纹各递增（0.10.13→0.10.14）。验证完**立即恢复** `.env` 原值。

### 2b. 小缺陷三处

- [ ] **Step 4: 删除死常量**：删除 `demo-app.js:20` 整行 `const RUN_TIMEOUT_MS = 300000;`。
- [ ] **Step 5: 去重 JSON 导出键**：删除 `downloadRunJson` 中后出现的重复行 `supplement_delta: run.context?.supplement_delta,`（约 2023 行），保留 2005 行带 `|| null` 的写法。
- [ ] **Step 6: 版本徽章对齐**：`index.html:29` `0.10.2 · DEMO` → `0.10.14 · DEMO`；`index.html:33` 遥测条改为不含具体数字的中性文案 `15 REGISTERED CASES / FROZEN REPORTS`（真实年报份数由定位页 `#demo-positioning-report-count` 动态显示，避免第二处硬编码失同步）。
- [ ] **Step 7: 回归**

```powershell
node --check assets\official-v4\demo-app.js
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_competition_demo_plan.py -q
```
Expected: 语法 0；pytest 全绿（该文件含前端 id 合同检查）。

---

## Task 3: 后端小修（bootstrap RPC 去重 + 过期结算限频）TDD

**Files:**
- Modify: `backend/app/main.py:4878-4912`（`get_demo_bootstrap`）
- Modify: `backend/app/demo_run_tasks.py:402-413,633-653`（`SupabaseDemoRunTaskStore.__init__` / `get`）
- Test: `backend/tests/test_competition_demo_plan.py`（追加 2 个测试，复用该文件既有 `Client()` 桩风格，见 `:1409-1433`）

- [ ] **Step 1: 写失败测试 1（bootstrap 质量窗口只读一次）**

追加到 `backend/tests/test_competition_demo_plan.py` 末尾：

```python
def test_demo_bootstrap_reads_runtime_quality_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """启动快照每次请求只读取一次运行时质量窗口，避免重复 Supabase RPC。"""
    from fastapi.testclient import TestClient
    import backend.app.main as main_module

    calls: list[str] = []

    def fake_snapshot(model_id: str):
        calls.append(model_id)
        return None

    monkeypatch.setattr(main_module, "_runtime_quality_snapshot", fake_snapshot)
    client = TestClient(main_module.app)
    response = client.get("/api/demo/bootstrap")
    assert response.status_code == 200
    assert len(calls) == 1, f"_runtime_quality_snapshot 被调用 {len(calls)} 次，应为 1 次"
```

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_competition_demo_plan.py::test_demo_bootstrap_reads_runtime_quality_once -q`
Expected: FAIL（当前调用 2 次）。
（若该测试因环境需 `AUDITTRACE_DEMO_MODE=true` 等变量才返回 200，参照本文件既有 bootstrap 测试的 fixture/monkeypatch 方式补齐前置，不要跳过断言。）

- [ ] **Step 2: 写失败测试 2（过期结算 30 秒限频）**

```python
def test_supabase_expiry_sweep_is_throttled() -> None:
    """任务轮询共享一次 30 秒内的过期结算，不每次轮询都发 RPC。"""
    from backend.app.demo_run_tasks import SupabaseDemoRunTaskStore

    sweeps = {"n": 0}

    class Client:
        def interrupt_expired_demo_run_tasks(self) -> None:
            sweeps["n"] += 1

        def get_demo_run_task(self, task_id: str) -> dict[str, object]:
            return {"task_id": task_id, "status": "queued", "steps": {}, "agent_steps": {}}

    store = SupabaseDemoRunTaskStore(Client())
    try:
        for _ in range(5):
            store.get("DEMO-RUN-THROTTLE")
        assert sweeps["n"] == 1
    finally:
        store.shutdown()
```

Run: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_competition_demo_plan.py::test_supabase_expiry_sweep_is_throttled -q`
Expected: FAIL（当前 sweeps==5）。

- [ ] **Step 3: 实现 bootstrap 去重**

`main.py` `get_demo_bootstrap` 中删除第二次计算（约 4906-4909 行）：

```python
    runtime_quality = _runtime_quality_snapshot(_model_settings()[2])
    payload["runtime_quality_window"] = runtime_quality
```

复用前面已算好的 `runtime_quality`（4881 行处），即直接改为：

```python
    payload["runtime_quality_window"] = runtime_quality
```

并保留其后 `payload["release"] = _release_fact_snapshot(readiness=model_readiness, runtime_quality=runtime_quality)` 不变。加一行中文注释："质量窗口快照每次启动请求只读取一次，release 与 window 共用同一快照。"

- [ ] **Step 4: 实现结算限频**

`demo_run_tasks.py` 顶部常量区加：

```python
# 过期结算维护 RPC 的最短间隔：任务轮询高频到达，不能让每次轮询都打一次数据库。
EXPIRY_SWEEP_MIN_INTERVAL_SECONDS = 30.0
```

`SupabaseDemoRunTaskStore.__init__` 里加：

```python
        self._last_sweep_monotonic = 0.0
```

`get()` 开头（替换现 638-643 行的 try 块）：

```python
        from .supabase_adapter import SupabaseError

        # 结算只是维护性动作；30 秒窗口内复用上一次结果，读写事实仍由 CAS 保证。
        now = time.monotonic()
        if now - self._last_sweep_monotonic >= EXPIRY_SWEEP_MIN_INTERVAL_SECONDS:
            self._last_sweep_monotonic = now
            try:
                self.client.interrupt_expired_demo_run_tasks()
            except SupabaseError:
                pass
```

- [ ] **Step 5: 跑绿并回归**

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_competition_demo_plan.py backend\tests\test_demo_run_tasks.py backend\tests\test_demo_run_task_store_race.py backend\tests\test_batch3_cache_manifest.py -q
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
backend\.venv\Scripts\python.exe scripts\check_chinese_comments.py
```
Expected: 定向 4 文件全绿 → 全量 349 passed（347+2，1 warning）→ 注释率 ≥10%。

---

## Task 4: 真实浏览器三条链彩排（录视频前置验收）`[真人授权模型预算]`

**背景：** 09-01 的浏览器验收只覆盖确定性链（零模型外呼）；键盘 Enter/Space 证据被登记为"未取得有效证据，须专项复验"。本 Task 是"能录视频"的硬前提。开始前向用户申请：本机真实模型调用预算（建议 ≥3 次完整三 Agent 链 = 9 次 provider 调用 + 视彩排损耗追加）。

**Files:** 无源码修改；产物入 `artifacts/source-fix-20260902/`。

- [ ] **Step 1: 本机确定性链（不花 Token）**

```powershell
$env:AUDITTRACE_DEMO_MODE="true"; $env:AUDITTRACE_ONSITE_LIVE_SAMPLE="true"; $env:AUDITTRACE_DEMO_USE_EXTERNAL_MODEL="false"
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
另开终端：`curl http://127.0.0.1:8000/api/demo/bootstrap`，人工核对 `bootstrap_ready=true`、15 案、`featured` 3 案 `rag.status` 全 ready、`release.competition_release_ready=false` 的展示口径。随后复用既有脚本逐视口跑：

```powershell
.agents\tools\browser-qa\.venv\Scripts\python.exe scripts\browser_demo_final_acceptance.py --viewport 1440x1000 --skip-live
```
（依次 1440x1000 / 1024x768 / 768x1024 / 390x844。）Expected: 每视口退出码 0、`axe_acceptance=accepted`、violations=0。同时人工审阅截图并专项检查**键盘链**：Tab 顺序、对话框 Esc 关闭与焦点归还、`Enter/Space` 触发主按钮与抽屉、`prefers-reduced-motion`。逐项结果写入 `artifacts/source-fix-20260902/keyboard-acceptance.json`——这是 09-01 台账里欠着的 Task 11。

- [ ] **Step 2: 真实模型链单案彩排**

`.env` 恢复 `AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=true` + 有效 Key（`AUDITTRACE_PROVIDER_PROBE_ENABLED=true`）。在浏览器里按演示脚本完整走 STD_DEV_T0（主按钮→六阶段→结果→查看原文证据→Agent 抽屉→下载 JSON/CSV→打印预览→一键重置→切换精选案例再跑一次）。记录：`execution_mode`、`provider_call_count=3`、三角色 completed、`model_success`。若中途降级：保留失败码，不得重试到"碰运气成功"当作通过——把首次真实结果如实入台账，再决定是否修根因。**每个视口至少 1 次完整链**，控制台错误/失败网络请求为 0 才可记通过。

- [ ] **Step 3: 现场样例链彩排**

本机开 `AUDITTRACE_ONSITE_LIVE_SAMPLE=true`（当前 render.yaml 无此变量，本机 bat 已带）。用非 15 案企业（建议 `000333 美的集团`，index.html 占位符同款示例）走"现场样例接入"抽屉：确认企业→检索公告→下载→校验→登记→RAG→烟测→字段提取→分析，直至 `completed` 或 `needs_human`（两者都要预演话术；R3 记录 600436 曾在 needs_human）。下载三件套并核对 AI 声明存在。全程 390x844 与 1440x1000 各一遍。

- [ ] **Step 4: 补充证据链彩排**

在任一 completed/degraded 结果后点"补充证据并重新评估"→ 选内置样例 → 子任务六阶段 → 父子差异卡显示、原字段未被覆盖。同时验证 Task 2 后该链在备用任务下仍可用（备用走本地 store，无登录）。

---

## Task 5: Render 生产 probe + 新鲜单案 B3 `[真人操作]`

- [ ] **Step 1: 核对部署提交**：浏览器打开 `https://<render域>/api/status` 的 `deployment.commit`，与 `git rev-parse HEAD` 对照（Task 9 提交后需重新部署再核）。不一致先重新部署再看后续。
- [ ] **Step 2: 生产 provider probe**：按 Task 1 裁决通道执行无 Token 探测（`AUDITTRACE_PROVIDER_PROBE_ENABLED=true` 下 `GET /api/status` 的 model 块），确认 `full_analysis_ready=true` 且 `paid_probe_performed=false`。历史教训：08-16 生产站曾在真实链上 `MODEL_PROVIDER_AUTH_FAILED`（本机 Key 与 Render Secret 不是一回事）——probe 绿了仍要做 Step 3。
- [ ] **Step 3: 生产单案新鲜 B3（用户授权 1 次）**：共享站 UI 跑 STD_DEV_T0 一次完整链，记录 run_id / task_id / 3 provider 调用 / 三角色状态；结果与失败码入台账。**不要**重跑 51/15 案付费批量（README 明令）。把台账路径追加进 `backend/release_records/`（新建 probe/b3 证据文件，不改已封存记录）。
- [ ] **Step 4: 冷启动演练**：让 Render 实例闲置休眠后访问首页与创建任务各一次，实测冷启动等待秒数写入 Task 6 的 runbook（决定演示日是否提前唤醒）。

---

## Task 6: 演示 Runbook（README_RUN 新增一节）

**Files:** Modify: `README_RUN.md`（"二、竞赛演示工作流"之后插入"二点五、演示日前检查清单"）

- [ ] **Step 1:** 写入以下内容的成稿（执行者起草、用户定稿）：
  1. 演示一律以**本机 bat 启动**为主链路（Render 共享站仅备份），录视频同理；
  2. 启动后先跑三条 curl：`/api/health`、`/api/status`、`/api/demo/bootstrap`，核对模型通道、台账 `availability=ready`、15 案 RAG ready；
  3. 若走共享站：演示前 30 分钟唤醒实例（Step 4 实测的冷启动时长 + 余量）；确认 `AUDITTRACE_MODEL_RUN_LIMIT` 的取值是否按当天计划临时调高（`render.yaml:34` 当前 2/15min/IP；彩排消耗同一 IP 额度会锁自己）；给出"演示日临时 env + 演示后回滚"两条命令；
  4. 缓存事实页：`AUDITTRACE_MODEL_CACHE_SECONDS=86400`——演示前一天预热过的案例当天可能命中缓存，页面会如实显示"已复用经校验的 AI 结果"而非"真实模型现场执行"；讲解词必须能接住这一状态；
  5. 失败预案：额度用尽→备用按钮（Task 2 修复后位于失败终态旁）；实例重启→`interrupted` 文案与"重置后显式重跑"话术；供应商 402/401→按页面中文指引处理，绝不现场改配置演示。
- [ ] **Step 2:** 版本号若因 Task 2 递增至 0.10.14，README_RUN 标题行同步。

---

## Task 7: 五分钟演示脚本对齐与录视频步骤验证

**Files:** 只读 `17_审迹智链_竞赛终版五分钟演示脚本_2026-08-24.md`（核对基准）；新脚本落 `02_最终确定方案/19_审迹智链_初赛演示与录视频Runbook_V2_2026-09-02.md`（避免覆盖旧稿）。

- [ ] **Step 1:** 逐步骤对照当前 UI（0.10.14、备用按钮新行为、遥测条新文案）执行一遍，标注"脚本描述与页面不一致"的每一处；
- [ ] **Step 2:** 按脚本实际录制一段完整视频（含真实模型链一次、降级讲解一次、现场样例一次、导出与打印一次），把录屏中发现的等待点（如 Agent 协作 1-2 分钟空窗）写进旁白预案；
- [ ] **Step 3:** 视频文件与截图归档 `artifacts/source-fix-20260902/video/`；在 `PROJECT_STATUS.json` 把 `"video": "deferred"` 更新为如实状态（已录/待审）。`[真人]` 是否把视频列为提交物由队长决定。

---

## Task 8: 方案书与页面事实核对报告（含老师批改版）

**Files:** 只读两份 `.docx` 与 `02_最终确定方案/12_方案书事实断言清单_V4.md`；报告落 `02_最终确定方案/20_审迹智链_方案书源码事实核对报告_2026-09-02.md`（新文件，不改方案书本体；发现需改文时列建议、由队长定稿）。

- [ ] **Step 1:** 抽取 docx 修订/批注文本：

```powershell
backend\.venv\Scripts\python.exe -c "import zipfile,re,sys; [print('====',f) or print(re.sub(r'<[^>]+>',' ', zipfile.ZipFile(f).read('word/document.xml').decode('utf-8', 'ignore'))[:20000]) for f in [r'审迹智链_AuditTrace_初赛项目方案书老师修改终稿.docx', r'20_审迹智链_初赛项目方案书老师批改版.docx']]" > artifacts\source-fix-20260902\teacher-docx-text.txt
```
（如需 w:ins/w:comment 精确提取，可加读 `word/comments.xml`。）
- [ ] **Step 2:** 建立"老师意见 → 落实情况 → 证据文件"三列对照表；无法核实的一律写"待核验"。
- [ ] **Step 3:** 数字口径核对：15 案/年报份数（`backend/competition_demo_cases.json` 汇总 vs `index.html:33`、`:77`、`:146` 的 45/15 文案）、`347 passed`、模型 ID（Task 1 裁决结果）、"12 条活跃来源"、"7/10=70%"、"五案 5/16 调用"、"168 小时保留"。每项标注来源文件与行号。
- [ ] **Step 4:** 视觉复核 `renderProcedureMap` 三列（Task 清单 #13）：若确认程序名重复出现属误导，再开一个小前端修复；本步只出结论不动代码。

---

## Task 9: Git 检查点 `[需用户批准]`

- [ ] **Step 1:** 向用户报告将纳入版本库的清单：28 个未跟踪测试文件、`backend/tests/conftest.py`、本轮 Task 2/3 修改、`backend/requirements-lock.txt`、新计划与台账目录（`artifacts/source-fix-20260902/` 是否入库由队长定）。逐目录 `git add`，**不使用** `git add -A`（避免卷入 `交付包/*.zip`、两份 `~$` 临时 docx、`backups/`、`tmp/`）。
- [ ] **Step 2:** add 之后 `git status` 逐一过目，确认无密钥（`.env` 必须仍被忽略；`git diff --cached | grep -iE "api_key|service_role|secret"` 人工检查命中项的上下文）。
- [ ] **Step 3:** 分两个提交：①`test: track competition regression suite` ②`fix: expose deterministic backup after model-chain failure`（含 Task 2/3）。提交信息正文引用本计划文件路径。**不 push**，除非用户另行要求。
- [ ] **Step 4:** 干净克隆复算验证（一次性即可）：临时目录 `git clone` + `python -m venv` + `pip install -r requirements.txt` + `pytest -q`，结果应等于 Task 0 数字；这是评委/队员"从克隆可复现"的最小证据。

---

## Task 10: 已知缺点登记（赛前**不**动，写进状态文件）

- [ ] **Step 1:** 在 `PROJECT_STATUS.md`（人类可读面）追加"2026-09-02 源码审查遗留缺点登记"：main.py 375KB/cases.py 110KB 单文件规模、qwen3.5-plus 70% 历史窗口与 deepseek-v4-flash 生产窗口未成形的不对称、评委包线口径待裁决作废或修复（现 `remediation_required` 与用户砍线决定并存）、B0—B3 真人评分/签字/双人冻结人工门、`update_stage` 乱序事件静默丢弃无计数留痕、`SupabasePublicModelLedger.reserve` 与任务链之间的极端竞态下可能出现"任务 running 但额度已释放"（TTL 180s 内自愈，演示场景无并发访客，接受）。每项：现状→影响→建议窗口（初赛后的重构周期）。
- [ ] **Step 2:** 明确不做的事：不在赛前拆分任何巨型文件；不放宽任何硬校验；不引入新前端测试框架（浏览器验收脚本已存在，够用）。

---

## 完成判据（全部满足才可宣布"初赛演示就绪"）

1. Task 0 全量测试在**最终代码状态**下复跑通过，注释率 ≥10%，两证据入台账；
2. Task 1 口径三方一致（AGENTS.md/发布记录/部署 env）且有队长裁决记录；
3. Task 2 备用入口在"供应商失败终态"真实浏览器复现成功；
4. Task 4 三链（确定性/真实模型/现场样例）× 四视口全部有截图与 console/network 零错误证据，键盘专项 JSON 落盘；
5. Task 5 生产 probe 绿 + 一次授权的新鲜 B3 证据入 release_records；
6. Task 6/7 runbook 与录视频实跑完成；
7. Task 8 报告中无"口头已改"项——老师意见逐条有证据文件或标"待核验"；
8. 所有提交均经用户批准；未批准前工作树保持可核对状态。

## 禁止事项（对执行者的硬约束）

- 禁止：修改 `03_第一周任务与成果/` 早期原型来"同步"功能；新建第二展示页；把 degraded/cached/backup 改文案伪装成 external_live 成功；为过测试改测试断言而不修根因；未经批准调用付费模型批量、push、部署、发送外部消息；删除或覆盖两份老师批改版 docx 与任何已封存 JSON。
