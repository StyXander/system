# 审迹智链 AuditTrace

面向可持续信息鉴证项目组的前期跨报告风险调查。接受委托或项目启动后、详细鉴证程序实施前，用五Agent追踪事项、潜在财务影响与跨期证据，形成《风险关注点清单》《资料需求清单》和事项证据档案。系统不自动出具鉴证意见。

2026年10月26日事项升级版使用五Agent主管线。当前已完成工程验证及原Supabase额度迁移，正式发布使用双塔首页和绿色工作台。真实模型对照、人工专业评价及生产多实例压力测试仍待完成。[修改对照与验证范围](docs/matter-upgrade/implementation.md)、[能力差距](docs/matter-upgrade/feature_gap_matrix.md)、[发布事实](docs/matter-upgrade/release_facts.json)分别记录。

个人演示部署无需登录，不设置每日token、运行次数或频率配额；实际模型用量仍随任务记录。开关为`AUDITTRACE_SINGLE_USER=true`，健康接口可核对实际策略。

## 2026-10-27 修复范围

本次只交付GitHub源码，不额外操作Render或ModelScope发布。保留双塔首页、浅绿色自然档案馆工作台和个人免登录模式，无每日token/次数/频率配额。

日期缺失、非法、超出观察时点和版本冲突分别定位到报告；不合格报告保留可见但不默认勾选，可以用其他合格年度继续。BAO24_AR仍缺经官方核实的发布日期，本轮官方查询未成功，未猜填日期。

可先无模型建立事项档案，再选一项真实五Agent深查；默认单事项，反证与复核不删减。失败续跑复用已完成角色，并重算受上游变化影响的复核。临时供应商错误最多重试一次，遵守Retry-After；超过8秒的等待交由用户稍后续跑，每次尝试都计入本次20次保护。HTTP认证/合同错误不盲重试。

结果首屏和Word前部列两份清单，CSV/JSON使用同一来源投影；清单条目可采纳为线索、暂缓或排除，保存子版本与理由。人工工作状态不提升证据支持程度。

**本轮仅做语法/差异检查和本地元数据只读审计，未运行测试套件、浏览器、付费模型或生产验收。** 性能收益和业务正确性待用户验收。[本轮逐项状态与限制](docs/finals/reliability_baseline_20261027.md)。

## 本地运行

```bash
pip install -r requirements-dev.txt
python -m backend.app.connectivity_bootstrap --allow-missing-sources
python -m uvicorn backend.app.connectivity_app:app --host 127.0.0.1 --port 8877
```

打开 `http://127.0.0.1:8877/`。服务仅挂载 `/api/connectivity` 和健康检查等正式入口。密钥填写在未入库的 `.env`，示例见 [.env.example](.env.example)。缺少模型配置时明确显示未执行，保留程序候选，不生成五Agent成功回执。

## 一次事项调查

选择同一企业的多年报告、观察截至日期与关注事项。集合允许缺年、缺少某一类报告；同年同类型不同版本须先选定。无金额气候风险、估计假设和目标叙述可以进入调查。

A1识别事项及身份依据；A2调查财务影响，A3追踪跨期承诺与财务后果，两者并行；A4检查边界、竞争解释与反证；A5综合判断并指定必要补查。角色可以申请检索、打开原页、查询规则和定位数值，程序执行后把实际回执返回。

单次运行共享20次模型请求上限、至多2个并行请求，默认深查1个事项（页面可选2或3项）。其余候选显示在待调查队列。预算耗尽、来源失效或模型失败时保留已有记录及未决问题。当前支持原件核验、文本块检索和可配置的本地语义通道；未配置语义模型时如实记录词法召回。扫描页可选OCR，不可用时展示覆盖限制。

关联支持、金额可比、承诺进展、财务阶段和人工采用分别保存。一般性会计政策不证明具体项目的处理，资本开支、在建余额、转固与现金流不能直接相加。事项调节只输出带证据前提的条件试算；原数值核对流程继续使用既有正式计算门禁。

## 兼容与验证

旧 `pair_id` 请求默认仍为原 `three_agents`；新页面默认 `five_agents`，通过 `report_set_id` 或显式 `analysis_scope=matter_connectivity` 进入事项流程。旧运行、原文地址及导出合同保留原来的含义。历史三角色回执不会改名为五Agent。

```bash
python -m pytest backend/tests -q
node --test tests/frontend/*.mjs tests/frontend/test_round3_frontend_status.js
python scripts/check_chinese_comments.py
python scripts/verify_matter_browser.py
```

浏览器验证使用真实本地API、合成PDF和明确注入的测试提供方，不外发资料。真实对照脚本默认只离线执行；带 `--allow-models` 才发送付费请求，仍受原额度台账及逐请求占额约束。详见 [运行与发布说明](README_RUN.md)。

AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。
