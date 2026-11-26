param(
    [string]$Sdk = $(if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { $env:ANDROID_SDK_ROOT }),
    [string]$BuildToolsVersion = '36.0.0',
    [string]$BuildTools,
    [string]$Platform = 'android-35',
    [string]$Jdk = $env:JAVA_HOME,
    [string]$Ndk,
    [string]$Keystore = "$env:USERPROFILE/.android/debug.keystore",
    [string]$Output = "$PSScriptRoot/dist/Cv10ControllerProbe.apk"
)

$ErrorActionPreference = 'Stop'

function Invoke-Tool {
    param([string]$Tool, [string[]]$Arguments)
    & $Tool @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Tool exited with code $LASTEXITCODE" }
}

if (!$Sdk) { throw 'Set ANDROID_HOME or pass -Sdk.' }
$android = (Get-Item -LiteralPath "$Sdk/platforms/$Platform/android.jar").FullName
if (!$Ndk) { $Ndk = "$Sdk/ndk/26.3.11579264" }
$clang = (Get-Item -LiteralPath "$Ndk/toolchains/llvm/prebuilt/windows-x86_64/bin/aarch64-linux-android26-clang++.cmd").FullName
if (!$BuildTools) { $BuildTools = "$Sdk/build-tools/$BuildToolsVersion" }
$tools = (Get-Item -LiteralPath $BuildTools).FullName
$java = if ($Jdk) { "$Jdk/bin/java.exe" } else { 'java.exe' }
$javac = if ($Jdk) { "$Jdk/bin/javac.exe" } else { 'javac.exe' }
$jar = if ($Jdk) { "$Jdk/bin/jar.exe" } else { 'jar.exe' }
$keytool = if ($Jdk) { "$Jdk/bin/keytool.exe" } else { 'keytool.exe' }
$public = Join-Path $PSScriptRoot '../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/java/org/freedesktop/monado/openxr_runtime'
$native = Join-Path $PSScriptRoot '../ports/Monado_CV10/src/xrt/targets/openxr_android/src/main/cpp'
$work = "$PSScriptRoot/build/probe"
New-Item -ItemType Directory -Force -Path "$work/classes", "$work/dex", "$work/lib/arm64-v8a",
    (Split-Path -Parent $Output) | Out-Null

Invoke-Tool $javac @('-encoding', 'UTF-8', '--release', '8', '-classpath', $android, '-d', "$work/classes",
    "$public/Cv10ControllerActivity.java", "$public/Cv10ControllerLink.java", "$public/Cv10ControllerReport.java",
    "$public/Cv10KitActivity.java", "$public/Cv10KitReport.java", "$public/Cv10KitCalibration.java", "$public/Cv10KitHid.java",
    "$public/Cv10KitSlamParameters.java", "$public/Cv10KitSlam.java",
    "$PSScriptRoot/probe/ProbeActivity.java")
Invoke-Tool $javac @('-encoding', 'UTF-8', '--release', '8', '-classpath', "$work/classes", '-d', $work,
    "$PSScriptRoot/probe/ReportVectors.java", "$PSScriptRoot/probe/KitVectors.java")
Invoke-Tool $java @('-classpath', "$work;$work/classes", 'org.freedesktop.monado.openxr_runtime.ReportVectors')
Invoke-Tool $java @('-classpath', "$work;$work/classes", 'org.freedesktop.monado.openxr_runtime.KitVectors')

Invoke-Tool $clang @('-std=c++17', '-Wall', '-Wextra', '-Werror', '-O2', '-fPIC', '-shared', '-static-libstdc++',
    '-Wl,-z,max-page-size=16384', '-ldl', "$native/cv10_kit_slam.cpp", '-o', "$work/lib/arm64-v8a/libcv10-kit-slam.so")
Invoke-Tool $jar @('cf', "$work/app.jar", '-C', "$work/classes", '.')
Invoke-Tool $java @('-cp', "$tools/lib/d8.jar", 'com.android.tools.r8.D8', '--release', '--min-api', '26',
    '--lib', $android, '--output', "$work/dex", "$work/app.jar")
Invoke-Tool "$tools/aapt2.exe" @('link', '-I', $android, '--manifest', "$PSScriptRoot/probe/AndroidManifest.xml",
    '-o', "$work/unsigned.apk")
Invoke-Tool $jar @('uf', "$work/unsigned.apk", '-C', "$work/dex", 'classes.dex', '-C', $work, 'lib/arm64-v8a/libcv10-kit-slam.so')
Invoke-Tool "$tools/zipalign.exe" @('-f', '-P', '16', '4', "$work/unsigned.apk", "$work/aligned.apk")

if (!(Test-Path -LiteralPath $Keystore)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Keystore) | Out-Null
    Invoke-Tool $keytool @('-genkeypair', '-keystore', $Keystore, '-storepass', 'android', '-keypass', 'android',
        '-alias', 'androiddebugkey', '-dname', 'CN=Android Debug,O=Android,C=US', '-keyalg', 'RSA', '-validity', '10000')
}

Invoke-Tool $java @('-jar', "$tools/lib/apksigner.jar", 'sign', '--ks', $Keystore, '--ks-key-alias', 'androiddebugkey',
    '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--v4-signing-enabled', 'false', '--out', $Output,
    "$work/aligned.apk")
Invoke-Tool $java @('-jar', "$tools/lib/apksigner.jar", 'verify', $Output)
Invoke-Tool "$tools/zipalign.exe" @('-c', '-P', '16', '4', $Output)
Get-FileHash -LiteralPath $Output -Algorithm SHA256
