# 真实模型运行与可靠性测试报告

## 测试范围

通过Render公开工作台接口执行，密钥保留在服务器。输入为真实登记报告，开发案例用于调试，不属于独立盲测。配置、任务ID及完整结果见runs。
模型请求成功只说明供应商返回有效响应，角色合同及语义校验可能继续失败。下表分别保留请求与工作流状态，不预填准确率。

| 批次 | 组别 | 任务 | 模型状态 | 请求/成功 | 已知输入/输出Token | 耗时秒 |
|---|---|---|---|---|---|---|
| baosteel-fixed | G7 | DEMO-RUN-C188A2713ACF | matter_single_partial | 4/4 | 39010/10670 | 156.1 |
| baosteel-fixed | G6 | DEMO-RUN-75DA8753F6C6 | five_agents_partial | 11/9 | 93701/19704 | 256.3 |
| baosteel-fixed | G3 | DEMO-RUN-6BDE5BC8B244 | five_agents_partial | 12/10 | 112569/23040 | 252.6 |
| baosteel-fixed | G1 | DEMO-RUN-F6B2CBB39D41 | matter_single_partial | 4/4 | 39490/11302 | 126.5 |
| baosteel-fixed-v2 | G7 | DEMO-RUN-D5A63672F83F | matter_single_partial | 4/2 | 35721/11483 | 191.3 |
| baosteel-fixed-v2 | G6 | DEMO-RUN-7A83B19E9AE2 | five_agents_partial | 5/0 | 0/0 | 153.3 |
| midea-fixed | G3 | DEMO-RUN-A50F7A4068D9 | five_agents_partial | 10/9 | 92131/17658 | 265.2 |

## 可复查条件

各组检查fixed_evidence_sha256是否一致，确认模型返回标识、预算及代码版本。不同代码批次只用于开发修复验证，不合并作方法优劣统计。未知Token和费用保持未知。

## 失败与修复

第一轮单模型出现RELATION_ENDPOINT_UNREGISTERED。程序拒绝了未登记关系端点，不能把请求成功计为完整业务完成。修复合并建议的前向引用映射，并让各架构都获得一次预算内的校验反馈修正。
五智能体无门禁组即使全部角色完成，旧代码仍因ablation非none标为partial。修复仅对门禁消融按实际角色完成状态判定，移除角色的实验仍保留跳过回执。

## 专业效果边界

未取得两名人员独立标注和仲裁，当前不报告准确率、FCR下降或工时节省。五类金额结论与关系任务语义尚须按ANNOTATION_GUIDE.md分别标注。

## 工程回归

97项相关Python测试通过，覆盖前向引用整体提交、失败回滚、固定证据、角色合同、完成状态和会计规则。该数量仅代表工程回归，不能作为97个真实企业样本。
