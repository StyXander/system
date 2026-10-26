# 审迹智链 AuditTrace

面向年度报告与可持续发展报告的财务影响关联与跨期追踪系统。系统围绕可持续事项整理财务路径、承诺进展、竞争解释和下一步证据要求，供财务、ESG及审计鉴证人员复核。

2026年10月26日事项升级版使用五Agent主管线。当前是完成本地工程验证的候选版本，真实模型对照、人工专业评价与生产数据库迁移仍待验收。[修改对照与验证范围](docs/matter-upgrade/implementation.md)、[能力差距](docs/matter-upgrade/feature_gap_matrix.md)、[发布事实](docs/matter-upgrade/release_facts.json)分别记录。

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

单次运行共享20次模型请求上限、至多2个并行请求，默认深查3个事项。其余候选显示在待调查队列。预算耗尽、来源失效或模型失败时保留已有记录及未决问题。当前支持原件核验、文本块检索和可配置的本地语义通道；未配置语义模型时如实记录词法召回。扫描页可选OCR，不可用时展示覆盖限制。

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
