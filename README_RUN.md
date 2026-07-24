# 审迹智链本地启动说明（W3工程版）

## 当前能做什么

- 根目录 `index.html` 是唯一展示网页；FastAPI 提供 `/api/health`、`/api/runs`、运行记录读取和人工复核保存。
- 后端只载入已登记的 `STD_DEV_T0` 标准股份开发资料，支持 2025/2024、2024/2023、2023/2022 三组连续期间。
- 网页勾选 R1、R2 会实际影响本次后端运行。R1使用收入和应收账款四字段；R2使用收入、经营活动现金流量净额，以及净利润增强项。R3—R8仍只是候选项，不会生成风险卡。
- 每个本次运行会生成一个 `run_id`，并把来源、公式结果、规则状态和人工复核保存到 `backend/runtime/runs/`。这是本地开发留痕，不是正式项目档案。
- 规则触发后，后端才会尝试“质疑 → 反证 → 语义复核”三个角色。模型只能基于本次登记的 `evidence_id` 输出结构化草稿；程序会校验 JSON、角色顺序、证据编号和禁用定性词。
- 未配置模型 Key、网络失败或模型输出越界时，系统只返回真实状态，例如 `config_missing`、`provider_unreachable`、`MODEL_OUTPUT_INVALID`，不会补写或伪造 AI 结论。

标准股份字段和来源目前是技术交叉复核后的开发资料，仍待团队人工专业确认。R1/R2均是当前工程版，不是正式审计规则结论。

## 启动

最省事的方法：双击根目录的 `启动审迹智链.bat`。第一次会创建项目专用的 `backend\.venv`、安装依赖、生成空白 `.env`，然后打开网页；以后双击同一个文件即可。黑色窗口不要关，关掉就等于停止后端。

只要看到 `AuditTrace is starting at http://127.0.0.1:8000`，等待几秒后网页会自动打开。若没有自动打开，可手动访问 `http://127.0.0.1:8000`。请通过这个地址打开，不要直接双击 `index.html`，这样网页、API和资源才来自同一个本地服务。

如需手动排查，在工作区根目录执行：

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env -ErrorAction SilentlyContinue
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

## 模型 Key（可选，但真实三Agent成功验收需要）

在根目录 `.env` 填入团队自己的配置后重启服务：

```ini
DEEPSEEK_API_KEY=团队自己的Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=实际可用的模型ID
```

Key 只由后端读取，不能填进网页或提交到仓库。没有 Key 时，R1/R2仍可完成确定性计算、来源校验和人工复核；页面会显示模型未配置。第一次使用有效 Key 后，应重点检查：三角色是否全部完成、每个主张是否只引用本次 `evidence_id`、以及运行记录是否保留模型ID、输入哈希、响应哈希和耗时。

## 验证

在工作区根目录执行：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

当前自动化测试覆盖：健康检查、R1复算、R2字段与公式、无Key不伪造AI草稿、越界证据ID拦截、运行记录与人工复核保存、以及不支持年度阻断。

网页手工核验建议：

1. 选择 2025，同时勾选 R1/R2，确认两条规则、七条来源和“未触发则不调用模型”状态一起显示。
2. 切换到 2023，确认年度、数值、来源文件和页码同步改为 2023/2022；R1会形成当前方向候选，未配置 Key 时显示 `config_missing`，不会显示伪造的三Agent文本。
3. 在“本次运行 · 人工复核”填写处理意见，保存后刷新或通过 `GET /api/runs/{run_id}` 查看本地留痕。

## 当前边界

本版本不含 PDF自动抽取、RAG知识库、官方实时检索、补充资料续分析、正式导出、冻结案例、T0/T1回测或效果结论。真实三Agent成功调用、R1/R2专业口径复核与RAG V1仍是后续阶段任务；未验收前，页面和材料都必须如实标注。
