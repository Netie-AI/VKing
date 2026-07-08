# Install oss-cad-suite for Vking prototype (Windows x64)
# Downloads from https://github.com/YosysHQ/oss-cad-suite-build/releases/latest
# Usage: powershell -ExecutionPolicy Bypass -File install_oss_cad.ps1

$ErrorActionPreference = "Stop"
$TargetRoot = if ($env:OSS_CAD_SUITE) { $env:OSS_CAD_SUITE } else { "C:\oss-cad-suite" }
$Bin = Join-Path $TargetRoot "bin"

if (Test-Path (Join-Path $Bin "iverilog.exe")) {
    Write-Host "Already installed at $TargetRoot"
    exit 0
}

Write-Host "Fetching latest oss-cad-suite Windows release metadata..."
$release = Invoke-RestMethod -Uri "https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/latest"
$asset = $release.assets | Where-Object { $_.name -match "windows-x64.*\.(exe|7z|zip)$" } | Select-Object -First 1
if (-not $asset) {
    Write-Error "No windows-x64 asset found. Download manually from $($release.html_url)"
}

$dest = Join-Path $env:TEMP $asset.name
Write-Host "Downloading $($asset.name) ($([math]::Round($asset.size/1MB)) MB)..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest -UseBasicParsing

New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null

if ($asset.name -match "\.exe$") {
    Write-Host "Running self-extracting installer to $TargetRoot ..."
    & $dest -o"$TargetRoot" -y
} elseif ($asset.name -match "\.7z$") {
    if (-not (Get-Command 7z -ErrorAction SilentlyContinue)) {
        Write-Error "7z required to extract .7z. Install 7-Zip or download the .exe release."
    }
    & 7z x $dest "-o$TargetRoot" -y
} else {
    Expand-Archive -Path $dest -DestinationPath $TargetRoot -Force
}

$iverilog = Get-ChildItem -Path $TargetRoot -Recurse -Filter "iverilog.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $iverilog) {
    Write-Error "iverilog.exe not found after extract. Check $TargetRoot"
}

$foundBin = $iverilog.Directory.FullName
Write-Host "Found bin: $foundBin"
Write-Host ""
Write-Host "Add to user PATH (new terminal required):"
Write-Host "  [Environment]::SetEnvironmentVariable('PATH', `"$foundBin;`" + [Environment]::GetEnvironmentVariable('PATH','User'), 'User')"
Write-Host "Or set for Vking only:"
Write-Host "  [Environment]::SetEnvironmentVariable('OSS_CAD_SUITE', '$($foundBin | Split-Path -Parent)', 'User')"
Write-Host ""
Write-Host "Verify: $foundBin\iverilog.exe -V"
