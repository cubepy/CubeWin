$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r .\requirements.txt
& .\install-engine.ps1
python -m pytest .\tests -q
python -m PyInstaller --noconfirm --clean .\CubeVPN.spec
Write-Host "`nBuild ready: $PSScriptRoot\dist\CubeVPN\CubeVPN.exe"
