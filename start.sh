#!/usr/bin/env bash
set -e

echo "========================================================"
echo "  审迹智链 (AuditTrace) - 跨报告证据链与智能鉴证系统"
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+。"
    exit 1
fi

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[提示] 已基于 .env.example 生成 .env 配置文件。"
fi

echo "[1/2] 正在初始化本地环境与元数据..."
python3 -m backend.app.connectivity_bootstrap --allow-missing-sources

echo "[2/2] 启动服务 (访问地址: http://127.0.0.1:8877)...
python3 -m uvicorn backend.app.connectivity_app:app --host 127.0.0.1 --port 8877
