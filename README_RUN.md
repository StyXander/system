# 审迹智链 AuditTrace

证据驱动的跨报告自主核验智能体系统。输入为已登记的上市公司年报与可持续发展报告，默认多智能体模式。

## 启动

```powershell
pip install -r requirements-dev.txt
python -m backend.app.connectivity_bootstrap --allow-missing-sources
python -m uvicorn backend.app.connectivity_app:app --host 127.0.0.1 --port 8877
```

服务入口为根目录index.html；业务API仅公开/api/connectivity与/api/health。模型密钥放在未入库的.env中；默认模式three_agents，必须以provider_calls判断实际调用，配置存在不等于模型成功。生产沿用原有Supabase任务与额度台账，不能静默改成本地台账。

## 核验机制

A1发现关系并申请取证，A2质疑可比性并查找反证，A3综合证据和程序复算后形成意见。各角色可以提交本报告内的检索请求；每次最多4项，重复查询不再执行，只有取得新原文才触发一次反馈调查。全运行最多20次模型请求（含修复与意见补全）。正式数值由Decimal引擎计算，反事实结果只存于closure，不回写正式结论。

程序核验为离线/测试模式，单模型为实验基线。模型失败时保留程序结果并显示AI分析未完成；离线、历史和真实模型运行分别留痕。协作视图显示真实回执，不模拟推理进度。

新增 `adaptive_agents` 为可选实验模式：共享补证动作池驱动白名单工具，竞争解释进入同一假设账本，最终排序与实际回执同时保存。未配置模型时明确降级；实际请求、token和模型解释不冒充程序事实。原有三种模式继续保留。

财务图谱默认展示最多12个节点，支持完整图谱、年度和证据状态筛选。读取结果和导出时重新核验两端原件身份，来源失效时保留历史并禁用金额情景。情景单价和实现比例使用同一后端十进制公式，导出通过 `scenario_price` 与 `scenario_usage` 携带相同参数；调整假设不会改写已保存的企业原值。

跨年和同业比较须具备主体、期间、范围、定义、分母及原件身份。登记覆盖矩阵不代表数值已经可比，缺少资格时不生成同比或排名。B组实验脚本默认不调用模型；真实运行必须显式使用 `--allow-models` 并确认预算，未执行的条件保留 `not_run`。

## 验收与边界

```powershell
python -m pytest backend/tests -q
python scripts/check_chinese_comments.py
python scripts/run_closure_experiment.py
```

真实模型对照脚本为scripts/run_final_comparison.py，需要具备合法的资料外发授权及供应商配置。预算仍受每日额度台账约束。独立人工金标准、准确率、节时和商业采用效果不能由工程测试推断。

旧主模块仍因额度、安全头及导出公共依赖保留；旧页面和旧业务API已退出正式发布入口，物理去旧尚未全部完成。删除明细和恢复包见本轮交付目录。禁止把保留的历史实验当作新系统验收。

AI生成内容，用于年度报告与可持续发展报告关联核对和后续调查参考，不构成审计结论、鉴证结论或鉴证意见。
