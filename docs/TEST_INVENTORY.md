# 测试清单

- 测试文件数：47
- 测试项数：502
- 需要外网的测试文件数：10

## 2026-09-09 数据链路缺陷回归

对应 `docs/2026-09-09_代码与运行逻辑审查及开源对照优化方案.md` 的五个反例与两处结构风险：

| 测试文件 | 固定住的缺陷 |
| --- | --- |
| `backend/tests/test_field_column_identity.py` | C01 本期 80／上期 120 取错列；表头无期间列时必须按歧义阻断 |
| `backend/tests/test_knowledge_relevance_gate.py` | C02 无关问题零命中仍返回、权威等级替代相关性、`limit=0`、跨企业误召回 |
| `backend/tests/test_cninfo_retry_policy.py` | C05 503/502/504/408 不重试、403 误标限流、`Retry-After` 未读、重试预算 |
| `backend/tests/test_pdf_identity_validation.py` | C03 名称+代码+类型齐了就能放行错误年度 |
| `backend/tests/test_secure_download.py` | 4.1 先收完再判体积；C04 重定向落点未复校；伪 PDF 只看 Content-Type |
| `backend/tests/test_cninfo_pagination.py` | 4.2 翻页触顶静默返回部分候选 |
| `backend/tests/test_knowledge_ingest_bounds.py` | C04 采集适配器边界与 `MIN_DELAY_SECONDS` 未落实（该模块仍未接入路由） |

## 默认离线边界

`pytest backend/tests -q` 在未配置 DEEPSEEK_API_KEY、未设置 AUDITTRACE_ONSITE_LIVE_SAMPLE、且没有 .env 的干净环境下应当全部通过：真实模型调用一律被就绪门禁挡成确定性备用或失败关闭，外部抓取类用例只在显式开启现场开关时执行。

## 需要外网的测试文件

- `backend/tests/test_backend_pipeline_acceptance.py`
- `backend/tests/test_batch3_cache_manifest.py`
- `backend/tests/test_batch5_privacy_consent.py`
- `backend/tests/test_batch6_industry_rules.py`
- `backend/tests/test_cninfo_pipeline.py`
- `backend/tests/test_competition_demo_plan.py`
- `backend/tests/test_future_system.py`
- `backend/tests/test_provider_readiness.py`
- `backend/tests/test_queue_worker_fencing.py`
- `backend/tests/test_v7_closure.py`

## 复现命令

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r requirements-dev.txt
backend/.venv/bin/python -m pytest -q
```

Windows PowerShell 等价命令见 README_RUN.md 第一节。
