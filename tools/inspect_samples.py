"""Fetch the CV10 research baseline and inspect it without running any APK."""

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '.research'
DOWNLOADS = WORK / 'downloads'
CATALOG = ROOT / 'research' / 'sources.json'
BUILD_TOOLS_VERSION = '36.0.0'
NATIVE_FOCUS = {
    'libvrservice.so',
    'libWalleDev.so',
    'libvrpose.so',
    'libHVRSDKServerApp.so',
    'libipcserver.so',
    'libruntime_service_module.so',
    'libxr_loader.so',
}


def check_file(path, spec):
    if 'bytes' in spec and path.stat().st_size != spec['bytes']:
        raise ValueError(f'Unexpected byte count for {path.name}')
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != spec['sha256']:
        raise ValueError(f'Unexpected SHA-256 for {path.name}: {digest}')


def fetch_one(spec):
    destination = DOWNLOADS / spec['file']
    if destination.is_file():
        try:
            check_file(destination, spec)
            return destination.name, 'verified cache'
        except ValueError:
            pass

    with tempfile.TemporaryDirectory(prefix='fetch-', dir=DOWNLOADS) as staging:
        staged = Path(staging) / destination.name
        for _ in range(3):
            transfer = subprocess.run([
                'curl.exe', '--fail', '--location', '--silent', '--show-error',
                '--connect-timeout', '12', '--max-time', '75', '--continue-at', '-',
                '--output', staged, spec['url'],
            ], capture_output=True, text=True, check=False)
            if transfer.returncode:
                failure = transfer.stderr.strip()
                if transfer.returncode in (33, 36):
                    staged.unlink(missing_ok=True)
                continue
            try:
                check_file(staged, spec)
                staged.replace(destination)
                return destination.name, 'downloaded and verified'
            except ValueError as error:
                failure = str(error)
                staged.unlink(missing_ok=True)
    raise RuntimeError(f'{destination.name}: {failure}')


def fetch(sources):
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    succeeded = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(fetch_one, source) for source in sources]
        for result in concurrent.futures.as_completed(pending):
            try:
                name, status = result.result()
                print(f'{name}: {status}', flush=True)
            except (OSError, RuntimeError) as error:
                print(f'Fetch failed: {error}', flush=True)
                succeeded = False
    return succeeded


def unpack(path, destination):
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(destination)


def run_tool(command, log):
    log.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(command[0], Path) and not command[0].is_file():
        log.write_text(f'Tool unavailable: {command[0]}\n', encoding='utf-8')
        return 127
    with log.open('wb') as output:
        return subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=False).returncode


def inspect_apk(path, label, build_tools, java, jadx):
    output = WORK / 'apk' / label
    raw = output / 'raw'
    unpack(path, raw)
    with zipfile.ZipFile(path) as archive:
        with (output / 'members.tsv').open('w', encoding='utf-8', newline='\n') as listing:
            listing.write('size\tcrc32\tentry\n')
            for member in archive.infolist():
                listing.write(f'{member.file_size}\t{member.CRC:08x}\t{member.filename}\n')

    results = {}
    recovered = set()
    results['signature'] = run_tool([
        java, '-jar', build_tools / 'lib' / 'apksigner.jar',
        'verify', '--verbose', '--print-certs', path,
    ], output / 'signature.txt')
    results['badging'] = run_tool([
        build_tools / 'aapt2.exe', 'dump', 'badging', path,
    ], output / 'badging.txt')
    results['manifest'] = run_tool([
        build_tools / 'aapt2.exe', 'dump', 'xmltree', '--file', 'AndroidManifest.xml', path,
    ], output / 'manifest.txt')
    if results['manifest']:
        results['manifest_fallback'] = run_tool([
            build_tools / 'aapt.exe', 'dump', 'xmltree', path, 'AndroidManifest.xml',
        ], output / 'manifest-aapt.txt')
        if not results['manifest_fallback']:
            recovered.add('manifest')

    results['jadx'] = run_tool([
        *jadx, '--no-res', '-j', '3', '-d', output / 'jadx', path,
    ], output / 'jadx.txt')
    if results['jadx'] == 3:
        dex_results = {
            f'dexdump_{dex.stem}': run_tool([
                build_tools / 'dexdump.exe', '-d', dex,
            ], output / 'dexdump' / f'{dex.stem}.txt')
            for dex in sorted(raw.glob('classes*.dex'))
        }
        results.update(dex_results)
        if dex_results and not any(dex_results.values()):
            recovered.add('jadx')
    for dex in sorted((raw / 'assets').glob('*.dex')):
        results[f'jadx_asset_{dex.stem}'] = run_tool([
            *jadx, '--no-res', '-j', '3', '-d', output / 'asset-dex' / dex.stem, dex,
        ], output / f'jadx-asset-{dex.stem}.txt')

    readelf = shutil.which('readelf')
    if readelf:
        for library in sorted(raw.rglob('*.so')):
            if library.name in NATIVE_FOCUS:
                entry = library.relative_to(raw).as_posix()
                results[f'elf_{entry}'] = run_tool([
                    readelf, '-W', '-h', '-d', '--dyn-syms', library,
                ], output / 'elf' / (entry + '.txt'))

    (output / 'status.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    errors = {name: status for name, status in results.items() if status and name not in recovered}
    print(f'{label}: raw ZIP extracted; alternate output: {sorted(recovered)}; tool errors: {errors}', flush=True)
    return not errors


def inspect(sdk_sources, community, android_sdk):
    java = shutil.which('java')
    build_tools = android_sdk / 'build-tools' / BUILD_TOOLS_VERSION
    if not java or not (build_tools / 'aapt2.exe').is_file():
        raise RuntimeError('Install Java and Android SDK Build-Tools 36.0.0 or pass --android-sdk.')

    archives = WORK / 'archives'
    apks = []
    for spec in sdk_sources:
        path = DOWNLOADS / spec['file']
        check_file(path, spec)
        destination = archives / spec['name']
        unpack(path, destination)
        if spec['name'].startswith('jadx-'):
            jadx = [java, '-Xmx3g', '-cp', str(destination / 'lib' / '*'), 'jadx.cli.JadxCLI']
        if 'apk_member' in spec:
            embedded = destination / spec['apk_member']
            check_file(embedded, {'sha256': spec['apk_sha256']})
            apks.append((embedded, spec['name']))
            for nested in destination.glob('*.zip'):
                unpack(nested, destination / nested.stem)

    for spec in community:
        path = DOWNLOADS / spec['file']
        check_file(path, spec)
        apks.append((path, path.stem))

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        pending = [pool.submit(inspect_apk, path, label, build_tools, java, jadx) for path, label in apks]
        results = [result.result() for result in pending]
    return all(results)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('fetch', 'inspect'))
    parser.add_argument('--android-sdk', type=Path, default=Path(
        os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
        or Path.home() / 'AppData' / 'Local' / 'Android' / 'Sdk'
    ))
    args = parser.parse_args()
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    community = catalog['community_apks']
    for spec in community:
        spec.setdefault('url', catalog['community_raw_directory'] + spec['file'])

    if args.action == 'fetch':
        success = fetch(catalog['sources'] + community)
    else:
        try:
            success = inspect(catalog['sources'], community, args.android_sdk)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as error:
            parser.exit(1, f'Inspection failed: {error}\n')
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())
