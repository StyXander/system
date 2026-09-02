"""把自动化测试日志与可供人工复核的开发运行记录隔离。"""

import os


os.environ["AUDITTRACE_RUNTIME_NAMESPACE"] = "pytest"
