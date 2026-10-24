"""Inventory and audit an installed, locally built OBS ELF runtime without loader overrides.

This is a dependency-closure check, not source-build or native-use attestation.
Only audit trusted build outputs: ldd invokes the platform's dynamic loader.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys


_TOOL_ENV = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'LANG': 'C'}


def _prefix(prefix):
    path = Path(prefix).absolute()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError('runtime prefix is missing or invalid') from exc
    if path != resolved:
        raise ValueError('runtime prefix has a symlink or noncanonical ancestor')
    if not path.is_dir():
        raise ValueError('runtime prefix is not a directory')
    return path


def _file_hash(path):
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('runtime entry is not a regular file: ' + str(path))
            digest = hashlib.sha256()
            while block := stream.read(1024 * 1024):
                digest.update(block)
            after = os.fstat(stream.fileno())
        current = path.lstat()
    except OSError as exc:
        raise ValueError('runtime file could not be read: ' + str(path)) from exc
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode)
    if identity(before) != identity(after) or identity(before) != identity(current):
        raise ValueError('runtime file changed while being inventoried: ' + str(path))
    return digest.hexdigest(), before


def runtime_inventory(prefix):
    """Return deterministic relative file identities; never follow directory symlinks."""
    root = _prefix(prefix)
    files = {}

    def visit(directory):
        with os.scandir(directory) as scan:
            entries = sorted(scan, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            name = path.relative_to(root).as_posix()
            info = path.lstat()
            mode = format(stat.S_IMODE(info.st_mode), '04o')
            if stat.S_ISLNK(info.st_mode):
                target = os.readlink(path)
                # Reject lexical escape before following any possibly external chain.
                lexical = Path(os.path.abspath(path.parent / target))
                if not lexical.is_relative_to(root):
                    raise ValueError('runtime symlink escapes prefix: ' + name)
                try:
                    resolved = path.resolve(strict=True)
                except (OSError, RuntimeError) as exc:
                    raise ValueError('runtime symlink is missing, broken or cyclic: ' + name) from exc
                if not resolved.is_relative_to(root):
                    raise ValueError('runtime symlink chain escapes prefix: ' + name)
                files[name] = {'kind': 'symlink', 'mode': mode, 'target': target,
                               'resolved': resolved.relative_to(root).as_posix()}
            elif stat.S_ISDIR(info.st_mode):
                visit(path)
            elif stat.S_ISREG(info.st_mode):
                digest, actual = _file_hash(path)
                files[name] = {'kind': 'file', 'mode': format(stat.S_IMODE(actual.st_mode), '04o'),
                               'sha256': digest, 'size': actual.st_size}
            else:
                raise ValueError('unsupported runtime entry (not regular file/directory/symlink): ' + name)

    visit(root)
    return {'version': 1, 'files': files}


def _tool(name, *arguments):
    executable = shutil.which(name, path=_TOOL_ENV['PATH'])
    if executable is None:
        raise ValueError('runtime audit tool is missing: ' + name)
    try:
        return subprocess.run([executable, *map(str, arguments)], cwd='/', env=dict(_TOOL_ENV),
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError('runtime audit tool failed: ' + name) from exc


def _is_elf(path):
    with path.open('rb') as stream:
        return stream.read(4) == b'\x7fELF'


def _elf_metadata(path):
    header = _tool('readelf', '--file-header', '--wide', path)
    dynamic = _tool('readelf', '--dynamic', '--wide', path)
    if header.returncode or dynamic.returncode:
        raise ValueError('invalid or unreadable ELF: ' + str(path))
    match = re.search(r'^\s*Type:\s+(\S+)', header.stdout, re.MULTILINE)
    if not match or match.group(1) not in {'EXEC', 'DYN', 'REL', 'CORE'}:
        raise ValueError('unsupported ELF header: ' + str(path))
    tags = {'NEEDED': [], 'SONAME': [], 'RUNPATH': [], 'RPATH': []}
    for line in dynamic.stdout.splitlines():
        match_tag = re.search(r'\((NEEDED|SONAME|RUNPATH|RPATH)\).*\[([^\]]*)\]', line)
        if match_tag:
            tags[match_tag.group(1)].append(match_tag.group(2))
    if any(len(tags[key]) > 1 for key in ('SONAME', 'RUNPATH', 'RPATH')) or any(not n for n in tags['NEEDED']):
        raise ValueError('ambiguous ELF dynamic metadata: ' + str(path))
    return {'elf_type': match.group(1), 'needed': tags['NEEDED'],
            'soname': tags['SONAME'][0] if tags['SONAME'] else None,
            'runpath': tags['RUNPATH'][0].split(':') if tags['RUNPATH'] else [],
            'rpath': tags['RPATH'][0].split(':') if tags['RPATH'] else []}


def _loader_edges(path):
    result = _tool('ldd', path)
    output = result.stdout + '\n' + result.stderr
    if re.search(r'=>\s+not found(?:\s|$)', output):
        raise ValueError('unresolved runtime dependency for ' + str(path) + ': ' + output.strip())
    if result.returncode:
        raise ValueError('ldd failed for ' + str(path) + ': ' + output.strip())
    edges = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.fullmatch(r'(.+?)\s+=>\s+(.+?)\s+\(0x[0-9a-fA-F]+\)', line)
        if match:
            name, resolved = match.groups()
            if not Path(resolved).is_absolute():
                raise ValueError('nonabsolute loader resolution for ' + str(path) + ': ' + line)
            edges.append({'name': name, 'resolved': resolved})
            continue
        match = re.fullmatch(r'(/.+?)\s+\(0x[0-9a-fA-F]+\)', line)
        if match:
            edges.append({'name': match.group(1), 'resolved': match.group(1)})
            continue
        match = re.fullmatch(r'(linux-(?:vdso|gate)\S*)\s+\(0x[0-9a-fA-F]+\)', line)
        if match:
            edges.append({'name': match.group(1), 'resolved': None, 'scope': 'virtual'})
            continue
        raise ValueError('unrecognized loader output for ' + str(path) + ': ' + line)
    return edges


def audit_runtime(prefix):
    """Audit every installed ELF independently, including plugins not needed by bin/obs."""
    root = _prefix(prefix)
    inventory = runtime_inventory(root)
    main = root / 'bin/obs'
    if not main.is_file() or not _is_elf(main):
        raise ValueError('installed bin/obs must be a real ELF executable')
    actual_main = main.resolve(strict=True)
    if not actual_main.is_relative_to(root) or not actual_main.stat().st_mode & 0o111:
        raise ValueError('installed bin/obs must be executable within the prefix')
    metadata = {}
    elf = {}
    shipped = {}
    for name, record in inventory['files'].items():
        if record['kind'] != 'file':
            continue
        path = root / name
        if not _is_elf(path):
            continue
        data = _elf_metadata(path)
        metadata[path] = data
        elf[name] = dict(data)
        if data['soname']:
            prior = shipped.setdefault(data['soname'], path)
            if prior != path:
                raise ValueError('shipped SONAME has multiple canonical targets: ' + data['soname'])
    if metadata[actual_main]['elf_type'] not in {'EXEC', 'DYN'}:
        raise ValueError('installed bin/obs is not an executable ELF type')
    ownership_failures = []
    for name, record in elf.items():
        path = root / name
        if not record['needed']:
            # Static executables and dependency-free DSOs/relocatable objects have
            # no closure to ask ldd for; ldd may reject them despite a valid ELF.
            record['linkage'] = 'static' if record['elf_type'] == 'EXEC' else 'no-needed'
            record['dependencies'] = []
            continue
        record['linkage'] = 'dynamic'
        edges = _loader_edges(path)
        seen = set()
        root_failures = []
        closure = {path}
        for edge in edges:
            seen.add(edge['name'])
            if edge['resolved'] is None:
                continue
            try:
                resolved = Path(edge['resolved']).resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError('resolved runtime dependency is missing: ' + edge['name']) from exc
            if not resolved.is_file() or not _is_elf(resolved):
                raise ValueError('loader dependency is not a real ELF: ' + str(resolved))
            if resolved not in metadata:
                metadata[resolved] = _elf_metadata(resolved)
            closure.add(resolved)
            soname = metadata[resolved]['soname']
            # Check both requested name and actual ELF SONAME: an alias must not
            # bypass the guard by resolving to a system copy of a shipped library.
            for identity in dict.fromkeys((edge['name'], soname)):
                if identity in shipped and shipped[identity] != resolved:
                    # Retain the same rejection predicate. Collect diagnostic
                    # context rather than hiding every root after the first.
                    root_failures.append({
                        'audited_elf': name, 'identity': identity,
                        'requested_name': edge['name'], 'resolved': str(resolved),
                        'expected': str(shipped[identity]), 'resolved_soname': soname,
                        'root_needed': record['needed'], 'root_runpath': record['runpath'],
                        'root_rpath': record['rpath'], 'direct_needed': identity in record['needed']})
                    # Keep the first actionable evidence if a subsequent strict
                    # loader/metadata guard fails before this root completes.
                    print('StreamStrike ELF ownership diagnostic: ' +
                          json.dumps(root_failures[-1], sort_keys=True), file=sys.stderr)
            # ldd may print an absolute interpreter path instead of its SONAME.
            # Trust the resolved ELF metadata, never a path-basename inference.
            if soname:
                seen.add(soname)
            inside = resolved.is_relative_to(root)
            if inside and resolved.relative_to(root).as_posix() not in inventory['files']:
                raise ValueError('loader reached an unrecorded installed library: ' + str(resolved))
            edge.update(resolved=str(resolved), soname=soname, scope='shipped' if inside else 'system')
        missing = set(record['needed']) - seen
        if missing:
            raise ValueError('unresolved direct dependencies absent from loader output: ' + ', '.join(sorted(missing)))
        record['dependencies'] = edges
        for failure in root_failures:
            # ldd is a flattened closure, not a proven parent-child load trace.
            # These are declared DT_NEEDED requesters, not inferred loader parents.
            failure['declared_requesters'] = [
                {'path': str(candidate), 'needed': metadata[candidate]['needed'],
                 'runpath': metadata[candidate]['runpath'], 'rpath': metadata[candidate]['rpath']}
                for candidate in sorted(closure)
                if failure['identity'] in metadata[candidate]['needed']]
            print('StreamStrike ELF ownership diagnostic: ' +
                  json.dumps(failure, sort_keys=True), file=sys.stderr)
        ownership_failures.extend(root_failures)
    if runtime_inventory(root) != inventory:
        raise ValueError('installed runtime changed during dependency audit')
    if ownership_failures:
        raise ValueError('shipped SONAME resolved outside its exact target: ' +
                         json.dumps(ownership_failures, sort_keys=True))
    return {'version': 1, 'inventory': inventory, 'elf': elf,
            'entrypoint': actual_main.relative_to(root).as_posix()}
