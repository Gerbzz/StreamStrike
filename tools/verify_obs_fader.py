"""Require complete original/migrated libobs all-three-fader public-API parity on Linux."""
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
COUNT = 1000
FADER_TYPES = {'cubic': 0, 'iec': 1, 'log': 2}


def validate_pair(original, migrated):
    if original['library'] == migrated['library'] or original['sha256'] == migrated['sha256']:
        raise ValueError('original and migrated libraries must be distinct')
    _validate_trace(original, migrated, 'iec')
    for proof in (original, migrated):
        if set(proof.get('additional', {})) != {'cubic', 'log'}:
            raise ValueError('native trace must contain cubic and logarithmic faders')
    for kind in ('cubic', 'log'):
        _validate_trace(original['additional'][kind], migrated['additional'][kind], kind)
    return True


def _validate_trace(original, migrated, kind):
    for proof in (original, migrated):
        rows = proof['rows']
        if len(rows) != COUNT or any(len(r) != 4 or any(type(v) is not int for v in r) for r in rows):
            raise ValueError('incomplete native fader trace: ' + kind)
        if [r[0] for r in rows] != [bits(value) for _, value in cases(kind)] or any(r[1] not in (0, 1) or any(v < 0 or v > 0xffffffff for v in r) for r in rows):
            raise ValueError('native fader coverage or values differ: ' + kind)
    if original['rust_callback'] is not False or migrated['rust_callback'] is not True:
        raise ValueError('migrated public API must select actual Rust callback: ' + kind)
    if original['rows'] != migrated['rows']:
        raise ValueError('complete libobs public API mismatch: ' + kind)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def cases(kind='iec'):
    if kind not in FADER_TYPES:
        raise ValueError('unknown fader type')
    edges = [float('-inf'), float('inf'), float('nan'), -0.0, 0.0, 1.0,
             .75, .5, .3, .15, .075, .025, .001, -9, -20, -30, -40, -50, -60, -114, -150]
    if kind != 'iec':
        # Retain IEC sequence exactly; add remaining formulas' limits separately.
        edges += [-96.0, 6.0] + [struct.unpack('<f', struct.pack('<I', n))[0]
                               for n in (0x26800001, 0x54cb2ff5)]
    neighbors = [struct.unpack('<f', struct.pack('<I', bits(x) + delta))[0]
                 for x in edges if math.isfinite(x) and x != 0.0 for delta in (-1, 1)]
    anchors = edges + neighbors
    remaining = 500 - len(anchors)
    return [(0, x) for x in anchors + [i / (remaining - 2) for i in range(remaining)]] + [
        (1, x) for x in anchors + [-160 + i / 2 for i in range(remaining)]]


class DlInfo(ctypes.Structure):
    _fields_ = [('name', ctypes.c_char_p), ('base', ctypes.c_void_p),
                ('symbol', ctypes.c_char_p), ('address', ctypes.c_void_p)]


