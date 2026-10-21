# 贡献指南

本项目是 FastAPI + 静态前端的单仓库 Python 项目。核心业务是**年度报告与可持续发展报告的披露关联核对**，不是通用文档问答。

## 环境准备

- Python 3.12（CI 与当前验收环境实测版本；更低版本未验证）
- Node.js 仅在前端契约测试需要（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` 已包含 `requirements.txt`，一次安装即可具备运行与测试依赖。

## 本地运行

```bash
cp .env.example .env          # Windows: copy .env.example .env
python -m backend.app.connectivity_bootstrap --allow-missing-sources
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>。不要直接双击 `index.html`，页面必须由 FastAPI 提供。

- `.env` 中的模型 Key 可选。留空 Key 时仍可用确定性计算路径；如需强制不联网，设置 `AUDITTRACE_DEMO_USE_EXTERNAL_MODEL=false`。
- 仓库不包含第三方年报 PDF。需要完整关联核对时，用 `scripts/register_connectivity_sources.py` 登记你自己下载的公开报告。

## 运行测试

```bash
# 快速契约测试（约 10 秒）
python -m pytest backend/tests/test_release_contract.py -q

# 完整回归
python -m pytest -q

# 前端状态机契约（需要 Node）
node --test tests/frontend/connectivity-status.test.mjs
```

提交前至少跑通前两条。测试被跳过（skipped）不等于通过，请在 PR 中说明跳过的用例和原因。

## 提交 Issue

使用仓库的 Issue 模板（Bug 报告 / 功能建议）。请务必写清：

1. 现象与发生时间；
2. 最小复现步骤；
3. 期望结果与实际结果；
4. 操作系统、Python 版本、是否配置了模型 Key；
5. 相关日志——**提交前删掉 API Key、`.env` 内容、私有文件路径和真实企业内部资料**。

不提供年报全文也能报 Bug：说明使用的报告类型（年报/ESG）和页码即可。

## 提交 Pull Request

1. 从 `main` 开分支，分支名建议 `fix/`、`feat/`、`docs/` 前缀；
2. 只改与本 PR 目标相关的文件，不做顺带重构；
3. 在 PR 描述中写：改了什么、为什么、跑过哪些测试及结果、对现有接口/合同的影响；
4. 涉及数据合同（`backend/app/connectivity_schemas.py`、结果导出格式）的改动，必须同时给出兼容性说明。

CI（`.github/workflows/tests.yml`）会在 Pull Request 上运行契约测试与完整回归。任一失败视为未就绪。

## 代码风格

- 遵循现有文件风格：模块级 docstring 用中文说明"这段代码在业务上保证什么"；
- 新增判断逻辑必须能被测试直接验证，不要只写注释；
- 金额与比例一律使用 `Decimal`，不得用 `float` 做核对运算；
- 缺失数据保持空缺（`unknown`），不得估算、补造或用同类指标替代。

## 不得提交的内容

以下内容不进入仓库，已在 `.gitignore` 中限制，但**不要依赖 .gitignore 兜底**：

- `.env`、任何真实 API Key、Token、数据库密码、Supabase Service Role Key；
- 第三方年报 / 可持续发展报告 PDF 全文及其扫描页图片；
- 真实企业内部资料、客户数据、未脱敏的个人信息；
- `runtime/`、本地 SQLite、模型原始调用响应、缓存与运行日志；
- 竞赛答辩材料、讲稿、PPT 等非代码交付物。

## 专业边界

本项目输出是**核对线索与证据定位**，不是审计结论、鉴证结论或鉴证意见。任何 PR 不得把"数字相符"改写为"披露真实"，也不得删除结论中的不确定性标注（`unknown` / `not_comparable` / 依据不足）。

## 许可证

本项目以 **AGPL-3.0** 发布，详见 [LICENSE](LICENSE) 与 [PROJECT_LICENSE.md](PROJECT_LICENSE.md)。

提交 Pull Request 即表示你同意以 AGPL-3.0 授权你的贡献。本项目未采用 CLA。

如果你所在组织不接受 AGPL 类许可证，请注意：通过网络提供服务同样会触发源码提供义务（AGPL 第 13 条）。

## 安全问题

请勿通过公开 Issue 报告安全漏洞，改为按 [SECURITY.md](SECURITY.md) 的流程处理。
