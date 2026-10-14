# 使用独立隐藏Word实例只读导出，生成文档逐页核验所需PDF。
param([string]$DocumentName = '*.docx')
$auditRoot = Split-Path -Parent $PSScriptRoot
$auditDocuments = Join-Path $auditRoot '决赛准备/项目同步发布_2026-10-14'
$auditOutput = Join-Path $auditDocuments '核验/Word渲染'
New-Item -ItemType Directory -Path $auditOutput -Force | Out-Null
$auditResults = @()
foreach ($auditFile in Get-ChildItem -LiteralPath $auditDocuments -Filter $DocumentName) {
    $auditDocument = $null
    $auditWord = New-Object -ComObject Word.Application
    $auditWord.Visible = $false
    $auditWord.DisplayAlerts = 0
    $auditWord.AutomationSecurity = 3
    try {
            $auditDocument = $auditWord.Documents.Open($auditFile.FullName, $false, $true)
            $auditDocument.Repaginate()
            $auditPdf = Join-Path $auditOutput ($auditFile.BaseName + '.pdf')
            $auditDocument.ExportAsFixedFormat($auditPdf, 17)
            if (!(Test-Path -LiteralPath $auditPdf)) { throw 'Word没有生成PDF，不能宣称导出成功。' }
            $auditResults += [pscustomobject]@{Document=$auditFile.Name; Pdf=$auditPdf}
    } finally {
        # 某些本机Word实例导出后关闭连接，记录关闭异常；PDF另行打开核对。
        try { if ($null -ne $auditDocument) { $auditDocument.Close($false) } } catch { Write-Warning ('Word关闭文档：' + $_.Exception.Message) }
        try { $auditWord.Quit() } catch { Write-Warning ('Word退出：' + $_.Exception.Message) }
    }
}
$auditResults | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $auditOutput '页数.json') -Encoding utf8
$auditResults | ConvertTo-Json -Depth 3
