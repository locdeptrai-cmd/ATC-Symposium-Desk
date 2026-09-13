# One-click bootstrap: install missing PC runtime, then start ATC Symposium Desk.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "  $Message"
}

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
    return $null
}

function Update-SessionPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$user;$machine"
    $pyRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $pyRoot) {
        Get-ChildItem $pyRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $env:Path = "$($_.FullName);$(Join-Path $_.FullName 'Scripts');$env:Path"
        }
    }
}

function Install-Python {
    Write-Step "Chua co Python 3.10+. Dang cai dat Python (user, khong can admin)..."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw "Khong tim thay winget. Cai Python 3.12 roi chay lai file nay."
    }
    & winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Cai Python that bai (ma $LASTEXITCODE)."
    }
    Update-SessionPath
}

function Install-CryptographyIfMissing($Python) {
    $importArgs = @($Python.Args) + @("-c", "import cryptography")
    & $Python.Exe @importArgs 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Step "Dang cai goi cryptography (HTTPS cho dien thoai)..."
    $pipArgs = @($Python.Args) + @("-m", "pip", "install", "--user", "--upgrade", "pip", "cryptography")
    & $Python.Exe @pipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip install cryptography that bai."
    }
    & $Python.Exe @importArgs 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Python chay duoc nhung chua import duoc cryptography."
    }
}

function Get-Adb {
    $sdk = $null
    $props = Join-Path $Root "android\local.properties"
    if (Test-Path $props) {
        $line = Get-Content -LiteralPath $props -ErrorAction SilentlyContinue |
            Where-Object { $_ -match "^\s*sdk\.dir=" } |
            Select-Object -First 1
        if ($line) {
            $sdk = ($line -replace "^\s*sdk\.dir=", "").Trim().Trim("'").Trim('"')
            $sdk = $sdk -replace "/", "\"
        }
    }
    $adbCandidates = @()
    if ($sdk) { $adbCandidates += (Join-Path $sdk "platform-tools\adb.exe") }
    $adbCandidates += @(
        (Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"),
        "adb"
    )
    foreach ($path in $adbCandidates) {
        if ($path -eq "adb") {
            $cmd = Get-Command adb -ErrorAction SilentlyContinue
            if ($cmd) { return $cmd.Source }
            continue
        }
        if (Test-Path -LiteralPath $path) { return $path }
    }
    return $null
}

function Install-PhoneApkIfReady {
    # Optional: never block PC launch. PS 5.1 treats adb stderr
    # ("daemon not running") as a terminating error when Stop is set.
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $apk = Join-Path $Root "phat-hanh\ATC-Desk.apk"
        if (-not (Test-Path -LiteralPath $apk)) { return }
        $adb = Get-Adb
        if (-not $adb) { return }
        $devices = & $adb devices 2>&1 | ForEach-Object { "$_" }
        $ready = @($devices | Where-Object { $_ -match "\tdevice$" })
        if ($ready.Count -eq 0) { return }
        Write-Step "Dien thoai Android da ket USB. Dang cai ATC-Desk.apk..."
        & $adb install -r --no-incremental $apk 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            & $adb shell am start -n vn.vatm.atcdesk/.MainActivity 2>&1 | Out-Null
            Write-Host "  Da cai va mo app tren dien thoai."
        } else {
            Write-Host "  Cai APK khong thanh cong. Van mo app tren may tinh."
        }
    } catch {
        Write-Host "  Bo qua cai APK dien thoai."
    } finally {
        $ErrorActionPreference = $saved
    }
}

Write-Host ""
Write-Host "  ATC Symposium Desk"
Write-Host "  Cai dat (neu thieu) roi chay app - chi can bam 1 lan"
Write-Host ""

$python = Get-Python
if (-not $python) {
    Install-Python
    $python = Get-Python
}
if (-not $python) {
    throw "Da cai Python nhung cua so nay chua nhin thay. Dong cua so, bam lai CAI_DAT_VA_CHAY.cmd."
}

& (Join-Path $PSScriptRoot "check-signature.ps1")

Install-CryptographyIfMissing $python
Install-PhoneApkIfReady

function Stop-OldDesk {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $pids = @()
        foreach ($port in 8765, 8766) {
            Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                ForEach-Object { if ($_.OwningProcess) { $pids += $_.OwningProcess } }
        }
        $pids = $pids | Select-Object -Unique
        foreach ($procId in $pids) {
            Write-Host "  Dong tien trinh cu tren cong 8765/8766 (PID $procId)."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Get-Process ffmpeg, ffprobe -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
        if ($pids) { Start-Sleep -Seconds 1 }
    } finally {
        $ErrorActionPreference = $saved
    }
}

$env:PYTHONUNBUFFERED = "1"
Stop-OldDesk
Write-Step "Dang mo ATC Symposium Desk..."
Write-Host "  May nay:     http://127.0.0.1:8765"
Write-Host "  Giu cua so nay mo. Ctrl+C de dung."
Write-Host ""

$serve = Join-Path $Root "tools\serve.py"
$runArgs = @($python.Args) + @($serve)
& $python.Exe @runArgs
$code = $LASTEXITCODE
# Ctrl+C / Stop-Process / window close is not a startup failure.
if ($null -eq $code -or $code -eq 0 -or $code -eq -1 -or $code -eq 0xC000013A) {
    return
}
throw "Khong khoi dong duoc server (ma $code). Neu cong 8765 dang dung, dong cua so MO_APP cu roi bam lai."
