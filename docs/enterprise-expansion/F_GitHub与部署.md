# GitHub 同步与生产业务验收

应用发布提交：`7eb8c6235bba552ff6328eec048b7972d0708a8e`。生产入口：[审迹智链](https://audittrace-demo.onrender.com)。2026年10月23日晚实际读取运行时提交，匹配该 SHA；版本 `2026.10.23.enterprise.1`。后续验收文档提交不改变已发布的应用源码。

- [PR #7](https://github.com/StyXander/system/pull/7)：企业搜索、真实双报告登记、案例扩容与交付材料，正常 merge 到 main。
- [PR #8](https://github.com/StyXander/system/pull/8)：修复 Render 保存旧启动命令导致新接口404的问题，正常 merge 到 main。
- [最终应用 GitHub CI](https://github.com/StyXander/system/actions/runs/39947139606)：1337 passed、33 skipped，前端29 passed；0失败。CI没有附带原件，不把跳过项算通过。
- 最终本地带原件全库：1341 passed、29 skipped、0失败；五批源码哈希冻结一致。与CI相差的4项是原件集成测试。详细回执见 evidence/test-summary.json。

Render部署 `dep-dbdkdqh5efls73av9150` 对应上述应用提交；GitHub部署状态于2026-10-23 11:40:33 UTC返回 success，随后另做业务检查。实际 `/api/health` 返回正式入口 `backend.app.connectivity_app:app`，目录接口200、Supabase共享持久化、16家企业17组报告34份原件，17组均就绪。没有仅凭部署平台 success 判定业务成功。

公网浏览器实际执行：进入工作台 → 搜索601012 → 确认隆基 → 查询2025双报告，返回同年度官方年报与可持续发展报告。匿名会话只能查询元数据和选择已验证案例，新下载与真实模型保留组织授权边界；没有冒充已执行公网登录。

伊利公网程序任务 `DEMO-RUN-8231AAA03D92`：从正式页面选择并启动 calculation_only，最终 completed、5条规则候选、零模型调用，文档和引用均属伊利。首次浏览器等待240秒时仍在运行，随后任务完成；恢复的是同一个任务，没有重复提交。结果页可见，原文及JSON、CSV、DOCX导出均200；桌面1440×1000、手机390×844无页面异常或横向溢出。截图和结构化回执见 evidence/production-*。

官方双报告查询首轮返回繁忙，后来重试成功；没有把繁忙响应当作配对成功。新增企业未登记时仍依赖官方接口可用性和组织下载权限，不能承诺任意公司现场均能即时完成。免费实例的本次耗时超过240秒，不承诺90秒结束。

本轮仅一次真实模型试跑在本机以官方双报告上下文调用 DeepSeek：3次请求、176683 Token，状态 three_agents_partial、最终有效AI意见0。A3部分意见未通过年度、原文、数值和专业边界校验，修复请求被已授权停止线阻止。完整真实多智能体成功0家；没有追加付费调用，也没有把本机试跑升级为公网模型验收。

保留的过程失败：首次GitHub CI因原件缺失却触发外网下载而失败，随后加入明确的离线合成合同并保留有原件时执行的真实集成测试；首次旧启动命令子进程验收发生Windows退出码3221225725，隔离复验5项与最终全库均通过。上述失败没有删除或改写为首次成功。

原工作目录未提交成果保持原样。远端 `feat/financial-impact-penetration` 的并行新增模块没有被覆盖或擅自视为本轮已验收；本轮复用现有财务关联层，未将那个独立分支混入发布。没有强制推送或重写main历史。

验收文档的最终合并采用 `[skip render]`，保留已实测的应用提交，避免纯证据更新再下载一遍原件；GitHub CI照常运行。这是Render的[官方自动部署跳过机制](https://render.com/docs/deploys#skipping-an-auto-deploy)，不跳过业务测试，也不改动服务配置。
