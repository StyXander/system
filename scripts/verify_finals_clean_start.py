"""在新的目录和虚拟环境复现登记快照启动，不复制密钥、runtime或历史结果。"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def main():
    out = ROOT / "outputs/决赛整改_2026-10-09" / ("干净复现_最终" if "--final" in sys.argv else "干净复现")
    checkout = out / "source"
    checkout.mkdir(parents=True, exist_ok=True)
    files = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    files += ["backend/app/source_corrections.py", "backend/source_corrections_20261009.json", "backend/source_date_verifications_20261009.json"]
    fingerprints = {}
    for name in sorted(set(files)):
        if not name or name.startswith(("outputs/", "backend/runtime/", "backend/.venv/")) or Path(name).name == ".env":
            continue
        source = ROOT / name
        if not source.is_file():
            continue
        target = checkout / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        fingerprints[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    assert not (checkout / ".env").exists()
    environment = out / "venv"
    created = not environment.exists()
    if created:
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    python = environment / "Scripts/python.exe"
    completed = subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--timeout", "12", "--retries", "1", "--index-url", "https://pypi.org/simple", "-r", str(checkout / "backend/requirements.txt")], capture_output=True)
    (out / "依赖安装日志.txt").write_bytes(completed.stdout + completed.stderr)
    record = {"source": str(checkout), "isolated_environment": True, "fresh_environment": created, "env_file_copied": False, "runtime_copied": False, "source_file_hashes": fingerprints, "dependency_install_returncode": completed.returncode}
    (out / "干净环境记录.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print("dependency_install_returncode", completed.returncode, "copied_files", len(fingerprints), flush=True)
    if completed.returncode:
        sys.exit(1)
    env = os.environ.copy()
    for name in list(env):
        if "API_KEY" in name or name.startswith("SUPABASE_"):
            env.pop(name, None)
    env.update({"AUDITTRACE_DEMO_MODE": "true", "AUDITTRACE_PUBLIC_DEMO": "true", "AUDITTRACE_DEMO_USE_EXTERNAL_MODEL": "false", "AUDITTRACE_PROVIDER_PROBE_ENABLED": "false", "AUDITTRACE_DEMO_TASK_PERSISTENCE": "local", "AUDITTRACE_RUNTIME_NAMESPACE": "clean_reproduction", "PYTHONIOENCODING": "utf-8"})
    result = subprocess.run([str(python), "-c", "import json;from fastapi.testclient import TestClient;from backend.app.main import app; c=TestClient(app); b=c.get('/api/demo/bootstrap'); assert b.status_code==200; r=c.post('/api/demo/expanded-cases/000333/preview'); assert r.status_code==200,r.text; a=r.json()['result']['analysis']; assert a['model_check']['provider_call_count']==0; print(json.dumps({'bootstrap_ready':b.json().get('bootstrap_ready'),'registered_cases':b.json().get('case_count'),'run_id':a['run_id'],'analysis_year':a['context'].get('current_year'),'rule_results':a['rule_results'],'provider_calls':0},ensure_ascii=False))"], cwd=checkout, env=env, capture_output=True)
    (out / "干净启动与结构化计算.json").write_bytes(result.stdout)
    (out / "干净启动诊断.txt").write_bytes(result.stderr)
    print("startup_calculation_returncode", result.returncode, flush=True)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
