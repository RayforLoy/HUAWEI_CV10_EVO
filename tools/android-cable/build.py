"""Build the signed ARM-only CV10 cable updater with the Windows Android SDK."""

from hashlib import sha256
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from zipfile import ZIP_STORED, ZipFile


SOURCE = Path(__file__).resolve().parent
REPO = SOURCE.parents[1]
BUILD = REPO / '.research' / 'android-cable-updater'
APK = REPO / 'firmware_update' / 'tools' / 'android' / 'CV10-Cable-Updater-2A-arm.apk'
IMAGE = REPO / 'firmware_update' / 'firmware' / 'cable' / 'modified' / 'C9.49.6-2A-input-observer.bin'
IMAGE_SHA256 = '34034349f4f991098569b385b7271adb9807a78d9f1dacc49d0413e483d786f5'
ASSET = 'cv10-c9496-input-2a.bin'
ABIS = {
    'arm64-v8a': 'aarch64-linux-android26',
    'armeabi-v7a': 'armv7a-linux-androideabi26',
}
LIBRARY = 'libcv10_crc.so'


def run(*args):
    subprocess.run(args, check=True)


def signing_key(jdk):
    key = BUILD / 'cv10-cable.p12'
    password = BUILD / 'keystore-password.txt'
    if not password.exists():
        if key.exists():
            raise FileNotFoundError(password)
        password.write_text(secrets.token_urlsafe(32) + '\n', encoding='ascii')
    if not key.exists():
        run(jdk / 'bin/keytool.exe', '-genkeypair', '-storetype', 'PKCS12',
            '-keystore', key, '-storepass:file', password, '-alias', 'cable-updater',
            '-keyalg', 'RSA', '-keysize', '3072', '-validity', '3650',
            '-dname', 'CN=CV10 Cable Updater')
    return key, password


def main():
    firmware = IMAGE.read_bytes()
    if len(firmware) != 49152 or sha256(firmware).hexdigest() != IMAGE_SHA256:
        raise ValueError('Expected the measured C9.49.6 2.00 A input image')

    sdk = Path(os.environ.get('ANDROID_HOME') or Path(os.environ['LOCALAPPDATA']) / 'Android/Sdk')
    jdk = Path(os.environ.get('JDK_HOME') or Path(os.environ['ProgramFiles']) / 'Android/Android Studio/jbr')
    bt = sdk / 'build-tools/36.0.0'
    android = sdk / 'platforms/android-36/android.jar'
    ndk = Path(os.environ.get('ANDROID_NDK_HOME') or sdk / 'ndk/26.3.11579264')
    clang = ndk / 'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe'
    java = jdk / 'bin/java.exe'
    BUILD.mkdir(parents=True, exist_ok=True)
    key, password = signing_key(jdk)

    with tempfile.TemporaryDirectory(dir=BUILD) as directory:
        work = Path(directory)
        classes = work / 'classes'
        classes.mkdir()
        assets = work / 'assets'
        assets.mkdir()
        (assets / ASSET).write_bytes(firmware)
        unsigned = work / 'unsigned.apk'
        run(bt / 'aapt2.exe', 'link', '-I', android, '--manifest', SOURCE / 'AndroidManifest.xml',
            '-A', assets, '-o', unsigned)
        run(jdk / 'bin/javac.exe', '-encoding', 'UTF-8', '--release', '8',
            '-cp', android, '-d', classes, *sorted(SOURCE.glob('*.java')))
        run(java, '-cp', bt / 'lib/d8.jar', 'com.android.tools.r8.D8', '--min-api', '26', '--lib', android,
            '--output', work, *sorted(classes.rglob('*.class')))
        with ZipFile(unsigned, 'a') as package:
            package.write(work / 'classes.dex', 'classes.dex')
            for abi, target in ABIS.items():
                compiled = work / abi / LIBRARY
                compiled.parent.mkdir()
                run(clang, f'--target={target}', '-shared', '-fPIC', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-Wl,-z,max-page-size=16384', '-Wl,-soname,' + LIBRARY,
                    SOURCE / 'firmware_crc.c', '-o', compiled)
                package.write(compiled, f'lib/{abi}/{LIBRARY}', compress_type=ZIP_STORED)

        aligned = work / 'aligned.apk'
        signed = work / 'signed.apk'
        run(bt / 'zipalign.exe', '-P', '16', '-f', '4', unsigned, aligned)
        signer = [java, '-jar', bt / 'lib/apksigner.jar']
        run(*signer, 'sign', '--ks', key, '--ks-key-alias', 'cable-updater',
            '--ks-pass', f'file:{password}', '--out', signed, aligned)
        run(*signer, 'verify', '--verbose', signed)
        run(bt / 'zipalign.exe', '-c', '-P', '16', '4', signed)
        with ZipFile(signed) as package:
            libraries = {name for name in package.namelist() if name.startswith('lib/')}
            if libraries != {f'lib/{abi}/{LIBRARY}' for abi in ABIS}:
                raise ValueError('Unexpected native ABI in APK')
            if package.read(f'assets/{ASSET}') != firmware:
                raise ValueError('Embedded image differs from the verified file')
        APK.parent.mkdir(parents=True, exist_ok=True)
        signed.replace(APK)
    print(APK)
    print('SHA-256', sha256(APK.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
