# AuditTrace 任务中心改造交付与验收记录

基准提交 `34a6b8a`；功能分支 `codex/task-center-isolation`。A/B提交 `68628e6`，C提交 `1777532`。

**交付状态：A–D代码已实现并完成本地工程检查；E只完成本地HTTP并发与DOM集成检查，真实浏览器及真实模型验收未完成。尚未发布到GitHub或部署。**

## 修改前后对照

| 项目 | 修改前 | 修改后 |
|---|---|---|
| 高频读取 | GET完整任务、Supabase select=* | 独立/status字段投影，不含result |
| 历史详情 | task→public→snapshot→再次get | public使用已有记录；分层读取走一次只读RPC |
| 事项详情 | 先取全任务再过滤 | PostgreSQL内过滤所选事项、所引证据；本地直接访问已载入台账对象 |
| PDF校验 | 每次整文件读入并重新哈希 | 路径/大小/mtime_ns缓存，1MB分块；按文件合并并发校验；导出强制重验 |
| 当前状态 | 共享task/timer/generation | activeRun独立轮询；viewRun独立代数和加载状态 |
| 历史列表 | localStorage为主 | 服务端分页；缓存只兜底 |
| 深查入口 | 无选中事项时可能发送90块 | 深查必须明确选择1项；初筛不调用模型 |
| 供应商Schema | 统一大合同，14595字符 | A1 2066 / A2 5734 / A3 6600 / A4 3858 / A5 4100字符 |
| 调用保护 | 20次共享，前部可能挤占 | 总额仍20；A1=3、A2=4、A3=4、A4=4、A5=5 |
| 工具循环 | 可重复调查 | 无新增证据停止调查，只做一次收尾；剩余问题程序写入资料需求 |
| 错误定位 | 统一MODEL_SCHEMA_INVALID | JSON/工具/字段/端点/发生期间分列，附角色、字段、原因、重试次数 |
| 角色卡 | 混合旧错误和新成功 | 当前事项+当前run_id仅最后状态，历史记录另折叠 |
| 结果阅读 | 候选与长清单直接展开 | 企业/状态/候选统计→调查摘要→关键事项→按需证据链；候选默认收起，每页10项 |

## 分阶段修改与验证

### A 后端读取

文件：`connectivity_api.py`、`demo_run_tasks.py`、`connectivity_graph.py`、`connectivity_extraction.py`、新`connectivity_read_models.py`和`connectivity_source_cache.py`、`connectivity_app.py`、只读SQL迁移。

同一伊利历史样本的本地状态响应1,103B，全量响应2,244,062B，体积减少99.95%。此比较仅用于体积；生产9.70秒与本地毫秒数不是同环境耗时，不计算提速倍数。完整兼容读取仅一次get；单事项远端仅读一次RPC；第二次读取命中规范化缓存且不重新读PDF字节；修改PDF会产生来源失效；force及导出重验保留。

### B 前端状态隔离

文件：`connectivity.js`、新`connectivity-run-state.js`、当前实际加载的`connectivity-shell.js`、`connectivity-matters.js`、`index.html`。未修改旧`connectivity-workspace.js`。

实际控制器DOM集成检查：启动A，连续打开B/C，C先返回、B后返回时只渲染C；A继续状态轮询；没有取消请求或重复POST。重新创建页面上下文时分别恢复A活动入口和C阅读视图。此为DOM工程检查，不冒充浏览器测试。

### C 单事项角色稳定性

文件：`connectivity_matter_agents.py`、`connectivity_matter_pipeline.py`、`connectivity_matter_schemas.py`、`connectivity_matters.py`、新budget/errors模块。保留五角色、A2/A3并行、跨年度证据、引用严格校验、发生期间引文门禁及临时ID统一映射。

合成新建任务 `CONNJOB-AA79476A456B` / `CONN-EC6E8805538A460B`：五角色全部completed，6次调用、余14次；parent_run_id=null、prior_provider_calls=0。**提供方明确注入为synthetic，真实外部模型调用0次。没有真实模型一次成功记录，不能认定C的真实模型验收通过。**

### D 结果页

