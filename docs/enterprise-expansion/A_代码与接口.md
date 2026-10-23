# 正式企业搜索与双报告接入

正式工作台原来只支持预先登记的报告对。本轮把企业身份发现、同年双报告查询、后台原件校验和现有核验任务接成一条流程，保留默认 three_agents 和既有六类规则。原工作目录的未提交改动没有覆盖；开发在独立分支进行。

| 模块 | 实际改动 |
|---|---|
| connectivity_catalog.py | SQLite 本地目录、Supabase cases 元数据主记录、离线镜像、原子部署快照；不可变版本配对；不在公共目录枚举个人任务链接 |
| connectivity_onboarding.py | 复用公司目录与年报适配器，增加官方 ESG 标题查询；逐跳白名单下载、主体与期间、哈希、逐页文字层处理、空间和并发限制 |
| connectivity_catalog_api.py | 正式身份搜索、报告对查询、目录筛选、接入任务及进度、同源登录与权限；复用 Auth、组织成员表和任务存储 |
| connectivity_extraction.py | load_registry 合并动态目录且不覆盖历史 document_id；扩展有原文依据的行业检索重点，不新增数学算子 |
| connectivity_api.py | 公网新模型调用先验证登录并继续使用旧配额；保存实际运行状态，不把未调用当成功 |
| connectivity_app.py | 正式应用挂载企业与会话路由，保持旧销售收款路由未挂载；发布标识 enterprise.1 |
| connectivity-companies.js / connectivity.js / index.html / workbench.css | 企业搜索与分层、版本选择、真实准备进度、行业/年度/状态筛选；切换仅修改下次运行参数，保留当前结果 |
| expand_company_cases / evaluate_company_cases / verify_* | 官方数据接入、真实程序运行、演示适配评分、重启与空实例恢复、真实浏览器复验 |

接口：GET /api/companies/search；GET /api/companies/{ticker}/report-pair；GET /api/connectivity/catalog；POST /api/connectivity/catalog/imports；GET /api/connectivity/catalog/imports/{task_id}；/api/auth/me、login、refresh、logout。接入成功只返回新 pair_id，运行继续使用原 POST /api/connectivity/runs。

共享部署沿用 AUDITTRACE_DEMO_TASK_PERSISTENCE=supabase，目录默认随之使用 Supabase；无需新增数据库表。只写公开 CONNPAIR 命名空间的 cases.metadata.connectivity_pair，其他租户和旧业务结果不进入搜索。可显式设置 AUDITTRACE_CONNECTIVITY_CATALOG_PERSISTENCE。单实例离线目录与任务均用 local，模型关闭。

报告对身份含双方 SHA-256 指纹。修订只追加版本；同一 AR 与新 ESG 配对时，引用编号也绑定配对身份。PDF 以哈希去重，单份上限 100MB、1800 页，准备并发 2、每实例最多 4 项准备任务；默认原件与解析缓存预算 2GB。身份与元数据查询共用既有限流。公网新下载要求真实组织写权限，新付费模型要求登录；令牌留在 HttpOnly Cookie。

parse_status=complete 指全部 PDF 页经过读取、文字层处理完成，不是所有图像内指标均已 OCR；每份提取覆盖与失败页另列。逐条定义、范围、币种、期间和单位仍由原流水线判断。没有把环保投入等同固定资产增加，也没有新增企业风险评分。
