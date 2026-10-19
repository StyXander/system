$ErrorActionPreference = 'Stop'
$releaseRoot = Split-Path -Parent $PSScriptRoot
$officePreflight = Join-Path $env:USERPROFILE '.codex/skills/.shared/office-com/scripts/office_com_preflight.ps1'
$check = & $officePreflight -Apps PowerPoint,Word | ConvertFrom-Json
if (-not $check.can_use_com) { throw ('请从已登录桌面的普通PowerShell运行：' + $check.reason) }
$pptSource = Join-Path $releaseRoot 'outputs/ai4/materials/答辩PPT_原模板修订候选_待渲染.pptx'
$renderDirectory = Join-Path $releaseRoot 'outputs/ai4/materials/rendered'
& (Join-Path $env:USERPROFILE '.codex/skills/pptx-win/scripts/export_slides.ps1') -InputPath $pptSource -OutputDir $renderDirectory
Write-Output '逐页检查PNG及原文件重开；检查完成前不可把候选稿改称正式提交件。Word请在桌面Word打开，更新目录后导出PDF并逐页核对。'
