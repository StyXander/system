# 当前工作区复核记录

复核日期：2026-09-02

## 已验证没有发现阻断当前主链的代码错误

- 后端全量回归：349 passed，1 warning；唯一 warning 为 Starlette TestClient 与 httpx 的兼容性弃用提示。
- `node --check assets/official-v4/demo-app.js`：通过。
- `node scripts/check_frontend_contract.mjs`：152 个唯一 ID、159 个引用，通过。
- `python -m compileall backend/app scripts conftest.py`：通过。
- 中文说明性注释：2376/23616 = 10.06%，达到 10% 门槛。
- 本地真实 FastAPI 浏览器复核：1440×1000、1024×768、768×1024、390×844 均通过；9 个状态 axe 违规为 0、键盘折叠/抽屉/打印展开通过、无横向溢出，JSON/CSV 下载成功。
- `/forensic-editorial/` 及其 CSS、JS、图标资源均返回 200。
- 归档后重新启动真实 FastAPI，`/`、`/api/health`、`/api/status`、`/api/cases`、
  `/api/demo/bootstrap` 和 `/forensic-editorial/` 均返回 200。

## 仍需人工处理或单独确认的项目

1. `scripts/build_delivery_packages.py` 仍指向已归档的第三周 DOCX，并指向两份不存在的旧根目录 DOCX：
   `05_第三周任务与成果/08_审迹智链_第三周滚动任务分工_2026-07-25至07-31.docx`、
   `12_审迹智链_闭环整改实施与验收记录_2026-07-28.docx` 和
   `13_审迹智链_0.7.1人工门槛待签与自动指标记录_2026-07-29.docx`。
   这只影响旧交付包构建脚本，不影响当前网站、API 或测试；本轮不修复评委包流程。
2. 本机 `.agents` 下的 `verify_current_documents.py` 可以找到归档文件，但其对旧版
   方案书的内容断言已经过时，实测在第一份文档处失败；它是历史材料核验工具，不属于当前
   网页/API 验收链，暂不改写其专业断言。
3. `scripts/final_artifact_consistency_audit.py` 同样属于旧材料一致性工具，实测在旧的
   `12_...docx` 路径处失败，并且要求旧文档包含已经更新前的测试计数；不影响当前主链。
4. `.pytest_tmp`、`.pytest_tmp2`、`.pytest_tmp3`、`.pytest_tmp4` 等历史临时目录
   仍有 Windows `PermissionError (WinError 5)` 风险；本次扫描对 `.pytest_tmp2` 和
   `.pytest_tmp4` 明确收到“拒绝访问”，未强制删除。全量测试使用系统临时目录已通过。
5. `08_官网V3_ForensicEditorial/` 是旧页面，但仍服务只读兼容路由，暂不移动。
6. Render 当前 `/api/status` 已指向 `9ce8b32dac07a2397d74c66e0a3c3444952030ed`，
   15 个案例和 15/15 RAG 就绪，`full_analysis_ready=true`；`competition_release_ready`
   仍为 false，原因是签字重新批准、人工评分和 fresh production B3 未完成，这不是部署故障。

## 归档原则

当前网页和后端所需文件留在原路径；旧版本优先可恢复移动，只有明确为临时转储且无引用的
文件才删除。任何后续删除 `08_官网V3_ForensicEditorial/` 或旧案例夹具前，必须先更新
路由、测试和部署验收证据。
