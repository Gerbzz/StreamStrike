"""Real installed ELF fixtures: loader closure is not a main-executable-only check."""
import hashlib
from contextlib import redirect_stderr
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'tools/obs_runtime.py'


class InstalledRuntime(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'installed runtime inventory/ELF auditor is missing')
        spec = importlib.util.spec_from_file_location('obs_runtime', MODULE)
        self.runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.runtime)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.prefix = self.root / 'install'
        (self.prefix / 'bin').mkdir(parents=True)
        (self.prefix / 'lib/obs-modules/core').mkdir(parents=True)
        self.compile(['-shared', '-fPIC', '-Wl,-soname,libss_runtime_fixture.so.1'],
                     'int fixture_value(void) { return 17; }', self.prefix / 'lib/libss_runtime_fixture.so.1.0')
        (self.prefix / 'lib/libss_runtime_fixture.so.1').symlink_to('libss_runtime_fixture.so.1.0')
        (self.prefix / 'lib/libss_runtime_fixture.so').symlink_to('libss_runtime_fixture.so.1')
        self.compile(['-L' + str(self.prefix / 'lib'), '-lss_runtime_fixture', '-Wl,-rpath,$ORIGIN/../lib'],
                     'extern int fixture_value(void); int main(void) { return fixture_value() != 17; }',
                     self.prefix / 'bin/obs')

    def compile(self, flags, source, output):
        # Put -l options after the translation unit; linker's --as-needed is real.
        subprocess.run(['gcc', '-x', 'c', '-', '-x', 'none', '-o', str(output), *flags], input=source.encode(),
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def plugin(self, runpath):
        self.compile(['-shared', '-fPIC', '-L' + str(self.prefix / 'lib'), '-lss_runtime_fixture',
                      '-Wl,-rpath,' + runpath],
                     'extern int fixture_value(void); int plugin_value(void) { return fixture_value(); }',
                     self.prefix / 'lib/obs-modules/core/plugin.so')

    def test_old_two_level_plugin_rpath_fails_even_when_executable_resolves(self):
        subprocess.run([str(self.prefix / 'bin/obs')], check=True)
        self.plugin('$ORIGIN:$ORIGIN/..')
        with self.assertRaisesRegex(ValueError, 'unresolved|not found'):
            self.runtime.audit_runtime(self.prefix)

    def test_correct_plugin_origin_depth_resolves_shipped_exact_library(self):
        self.plugin('$ORIGIN:$ORIGIN/..:$ORIGIN/../..')
        (self.prefix / 'lib/plugin-alias.so').symlink_to('obs-modules/core/plugin.so')
        report = self.runtime.audit_runtime(self.prefix)
        json.dumps(report)
        self.assertIn('lib/obs-modules/core/plugin.so', report['elf'])
        self.assertNotIn('lib/plugin-alias.so', report['elf'])
        plugin = report['elf']['lib/obs-modules/core/plugin.so']
        self.assertEqual(plugin['needed'], ['libss_runtime_fixture.so.1'])
        self.assertIn('$ORIGIN/../..', plugin['runpath'])
        dependency = next(x for x in plugin['dependencies'] if x['name'] == 'libss_runtime_fixture.so.1')
        self.assertEqual(dependency['resolved'], str(self.prefix / 'lib/libss_runtime_fixture.so.1.0'))
        self.assertEqual(dependency['scope'], 'shipped')

    def test_plugin_missing_dependency_is_not_hidden_by_successful_main(self):
        extra = self.root / 'libmissing-runtime-fixture.so'
        self.compile(['-shared', '-fPIC', '-Wl,-soname,libmissing-runtime-fixture.so'],
                     'int missing_value(void) { return 9; }', extra)
        self.compile(['-shared', '-fPIC', str(extra), '-Wl,-rpath,' + str(self.root)],
                     'extern int missing_value(void); int plugin_value(void) { return missing_value(); }',
                     self.prefix / 'lib/obs-modules/core/plugin.so')
        extra.unlink()
        subprocess.run([str(self.prefix / 'bin/obs')], check=True)
        with self.assertRaisesRegex(ValueError, 'unresolved|not found'):
            self.runtime.audit_runtime(self.prefix)

    def test_absolute_interpreter_edge_satisfies_its_verified_soname_dependency(self):
        # The loader prints its own absolute path, not the DT_NEEDED SONAME.
        headers = subprocess.check_output(
            ['readelf', '--program-headers', '--wide', str(self.prefix / 'bin/obs')], text=True)
        interpreter = re.search(r'Requesting program interpreter: ([^\]]+)\]', headers).group(1)
        dynamic = subprocess.check_output(['readelf', '--dynamic', '--wide', interpreter], text=True)
        soname = re.search(r'\(SONAME\).*\[([^\]]+)\]', dynamic).group(1)
        plugin = self.prefix / 'lib/obs-modules/core/interpreter-needed.so'
        self.compile(['-shared', '-fPIC', '-Wl,--no-as-needed', interpreter],
                     'int plugin_value(void) { return 17; }', plugin)
        loader_output = subprocess.check_output(['ldd', str(plugin)], text=True)
        self.assertRegex(loader_output, r'(?m)^\s*' + re.escape(interpreter) + r'\s+\(0x')
        report = self.runtime.audit_runtime(self.prefix)
        record = report['elf']['lib/obs-modules/core/interpreter-needed.so']
        self.assertIn(soname, record['needed'])
        dependency = next(edge for edge in record['dependencies'] if edge['name'] == interpreter)
        self.assertEqual(dependency['soname'], soname)
        self.assertEqual(dependency['resolved'], str(Path(interpreter).resolve()))
        self.assertEqual(dependency['scope'], 'system')

    def test_shipped_soname_cannot_resolve_to_external_copy(self):
        outside = self.root / 'outside'
        outside.mkdir()
        shutil.copyfile(self.prefix / 'lib/libss_runtime_fixture.so.1.0', outside / 'libss_runtime_fixture.so.1')
        self.plugin(str(outside))
        with self.assertRaisesRegex(ValueError, 'shipped.*outside|shipped.*target|shipped.*resolve'):
            self.runtime.audit_runtime(self.prefix)

    def test_loader_environment_cannot_mask_missing_module_rpath(self):
        self.plugin('$ORIGIN')
        with patch.dict(os.environ, {'LD_LIBRARY_PATH': str(self.prefix / 'lib'),
                                     'LD_PRELOAD': '/no/such/preload.so', 'LD_AUDIT': '/no/such/audit.so'}):
            before = dict(os.environ)
            with self.assertRaisesRegex(ValueError, 'unresolved|not found'):
                self.runtime.audit_runtime(self.prefix)
            self.assertEqual(dict(os.environ), before)

    def test_ownership_failure_reports_all_roots_and_declared_requesters(self):
        outside = self.root / 'outside'
        outside.mkdir()
        target = outside / 'libss_runtime_fixture.so.1'
        shutil.copyfile(self.prefix / 'lib/libss_runtime_fixture.so.1.0', target)
        self.plugin(str(outside))
        shutil.copyfile(self.prefix / 'lib/obs-modules/core/plugin.so',
                        self.prefix / 'lib/obs-modules/core/second.so')
        with self.assertRaises(ValueError) as caught:
            self.runtime.audit_runtime(self.prefix)
        prefix = 'shipped SONAME resolved outside its exact target: '
        self.assertTrue(str(caught.exception).startswith(prefix))
        failures = json.loads(str(caught.exception)[len(prefix):])
        self.assertEqual(len(failures), 2)
        self.assertEqual({failure['audited_elf'] for failure in failures},
                         {'lib/obs-modules/core/plugin.so', 'lib/obs-modules/core/second.so'})
        for failure in failures:
            self.assertEqual(failure['identity'], 'libss_runtime_fixture.so.1')
            self.assertEqual(failure['requested_name'], failure['identity'])
            self.assertEqual(failure['resolved_soname'], failure['identity'])
            self.assertEqual(failure['resolved'], str(target))
            self.assertEqual(failure['expected'], str(self.prefix / 'lib/libss_runtime_fixture.so.1.0'))
            self.assertEqual(failure['root_needed'], [failure['identity']])
            self.assertEqual(failure['root_runpath'], [str(outside)])
            self.assertEqual(failure['root_rpath'], [])
            self.assertTrue(failure['direct_needed'])
            self.assertEqual(failure['declared_requesters'], [{
                'path': str(self.prefix / failure['audited_elf']),
                'needed': [failure['identity']], 'runpath': [str(outside)], 'rpath': []}])

    def test_inventory_binds_file_bytes_permissions_and_link_target(self):
        data = self.prefix / 'data.txt'
        data.write_text('one')
        baseline = self.runtime.runtime_inventory(self.prefix)
        self.assertEqual(baseline['files']['data.txt']['sha256'], hashlib.sha256(b'one').hexdigest())
        data.write_text('two')
        changed = self.runtime.runtime_inventory(self.prefix)
        self.assertNotEqual(baseline, changed)
        data.chmod(0o600)
        changed_mode = self.runtime.runtime_inventory(self.prefix)
        self.assertNotEqual(changed, changed_mode)
        self.assertEqual(changed_mode['files']['data.txt']['mode'], '0600')
        link = self.prefix / 'lib/libss_runtime_fixture.so'
        link.unlink()
        link.symlink_to('libss_runtime_fixture.so.1.0')
        self.assertNotEqual(changed_mode, self.runtime.runtime_inventory(self.prefix))

    def test_ownership_diagnostics_distinguish_transitive_declared_requester(self):
        outside = self.root / 'outside'
        outside.mkdir()
        target = outside / 'libss_runtime_fixture.so.1'
        shutil.copyfile(self.prefix / 'lib/libss_runtime_fixture.so.1.0', target)
        consumer = outside / 'libconsumer.so'
        self.compile(['-shared', '-fPIC', str(target), '-Wl,-rpath,$ORIGIN',
                      '-Wl,-soname,libconsumer.so'],
                     'extern int fixture_value(void); int consumer(void) { return fixture_value(); }', consumer)
        self.compile(['-shared', '-fPIC', str(consumer), '-Wl,-rpath,' + str(outside)],
                     'extern int consumer(void); int plugin_value(void) { return consumer(); }',
                     self.prefix / 'lib/obs-modules/core/plugin.so')
        with self.assertRaises(ValueError) as caught:
            self.runtime.audit_runtime(self.prefix)
        prefix = 'shipped SONAME resolved outside its exact target: '
        self.assertTrue(str(caught.exception).startswith(prefix))
        failures = json.loads(str(caught.exception)[len(prefix):])
        self.assertEqual(len(failures), 1)
        failure = failures[0]
        self.assertFalse(failure['direct_needed'])
        self.assertEqual(failure['root_needed'], ['libconsumer.so'])
        self.assertEqual(failure['declared_requesters'], [{
            'path': str(consumer), 'needed': ['libss_runtime_fixture.so.1'],
            'runpath': ['$ORIGIN'], 'rpath': []}])

    def test_later_missing_dependency_does_not_hide_earlier_ownership_diagnostics(self):
        outside = self.root / 'outside'
        outside.mkdir()
        shutil.copyfile(self.prefix / 'lib/libss_runtime_fixture.so.1.0',
                        outside / 'libss_runtime_fixture.so.1')
        self.plugin(str(outside))
        missing = self.root / 'libmissing.so'
        self.compile(['-shared', '-fPIC', '-Wl,-soname,libmissing.so'],
                     'int missing(void) { return 0; }', missing)
        self.compile(['-shared', '-fPIC', str(missing), '-Wl,-rpath,' + str(self.root)],
                     'extern int missing(void); int plugin(void) { return missing(); }',
                     self.prefix / 'lib/obs-modules/core/zz-later.so')
        missing.unlink()
        diagnostics = io.StringIO()
        with redirect_stderr(diagnostics), self.assertRaisesRegex(ValueError, 'unresolved|not found'):
            self.runtime.audit_runtime(self.prefix)
        records = [json.loads(line.split(': ', 1)[1]) for line in diagnostics.getvalue().splitlines()]
        self.assertTrue(records)
        self.assertEqual(records[0]['audited_elf'], 'lib/obs-modules/core/plugin.so')
        self.assertEqual(records[0]['resolved'], str(outside / 'libss_runtime_fixture.so.1'))
        self.assertEqual(records[-1]['declared_requesters'][0]['path'],
                         str(self.prefix / 'lib/obs-modules/core/plugin.so'))

    def test_inventory_rejects_escaping_file_and_directory_symlinks(self):
        for name, target in [('escape-file', self.root / 'outside.txt'), ('escape-dir', self.root)]:
            if name == 'escape-file':
                target.write_text('outside')
            link = self.prefix / name
            link.symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'escape'):
                self.runtime.runtime_inventory(self.prefix)
            link.unlink()

    def test_inventory_rejects_symlink_ancestor_of_prefix(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.prefix, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ancestor|symlink'):
            self.runtime.runtime_inventory(alias)

    def test_inventory_rejects_special_files_and_broken_links(self):
        fifo = self.prefix / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'unsupported|regular'):
            self.runtime.runtime_inventory(self.prefix)
        fifo.unlink()
        (self.prefix / 'broken').symlink_to('missing')
        with self.assertRaisesRegex(ValueError, 'missing|broken|dangling'):
            self.runtime.runtime_inventory(self.prefix)

    def test_static_elf_is_explicit_and_non_elf_resources_are_inventoried(self):
        self.compile(['-static'], 'int main(void) { return 0; }', self.prefix / 'bin/obs')
        (self.prefix / 'data.txt').write_text('non-ELF resource')
        report = self.runtime.audit_runtime(self.prefix)
        self.assertEqual(report['elf']['bin/obs']['linkage'], 'static')
        self.assertEqual(report['elf']['bin/obs']['dependencies'], [])
        self.assertIn('data.txt', report['inventory']['files'])
        self.assertNotIn('data.txt', report['elf'])

    def test_main_must_be_a_real_elf_not_a_script_or_missing_path(self):
        main = self.prefix / 'bin/obs'
        main.write_text('#!/bin/sh\nexit 0\n')
        with self.assertRaisesRegex(ValueError, 'bin/obs.*ELF|ELF.*bin/obs'):
            self.runtime.audit_runtime(self.prefix)
        main.unlink()
        with self.assertRaisesRegex(ValueError, 'bin/obs'):
            self.runtime.audit_runtime(self.prefix)


if __name__ == '__main__':
    unittest.main()
