param([Parameter(Mandatory = $true)][string]$Serial)

$ErrorActionPreference = 'Stop'
$ndk = "$env:LOCALAPPDATA/Android/Sdk/ndk/27.0.12077973"
$compiler = "$ndk/toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android31-clang++.cmd"
$spirv = "$ndk/shader-tools/windows-x86_64"
$binary = "$PSScriptRoot/cv10-ahb-probe"
$shader = "$PSScriptRoot/verify.spv"
$remote = '/data/local/tmp/cv10-pocket-ahb-probe'
$remoteShader = '/data/local/tmp/cv10-pocket-ahb-verify.spv'
$pauseFile = "$PSScriptRoot/../fold7-unattended-battery-paused"

function Require-Battery {
    $level = adb -s $Serial shell dumpsys battery | Select-String '^\s*level:\s*(\d+)\s*$' | Select-Object -First 1
    if ((Test-Path $pauseFile) -or !$level -or [int]$level.Matches[0].Groups[1].Value -lt 20) {
        throw 'Battery pause active or unknown'
    }
}

& $compiler -std=c++17 -O2 -Wall -Wextra -Werror -Wno-missing-field-initializers -static-libstdc++ `
    "$PSScriptRoot/probe.cpp" -o $binary -lmediandk -landroid -lEGL -lGLESv2 -lvulkan
if ($LASTEXITCODE) { throw 'Native build failed' }
& "$spirv/glslc.exe" --target-env=vulkan1.1 "$PSScriptRoot/verify.comp" -o $shader
if ($LASTEXITCODE) { throw 'Shader build failed' }
& "$spirv/spirv-val.exe" --target-env vulkan1.1 $shader
if ($LASTEXITCODE) { throw 'SPIR-V validation failed' }

Require-Battery
try {
    adb -s $Serial push $binary $remote
    if ($LASTEXITCODE) { throw 'Could not upload probe' }
    adb -s $Serial push $shader $remoteShader
    if ($LASTEXITCODE) { throw 'Could not upload shader' }
    adb -s $Serial shell chmod 700 $remote
    if ($LASTEXITCODE) { throw 'Could not make probe executable' }
    foreach ($eye in 1600, 2240, 3200) {
        Require-Battery
        adb -s $Serial shell "timeout 20 $remote $remoteShader $eye" | Tee-Object "$PSScriptRoot/fold7-size-$eye.txt"
        if ($LASTEXITCODE) { throw "Probe failed at eye size $eye" }
    }
} finally {
    adb -s $Serial shell rm -f $remote $remoteShader | Out-Null
}
