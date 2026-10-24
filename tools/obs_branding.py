"""Build a hash-locked StreamStrike overlay without changing the pinned OBS donor."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

import obs_foundation
import obs_runtime

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'foundation/branding/overlay.json'
COPY = ROOT / 'foundation/streamstrike-obs'
RECEIPT = '.streamstrike-source.json'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def git(source, *args):
    return subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), *args], stderr=subprocess.PIPE)


def safe_path(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '.' in p.parts or '\\' in name or p.as_posix() != name:
        raise ValueError('unsafe source path: ' + name)
    if p.parts[0] in {'.git', 'build_ubuntu', RECEIPT}:
        raise ValueError('reserved source path: ' + name)
    return p


def _canonical_checkout(source, pin, name, blob, content):
    # Only the pinned commit's attributes may explain an EOL checkout.
    # Never invoke clean/smudge filters or accept arbitrary normalized bytes.
    info = Path(git(source, 'rev-parse', '--git-path', 'info/attributes').decode().strip())
    if not info.is_absolute(): info = source / info
    if info.exists() or info.is_symlink():
        raise ValueError('untracked Git info attributes cannot authorize source conversion')
    env = dict(os.environ); env['GIT_ATTR_NOSYSTEM'] = '1'; env.pop('GIT_ATTR_SOURCE', None)
    raw = subprocess.check_output(['git', '--no-replace-objects', '-C', str(source), '-c', 'core.attributesFile=/dev/null',
                                  'check-attr', '--source=' + pin, '-z', 'text', 'eol', 'filter',
                                  'working-tree-encoding', '--', name], env=env, stderr=subprocess.PIPE)
    fields = raw.rstrip(b'\0').split(b'\0')
    attrs = {fields[n+1].decode():fields[n+2].decode() for n in range(0,len(fields),3)}
    if attrs != {'text':'set','eol':'crlf','filter':'unspecified','working-tree-encoding':'unspecified'}:
        raise ValueError('source Git object identity mismatch: ' + name)
    canonical_blob = git(source, 'cat-file', 'blob', blob)
    actual = hashlib.sha1(b'blob ' + str(len(canonical_blob)).encode() + b'\0' + canonical_blob).hexdigest()
    if actual != blob or b'\0' in canonical_blob or b'\r\n' in canonical_blob or content != canonical_blob.replace(b'\n',b'\r\n'):
        raise ValueError('source Git object identity mismatch: ' + name)
    return canonical_blob, {'checkout_conversion':'text-eol-crlf','checkout_sha256':sha256(content)}


def _snapshot(source, pin, prefix=''):
    try:
        head = git(source, 'rev-parse', 'HEAD').decode().strip()
        dirty = git(source, 'status', '--porcelain', '--untracked-files=no').decode()
    except subprocess.CalledProcessError as exc:
        raise ValueError('missing or invalid donor/submodule repository') from exc
    if head != pin:
        raise ValueError('donor/submodule commit differs from pin')
    if dirty:
        raise ValueError('dirty donor/submodule source')
    files = {}; submodules = {}
    for entry in git(source, 'ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if not entry:
            continue
        metadata, raw_name = entry.split(b'\t', 1)
        mode, kind, blob = metadata.decode().split()
        name = raw_name.decode(); safe_path(name)
        full_name = prefix + name; path = source / name
        if kind == 'commit':
            # A missing directory must not fall through to the parent's Git repo.
            if not path.is_dir() or not (path / '.git').exists():
                raise ValueError('submodule is not initialized: ' + full_name)
            nested, descendants = _snapshot(path, blob, full_name + '/')
            files.update(nested); submodules[full_name] = blob; submodules.update(descendants)
            continue
        if kind != 'blob' or mode not in {'100644', '100755', '120000'}:
            raise ValueError('unsupported source mode: ' + full_name)
        if mode == '120000':
            if not path.is_symlink():
                raise ValueError('source symlink identity mismatch: ' + full_name)
            target = os.readlink(path)
            target_path = PurePosixPath(name).parent / target
            # Resolve only lexical traversal; target need not exist yet in the copy.
            normalized = os.path.normpath(str(target_path))
            if PurePosixPath(target).is_absolute() or normalized == '..' or normalized.startswith('../') or '\\' in target:
                raise ValueError('source symlink escapes tree: ' + full_name)
            try:
                contained = path.resolve(strict=True).is_relative_to(source.resolve())
            except (OSError, RuntimeError) as exc:
                raise ValueError('source symlink is missing or cyclic: ' + full_name) from exc
            if not contained:
                raise ValueError('source symlink chain escapes tree: ' + full_name)
            content = target.encode()
        else:
            if path.is_symlink() or not path.is_file():
                raise ValueError('source file identity mismatch: ' + full_name)
            content = path.read_bytes()
            if bool(path.stat().st_mode & stat.S_IXUSR) != (mode == '100755'):
                raise ValueError('source mode identity mismatch: ' + full_name)
        actual = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        checkout = {}
        if actual != blob:
            if mode == '120000':
                raise ValueError('source Git object identity mismatch: ' + full_name)
            content, checkout = _canonical_checkout(source, pin, name, blob, content)
        files[full_name] = {'mode': mode, 'sha256': sha256(content), 'content': content, **checkout}
    return files, submodules


def _overlay(files, overlay, asset_root):
    result = {path: dict(value) for path, value in files.items()}
    changed = set()
    for item in overlay['replacements']:
        name = item['path']; safe_path(name)
        if name in changed or name not in result or result[name]['mode'] == '120000':
            raise ValueError('invalid replacement path: ' + name)
        changed.add(name)
        data = result[name]['content']
        if sha256(data) != item['input_sha256']:
            raise ValueError('overlay input identity mismatch: ' + name)
        text = data.decode('utf-8')
        for edit in item['edits']:
            if not edit['before'] or text.count(edit['before']) != edit['count']:
                raise ValueError('overlay edit count mismatch: ' + name)
            text = text.replace(edit['before'], edit['after'])
        data = text.encode()
        if sha256(data) != item['output_sha256']:
            raise ValueError('overlay output identity mismatch: ' + name)
        result[name].update(content=data, sha256=sha256(data))
    for item in overlay['additions']:
        name = item['path']; safe_path(name); safe_path(item['source'])
        if name in result:
            raise ValueError('overlay addition would overwrite source: ' + name)
        source = asset_root / item['source']
        if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(asset_root.resolve()):
            raise ValueError('invalid overlay asset path: ' + name)
        data = source.read_bytes()
        if sha256(data) != item['sha256']:
            raise ValueError('overlay asset identity mismatch: ' + name)
        result[name] = {'mode': '100644', 'sha256': sha256(data), 'content': data}
    for name in result:
        if any(result.get(str(parent), {}).get('mode') == '120000' for parent in PurePosixPath(name).parents):
            raise ValueError('overlay path traverses source symlink: ' + name)
    return result


def _expected(source, overlay, asset_root):
    if overlay.get('version') != 1:
        raise ValueError('unsupported overlay version')
    files, submodules = _snapshot(source, overlay['donor_commit'])
    original = {p: {k:v for k,v in f.items() if k != 'content'} for p,f in files.items()}
    branded = _overlay(files, overlay, asset_root)
    try:
        version = git(source, 'describe', '--always', '--tags').decode().strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError('source version unavailable') from exc
    receipt = {'version': 1, 'donor_commit': overlay['donor_commit'], 'donor_path': str(source.resolve()),
               'donor_version': version, 'submodules': submodules,
               'donor_inventory_sha256': sha256(canonical(original)), 'overlay_sha256': sha256(canonical(overlay)),
               'files': {p: {k:v for k,v in f.items() if k != 'content'} for p,f in branded.items()}}
    return branded, receipt


def prepare_copy(source, output, overlay, asset_root):
    source = Path(source).resolve(); output = Path(output)
    if output.absolute() != output.resolve():
        raise ValueError('branded destination has a symlink ancestor')
    if output.exists() or output.is_symlink():
        raise FileExistsError('Refusing existing branded source destination: ' + str(output))
    if output.resolve().is_relative_to(source) or source.is_relative_to(output.resolve()):
        raise ValueError('branded source path overlaps donor')
    files, receipt = _expected(source, overlay, asset_root)
    output.mkdir(parents=True, exist_ok=False)
    for name, entry in files.items():
        dest = output / name; dest.parent.mkdir(parents=True, exist_ok=True)
        if entry['mode'] == '120000':
            dest.symlink_to(entry['content'].decode())
        else:
            dest.write_bytes(entry['content']); dest.chmod(0o755 if entry['mode'] == '100755' else 0o644)
    (output / RECEIPT).write_bytes(canonical(receipt) + b'\n')
    verify_copy(output, overlay, asset_root)
    return receipt


def verify_generated_directory(output):
    build = Path(output) / 'build_ubuntu'
    if build.is_symlink() or (build.exists() and not build.is_dir()):
        raise ValueError('build directory is a symlink or not a directory')
    if build.exists():
        for path in build.rglob('*'):
            if path.is_symlink() and not path.resolve().is_relative_to(build.resolve()):
                raise ValueError('build symlink escapes generated directory: ' + str(path.relative_to(build)))


def verify_copy(output, overlay, asset_root, source=None):
    output = Path(output)
    if output.absolute() != output.resolve() or (output / RECEIPT).is_symlink():
        raise ValueError('branded source directory/receipt must not be a symlink')
    verify_generated_directory(output)
    receipt = json.loads((output / RECEIPT).read_text())
    donor = Path(source) if source else Path(receipt['donor_path'])
    expected, identity = _expected(donor, overlay, asset_root)
    if receipt != identity:
        raise ValueError('branded source receipt differs from verified donor/overlay')
    for path in output.rglob('*'):
        name = path.relative_to(output).as_posix()
        if name == RECEIPT or name == 'build_ubuntu' or name.startswith('build_ubuntu/'):
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        if name not in expected:
            raise ValueError('unlisted file in branded source: ' + name)
    for name, entry in expected.items():
        path = output / name
        if entry['mode'] == '120000':
            data = os.readlink(path).encode() if path.is_symlink() else b''
        else:
            if path.is_symlink() or not path.is_file():
                raise ValueError('branded source identity mismatch: ' + name)
            data = path.read_bytes()
            if bool(path.stat().st_mode & stat.S_IXUSR) != (entry['mode'] == '100755'):
                raise ValueError('branded source mode identity mismatch: ' + name)
        if sha256(data) != entry['sha256']:
            raise ValueError('branded source identity mismatch: ' + name)
    return identity


def checked():
    lock = json.loads(obs_foundation.LOCK.read_text()); overlay = json.loads(MANIFEST.read_text())
    if overlay['donor_commit'] != lock['commit']:
        raise ValueError('overlay donor differs from original OBS lock')
    source = ROOT / lock['source_directory']
    # Preserve the original guard, while keeping evidence stdout machine-readable.
    with contextlib.redirect_stdout(sys.stderr):
        obs_foundation.verify(source, lock)
    return source, overlay


def build():
    source, overlay = checked(); receipt = verify_copy(COPY, overlay, ROOT, source)
    if sys.platform != 'linux':
        raise ValueError('branded developer build currently verified on Linux only')
    build_dir = COPY / 'build_ubuntu'; build_dir.mkdir(exist_ok=True)
    stamp = build_dir / 'streamstrike-branding-build.json'; stamp.unlink(missing_ok=True)
    runtime_report = build_dir / 'streamstrike-runtime-dependencies.json'; runtime_report.unlink(missing_ok=True)
    cache = (source / 'build_ubuntu/CMakeCache.txt').read_text()
    cef = re.search(r'^CEF_ROOT_DIR:[^=]+=([^\n]+)$', cache, re.M)
    if not cef or not Path(cef[1]).is_dir():
        raise ValueError('prepared original OBS CEF dependency is missing')
    version = receipt['donor_version']
    if not re.match(r'^\d+\.\d+\.\d+', version):
        raise ValueError('donor version tags required')
    prefix = build_dir / 'install/RelWithDebInfo'
    subprocess.run(['cmake', '--preset', 'ubuntu', '-DCMAKE_BUILD_TYPE=RelWithDebInfo',
                    '-DENABLE_BROWSER=ON', '-DENABLE_RELOCATABLE=ON',
                    '-DOBS_BUILD_NUMBER=0', # deterministic developer build; no source-tree cache write
                    '-DCMAKE_INSTALL_PREFIX:PATH=' + str(prefix), '-DCEF_ROOT_DIR:PATH=' + cef[1],
                    '-DOBS_VERSION_OVERRIDE=' + version + '-streamstrike'], cwd=COPY, check=True)
    subprocess.run(['cmake', '--build', 'build_ubuntu'], cwd=COPY, check=True)
    subprocess.run(['cmake', '--install', 'build_ubuntu', '--prefix', str(prefix)], cwd=COPY, check=True)
    verify_copy(COPY, overlay, ROOT, source); checked()
    binary = obs_foundation.executable(COPY)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError('branded OBS binary missing')
    runtime = obs_runtime.audit_runtime(prefix)
    with runtime_report.open('xb') as report:
        report.write(canonical(runtime) + b'\n')
    identity = {'donor_commit': overlay['donor_commit'], 'overlay_sha256': receipt['overlay_sha256'],
                                'source_inventory_sha256': sha256(canonical(receipt['files'])),
                                'executable_sha256': sha256(binary.read_bytes()),
                                'runtime_inventory_sha256': sha256(canonical(runtime['inventory'])),
                                'runtime_report_sha256': sha256(canonical(runtime))}
    with stamp.open('xb') as record:
        record.write(canonical(identity) + b'\n')


def runtime_digest(prefix):
    return sha256(canonical(obs_runtime.runtime_inventory(prefix)))


def validate_build(output, receipt):
    verify_generated_directory(output)
    binary = obs_foundation.executable(output)
    stamp_path = output / 'build_ubuntu/streamstrike-branding-build.json'
    report_path = output / 'build_ubuntu/streamstrike-runtime-dependencies.json'
    if stamp_path.is_symlink() or report_path.is_symlink():
        raise ValueError('build receipt/report must not be symlinks')
    stamp = json.loads(stamp_path.read_text())
    report = json.loads(report_path.read_text())
    expected = {'donor_commit': receipt['donor_commit'], 'overlay_sha256': receipt['overlay_sha256'],
                'source_inventory_sha256': sha256(canonical(receipt['files'])),
                'executable_sha256': sha256(binary.read_bytes()),
                'runtime_inventory_sha256': runtime_digest(output / 'build_ubuntu/install/RelWithDebInfo'),
                'runtime_report_sha256': sha256(canonical(report))}
    if stamp != expected or not os.access(binary, os.X_OK):
        raise ValueError('branded OBS build receipt differs from source or executable')
    return binary, stamp


def verify_build():
    source, overlay = checked(); receipt = verify_copy(COPY, overlay, ROOT, source)
    binary, stamp = validate_build(COPY, receipt)
    # Recheck loader closure before launch; never inject search paths or disable modules.
    runtime = obs_runtime.audit_runtime(COPY / 'build_ubuntu/install/RelWithDebInfo')
    if sha256(canonical(runtime['inventory'])) != stamp['runtime_inventory_sha256']:
        raise ValueError('runtime changed during dependency verification')
    if sha256(canonical(runtime)) != stamp['runtime_report_sha256']:
        raise ValueError('fresh dependency report differs from recorded build closure')
    return binary, stamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare','verify','build','run','capture','evidence'], nargs='?', default='run')
    args = parser.parse_args()
    try:
        if args.action == 'prepare':
            source, overlay = checked(); prepare_copy(source, COPY, overlay, ROOT); checked()
        elif args.action == 'verify':
            source, overlay = checked(); verify_copy(COPY, overlay, ROOT, source)
        elif args.action == 'build':
            build()
        else:
            binary, stamp = verify_build()
            if args.action == 'evidence':
                print(json.dumps(stamp, indent=2))
            else:
                launch_args = [str(binary)]
                if args.action == 'capture':
                    if not os.environ.get('STREAMSTRIKE_CAPTURE_DIR') or not os.environ.get('XDG_CONFIG_HOME'):
                        raise ValueError('capture requires an explicit output and isolated configuration')
                    launch_args += ['--safe-mode', '--disable-updater', '--disable-missing-files-check']
                subprocess.run(launch_args, cwd=binary.parent, check=True)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print('StreamStrike OBS branding: ' + str(exc), file=sys.stderr); return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
