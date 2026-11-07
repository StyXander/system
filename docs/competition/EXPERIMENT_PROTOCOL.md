# 技术效果实验协议

G1为单模型无口径约束，G7为单模型加约束，G6为五智能体无约束，G3为完整五智能体。各组保留来源及引文真实性检查，使用相同任务、底座模型、证据、参数和总预算上限。记录实际Token、成本、失败和耗时。单模型允许多轮自检。

先在固定候选证据包中评估推理和约束，再从共享报告集合进行端到端测试。固定证据ID文件必须覆盖所选事项的身份原文。初筛候选默认冻结于每次运行开始，比较时核对fixed_evidence_sha256一致。比较运行关闭额外反馈以避免消融条件连带改变补查机会。

```bash
python scripts/run_final_comparison.py --report-set REPORT_SET_ID --matter-id MATTER_ID --case-id CASE_ID --factor-design --experiment-mode fixed_evidence --allow-models --repeat 3 --output outputs/comparison/CASE_ID
python scripts/evaluate_matter_benchmark.py --comparison-json outputs/comparison/CASE_ID/comparison.json --gold-cases PATH_TO_REVIEWED_GOLD --output-report outputs/comparison/CASE_ID/evaluation.json
```

预算参数为--max-provider-calls及--max-role-rounds，证据ID列表为--evidence-ids。所有组实际用量和停止原因均保留。相同调用上限仅为预算控制的一部分，后续比较需检查实际Token和成本。

金标文件为scenarios数组。每项含case_id、matter_id、source_document_ids、split、annotations、adjudication与gold_evidence_ids。两名标注员独立填写verdict，分歧由专业人员复核。adjudication.final_verdict只接受五个标准代码。不同企业或同一项目的不同年度按项目簇隔离。样例不能填写真实准确率。

关系支持不自动转为金额一致。只有明确numeric_consistency为consistent且口径可比、证据齐全时才投影为确认一致，当前生产assessment无数值核验状态的记录保持证据不足。项目关系任务应另定义关系标签和指标。

FCR分母为0时为null，报告显示N/A。分类指标同时显示完成率、失败率、正确确证召回及覆盖。当前评价按group、mode、repeat分别输出，比较前核对各组覆盖相同案例，不能把同一案例重复运行当作新独立样本。结果不预设优势。

开发集先用6个事项，独立挑战集可用16个事项覆盖五类结论。需要第三方独立标注。扩展规模及置信区间依据资源和预期效应确定。