文件：`connectivity-matters.js/.css`、`connectivity-shell.js`、`connectivity.js`及摘要投影。每个模型任务仍只查1项；批量操作按顺序排多个单事项任务，可清空等待队列。等待队列存在当前页面内，刷新只恢复已创建的活动任务，尚未创建的队列项不会自动续发。

DOM渲染检查：90项档案只先绘制10项待查候选；候选默认收起；初次摘要不请求事项详情；点击后请求一次详情并出现5段证据链。角色卡只取当前事项当前运行最后状态。视觉布局尚未用新版真实浏览器验证。

### E 实际本地HTTP与日志

日志：`task-center-http-measurements.log`；结构化记录：`task-center-http-measurements.json`。通过真实uvicorn HTTP服务并发执行一次活动任务与两份合成历史读取，全部HTTP200。

| 本地测量项目 | 响应体积 | 后端Server-Timing |
|---|---:|---:|
| 运行中状态轮询，3个样本 | 809–941 B | 1.01–3.46 ms |
| 历史摘要，6个并发样本 | 9126 B | 5.18–25.11 ms |
| 单事项首次 | 38510 B | 7.09 ms |
| 同事项再次 | 38510 B | 5.12 ms |

本地没有生产数据库和真实企业全文，以上不是生产延迟或p95。生产数据库锁等待、多实例缓存一致性未验证。文件哈希缓存的读字节计数、命中/失效/force已由API及单元检查验证。

## 已运行检查

- 基准完整后端：1387 passed、33 skipped；改后完整后端：1405 passed、33 skipped，37.41秒。跳过项主要依赖未附带的PDF及历史封存件；测试成功不替代业务验收。
- 前端：35 passed，0 skipped；包含真实控制器与结果渲染的DOM集成检查，运行时显式提供linkedom测试依赖。
- SQL：在嵌入式PostgreSQL实际执行迁移，验证摘要过滤、摘要不含quote、单事项、递归引用证据、缺失事项、过期拒绝、仅service_role调用7项。
- Python编译、JS语法及git差异空白检查通过。
- 中文注释比例检查失败：基准9.94%，改后约9.89%，阈值10%；为基准已存在的仓库级门禁，本轮未为凑比例改动无关功能或降低阈值。

## 复验入口

```bash
python -m pytest backend/tests -q
npm install --prefix /tmp/audittrace-testdeps @electric-sql/pglite linkedom
AUDITTRACE_TEST_NODE_MODULES=/tmp/audittrace-testdeps/node_modules node --test tests/frontend/*.mjs tests/frontend/test_round3_frontend_status.js
AUDITTRACE_TEST_NODE_MODULES=/tmp/audittrace-testdeps/node_modules node scripts/verify_task_center_sql.mjs
python scripts/measure_task_center_http.py --output /tmp/task-center-measurements.json
python scripts/task_center_acceptance_server.py --port 8877 --role-delay 2
```

## 发布依赖与遗留清单

1. **发布前先执行**`supabase/connectivity_read_projection_migration.sql`。它新增稳定只读函数，不改任务数据；API仍执行会话授权。未部署此函数时新分层接口返回503，不退回全量读取。生产迁移未执行。
2. 新版真实浏览器视觉、Network、运行中切换企业历史、刷新恢复验收未完成。已连接浏览器访问执行环境127.0.0.1:8877返回ERR_CONNECTION_REFUSED。修改前生产网页已实际查看，不能用它的截图证明新版本。
3. 本地无真实模型密钥；缺少真实企业单事项五角色一次成功、实际错误分布和预算余量记录。不得把合成结果改名为真实模型验收。
4. 生产SQL性能、锁等待、多实例缓存尚待部署后验证；缓存均在进程内，不跨实例共享。
5. 批量等待队列刷新后不自动续发。已创建的活动任务保留并恢复入口；用户可重新勾选尚未创建的候选。
6. 原仓库的中文注释比例检查仍失败（基准已失败）。
7. 功能分支推送被自动审批拒绝，理由是缺少外部发布修改文件的明确授权。本地提交保留，未合并main、未触发生产部署。

严格验收结论：本轮交付代码、基线、工程验证与复验工具；**未达到任务书要求的全部生产/真实模型验收条件**。
