<#
Builds the Jarvis installer (Setup.exe) and, with -Publish, puts it on your GitHub releases page,
where every installed copy picks it up as an update.

Normally the GitHub workflow runs this for you (push a tag like v1.0.0). To build on your own PC:
    powershell -ExecutionPolicy Bypass -File build.ps1 -Version 1.0.0
Needs: Python 3.12 and the .NET SDK 8 or newer (for Velopack's packer). Output goes to .\Releases.

Parameters:
  -Version        the version to build, like 1.2.0 (must be higher than the last release)
  -UpdateSource   where installed copies look for updates, e.g. https://github.com/you/jarvis
  -Publish        upload to GitHub Releases (needs -Token, or GITHUB_TOKEN in the environment)
  -SignFile       Azure Artifact Signing metadata.json, to sign the app (optional, see RELEASING.md)
  -SkipInstall    don't pip install first (the workflow already did)
#>
param(
    [Parameter(Mandatory = $true)][string]$Version,
    [string]$UpdateSource = "",
    [switch]$Publish,
    [string]$Token = $env:GITHUB_TOKEN,
    [string]$SignFile = "",
    [string]$Notes = "RELEASE_NOTES.md",
    [switch]$SkipInstall
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# The install ID. NEVER change this after the first release: installed copies only accept updates
# with the same ID (a new ID means everyone has to reinstall). The visible name can change any time.
$PackId = "JarvisAssistant"
$Title = "Jarvis"

if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$') { throw "Version must look like 1.2.3 (got '$Version')." }

if (-not $SkipInstall) {
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt -r requirements-build.txt
    if ($LASTEXITCODE) { throw "pip install failed" }
}

# 1. Bake in where updates come from
if ($UpdateSource) { Set-Content -Path update_source.txt -Value $UpdateSource -NoNewline -Encoding utf8 }
elseif (Test-Path update_source.txt) { Write-Host "Using existing update_source.txt: $(Get-Content update_source.txt)" }
else { Write-Warning "No -UpdateSource: this build won't be able to update itself." }

# 2. Bundle Python + everything into dist\Jarvis
python -m PyInstaller jarvis.spec --noconfirm --clean
if ($LASTEXITCODE) { throw "PyInstaller failed" }

# 3. Does everything load inside the bundle? (catches missing modules before anyone installs it)
$result = Join-Path $env:TEMP "jarvis-selftest.txt"
Remove-Item $result -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "dist\Jarvis\Jarvis.exe" -ArgumentList "--selftest", "`"$result`"" -Wait -PassThru
$text = if (Test-Path $result) { Get-Content $result -Raw } else { "no result file" }
Write-Host $text
if ($p.ExitCode -ne 0) { throw "Self-test failed: the packaged app is missing pieces (see above)." }

# 4. Velopack's packer, the same version as the velopack Python package (they must match)
$vel = python -c "import importlib.metadata as m; print(m.version('velopack'))"
Write-Host "Velopack $vel"
dotnet tool update -g vpk --version $vel
if ($LASTEXITCODE) {
    Write-Warning "There's no vpk $vel; using the newest vpk instead. If updates misbehave, pin velopack in requirements.txt to a version vpk also has."
    dotnet tool update -g vpk
    if ($LASTEXITCODE) { throw "Couldn't install vpk (is the .NET SDK installed?)" }
}
$env:PATH = "$env:PATH;$env:USERPROFILE\.dotnet\tools"

$repo = ""
if ($UpdateSource -match 'github\.com/') { $repo = $UpdateSource.TrimEnd('/') }
elseif ((Test-Path update_source.txt) -and ((Get-Content update_source.txt -Raw) -match 'github\.com/')) { $repo = (Get-Content update_source.txt -Raw).Trim().TrimEnd('/') }

# 5. Fetch the previous release so this one can include a small "delta" update (fine if there isn't one)
if ($Publish -and $repo) {
    vpk download github --repoUrl $repo --token $Token
    if ($LASTEXITCODE) { Write-Host "No earlier release found (first release?); full update only." }
}

# 6. Make Setup.exe and the update packages in .\Releases
$packArgs = @("pack", "--packId", $PackId, "--packVersion", $Version, "--packDir", "dist\Jarvis",
              "--mainExe", "Jarvis.exe", "--packTitle", $Title, "--icon", "assets\jarvis.ico")
if (Test-Path $Notes) { $packArgs += @("--releaseNotes", $Notes) }
if ($SignFile) { $packArgs += @("--azureTrustedSignFile", $SignFile) }
vpk @packArgs
if ($LASTEXITCODE) { throw "vpk pack failed" }

# 7. Publish
if ($Publish) {
    if (-not $repo) { throw "-Publish needs a GitHub -UpdateSource like https://github.com/you/jarvis" }
    if (-not $Token) { throw "-Publish needs a GitHub token (-Token or GITHUB_TOKEN)" }
    vpk upload github --repoUrl $repo --token $Token --publish --releaseName "$Title $Version" --tag "v$Version" --merge
    if ($LASTEXITCODE) { throw "Upload to GitHub failed" }
    Write-Host "Published $Title $Version to $repo/releases"
} else {
    Write-Host "Built $Title $Version. Installer: Releases\$PackId-win-Setup.exe"
}
