"""Build Rust IEC archive only after an exact-compiler original-C oracle passes."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compiler_argv(database, source):
    entries = [e for e in json.loads(Path(database).read_text())
               if (Path(e['directory']) / e['file']).resolve() == Path(source).resolve()]
    if len(entries) != 1:
        raise ValueError('need exactly one actual libobs audio compile command')
    entry = entries[0]
    argv = entry.get('arguments') or shlex.split(entry['command'])
    if any(a.startswith('@') for a in argv):
        raise ValueError('response-file compile commands require explicit support')
    kept = [argv[0]]
    i = 1
    removed_source = False
    while i < len(argv):
        arg = argv[i]
        if arg in ('-o', '-MF', '-MT', '-MQ'):
            i += 2
            continue
        if arg in ('-c', '-MD', '-MMD', '-MP'):
            i += 1
            continue
        if (Path(entry['directory']) / arg).resolve() == Path(source).resolve():
            removed_source = True
        else:
            kept.append(arg)
        i += 1
    if not removed_source:
        raise ValueError('compile command source identity missing')
    return entry, kept


def build(database, source, rustc, compiler_path, output):
    here = Path(__file__).resolve().parent
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    profile_path = output.with_suffix('.profile.json')
    # Preserve prior useful artifacts, but never leave stale accepted outputs.
    for accepted in (output, profile_path):
        if accepted.exists():
            accepted.replace(accepted.with_name(accepted.name + '.previous-' + sha(accepted)))
    entry, cc = compiler_argv(database, source)
    cwd = entry['directory']
    if Path(shutil.which(cc[0]) or cc[0]).resolve() != Path(compiler_path).resolve():
        raise ValueError('compiler launcher requires explicit provenance support')
    # Compile once using the exact libobs invocation, not guessed CMake globals.
    obj = output.with_suffix('.oracle.o')
    subprocess.run([*cc, '-c', str(here / 'oracle.c'), '-o', str(obj)], cwd=cwd, check=True)
    compiler = subprocess.run([cc[0], '--version'], text=True, capture_output=True, check=True)
    macros = subprocess.run([*cc, '-dM', '-E', '-x', 'c', '/dev/null'], cwd=cwd,
                            text=True, capture_output=True, check=True)
    proof = {'compile_entry': entry, 'replayed_argv': cc, 'compiler_version': compiler.stdout,
             'compiler_sha256': sha(compiler_path), 'compiler_path': str(Path(compiler_path).resolve()),
             'compiler_macros': macros.stdout, 'rustc': str(Path(rustc).resolve()),
             'rustc_sha256': sha(rustc), 'rust_source_sha256': sha(here / 'iec.rs'),
             'oracle_source_sha256': sha(here / 'oracle.c'), 'attempts': []}
    proof['rustc_verbose_version'] = subprocess.check_output([rustc, '-Vv'], text=True)
    sysroot = Path(subprocess.check_output([rustc, '--print', 'sysroot'], text=True).strip())
    proof['rustc_sysroot'] = str(sysroot)
    proof['rustc_actual_sha256'] = sha(sysroot / 'bin/rustc')
    for kind in ('target', 'optimizers'):
        effective = subprocess.run([*cc, '-Q', '--help=' + kind], cwd=cwd, text=True, capture_output=True, check=True)
        proof['effective_' + kind] = effective.stdout + effective.stderr
    for profile in ('separate', 'fused'):
        archive = output.with_name(output.stem + '.' + profile + '.a')
        binary = output.with_name(output.stem + '.' + profile + '.oracle')
        command = [rustc, '--edition=2024', '--crate-name', 'streamstrike_fader',
                   '--crate-type=staticlib', '-C', 'panic=abort', '-C', 'opt-level=2',
                   '-C', 'relocation-model=pic', str(here / 'iec.rs'), '-o', str(archive)]
        if profile == 'fused':
            command += ['--cfg', 'streamstrike_fma']
        subprocess.run(command, check=True)
        # Keep compiler/ABI flags; no change to original arithmetic flags.
        subprocess.run([*cc, str(obj), str(archive), '-lm', '-o', str(binary)], cwd=cwd, check=True)
        result = subprocess.run([str(binary), profile], text=True, capture_output=True)
        proof['attempts'].append({'profile': profile, 'command': command,
                                  'returncode': result.returncode, 'stdout': result.stdout,
                                  'stderr': result.stderr})
        if result.returncode == 0:
            staged = output.with_suffix('.pending.a')
            staged.write_bytes(archive.read_bytes())
            proof.update(selected_profile=profile, archive_sha256=sha(staged))
            staged_profile = output.with_suffix('.pending.json')
            staged_profile.write_text(json.dumps(proof, indent=2) + '\n')
            staged_profile.replace(profile_path)
            staged.replace(output)
            print('IEC exact compiler profile:', profile)
            print(result.stdout, end='')
            return
        # A numerical mismatch may try the other supported arithmetic profile;
        # a crash, unsupported CPU, or malformed oracle is never a fallback.
        if result.returncode != 1:
            break
    output.with_suffix('.profile.json').write_text(json.dumps(proof, indent=2) + '\n')
    raise RuntimeError('no Rust profile matches original C; see profile evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('database', 'source', 'rustc', 'compiler', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    build(args.database, args.source, args.rustc, args.compiler, args.output)
