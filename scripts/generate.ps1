# Compatibility entry point for the cross-platform V generator.
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string] $RegistryRef,

    # Retain the named parameter for scripts written before the V generator.
    [Parameter()]
    [string] $Python,

    [Parameter()]
    [string] $VCompiler = 'v'
)

$ErrorActionPreference = 'Stop'
$GenerateArgs = @('run', (Join-Path $PSScriptRoot 'generate.vsh'))
if ($RegistryRef) {
    $GenerateArgs += $RegistryRef
}
& $VCompiler @GenerateArgs
if ($LASTEXITCODE -ne 0) {
    throw "Vulkan generation exited with status $LASTEXITCODE"
}
