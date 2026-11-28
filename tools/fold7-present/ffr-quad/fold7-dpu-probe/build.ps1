param(
    [Parameter(Mandatory)][string]$VideoFile,
    [string]$SdkDir = $env:ANDROID_HOME,
    [string]$JavaHome = $env:JAVA_HOME,
    [string]$Platform = 'android-35'
)
$ErrorActionPreference='Stop'
$dir=$PSScriptRoot
if (!$SdkDir -or !$JavaHome) { throw "Set Android SDK and JDK paths" }
$sdk=$SdkDir
$ndk="$sdk/ndk/27.0.12077973/toolchains/llvm/prebuilt/windows-x86_64/bin"
$bt="$sdk/build-tools/36.0.0"
$androidJar="$sdk/platforms/$Platform/android.jar"
New-Item -ItemType Directory -Force -Path "$dir/build/classes","$dir/build/lib/arm64-v8a","$dir/build/assets" | Out-Null
Copy-Item -LiteralPath $VideoFile -Destination "$dir/build/assets/clip.mp4"
& "$ndk/aarch64-linux-android34-clang++.cmd" -std=c++20 -O2 -Wall -Wextra -Werror -fPIC -shared -static-libstdc++ "$dir/probe.cpp" -landroid -llog -o "$dir/build/lib/arm64-v8a/libcv10dpu.so"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$JavaHome/bin/javac.exe" --release 17 -classpath $androidJar -d "$dir/build/classes" "$dir/Probe.java"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$bt/d8.bat" --min-api 34 --lib $androidJar --output "$dir/build" "$dir/build/classes/org/cv10/dpuprobe/Probe.class" "$dir/build/classes/org/cv10/dpuprobe/Probe`$1.class"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$bt/aapt2.exe" link -I $androidJar --manifest "$dir/AndroidManifest.xml" -o "$dir/build/raw.apk"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$JavaHome/bin/jar.exe" --update --no-compress --file "$dir/build/raw.apk" -C "$dir/build" classes.dex -C "$dir/build" lib -C "$dir/build" assets
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$bt/zipalign.exe" -f 4 "$dir/build/raw.apk" "$dir/build/aligned.apk"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$bt/apksigner.bat" sign --ks "$env:USERPROFILE/.android/debug.keystore" --ks-pass pass:android --out "$dir/build/probe.apk" "$dir/build/aligned.apk"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& "$bt/apksigner.bat" verify "$dir/build/probe.apk"
