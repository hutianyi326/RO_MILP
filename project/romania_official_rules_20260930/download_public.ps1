param([Parameter(Mandatory=$true)][string]$SourceList)
$ErrorActionPreference='Stop'
$roDownloadRows=Get-Content -LiteralPath $SourceList -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($roDownloadRow in $roDownloadRows) {
    $roDownloadDirectory=Join-Path 'data/raw/RO/rules/20260930' $roDownloadRow.id
    New-Item -ItemType Directory -Path $roDownloadDirectory -Force | Out-Null
    if ((Test-Path -LiteralPath (Join-Path $roDownloadDirectory 'metadata.json')) -or (Test-Path -LiteralPath (Join-Path $roDownloadDirectory 'download.json'))) {continue}
    try {
        $roDownloadResponse=Invoke-WebRequest -Uri $roDownloadRow.url -UseBasicParsing -TimeoutSec 35
        $roDownloadBytes=$roDownloadResponse.RawContentStream.ToArray()
        $roDownloadExtension=if ($roDownloadBytes.Length -gt 4 -and [Text.Encoding]::ASCII.GetString($roDownloadBytes,0,4) -eq '%PDF') {'pdf'} elseif ($roDownloadBytes[0] -eq 80 -and $roDownloadBytes[1] -eq 75) {if ($roDownloadRow.url -match '\.docx') {'docx'} else {'zip'}} else {'html'}
        $roDownloadFilename="original.$roDownloadExtension"
        $roDownloadPath=Join-Path $roDownloadDirectory $roDownloadFilename
        if (Test-Path -LiteralPath $roDownloadPath) {throw 'Original exists without receipt; inspect instead of overwrite'}
        [IO.File]::WriteAllBytes((Join-Path (Get-Location) $roDownloadPath),$roDownloadBytes)
        $roDownloadMetadata=[ordered]@{filename=$roDownloadFilename;resolved_url=$roDownloadResponse.BaseResponse.ResponseUri.AbsoluteUri;status=[int]$roDownloadResponse.StatusCode;content_type=[string]$roDownloadResponse.Headers['Content-Type'];retrieved_utc=[DateTime]::UtcNow.ToString('o')}
        $roDownloadMetadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $roDownloadDirectory 'download.json') -Encoding UTF8
        Write-Output "$($roDownloadRow.id): HTTP $($roDownloadResponse.StatusCode), $($roDownloadBytes.Length) bytes"
    } catch {Write-Output "$($roDownloadRow.id): FAILED $($_.Exception.Message)"}
}
