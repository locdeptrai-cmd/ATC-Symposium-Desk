# Build a single-file Windows EXE: web UI + library DB + Whisper ATC + ffmpeg.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$packTmp = Join-Path $Root ".tmp-pack"
New-Item -ItemType Directory -Force -Path $packTmp | Out-Null
$env:TEMP = $packTmp
$env:TMP = $packTmp
$env:PYINSTALLER_CONFIG_DIR = Join-Path $packTmp "pyinstaller"

function Get-Python {
    $candidates = @(
        @{ Exe = "python"; Args = @() },
        @{ Exe = "py"; Args = @("-3") },
        @{ Exe = "python3"; Args = @() }
    )
    foreach ($item in $candidates) {
        $cmd = Get-Command $item.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $ok = $false
        try {
            $checkArgs = @($item.Args) + @(
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
            )
            & $item.Exe @checkArgs 2>$null | Out-Null
            $ok = ($LASTEXITCODE -eq 0)
        } catch {
            $ok = $false
        }
        if ($ok) {
            return @{ Exe = $item.Exe; Args = @($item.Args) }
        }
    }
    throw "Can Python 3.10+ de dong goi EXE."
}

$python = Get-Python
Write-Host "Python: $($python.Exe)"

$db = Join-Path $Root "web\data\library.sqlite"
$snapshot = Join-Path $Root "web\js\library-data.js"
if (-not (Test-Path -LiteralPath $db)) { throw "Thieu DB: $db" }
if (-not (Test-Path -LiteralPath $snapshot)) { throw "Thieu snapshot thu vien: $snapshot" }

$pipArgs = @($python.Args) + @("-m", "pip", "install", "pyinstaller", "cryptography", "faster-whisper")
& $python.Exe @pipArgs
if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller/cryptography/faster-whisper that bai" }

$turbo = Join-Path $Root "models\whisper\atc-turbo-ct2\model.bin"
if (-not (Test-Path -LiteralPath $turbo)) { throw "Thieu model ATC turbo: $turbo" }

$binDir = Join-Path $Root "tools\bin"
New-Item -ItemType Directory -Force -Path $binDir | Out-Null
$ffmpegDest = Join-Path $binDir "ffmpeg.exe"
if (-not (Test-Path -LiteralPath $ffmpegDest) -or ((Get-Item -LiteralPath $ffmpegDest).Length -lt 1MB)) {
    $ffCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
    $ffSrc = $null
    if ($ffCmd) { $ffSrc = $ffCmd.Source }
    if ($ffSrc) {
        $item = Get-Item -LiteralPath $ffSrc -Force
        if ($item.LinkType) { $ffSrc = $item.Target }
    }
    if (-not $ffSrc -or -not (Test-Path -LiteralPath $ffSrc)) {
        throw "Thieu ffmpeg de dong goi vao EXE. Cai Gyan.FFmpeg roi chay lai."
    }
    Write-Host "Chep ffmpeg vao tools\bin tu $ffSrc"
    Copy-Item -LiteralPath $ffSrc -Destination $ffmpegDest -Force
}

$icoArgs = @($python.Args) + @((Join-Path $Root "tools\make_ico.py"))
& $python.Exe @icoArgs
if ($LASTEXITCODE -ne 0) { throw "Tao icon EXE that bai" }

$spec = Join-Path $Root "ATC-Desk.spec"
$packArgs = @($python.Args) + @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    $spec
)
Write-Host "Dang dong goi ATC-Desk.exe (mot file: UI + DB + Whisper ATC + ffmpeg)..."
& $python.Exe @packArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller that bai" }

$built = Join-Path $Root "dist\ATC-Desk.exe"
if (-not (Test-Path -LiteralPath $built)) {
    throw "Khong thay EXE: $built"
}

$outDir = Join-Path $Root "phat-hanh"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$dest = Join-Path $outDir "ATC-Desk.exe"
Copy-Item -LiteralPath $built -Destination $dest -Force
$sizeMb = [math]::Round((Get-Item -LiteralPath $dest).Length / 1MB, 2)
Write-Host "EXE: $dest ($sizeMb MB)"
$apk = Join-Path $outDir "ATC-Desk-Mobile.apk"
if (Test-Path -LiteralPath $apk) {
    Write-Host "APK (cung thu muc, de EXE phuc vu cai Android): $apk"
} else {
    Write-Host "Chua co APK trong phat-hanh\. Chay tools\dong-goi-apk.ps1 neu can Android native."
}
Write-Host "May Windows moi: copy ATC-Desk.exe, double-click. Kem DB + model STT + ffmpeg."
Write-Host "Dien thoai: PWA tu EXE (iOS+Android, cung chat luong ghi loi) hoac ATC-Desk-Mobile.apk."
