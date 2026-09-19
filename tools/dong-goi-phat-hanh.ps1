# Build release artifacts into phat-hanh\: fat Windows EXE and Android/iOS-shared mobile APK.
# iOS native still needs a Mac + Xcode; this script syncs the Capacitor iOS project.
# iPhone without Mac uses the PWA served by CHAY.cmd / ATC-Desk.exe (same web).
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "=== 1/3 Android APK ==="
& (Join-Path $PSScriptRoot "dong-goi-apk.ps1")
if ($LASTEXITCODE -ne 0) { throw "dong-goi-apk that bai" }
Set-Location $Root

Write-Host ""
Write-Host "=== 2/3 iOS project sync (khong compile IPA tren Windows) ==="
if (-not (Test-Path (Join-Path $Root "node_modules\@capacitor\cli"))) {
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install that bai" }
}
npx cap sync ios
if ($LASTEXITCODE -ne 0) { throw "cap sync ios that bai" }
node (Join-Path $Root "tools\strip-native-certs.js")
Set-Location $Root

Write-Host ""
Write-Host "=== 3/3 Windows EXE (mot file, kem DB) ==="
& (Join-Path $PSScriptRoot "dong-goi-windows.ps1")
if ($LASTEXITCODE -ne 0) { throw "dong-goi-windows that bai" }
Set-Location $Root

Write-Host ""
Write-Host "Xong. File phat hanh:"
Get-ChildItem (Join-Path $Root "phat-hanh") | ForEach-Object {
    $mb = [math]::Round($_.Length / 1MB, 2)
    Write-Host ("  {0}  {1} MB" -f $_.Name, $mb)
}
Write-Host "iOS native: copy thu muc ios/ sang Mac, mo ios/App/App.xcworkspace."
