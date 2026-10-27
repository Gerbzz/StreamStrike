"""Pinned original OBS cubic/logarithmic bodies against actual Rust C ABI."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_obs_fader import ROOT, SOURCE, SOURCE_SHA

MATH = ROOT / 'evidence/upstream/libobs/media-io/audio-math.h'
MATH_SHA = 'd27ca0475c3fe9b8144eccbbc850b8f7f1015fdac344b170641d3997834baa53'


def remaining_functions():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != SOURCE_SHA:
        raise ValueError('pinned OBS controls source differs')
    if hashlib.sha256(MATH.read_bytes()).hexdigest() != MATH_SHA:
        raise ValueError('pinned OBS audio math source differs')
    math = MATH.read_text()
    text = SOURCE.read_text()
    return (math[math.index('static inline float mul_to_db('):math.index('#ifdef _MSC_VER', math.index('static inline'))]
            + text[text.index('static float cubic_def_to_db('):text.index('static float iec_def_to_db(')]
            + text[text.index('#define LOG_OFFSET_DB'):text.index('static void signal_volume_changed(')])


class RemainingFaderParity(unittest.TestCase):
    def test_original_separate_cubic_and_log_functions_match_rust(self):
        self.run_oracle(False)

    def test_original_fused_cubic_and_log_functions_match_rust(self):
        self.run_oracle(True)

    def run_oracle(self, fused):
        rustc, cc = shutil.which('rustc'), shutil.which('cc')
        self.assertIsNotNone(rustc, 'Rust compiler is required; never skip parity')
        self.assertIsNotNone(cc)
        with tempfile.TemporaryDirectory(prefix='streamstrike-remaining-faders-') as tmp:
            tmp = Path(tmp)
            archive = tmp / 'fader.a'
            subprocess.run([rustc, '--edition=2024', '--crate-type=staticlib',
                            '-C', 'panic=abort', '-C', 'opt-level=2', '-C', 'relocation-model=pic',
                            str(ROOT / 'foundation/rust-fader/iec.rs'), '-o', str(archive)]
                           + (['--cfg', 'streamstrike_fma'] if fused else []), check=True)
            program = tmp / 'oracle.c'
            program.write_text('#include <math.h>\n#include <stdint.h>\n#include <stdio.h>\n#include <string.h>\n'
                               + remaining_functions() + (ROOT / 'tests/rust_fader/remaining_oracle.c').read_text())
            binary = tmp / 'oracle'
            subprocess.run([cc, '-std=gnu17', '-Wall', '-Wextra', '-Werror', '-O2']
                           + (['-mfma', '-ffp-contract=fast'] if fused else ['-ffp-contract=off'])
                           + [str(program), str(archive), '-lm', '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Remaining fader parity: 200000 random bit patterns plus boundary neighbors passed', result.stdout)

class RemainingFaderIntegration(unittest.TestCase):
    def test_exact_build_oracle_contains_all_original_helpers(self):
        self.assertIn(remaining_functions(), (ROOT / 'foundation/rust-fader/oracle.c').read_text())

    def test_original_dispatch_selects_rust_for_all_three_types(self):
        import json, sys
        sys.path.insert(0, str(ROOT / 'tools'))
        import obs_branding
        overlay = json.loads((ROOT / 'foundation/branding/overlay.json').read_text())
        names = {'libobs/obs-audio-controls.c', 'libobs/CMakeLists.txt'}
        selected = {'replacements': [v for v in overlay['replacements'] if v['path'] in names],
                    'additions': [v for v in overlay['additions'] if v['path'].startswith('libobs/streamstrike-fader/')]}
        files = {name: {'mode': '100644', 'content': (ROOT / 'evidence/upstream' / name).read_bytes()}
                 for name in names}
        c = obs_branding._overlay(files, selected, ROOT)['libobs/obs-audio-controls.c']['content'].decode()
        for kind in ('cubic', 'iec', 'log'):
            for direction in ('def_to_db', 'db_to_def'):
                name = kind + '_' + direction
                self.assertNotIn('static float ' + name + '(', c)
                self.assertIn('#define ' + name + ' streamstrike_' + name, c)
                self.assertIn('fader->' + direction + ' = ' + name + ';', c)

    def test_original_iec_case_sequence_is_retained_byte_for_byte(self):
        import sys, struct
        sys.path.insert(0, str(ROOT / 'tools'))
        from verify_obs_fader import cases, bits
        serialized = b''.join(struct.pack('<BI', op, bits(value)) for op, value in cases())
        self.assertEqual(hashlib.sha256(serialized).hexdigest(),
                         '727529391bc579109cbd47be4668c72acc5fa545257eb92145a13012337c3ab6')

    def test_directed_cubic_transitions_are_present_in_native_trace(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from verify_obs_fader import cases, bits
        values = {bits(value) for op, value in cases('cubic') if op == 0}
        self.assertTrue({0x26800000, 0x26800001, 0x26800002,
                         0x54cb2ff4, 0x54cb2ff5, 0x54cb2ff6} <= values)

    def test_native_gate_preserves_iec_cases_and_adds_both_remaining_types(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        import verify_obs_fader as native
        self.assertEqual(native.FADER_TYPES, {'cubic': 0, 'iec': 1, 'log': 2})
        self.assertEqual(len(native.cases()), 1000)
        self.assertEqual(len(native.cases('cubic')), 1000)
        self.assertEqual(len(native.cases('log')), 1000)
        self.assertIn(native.bits(-96.0), [native.bits(v) for _, v in native.cases('log')])
        self.assertIn(0x3f000001, [native.bits(v) for _, v in native.cases('iec')])

class RemainingNativeRejections(unittest.TestCase):
    def setUp(self):
        import sys, copy
        sys.path.insert(0, str(ROOT / 'tools'))
        import verify_obs_fader as native
        self.native = native
        traces = {kind: {'rows': [[native.bits(value), 0, 0, 0] for _, value in native.cases(kind)],
                         'rust_callback': False} for kind in native.FADER_TYPES}
        self.original = {'library': '/original/libobs.so', 'sha256': 'a'*64, **traces.pop('iec'), 'additional': traces}
        self.migrated = copy.deepcopy(self.original)
        self.migrated.update(library='/migrated/libobs.so', sha256='b'*64, rust_callback=True)
        for trace in self.migrated['additional'].values(): trace['rust_callback'] = True

    def test_missing_logarithmic_trace_is_rejected(self):
        del self.migrated['additional']['log']
        with self.assertRaises(ValueError): self.native.validate_pair(self.original, self.migrated)

    def test_wrong_constructor_callback_for_each_remaining_type_is_rejected(self):
        import copy
        for kind in ('cubic', 'log'):
            candidate = copy.deepcopy(self.migrated)
            candidate['additional'][kind]['rust_callback'] = False
            with self.assertRaises(ValueError): self.native.validate_pair(self.original, candidate)

    def test_duplicate_wrong_type_input_sequence_is_rejected(self):
        for proof in (self.original, self.migrated):
            proof['additional']['log']['rows'] = proof['rows']
        with self.assertRaises(ValueError): self.native.validate_pair(self.original, self.migrated)

    def test_single_remaining_type_value_difference_is_rejected(self):
        self.migrated['additional']['cubic']['rows'][0][2] = 1
        with self.assertRaises(ValueError): self.native.validate_pair(self.original, self.migrated)


if __name__ == '__main__':
    unittest.main()
