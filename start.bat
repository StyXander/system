@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================================
echo   审迹智链 (AuditTrace) - 跨报告证据链与智能鉴证系统
echo ========================================================

rem Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+ 并加入 PATH。
    pause
    exit /b 1
)

rem Create .env if missing
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [提示] 已基于 .env.example 生成 .env 配置文件。
    )
)

echo [1/2] 正在初始化本地环境与元数据...
python -m backend.app.connectivity_bootstrap --allow-missing-sources

echo [2/2] 启动服务 (访问地址: http://127.0.0.1:8877)...
python -m uvicorn backend.app.connectivity_app:app --host 127.0.0.1 --port 8877

pause
