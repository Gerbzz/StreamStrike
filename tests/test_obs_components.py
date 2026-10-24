"""Real Git, tar and ELF fixtures for finite CEF ownership provenance."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
MODULE = ROOT / 'tools/obs_components.py'
CONTRACTS = (
    'cmake/linux/helpers.cmake', 'cmake/linux/defaults.cmake', 'CMakePresets.json',
    'cmake/finders/FindCEF.cmake', '.github/scripts/utils.zsh/setup_ubuntu',
    'plugins/obs-browser/CMakeLists.txt', 'plugins/obs-browser/cmake/os-linux.cmake',
)
PAYLOAD = ('libcef.so', 'chrome-sandbox', 'libEGL.so', 'libGLESv2.so',
           'libvk_swiftshader.so', 'libvulkan.so.1')
CORE = 'lib/x86_64-linux-gnu/obs-modules/core'


def digest(data):
    return hashlib.sha256(data).hexdigest()


class ComponentOwnership(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.is_file(), 'finite source-bound CEF ownership factory is missing')
        spec = importlib.util.spec_from_file_location('obs_components_fixture', MODULE)
        self.components = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.components)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'donor'
        self.copy = self.root / 'copy'
        self.prefix = self.copy / 'build_ubuntu/install/RelWithDebInfo'
        self.core = self.prefix / CORE
        self.core.mkdir(parents=True)
        self.source.mkdir()
        self.originals = {p: ('original contract ' + p + '\n').encode() for p in CONTRACTS}
        self.copied = {p: ('copied contract ' + p + '\n').encode() for p in CONTRACTS}
        for base, entries in ((self.source, self.originals), (self.copy, self.copied)):
            for name, data in entries.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        browser = self.source / 'plugins/obs-browser'
        self.git(browser, 'init', '-q')
        self.git(browser, 'add', '.')
        self.git(browser, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'browser fixture')
        browser_pin = self.git(browser, 'rev-parse', 'HEAD').strip()
        self.git(self.source, 'init', '-q')
        self.git(self.source, 'add', *[p for p in CONTRACTS if not p.startswith('plugins/')])
        self.git(self.source, 'update-index', '--add', '--cacheinfo', '160000,' + browser_pin + ',plugins/obs-browser')
        self.git(self.source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'donor fixture')
        donor_pin = self.git(self.source, 'rev-parse', 'HEAD').strip()
        self.receipt = {'version': 1, 'donor_commit': donor_pin, 'donor_path': str(self.source),
                        'submodules': {'plugins/obs-browser': browser_pin},
                        'donor_inventory_sha256': '1' * 64, 'overlay_sha256': '2' * 64,
                        'files': {p: {'mode': '100644', 'sha256': digest(data)} for p, data in self.copied.items()}}
        self.save_receipt()
        self.prepared = self.source / '.deps/cef_binary_7871_linux_x86_64'
        (self.prepared / 'Release').mkdir(parents=True)
        self.archive = self.source / '.deps/cef_binary_7871_linux_x86_64.tar.xz'
        elf = self.root / 'fixture.so'
        subprocess.run(['gcc', '-shared', '-fPIC', '-x', 'c', '-', '-o', str(elf)],
                       input=b'int fixture(void) { return 17; }\n', check=True, capture_output=True)
        self.elf = elf.read_bytes()
        for name in PAYLOAD:
            (self.prepared / 'Release' / name).write_bytes(self.elf)
            (self.core / name).write_bytes(self.elf)
        for name in ('obs-browser.so', 'obs-browser-page'):
            (self.core / name).write_bytes(self.elf)
        self.archive_entries = [('cef-original-root/Release/' + name, self.elf, 'file') for name in PAYLOAD]
        self.write_archive()
        for base in (self.source, self.copy):
            (base / 'build_ubuntu').mkdir(exist_ok=True)
            (base / 'build_ubuntu/CMakeCache.txt').write_text(
                'CEF_ROOT_DIR:PATH=' + str(self.prepared) + '\n'
                'CEF_LIBRARY_RELEASE:FILEPATH=' + str(self.prepared / 'Release/libcef.so') + '\n'
                'CMAKE_INSTALL_LIBDIR:PATH=lib/CMAKE_SYSTEM_PROCESSOR-linux-gnu\n'
                'CMAKE_INSTALL_PREFIX:PATH=' + str(base / 'build_ubuntu/install/RelWithDebInfo') + '\n'
                'CMAKE_BUILD_TYPE:STRING=RelWithDebInfo\n')
        constants = {'DONOR_COMMIT': donor_pin, 'BROWSER_COMMIT': browser_pin,
                     'CONTRACT_SHA256': {p: digest(data) for p, data in self.originals.items()},
                     'COPY_CONTRACT_SHA256': {p: digest(data) for p, data in self.copied.items()},
                     'ARCHIVE_SHA256': digest(self.archive.read_bytes())}
        self.constants = patch.multiple(self.components, **constants)
        self.constants.start()
        self.addCleanup(self.constants.stop)

    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.PIPE, text=True)

    def save_receipt(self):
        (self.copy / '.streamstrike-source.json').write_text(json.dumps(self.receipt))

    def write_archive(self):
        with tarfile.open(self.archive, 'w:xz') as tar:
            for name, data, kind in self.archive_entries:
                entry = tarfile.TarInfo(name)
                entry.mode = 0o755
                if kind == 'file':
                    entry.size = len(data)
                    tar.addfile(entry, io.BytesIO(data))
                else:
                    entry.type = tarfile.SYMTYPE
                    entry.linkname = 'libcef.so'
                    tar.addfile(entry)

    def context(self):
        return self.components.ownership_context(self.source, self.copy, self.prefix, self.receipt)

    def test_verified_archive_prepared_and_installed_bytes_define_only_finite_members(self):
        (self.core / 'frontend-tools.so').write_bytes(self.elf)
        (self.core / 'libunknown.so').write_bytes(self.elf)
        result = self.context()
        json.dumps(result)
        self.assertEqual(result['version'], 1)
        self.assertEqual(result['component'], 'cef')
        expected = {CORE + '/' + name: {'role': 'payload', 'sha256': digest(self.elf)} for name in PAYLOAD}
        expected.update({CORE + '/' + name: {'role': 'consumer', 'sha256': digest(self.elf)}
                         for name in ('obs-browser.so', 'obs-browser-page')})
        self.assertEqual(result['members'], expected)
        self.assertEqual(result['provenance']['archive']['sha256'], digest(self.archive.read_bytes()))
        self.assertEqual(result['provenance']['archive']['top_component'], 'cef-original-root')

    def test_donor_and_copied_source_contract_tampering_rejected(self):
        for base in (self.source, self.copy):
            with self.subTest(base=base):
                path = base / 'cmake/linux/helpers.cmake'
                original = path.read_bytes()
                path.write_bytes(original + b'altered')
                with self.assertRaisesRegex(ValueError, 'contract'):
                    self.context()
                path.write_bytes(original)

    def test_receipt_pin_gitlink_and_file_identity_tampering_rejected(self):
        changes = [('donor_commit', '0' * 40), ('submodules', {'plugins/obs-browser': '0' * 40}),
                   ('files', {}), ('donor_path', str(self.root))]
        original = copy.deepcopy(self.receipt)
        for key, value in changes:
            with self.subTest(key=key):
                self.receipt[key] = value
                self.save_receipt()
                with self.assertRaises(ValueError):
                    self.context()
                self.receipt = copy.deepcopy(original)
        self.save_receipt()

    def test_actual_gitlink_cannot_be_replaced_by_matching_receipt_claim(self):
        self.git(self.source, 'update-index', '--cacheinfo', '160000,' + '0' * 39 + '1,plugins/obs-browser')
        self.git(self.source, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'changed gitlink')
        changed_commit = self.git(self.source, 'rev-parse', 'HEAD').strip()
        self.receipt['donor_commit'] = changed_commit
        self.save_receipt()
        with patch.object(self.components, 'DONOR_COMMIT', changed_commit):
            with self.assertRaisesRegex(ValueError, 'gitlink'):
                self.context()

    def test_retained_archive_tamper_rejected_even_when_prepared_equals_installed(self):
        with self.archive.open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'archive'):
            self.context()

    def test_archive_path_replacement_during_streaming_rejected_even_with_same_bytes(self):
        original_read = self.components._HashingReader.read
        swapped = False

        def replace_then_read(reader, size=-1):
            nonlocal swapped
            if not swapped:
                replacement = self.root / 'replacement.tar.xz'
                replacement.write_bytes(self.archive.read_bytes())
                os.replace(replacement, self.archive)
                swapped = True
            return original_read(reader, size)

        with patch.object(self.components._HashingReader, 'read', replace_then_read):
            with self.assertRaisesRegex(ValueError, 'archive.*changed|archive.*identity'):
                self.context()

    def test_prepared_and_installed_equal_tamper_is_not_archive_provenance(self):
        for base in (self.prepared / 'Release', self.core):
            (base / 'libvulkan.so.1').write_bytes(self.elf + b'changed')
        with self.assertRaisesRegex(ValueError, 'archive|payload|identity'):
            self.context()

    def test_prepared_or_installed_payload_tampering_rejected(self):
        for base in (self.prepared / 'Release', self.core):
            path = base / 'libcef.so'
            path.write_bytes(self.elf + b'changed')
            with self.assertRaisesRegex(ValueError, 'payload|identity'):
                self.context()
            path.write_bytes(self.elf)

    def test_cache_wrong_prepared_location_or_layout_rejected(self):
        for base in (self.source, self.copy):
            path = base / 'build_ubuntu/CMakeCache.txt'
            original = path.read_text()
            for old, new in [(str(self.prepared), str(self.root / 'other')),
                             ('lib/CMAKE_SYSTEM_PROCESSOR-linux-gnu', 'lib/aarch64-linux-gnu')]:
                path.write_text(original.replace(old, new))
                with self.assertRaisesRegex(ValueError, 'cache|layout|CEF'):
                    self.context()
            path.write_text(original)

    def test_cache_duplicate_or_missing_critical_key_rejected(self):
        path = self.copy / 'build_ubuntu/CMakeCache.txt'
        original = path.read_text()
        for changed in [original + 'CEF_ROOT_DIR:PATH=' + str(self.prepared) + '\n',
                        '\n'.join(x for x in original.splitlines() if not x.startswith('CEF_LIBRARY_RELEASE:'))]:
            path.write_text(changed)
            with self.assertRaisesRegex(ValueError, 'cache|CEF'):
                self.context()

    def test_missing_duplicate_linked_or_multi_root_archive_member_rejected(self):
        original = list(self.archive_entries)
        variants = [original[:-1], original + [original[0]],
                    [(original[0][0], b'', 'link')] + original[1:],
                    [('different-root/Release/libcef.so', self.elf, 'file')] + original[1:],
                    [('cef-original-root/../Release/libcef.so', self.elf, 'file')] + original[1:],
                    [('cef-original-root/Release/libcef.so/', self.elf, 'file')] + original[1:]]
        for entries in variants:
            with self.subTest(entries=entries[0][0]):
                self.archive_entries = entries
                self.write_archive()
                with patch.object(self.components, 'ARCHIVE_SHA256', digest(self.archive.read_bytes())):
                    with self.assertRaisesRegex(ValueError, 'archive|member'):
                        self.context()

    def test_invalid_compressed_archive_surfaces_as_value_error(self):
        self.archive.write_bytes(b'not an xz archive')
        with patch.object(self.components, 'ARCHIVE_SHA256', digest(self.archive.read_bytes())):
            with self.assertRaisesRegex(ValueError, 'archive'):
                self.context()

    def test_symlink_or_symlink_ancestor_cannot_supply_owned_files(self):
        paths = [self.archive, self.prepared / 'Release/libcef.so', self.core / 'libcef.so',
                 self.copy / 'cmake/linux/helpers.cmake']
        for path in paths:
            with self.subTest(path=path):
                data = path.read_bytes()
                outside = self.root / 'outside-file'
                outside.write_bytes(data)
                path.unlink()
                path.symlink_to(outside)
                with self.assertRaisesRegex(ValueError, 'symlink|canonical|path'):
                    self.context()
                path.unlink()
                path.write_bytes(data)
        directory = self.prepared / 'Release'
        moved = self.root / 'outside-release'
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink|canonical|path'):
            self.context()

    def test_non_elf_and_wrong_architecture_cannot_be_classified(self):
        path = self.core / 'obs-browser-page'
        for data in (b'#!/bin/sh\nexit 0\n', self.elf[:18] + b'\xb7\x00' + self.elf[20:]):
            path.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'ELF|architecture'):
                self.context()

    def test_wrong_prefix_and_missing_consumer_rejected(self):
        with self.assertRaisesRegex(ValueError, 'prefix|layout'):
            self.components.ownership_context(self.source, self.copy, self.core, self.receipt)
        (self.core / 'obs-browser-page').unlink()
        with self.assertRaises(ValueError):
            self.context()


if __name__ == '__main__':
    unittest.main()
