param([Parameter(Mandatory=$true)][string]$RequestList)
$ErrorActionPreference='Stop'
$sampleRequests=Get-Content -LiteralPath $RequestList -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($sampleRequest in $sampleRequests) {
  $sampleDir=Join-Path 'data/raw/RO/samples/20260930' $sampleRequest.id
  New-Item -ItemType Directory -Path $sampleDir -Force | Out-Null
  $sampleReceipt=Join-Path $sampleDir 'receipt.json'
  if(Test-Path -LiteralPath $sampleReceipt){continue}
  $sampleMeta=[ordered]@{id=$sampleRequest.id;dataset=$sampleRequest.dataset;url=$sampleRequest.url;method='GET';parameters=$sampleRequest.body;requested_scope=$sampleRequest.scope;retrieved_utc=[DateTime]::UtcNow.ToString('o');status='FAILED';error=$null}
  try {
    $sampleArgs=@{Uri=$sampleRequest.url;UseBasicParsing=$true;TimeoutSec=35}
    if($sampleRequest.body){
      $sampleFormResponse=Invoke-WebRequest -Uri $sampleRequest.url -UseBasicParsing -TimeoutSec 35 -SessionVariable samplePublicSession
      $sampleTokenMatch=[regex]::Match($sampleFormResponse.Content,'name="_token" value="([^"]+)"')
      $sampleFormBody=@{}
      $sampleRequest.body.psobject.Properties | ForEach-Object {$sampleFormBody[$_.Name]=$_.Value}
      if($sampleTokenMatch.Success){$sampleFormBody['_token']=$sampleTokenMatch.Groups[1].Value}
      $sampleArgs.Method='POST';$sampleArgs.Body=$sampleFormBody;$sampleArgs.WebSession=$samplePublicSession;$sampleArgs.ContentType='application/x-www-form-urlencoded';$sampleMeta.method='POST'
    }
    $sampleResponse=Invoke-WebRequest @sampleArgs
    $sampleBytes=$sampleResponse.RawContentStream.ToArray()
    $sampleExt='html'
    if($sampleBytes.Length -ge 4 -and [Text.Encoding]::ASCII.GetString($sampleBytes,0,4) -eq '%PDF'){$sampleExt='pdf'}
    elseif($sampleBytes.Length -ge 2 -and $sampleBytes[0] -eq 80 -and $sampleBytes[1] -eq 75){$sampleExt='zip'}
    elseif([string]$sampleResponse.Headers['Content-Type'] -match 'json'){$sampleExt='json'}
    elseif([string]$sampleResponse.Headers['Content-Type'] -match 'xml'){$sampleExt='xml'}
    $samplePath=Join-Path $sampleDir "original.$sampleExt"
    if(Test-Path -LiteralPath $samplePath){throw 'Original already exists: no overwrite permitted'}
    [IO.File]::WriteAllBytes((Join-Path (Get-Location) $samplePath),$sampleBytes)
    $sampleMeta.status='HTTP_OK_UNPARSED';$sampleMeta.http_status=[int]$sampleResponse.StatusCode
    $sampleMeta.resolved_url=$sampleResponse.BaseResponse.ResponseUri.AbsoluteUri
    $sampleMeta.content_type=[string]$sampleResponse.Headers['Content-Type']
    $sampleMeta.raw_file=$samplePath.Replace('\','/');$sampleMeta.bytes=$sampleBytes.Length
    $sampleMeta.sha256=(Get-FileHash -LiteralPath $samplePath -Algorithm SHA256).Hash.ToLower()
    Write-Output "$($sampleRequest.id): HTTP $($sampleResponse.StatusCode), $($sampleBytes.Length) bytes"
  } catch {$sampleMeta.error=$_.Exception.Message;Write-Output "$($sampleRequest.id): FAILED $($sampleMeta.error)"}
  $sampleMeta | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $sampleReceipt -Encoding UTF8
}
