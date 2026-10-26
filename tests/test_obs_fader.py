"""Original-source IEC conversion oracle, linked to the actual Rust C ABI."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'evidence/upstream/libobs/obs-audio-controls.c'
SOURCE_SHA = 'eb3eed166c8bd2b242fc774ce4b0a25b6b0704c96aa66901366f64cf3855e4ac'


def original_functions():
    source = SOURCE.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA:
        raise ValueError('pinned OBS audio source differs')
    text = source.decode()
    start = text.index('static float iec_def_to_db(')
    end = text.index('#define LOG_OFFSET_DB', start)
    return text[start:end]


class IecFaderParity(unittest.TestCase):
    def test_original_source_functions_match_rust_c_abi(self):
        rustc = shutil.which('rustc')
        self.assertIsNotNone(rustc, 'Rust compiler is required; never silently skip parity')
        cc = shutil.which('cc')
        self.assertIsNotNone(cc)
        with tempfile.TemporaryDirectory(prefix='streamstrike-fader-') as tmp:
            tmp = Path(tmp)
            archive = tmp / 'libfader.a'
            subprocess.run([rustc, '--edition=2024', '--crate-type=staticlib',
                            '-C', 'panic=abort', '-C', 'opt-level=2', '-C', 'relocation-model=pic',
                            str(ROOT / 'foundation/rust-fader/iec.rs'), '-o', str(archive)], check=True)
            program = tmp / 'oracle.c'
            program.write_text('#include <math.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <string.h>\n'
                               + original_functions()
                               + (ROOT / 'tests/rust_fader/iec_oracle.c').read_text())
            binary = tmp / 'oracle'
            subprocess.run([cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-O2', '-ffp-contract=off',
                            str(program), str(archive), '-lm', '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('IEC parity: 200000 random bit patterns plus boundary neighbors passed', result.stdout)


class FaderOverlay(unittest.TestCase):
    def test_strict_link_declares_existing_glib_dependencies(self):
        cmake = (ROOT / 'foundation/rust-fader/StreamStrikeFader.cmake').read_text()
        self.assertIn('if(TARGET gio::gio)', cmake)
        self.assertIn('find_library(STREAMSTRIKE_GOBJECT_LIBRARY NAMES gobject-2.0 HINTS ${PC_Gio_LIBRARY_DIRS} REQUIRED)', cmake)
        self.assertIn('find_library(STREAMSTRIKE_GLIB_LIBRARY NAMES glib-2.0 HINTS ${PC_Gio_LIBRARY_DIRS} REQUIRED)', cmake)
        self.assertIn('target_link_libraries(libobs PRIVATE "${STREAMSTRIKE_GOBJECT_LIBRARY}" "${STREAMSTRIKE_GLIB_LIBRARY}")', cmake)
        self.assertIn('"LINKER:--no-undefined"', cmake)

    def test_runtime_overlay_replaces_functions_and_links_rust(self):
        import json, sys
        sys.path.insert(0, str(ROOT / 'tools'))
        import obs_branding
        overlay = json.loads((ROOT / 'foundation/branding/overlay.json').read_text())
        names = {'libobs/obs-audio-controls.c', 'libobs/CMakeLists.txt'}
        selected = {'replacements': [v for v in overlay['replacements'] if v['path'] in names],
                    'additions': [v for v in overlay['additions'] if v['path'].startswith('libobs/streamstrike-fader/')]}
        self.assertEqual({v['path'] for v in selected['replacements']}, names)
        files = {name: {'mode': '100644', 'content': (ROOT / 'evidence/upstream' / name).read_bytes()}
                 for name in names}
        result = obs_branding._overlay(files, selected, ROOT)
        c = result['libobs/obs-audio-controls.c']['content'].decode()
        self.assertNotIn('static float iec_def_to_db(', c)
        self.assertNotIn('static float iec_db_to_def(', c)
        self.assertIn('#define iec_def_to_db streamstrike_iec_def_to_db', c)
        self.assertIn('#define iec_db_to_def streamstrike_iec_db_to_def', c)
        self.assertIn('fader->def_to_db = iec_def_to_db;', c)
        self.assertIn('fader->db_to_def = iec_db_to_def;', c)
        self.assertIn('include(streamstrike-fader/StreamStrikeFader.cmake)', result['libobs/CMakeLists.txt']['content'].decode())
        self.assertEqual(result['libobs/streamstrike-fader/iec.rs']['content'], (ROOT / 'foundation/rust-fader/iec.rs').read_bytes())

class FaderNativeEvidence(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from verify_obs_fader import validate_pair, cases, bits
        self.validate = validate_pair
        self.original = {'library': '/original/libobs.so', 'sha256': 'a'*64,
                         'rows': [[bits(value), 0, 0, 0] for _, value in cases()], 'rust_callback': False}
        self.migrated = {**self.original, 'library': '/migrated/libobs.so', 'sha256': 'b'*64,
                         'rust_callback': True}

    def test_distinct_complete_matching_traces_are_accepted(self):
        self.assertTrue(self.validate(self.original, self.migrated))

    def test_cannot_compare_library_with_itself(self):
        with self.assertRaises(ValueError): self.validate(self.original, self.original)

    def test_modified_row_is_rejected(self):
        altered = {**self.migrated, 'rows': [[1, 0, 0, 0]] + self.migrated['rows'][1:]}
        with self.assertRaises(ValueError): self.validate(self.original, altered)

    def test_missing_rows_are_rejected(self):
        with self.assertRaises(ValueError): self.validate(self.original, {**self.migrated, 'rows': []})

    def test_callback_must_point_into_rust_implementation(self):
        with self.assertRaises(ValueError): self.validate(self.original, {**self.migrated, 'rust_callback': False})

    def test_identical_binary_is_not_migration(self):
        with self.assertRaises(ValueError): self.validate(self.original, {**self.migrated, 'sha256': self.original['sha256']})

    def test_identically_forged_input_sequences_are_rejected(self):
        rows = [[0, 0, 0, 0]] * 1000
        with self.assertRaises(ValueError):
            self.validate({**self.original, 'rows': rows}, {**self.migrated, 'rows': rows})

    def test_native_cases_cover_fma_sensitive_boundary_neighbor(self):
        from verify_obs_fader import cases, bits
        self.assertIn(0x3f000001, [bits(value) for operation, value in cases() if operation == 0])

if __name__ == '__main__':
    unittest.main()
