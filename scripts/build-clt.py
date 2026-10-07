#!/usr/bin/env python3
"""Build the macOS 15 ARM64 app using installed Command Line Tools only."""
import datetime
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DIST = Path(os.environ.get('COMPOSITOR_DIST', str(ROOT / 'dist'))).resolve()
WORK = ROOT / 'build-clt'
SDK = Path(os.environ.get('COMPOSITOR_SDK', '/Library/Developer/CommandLineTools/SDKs/MacOSX15.5.sdk'))
TARGET = 'arm64-apple-macosx15.6'
NAME = 'Compositor-1.4.5-macos15-arm64'
APP = DIST / 'Compositor.app'


def space():
    free = shutil.disk_usage(ROOT).free
    if free < 1536 * 1024**2:
        raise RuntimeError(f'Build paused: only {free / 1024**3:.2f} GiB free; at least 1.5 GiB required.')


def run(args, log=None):
    print('+', ' '.join(map(str, args)), flush=True)
    if log:
        with open(log, 'w') as stream:
            result = subprocess.run(list(map(str, args)), cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print(Path(log).read_text(), file=sys.stderr)
            raise RuntimeError(f'Command failed; see {log}')
    else:
        subprocess.run(list(map(str, args)), cwd=ROOT, check=True)


def capture(args):
    return subprocess.check_output(list(map(str, args)), cwd=ROOT, stderr=subprocess.STDOUT).decode()


def main():
    if sys.platform != 'darwin' or not SDK.is_dir():
        raise RuntimeError('Requires macOS and the installed macOS 15.5 SDK. No tools are installed by this script.')
    # xcrun otherwise exports the system default SDKROOT (26.2) to the linker.
    os.environ['SDKROOT'] = str(SDK)
    DIST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(exist_ok=True)
    space()
    cache = WORK / 'ModuleCache'
    binary = WORK / 'Compositor'
    if '--package-only' not in sys.argv:
        objects = []
        for source in sorted((ROOT / 'Compositor').rglob('*.c')):
            obj = WORK / (source.stem + '.o')
            run(['xcrun', 'clang', '-target', TARGET, '-isysroot', SDK, '-O3', '-c', source, '-o', obj])
            objects.append(obj)
        sources = sorted((ROOT / 'Compositor').rglob('*.swift'))
        rsp = WORK / 'sources.rsp'
        rsp.write_text('\n'.join(json.dumps(str(p)) for p in sources) + '\n')
        # One compiler frontend and one backend thread limit peak work on an 8 GB Mac.
        run(['xcrun', 'swiftc', '-O', '-whole-module-optimization', '-num-threads', '1',
             '-sdk', SDK, '-target', TARGET, '-swift-version', '5', '-module-name', 'Compositor',
             '-module-cache-path', cache, '-import-objc-header', ROOT / 'Compositor/Compositor-Bridging-Header.h',
             '@' + str(rsp), *objects, '-o', binary], DIST / 'macos15-build.log')
    elif not binary.is_file():
        raise RuntimeError('No compiled binary to package')
    space()
    for folder in ['MacOS', 'Resources']:
        (APP / 'Contents' / folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, APP / 'Contents/MacOS/Compositor')
    with open(ROOT / 'Config/Info.plist', 'rb') as stream:
        info = plistlib.load(stream)
    info.update(CFBundleExecutable='Compositor', CFBundleName='Compositor', CFBundleDisplayName='Compositor',
                CFBundleIdentifier='com.wonderassembly.compositor.macos15', CFBundlePackageType='APPL',
                CFBundleShortVersionString='1.4.5', CFBundleVersion='40', LSMinimumSystemVersion='15.6',
                LSApplicationCategoryType='public.app-category.graphics-design', NSPrincipalClass='NSApplication',
                CFBundleIconFile='AppIcon', NSHighResolutionCapable=True)
    with open(APP / 'Contents/Info.plist', 'wb') as stream:
        plistlib.dump(info, stream)
    iconset = WORK / 'AppIcon.iconset'
    iconset.mkdir(exist_ok=True)
    icons = ROOT / 'Compositor/Assets.xcassets/AppIcon.appiconset'
    for size in [16, 32, 128, 256, 512]:
        shutil.copy2(icons / f'app-icon-{size}.png', iconset / f'icon_{size}x{size}.png')
        shutil.copy2(icons / f'app-icon-{size * 2}.png', iconset / f'icon_{size}x{size}@2x.png')
    run(['iconutil', '-c', 'icns', iconset, '-o', APP / 'Contents/Resources/AppIcon.icns'])
    run(['codesign', '--force', '--sign', '-', '--options', 'runtime', '--entitlements',
         ROOT / 'Config/Compositor.entitlements', APP])
    run(['codesign', '--verify', '--deep', '--strict', '--verbose=2', APP])
    executable = APP / 'Contents/MacOS/Compositor'
    if capture(['xcrun', 'lipo', '-archs', executable]).strip() != 'arm64':
        raise RuntimeError('Unexpected architecture')
    load = capture(['xcrun', 'otool', '-L', executable])
    if 'Sparkle' in load or 'SUFeedURL' in info:
        raise RuntimeError('Upstream updater must be absent')
    metadata = capture(['xcrun', 'vtool', '-show-build', executable])
    if 'sdk 15.5' not in metadata and SDK.name == 'MacOSX15.5.sdk':
        raise RuntimeError('Linker did not use SDK 15.5')
    if 'minos 15.6' not in metadata:
        raise RuntimeError('Unexpected Mach-O minimum OS')
    entitlements = plistlib.loads(subprocess.check_output(['codesign', '-d', '--entitlements', ':-', str(APP)], stderr=subprocess.DEVNULL))
    for key in ['com.apple.security.app-sandbox', 'com.apple.security.files.user-selected.read-write']:
        if entitlements.get(key) is not True:
            raise RuntimeError(f'Missing entitlement: {key}')
    report = DIST / f'{NAME}-build-info.txt'
    report.write_text('Compositor macOS 15 compatibility build\n'
                      f'Built (UTC): {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n'
                      'Architecture: arm64\nMinimum macOS: 15.6\nSigning: ad hoc; not notarized\n'
                      'Updater: removed\nC: -O3; Swift: -O, whole-module optimization, one backend thread\n'
                      f'SDK: {SDK}\n' + capture(['xcrun', 'swiftc', '--version']) + '\n' + metadata + '\n'
                      + capture(['codesign', '-dv', '--verbose=2', APP]) + '\n'
                      'Runtime checks are recorded separately in runtime-validation.txt.\n'
                      'Xcode unit-test target not run: full Xcode is unavailable.\n')
    stage = WORK / 'stage'
    stage.mkdir(exist_ok=True)
    run(['ditto', APP, stage / 'Compositor.app'])
    link = stage / 'Applications'
    if not link.is_symlink():
        link.symlink_to('/Applications')
    shutil.copy2(report, stage / 'Build Info.txt')
    shutil.copy2(ROOT / 'LICENSE', stage / 'LICENSE.txt')
    (stage / 'READ ME.txt').write_text('Compositor for macOS 15.6+ on Apple silicon\n\n'
        'Drag Compositor.app to Applications. Keep backups of important projects.\n'
        'This custom build has a separate bundle identifier and no automatic updater.\n'
        'Ad-hoc signed, not Developer ID signed or notarized. Approve only trusted downloaded builds\n'
        'through the normal macOS Privacy & Security interface if macOS blocks opening.\n'
        'No security settings were disabled. See Build Info.txt and runtime-validation.txt.\n')
    runtime = DIST / 'runtime-validation.txt'
    if runtime.exists():
        shutil.copy2(runtime, stage / runtime.name)
    space()
    dmg = DIST / f'{NAME}.dmg'
    run(['hdiutil', 'create', '-ov', '-volname', 'Compositor macOS 15', '-srcfolder', stage, '-format', 'UDZO', dmg])
    run(['hdiutil', 'verify', dmg])
    print(f'Built app: {APP}\nBuilt DMG: {dmg}', flush=True)


if __name__ == '__main__':
    main()
