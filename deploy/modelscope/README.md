# 审迹智链 ModelScope 部署

空间：https://modelscope.cn/studios/burgerhaamm/audittrace

推荐全屏网站：https://modelscope.cn/studios/burgerhaamm/audittrace?mode=full

容器服务域名为 `burgerhaamm-audittrace.ms.show`，平台对该域名使用短期 Studio 会话校验；分享时使用上面的官方空间或全屏地址，不分享短期 Token 链接。

部署类型为 Docker，免费硬件为平台当前返回的 `platform/2v-cpu-8g-mem`；入口监听 `0.0.0.0:7860`。费用资源不在本次范围内。Docker 需要本人完成阿里云绑定与实名认证。

运行前端仍为工作区根目录 `index.html` 和 `assets/official-v4/`，后端仍为 `backend.app.main:app`。本目录只提供托管适配，不建立第二套网页。

`prepare.py` 从已提交的运行文件白名单构建 `tmp/modelscope-deploy/repo/`，阻止未提交的运行修改、扫描密钥、排除全文 PDF 和本机运行目录，并写入逐文件 SHA-256 清单。其 Git master 分支同步到该创空间，禁止强推。`.gitattributes` 保留源文件字节；云端 `deployment.source_snapshot_sha256` 与包中清单核对，`source_baseline_commit` 表示源码所在 GitHub 提交，与创空间自己的部署提交分别记录。

生产依赖采用 `backend/requirements.txt` 和 `requirements-lock.txt` 的约束，通过阿里云国内软件镜像安装。`app.py` 在运行阶段准备标准来源、公司目录和现有案例台账，再启动网站；构建镜像时不注入密钥。

平台 Secret：`DEEPSEEK_API_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`SUPABASE_URL`、独立生成的 `AUDITTRACE_PUBLIC_QUOTA_SECRET`。模型与任务台账延用现有 DeepSeek、Supabase 配置；完成结果可恢复，运行中任务不自动重放。来源缓存仍按哈希验证，禁止把下载失败写成来源就绪。

新公开入口使用项目受控默认额度：每来源每15分钟2次、全局10次、并发2、每日60次，输入140万及输出15万 token 上限。Render 原评委试用窗口的大额度未复制到此空间。平台免费资源不代表模型调用免费。

服务器只在明确设定 `AUDITTRACE_DEPLOYMENT_PLATFORM=modelscope` 时允许两个 ModelScope 社区域名嵌入；其他部署继续禁止嵌入。状态接口分别标记 ModelScope、源码快照和工作区基线。

验收使用 `verify_http.py --session-file 本地短期会话文件`，加 `--direct` 可核对不经过代理的连接。会话文件由实际页面的 iframe 入口取得，验收结束删除。脚本不创建模型调用。还须在真实浏览器检查四个视口、资料条件检验、原文回查、模型分析、控制台与网络。

2026年10月14日已验证23案加载、资料条件变化、JSON/CSV下载及原文第7页。当天 ModelScope 真实运行 `RUN-V7-7B97487A0326` 的三个角色完成，包含3次模型调用。该记录是当天已完成运行，重新打开页面不代表新增调用。平台外壳在平板与手机宽度仍维持约1280像素布局，窄屏验收未通过；现场使用电脑全屏入口。

AI生成内容，仅供审计计划阶段进一步核查，不构成审计结论或审计意见。