def inspect_library(path, migrated):
    path = Path(path).resolve(strict=True)
    before = digest(path)
    library = ctypes.CDLL(str(path), mode=os.RTLD_LOCAL | os.RTLD_NOW)
    addr = ctypes.CDLL(None).dladdr
    addr.argtypes = [ctypes.c_void_p, ctypes.POINTER(DlInfo)]; addr.restype = ctypes.c_int
    info = DlInfo()
    if not addr(ctypes.cast(library.obs_fader_create, ctypes.c_void_p), ctypes.byref(info)) or Path(os.fsdecode(info.name)).resolve() != path:
        raise ValueError('public API loaded a different libobs')
    create = library.obs_fader_create; create.argtypes = [ctypes.c_int]; create.restype = ctypes.c_void_p
    destroy = library.obs_fader_destroy; destroy.argtypes = [ctypes.c_void_p]; destroy.restype = None
    set_db = library.obs_fader_set_db; set_def = library.obs_fader_set_deflection
    for function in (set_db, set_def):
        function.argtypes = [ctypes.c_void_p, ctypes.c_float]; function.restype = ctypes.c_bool
    get_db = library.obs_fader_get_db; get_def = library.obs_fader_get_deflection
    for function in (get_db, get_def):
        function.argtypes = [ctypes.c_void_p]; function.restype = ctypes.c_float
    get_callback = library.obs_fader_db_to_def
    get_callback.argtypes = [ctypes.c_void_p]; get_callback.restype = ctypes.c_void_p
    symbols = subprocess.check_output(['nm', '--defined-only', str(path)], text=True)
    entries = [line.split() for line in symbols.splitlines()]
    rust = {parts[2]: int(parts[0], 16) for parts in entries if len(parts) == 3 and parts[2].startswith('streamstrike_') and parts[2].endswith(('_def_to_db', '_db_to_def'))}
    expected_symbols = {'streamstrike_' + kind + '_' + direction
                        for kind in FADER_TYPES for direction in ('def_to_db', 'db_to_def')}
    if (migrated and set(rust) != expected_symbols) or (not migrated and rust):
        raise ValueError('unexpected Rust implementation symbols')
    traces = {}
    # Pinned OBS enum: cubic=0, IEC=1, logarithmic=2. Original constructors and
    # state/clamping remain in libobs; every public conversion selects Rust.
    for kind, enum in FADER_TYPES.items():
        fader = create(enum)
        if not fader:
            raise ValueError('original public constructor failed: ' + kind)
        try:
            rust_callback = bool(rust) and get_callback(fader) == info.base + rust['streamstrike_' + kind + '_db_to_def']
            if migrated and not rust_callback:
                raise ValueError('actual dispatch does not point to Rust: ' + kind)
            rows = []
            for operation, value in cases(kind):
                accepted = (set_db if operation else set_def)(fader, value)
                rows.append([bits(value), int(accepted), bits(get_db(fader)), bits(get_def(fader))])
            traces[kind] = {'rows': rows, 'rust_callback': rust_callback}
        finally:
            destroy(fader)

    if digest(path) != before:
        raise ValueError('native library changed during oracle')
    return {'library': str(path), 'sha256': before, **traces.pop('iec'), 'additional': traces}


def library_path(prefix):
    found = {p.resolve(strict=True) for p in Path(prefix).rglob('libobs.so*') if p.is_file()}
    if len(found) != 1:
        raise ValueError('expected one complete libobs installation')
    return found.pop()


def run():
    import obs_branding, obs_foundation
    source, overlay = obs_branding.checked()
    _, build = obs_branding.verify_build()
    original = library_path(source / 'build_ubuntu/install/RelWithDebInfo')
    migrated = library_path(obs_branding.COPY / 'build_ubuntu/install/RelWithDebInfo')
    evidence = ROOT / 'obs-fader-evidence'
    evidence.mkdir(exist_ok=False)
    hashes = [digest(original), digest(migrated)]
    proofs = []
    # Separate processes avoid same-SONAME resolution contaminating the comparison.
    env = {k: v for k, v in os.environ.items() if not k.startswith(('LD_', 'DYLD_', 'PYTHON'))}
    for index, path in enumerate((original, migrated)):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--one', str(path), str(index)],
                                cwd=ROOT, env=env, text=True, capture_output=True, timeout=120)
        (evidence / f'{index}.stdout.json').write_text(result.stdout)
        (evidence / f'{index}.stderr.txt').write_text(result.stderr)
        result.check_returncode()
        proof = json.loads(result.stdout)
        if proof['library'] != str(path) or proof['sha256'] != hashes[index]:
            raise ValueError('trace identity differs from exact requested library')
        proofs.append(proof)
    validate_pair(*proofs)
    if hashes != [digest(original), digest(migrated)]:
        raise ValueError('libobs changed during differential oracle')
    obs_branding.checked()
    if obs_branding.verify_build()[1] != build:
        raise ValueError('source/build identity changed during oracle')
    (evidence / 'verified.json').write_text(json.dumps({'cases': COUNT * len(FADER_TYPES), 'cases_per_type': COUNT, 'fader_types': FADER_TYPES, 'build': build,
        'original_sha256': hashes[0], 'migrated_sha256': hashes[1],
        'verifier_sha256': digest(__file__),
        'scope': 'Six conversion bodies in complete Linux libobs; system libm FFI and C fader state remain; not full fader/OBS rewrite or media acceptance'}, indent=2) + '\n')
    print(f'Passed {COUNT * len(FADER_TYPES)} complete-libobs public-API cases; all three actual callbacks point to Rust')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--one':
        print(json.dumps(inspect_library(sys.argv[2], bool(int(sys.argv[3])))))
    elif len(sys.argv) == 1:
        run()
    else:
        raise SystemExit('usage: verify_obs_fader.py')
