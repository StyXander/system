# 安全策略

## 支持范围

仅当前 `main` 分支的最新提交接受安全修复。历史分支、竞赛快照和 `archive/` 下的存档材料不再回溯修补。

## 报告漏洞

**请不要在公开 Issue 中提交漏洞细节、可复现的利用代码或任何真实数据。**

优先使用 GitHub 的私密通道：

1. 仓库 **Security** 标签页 → **Report a vulnerability**（Private vulnerability reporting）。
2. 该功能需要仓库所有者先在 **Settings → Code security → Private vulnerability reporting** 中启用。若该入口不存在，说明尚未开启。
3. 尚未开启时，请开一个**不含技术细节**的公开 Issue，仅说明"需要私密安全通道"，维护者会提供后续方式。

不要向仓库或 Issue 提交 API Key、`.env` 内容、Supabase Service Role Key、真实企业内部资料或个人身份信息。如果已经提交，**删除文件不足以消除泄露**，必须立即在供应商侧吊销并轮换密钥。

本文件不承诺响应时限。维护者为学生团队，实际响应取决于学期安排；如实说明比承诺一个无法兑现的 SLA 更有用。

## 项目安全边界

### 数据处理

- 系统只应处理**公开来源**的年度报告与可持续发展报告（如巨潮资讯网）。
- 企业内部资料、客户原始底稿默认不上传公共站点。正式使用应部署在审计师本机、事务所内网或私有环境。
- 仓库**不包含**第三方报告 PDF 全文。`.gitignore` 阻止 `*.pdf` 入库，但这不是版权或安全的充分保障。

### 已实现的防护

| 风险 | 现有措施 | 位置 |
|---|---|---|
| 下载任意地址（SSRF） | 只允许巨潮 / 深交所 / 明确标注的新浪公告镜像三类官方域名，正则不匹配直接拒绝 | `backend/app/connectivity_extraction.py`（`ensure_source`） |
| 下载 SSRF / 无限重定向 | 逐跳复校目标地址，限制重定向跳数，体积上限在接收过程中生效 | `backend/app/secure_download.py` |
| 下载到被替换的报告 | 下载时比对登记表中的 SHA-256；不一致即 409 停止读取，不用其他版本替代 | `backend/app/connectivity_extraction.py` |
| 文件类型伪装 | 期望 PDF 时以文件头 `%PDF-` 为准，`Content-Type` 仅作辅助 | `backend/app/secure_download.py` |
| 证据文件被篡改 | 边读边算 SHA-256，成功后原子替换目标文件 | `backend/app/secure_download.py` |
| 并发读取 PDF 崩溃 | 解析与页图渲染共用进程级锁 `PDF_ACCESS_LOCK` | `backend/app/source_viewer.py` |
| 模型编造证据 | 模型提案的引用须通过 `validate_refs` 逐条校验，无依据的新关系不采纳 | `backend/app/connectivity_engine.py` |
| 模型被原文提示注入 | 模型只输出结构化提案，事实与结论层由确定性代码生成 | `backend/app/connectivity_pipeline.py` |
| 公开实例被刷模型调用 | 服务端配额秘密 + 并发/全局/每日预算 | `backend/app/main.py` |
| 模型传输未授权 | 按案例记录 consent，可撤销 | `backend/app/main.py`（`/api/cases/{case_id}/model-consent`） |
| 跨用户读取他人任务 | 历史列表只返回当前浏览器会话任务，无会话返回 409 | `backend/app/connectivity_api.py` |

### 部署注意

- `AUDITTRACE_TRUST_LOOPBACK` 仅限本机开发置 1，对外部署必须留空，否则内部诊断接口可读。
- `AUDITTRACE_TRUSTED_PROXY_HOPS` 与 `AUDITTRACE_TRUSTED_PROXY_CIDRS` 必须同时配置，否则不信任 `X-Forwarded-For`。
- `AUDITTRACE_PUBLIC_QUOTA_SECRET` 必须是至少 32 位服务端随机值，不得写入前端构建物。
- 密钥一律通过服务端 Secret 注入；`.env` 永不入库。

## 已知风险（尚未修复）

以下问题在本次开源准备审查中被记录，**尚未处理**：

1. **缺少自动化依赖漏洞扫描**。CI 目前不运行 `pip-audit`，依赖漏洞依赖人工检查。本次审查用 `pip-audit` 手工扫过 `requirements.txt` 与 `requirements-dev.txt`，结果均为 0 漏洞，但没有持续机制。
2. **未接入任何密钥扫描器**。当前依靠 `.gitignore` 与人工审查，没有 pre-commit 或 CI 级密钥扫描。
3. **两个历史文档含本机绝对路径**（`archive/2026-09-02/历史报告/审迹智链_剩余任务执行计划_2026-08-09.md`、`docs/superpowers/plans/2026-09-03-三AI协作总调度计划.md`）。不含密钥，仅为路径信息。
4. **历史提交元数据含一个真实个人邮箱**（`StyXander` 账号）。已存在于公开历史，清除需历史重写，本次未执行。

## 许可相关约束（已解决冲突，但约束仍在）

**PyMuPDF 的 AGPL-3.0**（`backend/app/` 多处 `import pymupdf`）曾是许可阻断项。2026-10-21 已通过将整仓改为 **AGPL-3.0** 解决，当前不构成冲突。但由此产生两条约束：

- 本项目不能改以 MIT / Apache-2.0 发布，除非先移除 PyMuPDF；
- 对外提供网络服务时，须按 AGPL 第 13 条向使用者提供完整对应源码。

详见 [PROJECT_LICENSE.md](PROJECT_LICENSE.md) 与 [docs/LICENSING_DECISION.md](docs/LICENSING_DECISION.md)。

## AI 输出不构成专业结论

系统中的 AI 意见用于**核对线索与后续调查参考**，不构成审计结论、鉴证结论或鉴证意见。"数字相符"不等于披露真实，"依据不足"和"不可比"也不等于未发现矛盾。安全问题的修复不得以降低这些边界标注为代价。
