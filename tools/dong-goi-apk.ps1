# Build debug APK with the bundled JDK 21 and copy it to phat-hanh\ATC-Desk.apk.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$javaHome = Join-Path $Root ".jdk21\jdk-21.0.12+8"
$javaExe = Join-Path $javaHome "bin\java.exe"
if (-not (Test-Path -LiteralPath $javaExe)) {
    throw "Thieu JDK 21 tai $javaHome"
}

$env:JAVA_HOME = $javaHome
$env:GRADLE_USER_HOME = Join-Path $Root ".gradle-home"
$env:Path = "$(Join-Path $javaHome 'bin');$env:Path"

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "GRADLE_USER_HOME=$env:GRADLE_USER_HOME"
& $javaExe -version

if (-not (Test-Path (Join-Path $Root "node_modules\@capacitor\cli"))) {
    Write-Host "Dang npm install..."
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install that bai" }
}

Write-Host "Dang cap sync android..."
npx cap sync android
if ($LASTEXITCODE -ne 0) { throw "cap sync that bai" }

node (Join-Path $Root "tools\strip-native-certs.js")

Set-Location (Join-Path $Root "android")
Write-Host "Dung Gradle daemon cu (neu co)..."
.\gradlew.bat --stop
Write-Host "Dang assembleDebug..."
.\gradlew.bat assembleDebug --no-daemon
if ($LASTEXITCODE -ne 0) { throw "Gradle assembleDebug that bai" }

$built = Join-Path $Root "android\app\build\outputs\apk\debug\app-debug.apk"
if (-not (Test-Path -LiteralPath $built)) {
    throw "Khong thay APK: $built"
}

$outDir = Join-Path $Root "phat-hanh"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$dest = Join-Path $outDir "ATC-Desk.apk"
Copy-Item -LiteralPath $built -Destination $dest -Force
$sizeMb = [math]::Round((Get-Item -LiteralPath $dest).Length / 1MB, 2)
Write-Host "APK: $dest ($sizeMb MB)"
