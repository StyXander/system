# 科创杯材料入口

先查看EXECUTION_STATUS.md和TEST_REPORT.md，区分真实交付、模型降级与仍需外部完成的事项。

| 用途 | 位置 |
|---|---|
| 综合报告与可编辑材料 | deliverables/ |
| 真实运行及失败原始记录 | runs/ |
| 三家企业原文及Word底稿 | dossiers/及deliverables/ |
| 实验协议与标注规程 | EXPERIMENT_PROTOCOL.md、ANNOTATION_GUIDE.md |
| 六个开发问题及独立标注任务包 | development_cases.json、annotation_packet_A.json、annotation_packet_B.json |
| 文献与产品比较 | RELATED_WORK.md |
| 申报信息与贡献确认 | APPLICATION_CHECKLIST.md |
| 技术交底及试用模板 | IP_DISCLOSURE.md、TRIAL_FORMS.md |
| 源码鉴别材料 | ../copyright/current/ |
| 完整计划与190项任务登记 | EXECUTION_PLAN.md、TASK_REGISTER.csv |

生成Word：python scripts/build_competition_materials.py。该脚本只读取保存资料与运行，不会调用模型。

真实模型测试入口：scripts/run_render_comparison.py，明确指定--allow-models；密钥始终在Render。复用同一输出目录恢复相同任务，避免重复付费。实例中断不自动重放请求，应核对回执后建立明确的新测试或使用工作台重试。

所有准确率、提效、应用证明和知识产权状态按真实进展维护。尚未独立标注，不填报准确率。
