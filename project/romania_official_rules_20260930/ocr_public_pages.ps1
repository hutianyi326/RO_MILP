param([string]$SourceId, [string]$WorkPath='project/romania_official_rules_20260930')
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] | Out-Null
$roOcrEngine=[Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
$roAsTask=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Length -eq 1 -and $_.GetParameters().Length -eq 1} | Select-Object -First 1
function Await-RoTask($Operation,[Type]$ResultType) {
    $roTask=$roAsTask.MakeGenericMethod($ResultType).Invoke($null,@($Operation))
    $roTask.Wait()
    $roTask.Result
}
$roOcrDir=Join-Path $WorkPath 'rendered'
$roOcrOutput=Join-Path $WorkPath "extracted/$SourceId.ocr.txt"
$roOcrParts=New-Object 'System.Collections.Generic.List[string]'
$roOcrParts.Add('DERIVED OCR: Windows built-in recognizer, zh-Hans-CN/ja profile; verify Romanian accents and all formulas against original PDF. Not an original document.')
foreach ($roOcrImage in (Get-ChildItem -LiteralPath $roOcrDir -Filter "$($SourceId)_p*.png" | Sort-Object {[int]($_.BaseName -replace '^.*_p','')})) {
    $roFile=Await-RoTask ([Windows.Storage.StorageFile]::GetFileFromPathAsync($roOcrImage.FullName)) ([Windows.Storage.StorageFile])
    $roStream=Await-RoTask ($roFile.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $roDecoder=Await-RoTask ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($roStream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $roBitmap=Await-RoTask ($roDecoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $roResult=Await-RoTask ($roOcrEngine.RecognizeAsync($roBitmap)) ([Windows.Media.Ocr.OcrResult])
    $roOcrParts.Add("=== PDF PAGE $($roOcrImage.BaseName -replace '^.*_p','') ===")
    $roOcrParts.Add(($roResult.Lines | ForEach-Object {($_.Words | ForEach-Object {$_.Text}) -join ' '}) -join "`n")
    $roBitmap.Dispose(); $roStream.Dispose()
}
[IO.File]::WriteAllText($roOcrOutput,($roOcrParts -join "`n"),[Text.UTF8Encoding]::new($false))
Write-Output "$SourceId OCR saved, $($roOcrParts.Count) sections."
