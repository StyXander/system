param([string]$BaseUrl = 'http://127.0.0.1:8774')
$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $PSScriptRoot
$demoIndex = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $releaseRoot 'outputs/ai4/demo/demo-index.json') | ConvertFrom-Json
Invoke-WebRequest -Uri ($BaseUrl + '/api/connectivity/runs/' + $demoIndex.task_id) -UseBasicParsing | Out-Null
Write-Output ('录制对象：仅程序计算的已保存本地任务 ' + $demoIndex.task_id)
Write-Output ($BaseUrl + '/?connectivity_task=' + $demoIndex.task_id)
Write-Output '在桌面浏览器打开以上地址，按Win+Alt+R开始Xbox Game Bar录制，依90秒操作脚本演示，再按Win+Alt+R停止。系统未启用Game Bar时用已安装录屏工具；本脚本不谎报录像已生成。'
Write-Output '录制后检查视频可播放、声音清楚且没有密钥、学校信息或私人通知，再放入本地提交目录。'
