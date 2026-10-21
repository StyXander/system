# Third-party notices

本文件列出当前工程直接使用或由运行环境固定安装的主要第三方组件。具体版本以 `backend/requirements-lock.txt` 为准；正式外发前仍应根据实际打包清单复核每个组件的许可证文本和版权声明。

## Python 运行依赖

| 组件 | 当前锁定版本 | 许可证口径 | 用途 |
|---|---:|---|---|
| FastAPI | 0.139.2 | MIT | HTTP API 与页面服务 |
| Uvicorn | 0.51.0 | BSD-3-Clause | 本地 ASGI 服务 |
| Pydantic | 2.13.4 | MIT | 数据模型和结构校验 |
| python-dotenv | 1.2.2 | BSD-3-Clause | 本机 `.env` 配置读取 |
| HTTPX | 0.28.1 | BSD-3-Clause | 测试与 HTTP 客户端 |
| pytest | 8.4.2 | MIT | 自动化测试 |
| PyMuPDF | 1.28.0 | AGPL-3.0 或 Artifex 商业许可 | PDF 文本和页级处理 |
| NumPy | 2.5.1 | BSD-3-Clause | 数值计算 |
| faiss-cpu | 1.14.3 | MIT | 本地向量检索索引 |
| python-multipart | 0.0.32 | Apache-2.0 | 文件上传解析 |
| python-docx | 1.2.0 | MIT | Word 文档处理 |
| openpyxl | 3.1.5 | MIT | Excel 评估记录处理 |

运行依赖还会带入 Starlette、AnyIO、h11、httpcore、typing-extensions、certifi、click、packaging、pluggy、Pygments、PyYAML、lxml、watchfiles、websockets 等传递依赖。它们的版本和元数据保存在锁定文件及本机环境中，生成外发包时应重新导出并扫描，不得只依赖本摘要。

## 2026-09-08 交付面复核补登记

下列组件由 `scripts/check_delivery_surface.py` 从四份依赖文件解析出，原先只在上一段以“等传递依赖”概括。许可证取自本机 `backend/.venv` 内该分发包的 PyPI 元数据（`Metadata-Version 2.x` 的 `License-Expression` 或 `License :: OSI Approved` 分类），登记时点为 2026-09-08；本机未安装的组件一律写“待核验”，不按记忆填写许可证。

| 组件 | 本机版本 | 元数据声明许可证 | 来源 |
|---|---:|---|---|
| annotated-doc | 0.0.4 | MIT | 运行依赖传递 |
| annotated-types | 0.8.0 | MIT | 运行依赖传递 |
| colorama | 0.4.6 | BSD License（分类项，未给 SPDX 表达式） | 运行依赖传递 |
| et_xmlfile | 2.0.0 | MIT | 运行依赖传递 |
| httptools | 0.8.0 | MIT | 运行依赖传递 |
| idna | 3.18 | BSD-3-Clause | 运行依赖传递 |
| iniconfig | 2.3.0 | MIT | 测试依赖传递 |
| pydantic_core | 2.46.4 | MIT | 运行依赖传递 |
| typing-inspection | 0.4.2 | MIT | 运行依赖传递 |
| playwright | 1.62.0 | Apache-2.0 | 验收工具链 |
| axe-playwright-python | 0.1.8 | 元数据未声明许可证，待核验 | 验收工具链 |
| pillow | 本机未安装 | 待核验 | 验收工具链 |
| pypdf | 本机未安装 | 待核验 | 验收工具链 |
| pypdfium2 | 本机未安装 | 待核验 | 验收工具链 |

外发前必须按实际打包清单重新导出这一节：版本会变，且 `colorama`、`axe-playwright-python` 等条目仍需回到包内 LICENSE 文本核对，不能只凭元数据分类项。

## 网页图标

`assets/icons.svg` 中的线性图标路径使用了少量改编的 [Lucide](https://lucide.dev/) 内容，按 MIT License 使用。

Copyright (c) 2022 Lucide Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 特别注意：PyMuPDF（当前许可阻断项）

PyMuPDF 采用 **AGPL-3.0 或 Artifex 商业许可** 双轨授权。本仓库对它的使用位于核心链路，不是可替换的边缘依赖：

| 文件 | 用途 |
|---|---|
| `backend/app/rag.py`、`backend/app/field_extraction.py` | 逐页文本抽取 |
| `backend/app/source_viewer.py`、`backend/app/connectivity_api.py` | 证据页渲染为 PNG |
| `backend/app/connectivity_extraction.py`、`backend/app/connectivity_bootstrap.py` | 报告解析与就绪校验 |
| `backend/app/cninfo.py`、`backend/app/cases.py` | PDF 身份校验（文件头 / 页数 / 企业 / 年度） |
| `backend/tests/` 7 个测试文件，`scripts/browser_demo_structured_output_audit.py` | 测试与验收 |

以 `import pymupdf` 方式进程内链接，构成强耦合。

因此：

- 给本仓库添加 MIT 或 Apache-2.0 的 `LICENSE` **不能**解决合规问题，反而会与该依赖冲突；
- 合规路径只有三条：整仓采用 AGPL-3.0、以商业许可获取 PyMuPDF、或替换为宽松许可的 PDF 库；
- 完整分析与待决事项见 [docs/LICENSING_DECISION.md](docs/LICENSING_DECISION.md)。

在许可证正式确定前，项目保持竞赛评审与受控技术复验边界。本文件不构成法律意见。
