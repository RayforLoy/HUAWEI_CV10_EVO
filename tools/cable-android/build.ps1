[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string] $Sdk,
    [Parameter(Mandatory)] [string] $Jdk,
    [Parameter(Mandatory)] [string] $Stock53,
    [Parameter(Mandatory)] [string] $Phone2A,
    [Parameter(Mandatory)] [string] $PinC,
    [Parameter(Mandatory)] [string] $Rt9471Phone2A,
    [string] $Stock49,
    [string] $Stock52,
    [string] $BuildToolsVersion = '34.0.0',
    [string] $Keystore = (Join-Path $env:USERPROFILE '.android/debug.keystore'),
    [string] $OutputDirectory
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$stockDirectory = Join-Path $repository 'firmware_update/firmware/cable/stock'
if (!$Stock49) { $Stock49 = Join-Path $stockDirectory 'CV10-cable-C9.49.6.bin' }
if (!$Stock52) { $Stock52 = Join-Path $stockDirectory 'CV10-cable-C9.52.6.bin' }
if (!$OutputDirectory) { $OutputDirectory = Join-Path $repository '.research/cable/android-app' }
$OutputDirectory = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
$Sdk = (Resolve-Path -LiteralPath $Sdk).Path
$Jdk = (Resolve-Path -LiteralPath $Jdk).Path
$Keystore = (Resolve-Path -LiteralPath $Keystore).Path
$buildTools = Join-Path $Sdk "build-tools/$BuildToolsVersion"
$androidJar = Join-Path $Sdk 'platforms/android-35/android.jar'
$java = Join-Path $Jdk 'bin/java.exe'
$javac = Join-Path $Jdk 'bin/javac.exe'
$jar = Join-Path $Jdk 'bin/jar.exe'

function Invoke-CableBuildTool([string] $Program, [string[]] $Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program exited with code $LASTEXITCODE" }
}

$work = Join-Path $OutputDirectory ('build-' + [Guid]::NewGuid().ToString('N'))
$assetDir = Join-Path $work 'assets'
$classDir = Join-Path $work 'classes'
$dexDir = Join-Path $work 'dex'
New-Item -ItemType Directory -Path $assetDir, $classDir, $dexDir | Out-Null

$images = @{
    'stock49.bin' = @($Stock49, 'f16057065c4c29d6d86901239371f2a6aab2bcf03c6976505c8f5971fba93e02')
    'stock52.bin' = @($Stock52, '1ebf1217d0dda526f64ed3b15504db409fbdf25bc866f0fbebb874adcd00485a')
    'stock53.bin' = @($Stock53, '8e8d9d0df2809f2d3a673519834c83662acc5be6635060d75ef246133956843e')
    'phone2a.bin' = @($Phone2A, 'ba4fa99083c69bcacbd44b0a7afcbfcde228b5535752bc47c59cea13fc3d1096')
    'pinc.bin' = @($PinC, 'c9d88fcc5205bfb6f9aa6cdd93839c0bfb056522f542132d9ef028efe1c129f6')
    'rt9471-phone2a.bin' = @($Rt9471Phone2A, '6b481d03fadb6911b7fe3e51903a8cc48b9029c5cea85dc848ee5c35787d1f9c')
}
foreach ($asset in $images.Keys) {
    $source, $expected = $images[$asset]
    $destination = Join-Path $assetDir $asset
    Copy-Item -LiteralPath $source -Destination $destination
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ine $expected) {
        throw "SHA-256 mismatch for $asset ($source)"
    }
}

$sources = @(Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'src') -Recurse -Filter '*.java' -File).FullName
$classes = Join-Path $work 'classes.jar'
$unsigned = Join-Path $work 'unsigned.apk'
$aligned = Join-Path $work 'aligned.apk'
$signed = Join-Path $work 'signed.apk'
$final = Join-Path $OutputDirectory 'CV10-Cable-Tool-Android.apk'
$manifest = Join-Path $PSScriptRoot 'AndroidManifest.xml'

Invoke-CableBuildTool $javac (@('-encoding', 'UTF-8', '--release', '8', '-classpath', $androidJar, '-d', $classDir) + $sources)
Invoke-CableBuildTool $jar @('cf', $classes, '-C', $classDir, '.')
Invoke-CableBuildTool $java @('-cp', (Join-Path $buildTools 'lib/d8.jar'), 'com.android.tools.r8.D8', '--min-api', '26', '--lib', $androidJar, '--output', $dexDir, $classes)
Invoke-CableBuildTool (Join-Path $buildTools 'aapt2.exe') @('link', '-I', $androidJar, '--manifest', $manifest, '-A', $assetDir, '-o', $unsigned)
Push-Location -LiteralPath $dexDir
try {
    Invoke-CableBuildTool (Join-Path $buildTools 'aapt.exe') @('add', $unsigned, 'classes.dex')
} finally {
    Pop-Location
}
Invoke-CableBuildTool (Join-Path $buildTools 'zipalign.exe') @('-f', '4', $unsigned, $aligned)
$signer = Join-Path $buildTools 'lib/apksigner.jar'
Invoke-CableBuildTool $java @('-jar', $signer, 'sign', '--ks', $Keystore, '--ks-key-alias', 'androiddebugkey', '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', $signed, $aligned)
Invoke-CableBuildTool $java @('-jar', $signer, 'verify', '--verbose', $signed)
Copy-Item -LiteralPath $signed -Destination $final
Get-FileHash -LiteralPath $final -Algorithm SHA256
