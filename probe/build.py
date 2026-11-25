"""Build the CV10 debug APK with the Windows Android SDK and a JDK."""
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

src = Path(__file__).resolve().parent
out = src.parent / ".research" / "probe"
out.mkdir(parents=True, exist_ok=True)
sdk = Path(os.environ.get("ANDROID_HOME") or Path(os.environ["LOCALAPPDATA"]) / "Android/Sdk")
jdk = Path(os.environ.get("JDK_HOME") or Path(os.environ["ProgramFiles"]) / "Android/Android Studio/jbr")
bt = sdk / "build-tools/36.0.0"
android = sdk / "platforms/android-36/android.jar"
key = out / "debug.p12"
apk = out / "cv10-display.apk"

def run(*args):
    subprocess.run(args, check=True)

with tempfile.TemporaryDirectory(dir=out) as tmp:
    work = Path(tmp)
    unsigned = work / "unsigned.apk"
    run(bt / "aapt2.exe", "link", "-I", android, "--manifest", src / "AndroidManifest.xml", "-o", unsigned)
    run(jdk / "bin/javac.exe", "-encoding", "UTF-8", "--release", "8", "-cp", android,
        "-d", work, *sorted(src.glob("*.java")))
    run(jdk / "bin/java.exe", "-cp", bt / "lib/d8.jar", "com.android.tools.r8.D8",
        "--min-api", "26", "--lib", android, "--output", work, *work.rglob("*.class"))
    with ZipFile(unsigned, "a") as package:
        package.write(work / "classes.dex", "classes.dex")
    aligned = work / "aligned.apk"
    run(bt / "zipalign.exe", "-f", "4", unsigned, aligned)
    if not key.exists():
        run(jdk / "bin/keytool.exe", "-genkeypair", "-storetype", "PKCS12", "-keystore", key,
            "-storepass", "android", "-alias", "debug", "-keyalg", "RSA", "-validity", "3650",
            "-dname", "CN=Local CV10 Debug")
    signer = [jdk / "bin/java.exe", "-jar", bt / "lib/apksigner.jar"]
    run(*signer, "sign", "--ks", key, "--ks-pass", "pass:android", "--out", apk, aligned)
    run(*signer, "verify", apk)
print(apk)
