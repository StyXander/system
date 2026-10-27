# 任务中心改造基线（2026-10-27）

基准提交：`34a6b8a`。修改前核实；不得将本文件中的历史模型回执视为本轮新建任务验收。

## 代码核实

| 检查项 | 结论 | 修改前位置与证据 |
|---|---|---|
| public 重复读取 | 确认 | connectivity_api.py:79–80 public 调 snapshot；:279 read 先 task；demo_run_tasks.py:713 snapshot 再 get |
| PDF 整文件哈希 | 确认 | connectivity_graph.py:341 path.read_bytes |
| 轮询全字段 | 确认（位置已变化） | demo_run_tasks.py:667 get 调 supabase_adapter.py:482 get_demo_run_task，:486 select=* |
| 历史打开中断轮询 | 确认 | connectivity.js:5 单 task/timer/generation；:712–715 打开历史清 timer、清 task |
| 当前首页脚本 | 确认 | index.html:18–19 加载 connectivity.js、connectivity-shell.js；旧 workspace 未加载 |
| 长文与混合角色卡 | 确认 | connectivity-matters.js:57 planningHtml 全部拼接；角色投影未隔离父任务 |
| 通用 Agent Schema | 确认 | connectivity_matter_agents.py:81 AgentMatterResult.model_json_schema |
| 90 块兜底与轮次 | 确认 | connectivity_matter_pipeline.py:182；max_role_rounds 默认2，另有最终综合、校验重试 |
| 分层接口 | 已变化 | connectivity_api.py:156 /runs 已分页；:283 matters、:290 detail 均 public 完整读取。没有 /summary。shell.js:105 历史主要 localStorage |

## 修改前测量

生产地址：https://audittrace-demo.onrender.com/ 。HTTP 样本取自同一执行环境的 urllib；无缓存的单次样本，不是 p95，也不等同浏览器 Network。

| 项目 | 修改前 | 证据/限制 |
|---|---:|---|
| 历史列表 HTTP 响应 | 1,739 B / 4,592 ms | GET /api/connectivity/runs，200 |
| 历史详情 HTTP 响应 | 2,160,490 B / 9,701 ms | DEMO-RUN-6BBECD0E03A8，200 |
| 浏览器历史列表首次可见 | 未精确测量 | Edge 实际点击后列表可见；原列表来自 localStorage，不能冒充服务端加载指标 |
| 浏览器历史详情 | 未精确测量 | 实际点击后先出现等待页，后出现长文结果。点击动作返回1,028ms时仍在等待，不是详情完成耗时 |
| 运行中轮询响应/服务端耗时 | 未测 | 不接管用户已有活动任务；生产 uvicorn 日志没有 duration/bytes 字段 |
| 运行时点击历史的连续性 | 静态确认存在缺陷，动态未验 | 打开历史清除共享定时器与 generation |
| 本轮新建模型调用数/错误 | 未测 | 改造前没有创建付费运行 |
| 历史任务调用（仅诊断） | 17次；Schema失败2次 | 伊利上述任务 provider_calls；非本轮新建运行 |

已通过 Render 只读日志确认上述 GET 200，服务 `srv-d9hnc7jeo5us73ehi1c0`，用户确认工作区 `123`。请求型日志查询为空，应用访问日志只有方法、路径、状态；因此无法反推服务端处理耗时。浏览器接口未暴露 Network/HAR；后续增加服务端计时后分别报告本地测量和生产未验证项。

## 阶段对比

### A、B 工程检查（尚不构成生产验收）

使用同一伊利历史响应作为本地台账样本；本地没有该企业 PDF，读取如实标记来源失效。FastAPI TestClient 单次测量，无生产网络/数据库延迟，不能与生产耗时作加速倍数比较。

| 同一历史样本的本地读取 | 字节 | 本地总耗时 |
|---|---:|---:|
| 完整兼容入口 | 2,244,062 | 209.24 ms |
| 轻量状态入口 | 1,103 | 3.14 ms |
| 摘要首次 | 60,781 | 10.37 ms |
| 摘要再次（规范化缓存） | 60,781 | 6.79 ms |

状态体积相对本地全量降低99.95%；相对生产原始响应降低99.95%。摘要仍包含较长清单，D阶段继续收敛呈现。测试验证远端状态使用字段投影、单事项仅一次RPC、完整兼容读取仅一次get、文件未变化不重读字节/变化后重算/force重算。后端15项与前端2项检查通过；既有事项权限与导出检查通过。

改动文件：connectivity_api.py、demo_run_tasks.py、connectivity_graph.py、新read_models/source_cache；connectivity.js、connectivity-shell.js、connectivity-matters.js、新run-state脚本及index.html；新增只读SQL函数、测试。已加入Server-Timing与访问计时日志。

未验证：生产SQL函数尚未执行、新版浏览器并发验收尚未运行、真实模型新建任务尚未运行。A/B实现可检查，验收状态仍为待验证。


### C / D / E最终记录

C已加入角色专用合同、单事项门禁、角色预算和结构化错误；合成新任务6次调用完成五角色，真实模型未验。D已加入摘要、证据链、按需详情和10项候选分页，DOM检查通过，真实浏览器未验。E实际本地HTTP并发样本、逐阶段文件清单、最终数值及发布限制见[交付与验收记录](task-center-acceptance.md)。最终后端1405 passed、33 skipped，前端35 passed。原仓库中文注释比例检查仍失败；生产SQL、真实浏览器及真实模型验收未完成。
