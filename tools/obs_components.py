"""Derive finite CEF packaging ownership from pinned source and retained archive.

This is provenance, not loader policy or native-use attestation. Call only after
verifying the complete donor/overlay receipt, and rederive before every audit.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tarfile

import obs_runtime

DONOR_COMMIT = '72e86655715d9a25d69ce446aa4dd44ba58e10d2'
BROWSER_COMMIT = '85c7f2668936679b43329a9ee9f1e269d9bac812'
ARCHIVE_SHA256 = '8ffc64d06ea74da613eeda7f2aa5d4e98661af6fa3ed8c68724c9a6e4e89ea8e'
CONTRACT_SHA256 = {
    'cmake/linux/helpers.cmake': '47a17eff2c12bf2ca9014eb617599621dcb8cd79e2281f2912b90230522d1b07',
    'cmake/linux/defaults.cmake': '21f2dd8f6c7d9383391be10a710784b2ab06cd158d7b3c1f1f1b32b026778e82',
    'CMakePresets.json': '6349158638e4b619dfde33732769a6bfc68b6868990bd0c215838779e8dffb88',
    'cmake/finders/FindCEF.cmake': '6a975a2f2e40031243321d012e1210c9c5ab5908366daa91cea3cea5eb041733',
    '.github/scripts/utils.zsh/setup_ubuntu': '5e91936fdfc74fb2973a198299660d1195a04428ed0e83f6388cc092fd5d6942',
    'plugins/obs-browser/CMakeLists.txt': 'c300e3898e4c2f4b7f448bb189fc0ab4c43b871144a5e4a66f224382077cb69e',
    'plugins/obs-browser/cmake/os-linux.cmake': '359496480bd5c4b254e4ca5e1310a82239a8fc6c5d14aa9380c15c884a6ddb46',
}
COPY_CONTRACT_SHA256 = {
    **CONTRACT_SHA256,
    'cmake/linux/defaults.cmake': 'a0f28e35cd2f2463ea3adf72b30f4cb3ea7f4a40980a8fdfdb2a3387c9b63712',
    'plugins/obs-browser/cmake/os-linux.cmake': 'fa03af0578c2fd8f35a21bfb02e2759e96f0ee99313d4e34c84d4ad1b9b05244',
}
PAYLOAD = ('libcef.so', 'chrome-sandbox', 'libEGL.so', 'libGLESv2.so',
           'libvk_swiftshader.so', 'libvulkan.so.1')
CONSUMERS = ('obs-browser.so', 'obs-browser-page')
CORE = 'lib/x86_64-linux-gnu/obs-modules/core'
PREPARED = '.deps/cef_binary_7871_linux_x86_64'
ARCHIVE = PREPARED + '.tar.xz'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _regular(root, name):
    path = root / name
    try:
        resolved = path.resolve(strict=True)
        if path != resolved or not resolved.is_relative_to(root):
            raise ValueError('component path has a symlink or noncanonical ancestor: ' + str(path))
        if not stat.S_ISREG(path.lstat().st_mode):
            raise ValueError('component path is not a regular file: ' + str(path))
    except (OSError, RuntimeError) as exc:
        raise ValueError('component path is missing or invalid: ' + str(path)) from exc
    return path


def _record(path):
    digest, info = obs_runtime._file_hash(path)
    return {'sha256': digest, 'size': info.st_size, 'mode': format(stat.S_IMODE(info.st_mode), '04o')}


def _elf_header(header):
    if len(header) < 20 or header[:4] != b'\x7fELF' or header[4:7] != b'\x02\x01\x01' or header[18:20] != b'\x3e\x00':
        raise ValueError('component must be an ELF64 little-endian x86_64 architecture file')


def _git(source, *args):
    try:
        return subprocess.check_output(
            ['/usr/bin/git', '--no-replace-objects', '-C', str(source), *args],
            env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'LANG': 'C'},
            stderr=subprocess.PIPE, text=True, timeout=30).strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError('component donor Git identity unavailable') from exc


def _check_git(source):
    if _git(source, 'rev-parse', 'HEAD') != DONOR_COMMIT:
        raise ValueError('component donor commit differs from pin')
    expected = '160000 commit ' + BROWSER_COMMIT + '\tplugins/obs-browser'
    if _git(source, 'ls-tree', 'HEAD', '--', 'plugins/obs-browser') != expected:
        raise ValueError('component browser gitlink differs from pin')
    browser = obs_runtime._prefix(source / 'plugins/obs-browser')
    if not (browser / '.git').exists() or _git(browser, 'rev-parse', 'HEAD') != BROWSER_COMMIT:
        raise ValueError('component browser checkout commit differs from gitlink')


def _cache(path, base, prepared):
    wanted = {'CEF_ROOT_DIR', 'CEF_LIBRARY_RELEASE', 'CMAKE_INSTALL_LIBDIR',
              'CMAKE_INSTALL_PREFIX', 'CMAKE_BUILD_TYPE'}
    values = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r'([^:#/][^:]*):[^=]+=(.*)', line)
        if not match or match[1] not in wanted:
            continue
        if match[1] in values:
            raise ValueError('duplicate component CMake cache key: ' + match[1])
        values[match[1]] = match[2]
    expected = {'CEF_ROOT_DIR': str(prepared), 'CEF_LIBRARY_RELEASE': str(prepared / 'Release/libcef.so'),
                'CMAKE_INSTALL_PREFIX': str(base / 'build_ubuntu/install/RelWithDebInfo'),
                'CMAKE_BUILD_TYPE': 'RelWithDebInfo'}
    if any(values.get(key) != value for key, value in expected.items()):
        raise ValueError('component CMake cache CEF location or build layout differs from contract')
    if values.get('CMAKE_INSTALL_LIBDIR') not in {'lib/CMAKE_SYSTEM_PROCESSOR-linux-gnu', 'lib/x86_64-linux-gnu'}:
        raise ValueError('component CMake cache library layout is not pinned Ubuntu x86_64')
    return values


class _HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size=-1):
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def _archive_members(path):
    selected = {'Release/' + name for name in PAYLOAD}
    members = {}
    top = set()
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as raw:
            before = os.fstat(raw.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('retained CEF archive is not a regular file')
            # Verify before parsing, then rewind the SAME descriptor. The second
            # digest binds precisely the compressed bytes used for member reads.
            digest = hashlib.sha256()
            while block := raw.read(1024 * 1024):
                digest.update(block)
            if digest.hexdigest() != ARCHIVE_SHA256:
                raise ValueError('retained CEF archive identity differs from pin')
            raw.seek(0)
            identity = {'sha256': digest.hexdigest(), 'size': before.st_size,
                        'mode': format(stat.S_IMODE(before.st_mode), '04o')}
            reader = _HashingReader(raw)
            with tarfile.open(fileobj=reader, mode='r|xz') as archive:
                for entry in archive:
                    name = entry.name.rstrip('/')
                    parts = PurePosixPath(name).parts
                    if (not parts or (name != entry.name and not entry.isdir())
                            or PurePosixPath(name).is_absolute() or '\\' in name
                            or '..' in parts or PurePosixPath(name).as_posix() != name):
                        raise ValueError('unsafe or ambiguous CEF archive member')
                    top.add(parts[0])
                    if len(top) != 1:
                        raise ValueError('CEF archive has ambiguous top components')
                    relative = '/'.join(parts[1:])
                    if relative not in selected:
                        continue
                    if relative in members or not entry.isfile() or entry.issparse():
                        raise ValueError('duplicate or linked CEF archive selected member: ' + relative)
                    stream = archive.extractfile(entry)
                    if stream is None:
                        raise ValueError('unreadable CEF archive selected member: ' + relative)
                    digest = hashlib.sha256()
                    size = 0
                    header = b''
                    with stream:
                        while block := stream.read(1024 * 1024):
                            if len(header) < 20:
                                header += block[:20-len(header)]
                            size += len(block)
                            digest.update(block)
                    _elf_header(header)
                    if size != entry.size:
                        raise ValueError('CEF archive selected member size mismatch')
                    members[relative] = {'archive_path': name, 'sha256': digest.hexdigest(),
                                         'size': size, 'mode': format(entry.mode, '04o')}
            # Bind all compressed bytes, including anything after the tar end marker.
            while reader.read(1024 * 1024):
                pass
            if reader.digest.hexdigest() != ARCHIVE_SHA256:
                raise ValueError('CEF archive changed during member verification')
            state = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mode,
                                  info.st_mtime_ns, info.st_ctime_ns)
            if state(before) != state(os.fstat(raw.fileno())) or state(before) != state(path.lstat()):
                raise ValueError('CEF archive identity changed during verification')
            _regular(Path(path.anchor), str(path.relative_to(path.anchor)))
    except (OSError, tarfile.TarError, EOFError) as exc:
        raise ValueError('invalid CEF archive or selected member') from exc
    if set(members) != selected or len(top) != 1:
        raise ValueError('CEF archive selected member is missing')
    return {'path': ARCHIVE, **identity, 'top_component': next(iter(top)), 'members': members}


def ownership_context(source, copy, prefix, receipt):
    """Return explicit payload/consumer ownership; never infer it from core ancestry."""
    source = obs_runtime._prefix(source)
    copy = obs_runtime._prefix(copy)
    prefix = obs_runtime._prefix(prefix)
    if source.is_relative_to(copy) or copy.is_relative_to(source):
        raise ValueError('component source/copy paths overlap')
    if prefix != copy / 'build_ubuntu/install/RelWithDebInfo':
        raise ValueError('component install prefix differs from exact build layout')
    if (receipt.get('version') != 1 or receipt.get('donor_commit') != DONOR_COMMIT
            or receipt.get('donor_path') != str(source)
            or receipt.get('submodules', {}).get('plugins/obs-browser') != BROWSER_COMMIT):
        raise ValueError('component receipt donor/gitlink identity differs from pin')
    for key in ('donor_inventory_sha256', 'overlay_sha256'):
        if not isinstance(receipt.get(key), str) or not re.fullmatch('[a-f0-9]{64}', receipt[key]):
            raise ValueError('component receipt identity is invalid: ' + key)
    receipt_path = _regular(copy, '.streamstrike-source.json')
    if json.loads(receipt_path.read_text()) != receipt:
        raise ValueError('component receipt differs from current copied-source receipt')
    _check_git(source)
    observed = {receipt_path: _record(receipt_path)}
    contracts = {'donor': {}, 'copy': {}}
    for label, base, expected in (('donor', source, CONTRACT_SHA256), ('copy', copy, COPY_CONTRACT_SHA256)):
        for name, digest in expected.items():
            path = _regular(base, name)
            identity = _record(path)
            if identity['sha256'] != digest:
                raise ValueError('component source contract identity mismatch: ' + label + '/' + name)
            if label == 'copy':
                item = receipt.get('files', {}).get(name, {})
                if item.get('sha256') != digest or item.get('mode') not in {'100644', '100755'}:
                    raise ValueError('component copied contract differs from source receipt: ' + name)
            observed[path] = identity
            contracts[label][name] = identity
    prepared = obs_runtime._prefix(source / PREPARED)
    caches = {}
    for label, base in (('donor', source), ('copy', copy)):
        path = _regular(base, 'build_ubuntu/CMakeCache.txt')
        observed[path] = _record(path)
        caches[label] = {'sha256': observed[path]['sha256'], 'values': _cache(path, base, prepared)}
    archive = _archive_members(_regular(source, ARCHIVE))
    members = {}
    inputs = {}
    for name in PAYLOAD:
        relative = CORE + '/' + name
        prepared_path = _regular(prepared, 'Release/' + name)
        installed_path = _regular(prefix, relative)
        original = _record(prepared_path)
        installed = _record(installed_path)
        archived = archive['members']['Release/' + name]
        if original['sha256'] != archived['sha256'] or installed['sha256'] != archived['sha256']:
            raise ValueError('CEF payload identity differs between archive/prepared/installed: ' + name)
        with installed_path.open('rb') as stream:
            _elf_header(stream.read(20))
        observed[prepared_path] = original
        observed[installed_path] = installed
        inputs['Release/' + name] = {'prepared': original, 'installed': installed}
        members[relative] = {'role': 'payload', 'sha256': installed['sha256']}
    for name in CONSUMERS:
        relative = CORE + '/' + name
        path = _regular(prefix, relative)
        with path.open('rb') as stream:
            _elf_header(stream.read(20))
        observed[path] = _record(path)
        members[relative] = {'role': 'consumer', 'sha256': observed[path]['sha256']}
    for path, identity in observed.items():
        if _regular(Path(path.anchor), str(path.relative_to(path.anchor))) != path or _record(path) != identity:
            raise ValueError('component identity changed during ownership verification')
    _check_git(source)
    return {'version': 1, 'component': 'cef', 'members': members,
            'provenance': {'donor_commit': DONOR_COMMIT, 'browser_commit': BROWSER_COMMIT,
                           'donor_path': str(source), 'copy_path': str(copy), 'prefix': str(prefix),
                           'source_contracts': contracts, 'source_receipt_sha256': _sha(_canonical(receipt)),
                           'source_inventory_sha256': _sha(_canonical(receipt['files'])),
                           'overlay_sha256': receipt['overlay_sha256'], 'archive': archive,
                           'prepared_root': str(prepared), 'payload_identities': inputs, 'caches': caches}}
