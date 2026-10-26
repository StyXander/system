# 审迹智链 ModelScope 部署

正式空间：https://modelscope.cn/studios/burgerhaamm/audittrace

全屏入口：https://modelscope.cn/studios/burgerhaamm/audittrace?mode=full

当前运行同一套五Agent可持续事项调查、双塔Canvas首页与自然档案馆绿色工作台。前端仍为根目录`index.html`及`assets/official-v4/`；后端正式入口为`backend.app.connectivity_app:app`。不建立另一套业务网页。

## 打包与发布

在已提交、运行文件干净的工作区执行：

```bash
python deploy/modelscope/prepare.py
```

输出在`tmp/modelscope-deploy/repo/`。白名单只收集运行文件，扫描密钥，排除全文PDF、本地运行目录与私有会话。`.gitattributes`保留原始换行及创空间要求的LFS规则；推送时保留原创空间Git历史，禁止强推。上传凭据不进入代码或远端URL。

将打包目录同步至现有创空间仓库master并提交推送后，在“空间管理”点击“重新部署”，核对文件变化，再点击“确认部署”。推送文件本身不会更新正在运行的镜像。构建成功与服务实际启动也须分别确认。

Docker监听`0.0.0.0:7860`，沿用现有免费2v CPU/8G内存实例。依赖通过阿里云镜像安装，并使用项目约束文件。服务密钥仍由平台管理：`DEEPSEEK_API_KEY`、`SUPABASE_SERVICE_ROLE_KEY`、`SUPABASE_URL`、`AUDITTRACE_PUBLIC_QUOTA_SECRET`；不得写进镜像。个人演示设置`AUDITTRACE_SINGLE_USER=true`，报告接入、模型运行与历史操作无需组织登录，取消每日token、次数和频率配额。旧平台配额变量即使存在也不会生效。

新事项入口默认启用；关闭`CONNECTIVITY_MATTER_ENABLED`可阻止新事项运行并保留历史读取。Supabase须先执行`supabase/connectivity_matter_migration.sql`；2026-10-26已在原项目执行，新增列、检查点RPC及角色权限已核实。生产多实例并发与专业效果验收仍另行记录。

## 核验

`deployment-source.json`保存逐文件SHA-256、`source_snapshot_sha256`和`source_baseline_commit`。后两者在`/api/health`分别返回；创空间部署提交与GitHub源代码提交是不同身份。配置存在不等于真实模型调用成功。

平台域名`burgerhaamm-audittrace.ms.show`需要短期Studio会话。分享使用上面的官方空间地址，不分享短期Token链接。通过实际页面iframe取得会话入口，放入权限受限的临时文件后运行：

```bash
python deploy/modelscope/verify_http.py --session-file /path/to/private-session-file
```

验证器只读取正式健康、bootstrap、资料集合、首页及静态资源，比较实际字节，不启动模型调用；结束后删除会话文件。Render也可使用同一验证器：

```bash
python deploy/modelscope/verify_http.py --base-url https://audittrace-demo.onrender.com --output-dir outputs/render-http
```

只有ModelScope部署允许两个官方社区域名嵌入；其他部署继续禁止嵌入。真实浏览器还须确认双塔首页、绿色工作区、五Agent资料选择、原文与导出。历史2026-10-14三角色记录不计为本次五Agent效果。真实多年度模型对照、消融及人工专业评价尚未完成。
