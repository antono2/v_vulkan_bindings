# Compatibility entry point for the cross-platform V generator.
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
$PreviousPython = $env:PYTHON
$GenerateArgs = @('run', (Join-Path $PSScriptRoot 'generate.vsh'))
if ($RegistryRef) {
    $GenerateArgs += $RegistryRef
}
try {
    $env:PYTHON = $Python
    & $VCompiler @GenerateArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Vulkan generation exited with status $LASTEXITCODE"
    }
} finally {
    $env:PYTHON = $PreviousPython
}
