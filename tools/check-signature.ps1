# Compare SIGNATURE.txt by UTF-8 SHA-256 so Windows PowerShell 5.1
# does not mis-decode Vietnamese in this .ps1 (no BOM).
$ErrorActionPreference = "Stop"
$root = if ((Split-Path -Leaf $PSScriptRoot) -eq "tools") {
    Split-Path -Parent $PSScriptRoot
} else {
    $PSScriptRoot
}
$expectedHash = "a2fbda0ad4297deda52d14d5dca9af8027c601730cec3ca359982dd151896373"
$path = Join-Path $root "SIGNATURE.txt"
if (-not (Test-Path -LiteralPath $path)) {
    throw "UNG DUNG DA KHOA: SIGNATURE.txt bi thieu hoac bi sua."
}
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $path))
if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) {
    $bytes = $bytes[3..($bytes.Length - 1)]
}
$text = [System.Text.Encoding]::UTF8.GetString($bytes).Trim()
$sha = [System.Security.Cryptography.SHA256]::Create()
try {
    $hash = ($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($text)) | ForEach-Object { $_.ToString("x2") }) -join ""
} finally {
    $sha.Dispose()
}
if ($hash -ne $expectedHash) {
    throw "UNG DUNG DA KHOA: SIGNATURE.txt bi thieu hoac bi sua."
}
