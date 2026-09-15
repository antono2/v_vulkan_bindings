[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $RegistryRef,

    [Parameter()]
    [string] $Python = 'python',

    [Parameter()]
    [string] $VCompiler = 'v'
)

$ErrorActionPreference = 'Stop'
$ProjectDirectory = Split-Path -Parent $PSScriptRoot
if (-not $RegistryRef) {
    $RegistryRef = (Get-Content -LiteralPath (Join-Path $ProjectDirectory 'VERSION') -Raw).Trim()
}
if ($RegistryRef -notmatch '^v[0-9]+\.[0-9]+\.[0-9]+$') {
    throw "Invalid Vulkan-Docs tag: $RegistryRef"
}

$Git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Git) { throw 'Git is required' }
$PythonCommand = Get-Command $Python -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $PythonCommand) { throw "$Python is required" }

$DocsDirectory = Join-Path $ProjectDirectory 'vulkandocs'
$DocsGitDirectory = Join-Path $DocsDirectory '.git'
if (-not (Test-Path -LiteralPath $DocsGitDirectory -PathType Container)) {
    if (Test-Path -LiteralPath $DocsDirectory) {
        throw 'vulkandocs exists but is not a Git checkout; move or remove it, then run this script again'
    }
    & $Git.Source clone --depth 1 --branch $RegistryRef https://github.com/KhronosGroup/Vulkan-Docs.git $DocsDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Could not clone Vulkan-Docs' }
} else {
    $Changes = & $Git.Source -C $DocsDirectory status --porcelain
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect the Vulkan-Docs checkout' }
    if ($Changes) { throw 'vulkandocs has local changes; refusing to change its revision' }
    & $Git.Source -C $DocsDirectory fetch --depth 1 origin "refs/tags/$RegistryRef"
    if ($LASTEXITCODE -ne 0) { throw "Could not fetch Vulkan-Docs tag $RegistryRef" }
    & $Git.Source -C $DocsDirectory checkout --quiet --detach FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { throw "Could not check out Vulkan-Docs tag $RegistryRef" }
}

$VenvDirectory = Join-Path $ProjectDirectory '.venv'
$VenvPython = Join-Path $VenvDirectory 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    if (Test-Path -LiteralPath $VenvDirectory) {
        throw '.venv is incomplete; move or remove it, then run this script again'
    }
    & $PythonCommand.Source -m venv $VenvDirectory
    if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv' }
}
& $VenvPython -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) { throw '.venv does not contain a working pip installation' }
& $VenvPython -m pip install --quiet --requirement (Join-Path $ProjectDirectory '.github\generator-requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Could not install generator dependencies' }

Push-Location $ProjectDirectory
try {
    & $VenvPython src/main.py -registry vulkandocs/xml/vk.xml vulkan.v
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate Vulkan bindings' }
    & $VenvPython src/main.py -registry vulkandocs/xml/video.xml vulkan_video.v
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate Vulkan Video bindings' }

    $V = Get-Command $VCompiler -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($V) {
        & $V.Source fmt -w src/vulkan.v
        if ($LASTEXITCODE -ne 0) { throw 'Could not format Vulkan bindings' }
        & $V.Source fmt -w src/vulkan_video.v
        if ($LASTEXITCODE -ne 0) { throw 'Could not format Vulkan Video bindings' }
    } else {
        Write-Warning 'V was not found; generated files were not formatted'
    }
} finally {
    Pop-Location
}

Write-Output "Generated Vulkan bindings from Vulkan-Docs $RegistryRef"
