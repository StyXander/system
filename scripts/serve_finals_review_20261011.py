"""本机只读复核实例：复用保存任务，阻断外部网络与模型，隔离运行时目录。"""
import ipaddress
import json
import os
import socket
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dotenv import dotenv_values
for name in dotenv_values(ROOT/".env"):
    if "API_KEY" in name or name.startswith("SUPABASE_"):
        os.environ[name]=""
os.environ.update({"AUDITTRACE_DEMO_MODE":"true","AUDITTRACE_PUBLIC_DEMO":"true","AUDITTRACE_DEMO_USE_EXTERNAL_MODEL":"false","AUDITTRACE_PROVIDER_PROBE_ENABLED":"false","AUDITTRACE_DEMO_TASK_PERSISTENCE":"local","AUDITTRACE_RUNTIME_NAMESPACE":"finals_20261011","PYTHONIOENCODING":"utf-8"})
original_connect=socket.socket.connect
original_connect_ex=socket.socket.connect_ex
def local_only(address):
    host=address[0] if isinstance(address,tuple) else ""
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return host=="localhost"
def connect(sock,address):
    if not local_only(address):raise PermissionError("本轮复核实例阻断外部连接")
    return original_connect(sock,address)
def connect_ex(sock,address):
    if not local_only(address):raise PermissionError("本轮复核实例阻断外部连接")
    return original_connect_ex(sock,address)
socket.socket.connect=connect
socket.socket.connect_ex=connect_ex
raw=ROOT/"outputs/决赛整改_2026-10-09/e29c175_线上真实模型/原任务与真实结果.json"
task=json.loads(raw.read_text(encoding="utf-8"))
target=ROOT/"runtime/finals_20261011/demo-run-tasks"/(task["task_id"]+".json")
target.parent.mkdir(parents=True,exist_ok=True)
target.write_bytes(raw.read_bytes())
import uvicorn
from backend.app.main import app
uvicorn.run(app,host="127.0.0.1",port=8031,log_level="warning")
