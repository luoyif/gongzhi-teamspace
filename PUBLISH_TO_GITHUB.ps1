param([string]$Repository='luoyif/gongzhi-teamspace')
$ErrorActionPreference='Stop'
if ($Repository -notmatch '^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$') { throw 'Expected owner/repo' }
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)
if (-not (Test-Path .git)) { throw 'Git repository not initialized' }
if (git status --porcelain) { throw 'Review and commit local changes first' }
$remote="https://github.com/$Repository.git"
$existing=git remote get-url origin 2>$null
if ($existing -and $existing -ne $remote) { throw 'origin is not the expected GitHub repository' }
if (-not $existing) { git remote add origin $remote }
Write-Host 'An empty GitHub repo must already exist and you must authenticate with GitHub.'
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Push did not complete; check repository permissions/authentication.' }
