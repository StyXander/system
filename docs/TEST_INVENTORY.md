# 测试清单

- 测试文件数：34
- 测试项数：349
- 需要外网的测试文件数：10

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
