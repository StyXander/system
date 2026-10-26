# 审迹智链运行与发布说明

本说明适用于 `2026.10.26.matter.1` 候选版本。程序入口为 `backend.app.connectivity_app:app`，根页面为 `index.html`。当前版本尚未取得生产迁移、真实五Agent及人工专业评价的验收证据。

## 环境与启动

```bash
pip install -r requirements-dev.txt
python -m backend.app.connectivity_bootstrap --allow-missing-sources
python -m uvicorn backend.app.connectivity_app:app --host 127.0.0.1 --port 8877
```

复制 `.env.example` 后仅在服务端填写配置。五Agent只向 `api.deepseek.com` 发送已登记报告上下文；密钥不进入浏览器、Git或调用记录。模型名称与接口配置由操作方核实，不把配置存在当作真实调用成功。

本机可明确选择 `AUDITTRACE_DEMO_TASK_PERSISTENCE=local`。生产沿用Supabase任务、公开目录和额度台账；远端不可用时不得静默改用本地写入。旧主模块仍提供额度、登录、安全响应头和导出依赖，不能整目录删除。

## 多年资料与运行合同

`POST /api/connectivity/report-sets` 接收已登记 `document_ids` 与 `as_of_date`，返回不可变集合。`GET /api/connectivity/report-sets` 返回集合及登记文档。不同企业、同年同类型的多个版本、无指纹或晚于观察时点的资料均拒绝。

`POST /api/connectivity/catalog/report-set-imports` 接收证券代码、至多5个年度及已确认企业身份标志。它沿用原接入权限、同源限制、来源核验和异步任务。官方查询不完整会停止，不选择任意首个候选。允许某年度只准备一类报告，缺口单列。

```json
{
  "report_set_id": "由登记接口返回的集合ID",
  "mode": "five_agents",
  "analysis_scope": "matter_connectivity",
  "matter_types": ["climate_risk", "transition_project", "commitment", "resource_efficiency", "other"],
  "budget": {"max_provider_calls":20,"max_parallel_calls":2,"max_matters":3,"max_role_rounds":2}
}
```

旧请求仍用 `pair_id`，缺省模式继续是原三角色。事项范围内的 `single_model` 与 `three_agents` 是显式对照，不剥夺它们的检索工具。`adaptive_agents` 保持原实验流程，不与多年事项合同混用。

`GET /runs/{task_id}/matters` 及其事项详情接口读取同一保存结果。归并、拆分、采用和驳回写入 `matter-revisions` 子版本，要求输入版本、动作编号和理由。一个父版本只接受一个直接子修订；继续修改必须读取子版本。个人演示模式允许在不同浏览器读取、导出和继续整理同一工作区的历史任务。

## 检索与扫描页

默认进行中文双字词项BM25、别名扩展和过滤，记录零命中及覆盖。设置 `CONNECTIVITY_MATTER_EMBEDDING_MODEL` 可加载指定本地sentence-transformers模型并融合排序；需单独安装对应依赖与模型文件，不会自动下载或向其他供应商发送资料。当前未进行真实语义模型质量验证。

扫描页设置 `CONNECTIVITY_MATTER_OCR=true` 后，服务器须具备Tesseract及 `chi_sim`、`eng` 语言包。OCR不可用或未启用时记录未解析页。跨页段落分成各自带页码的证据，以相邻证据编号关联，不拼造单页引文。

## 个人演示模式

本次Render与ModelScope均设置`AUDITTRACE_SINGLE_USER=true`。报告接入、多年资料选择、真实模型运行、历史读取、修订及导出不要求组织登录，历史任务不再按浏览器会话限制访问。平台原有的每日输入/输出token、每日次数和频率配额不再参与放行；即使旧环境变量仍存在，也不会拦截演示。

模型实际调用与usage仍随运行保存，不把未知用量填成零。单次调查的结束条件、工具循环和并行调度属于执行逻辑，不累计成每日使用额度。`/api/health`及bootstrap公开返回实际`access_mode`与`usage_quotas_enabled`，用于确认托管平台已加载个人模式。

2026-10-26已执行的Supabase额度迁移保留；个人模式不申请、检查或结算额度租约，不受旧预算台账与旧租约阻断。任务、检查点和来源仍保存，证据资格与来源哈希检查继续执行。

## 对照与消融

```bash
# 默认只做离线程序检查。不会自行覆盖生产持久化设置。
python scripts/run_final_comparison.py --report-set 实际集合ID --as-of 2026-10-26
# 有模型配置后执行同资料对照，个人模式不设每日用量配额。
python scripts/run_final_comparison.py --report-set 实际集合ID --as-of 2026-10-26 --allow-models --ablations
```

仅需独立本地实验账本时显式添加 `--local`。脚本记录单模型、事项三角色、五角色及移除跨期/反证角色的消融，保存回执、token、耗时、失败及检查点。未配置有效计价时费用保持空值，人工评分未做时专业指标保持未评价。默认运行不自动宣称对照或消融已经执行。

## 发布与回退

先部署到测试环境，检查 `/api/health` 的实际提交、版本、模型配置性质，再验证一条新建路径和一条历史回查路径。核对同一事项的页面、原文及JSON/CSV/Word导出。启用真实流量前补齐真实报告、真实供应商及专业评价证据。

`CONNECTIVITY_MATTER_ENABLED=false` 会关闭新事项运行，默认选择退回原三角色，仍允许读取历史事项结果。它不会把五Agent请求暗换为旧流程。也可回退到本轮基线提交 `6dd5fb26599105946bac1b5c4f6e8759fea5a571`。新增列和RPC可以保留，旧入口不依赖它们；历史数据不因回退而删除。
