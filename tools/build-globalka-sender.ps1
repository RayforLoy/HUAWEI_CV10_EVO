param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '..\resources')
)

$ErrorActionPreference = 'Stop'
$revision = '266dbe02e115c7aeed936dedc2d1924ae375bc8c'
$sourceHash = '85395fffc0f20e7c8124f02c7bc891e9c9e84f50c6d048e6db1401e50e9d177b'
$url = "https://raw.githubusercontent.com/samrat1games/huawei-vr-glass-globalka/$revision/windows/VRGlassPC.cs"
$compiler = @('Framework64', 'Framework') |
    ForEach-Object { Join-Path $env:WINDIR "Microsoft.NET\$_\v4.0.30319\csc.exe" } |
    Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$compiler) { throw 'The .NET Framework 4 C# compiler was not found.' }

$scratch = New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) ('vrglasspc-' + [guid]::NewGuid()))
try {
    $source = Join-Path $scratch.FullName 'VRGlassPC.cs'
    $built = Join-Path $scratch.FullName 'VRGlassPC.exe'
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $source
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $sourceHash) {
        throw 'The Windows sender source does not match the pinned SHA-256.'
    }
    $code = [IO.File]::ReadAllText($source)
    $code = $code.Replace('new EncoderParameter(Encoder.Quality', 'new EncoderParameter(System.Drawing.Imaging.Encoder.Quality')
    [IO.File]::WriteAllText($source, $code, [Text.UTF8Encoding]::new($true))
    & $compiler /nologo /target:winexe /optimize+ "/out:$built" /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll $source
    if ($LASTEXITCODE -ne 0) { throw "C# compilation failed ($LASTEXITCODE)." }
    $output = New-Item -ItemType Directory -Force -Path $OutputDirectory
    $destination = Join-Path $output.FullName 'VRGlassPC.exe'
    Copy-Item -LiteralPath $built -Destination $destination -Force
    Get-FileHash -LiteralPath $destination -Algorithm SHA256
} finally {
    foreach ($file in @('VRGlassPC.cs','VRGlassPC.exe')) {
        $path = Join-Path $scratch.FullName $file
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
    }
    Remove-Item -LiteralPath $scratch.FullName
}
