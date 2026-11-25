"""Build the Fold7/CV10 debug APK from the 11.19 source distribution (Windows)."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DIGEST = "0f6de4efe4e19c4c1097e6019c639e4e4a046aa4cbd946813d1dc2781c492388"
ANDROID = "{http://schemas.android.com/apk/res/android}"


def run(*args, cwd=None):
    subprocess.run([str(arg) for arg in args], cwd=cwd, check=True)


def build(archive, output, work, sdk):
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != DIGEST:
            raise ValueError("Patch targets the 11.19 distribution. Check the archive hash.")
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            parts = member.split("/", 2)
            if len(parts) != 3 or parts[1] != "Source":
                continue
            relative = parts[2]
            if not relative.startswith(("apktool/", "native/", "tools/", "deps/openxr_aar/")):
                continue
            if member.endswith("/"):
                continue
            dest = work / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, dest.open("wb") as target:
                shutil.copyfileobj(source, target)

    # Normalize mixed upstream line endings before applying the source patch.
    for name in ("xr_session.cpp", "xr_session.h"):
        file = work / "native" / name
        file.write_bytes(file.read_text(encoding="utf8").encode())
    run("git", "init", "-q", cwd=work)
    run("git", "apply", "--ignore-space-change", HERE / "monado.patch", cwd=work)
    prefab = work / "deps/openxr_aar/prefab/modules"
    ndk = Path(os.getenv("ANDROID_NDK_HOME", sdk / "ndk/28.2.13676358")) / "toolchains/llvm/prebuilt/windows-x86_64/bin"
    app = work / "apktool"
    lib = app / "lib/arm64-v8a/libp5m-vr.so"
    run(ndk / "clang++.exe", "--target=aarch64-linux-android29", "-std=c++17", "-shared",
        "-fPIC", "-O2", "-s", "-Wl,--no-undefined,-soname,libp5m-vr.so,-z,max-page-size=16384",
        "-I", prefab / "headers/include", *sorted((work / "native").glob("*.cpp")),
        prefab / "openxr_loader/libs/android.arm64-v8a/libopenxr_loader.so",
        "-llog", "-landroid", "-lEGL", "-lGLESv3", "-ljnigraphics", "-o", lib)

    manifest = app / "AndroidManifest.xml"
    ET.register_namespace("android", ANDROID[1:-1])
    doc = ET.parse(manifest)
    root = doc.getroot()
    loader = ET.parse(work / "deps/openxr_aar/AndroidManifest.xml").getroot()
    for permission in loader.findall("uses-permission"):
        if all(item.get(ANDROID+"name") != permission.get(ANDROID+"name")
               for item in root.findall("uses-permission")):
            root.insert(0, permission)
    root.find("queries").extend(loader.find("queries"))
    doc.write(manifest, encoding="utf-8", xml_declaration=True)
    jar = work / "tools/apktool.jar"
    frameworks = work / "framework-cache"
    run("java", "-jar", jar, "if", "-p", frameworks, work / "tools/framework/1.apk")
    run("java", "-jar", jar, "b", "-p", frameworks, app, "-o", work / "unsigned.apk")
    bt = sdk / "build-tools/36.0.0"
    run(bt / "zipalign.exe", "-P", "16", "4", work / "unsigned.apk", work / "aligned.apk")
    key = Path.home() / ".android/debug.keystore"
    run(bt / "apksigner.bat", "sign", "--ks", key, "--ks-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey", "--v4-signing-enabled", "false",
        "--out", work / "signed.apk", work / "aligned.apk")
    run(bt / "apksigner.bat", "verify", "--verbose", work / "signed.apk")
    run(bt / "zipalign.exe", "-c", "-P", "16", "4", work / "signed.apk")
    os.replace(work / "signed.apk", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path,
                        default=ROOT / "resources/PiliPlus_VR_Quest3_11.19.zip")
    parser.add_argument("--output", type=Path, default=ROOT / ".research/piliplus/PiliPlus-CV10.apk")
    args = parser.parse_args()
    args.output.parent.mkdir(exist_ok=True, parents=True)
    sdk = os.getenv("ANDROID_HOME") or os.getenv("ANDROID_SDK_ROOT") or Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk"
    with tempfile.TemporaryDirectory(dir=args.output.parent.resolve()) as temp:
        build(args.archive, args.output.resolve(), Path(temp), Path(sdk))
    print(args.output.resolve())

