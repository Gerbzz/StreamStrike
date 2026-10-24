import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

class BrandingCopy(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / 'tools/obs_branding.py').is_file(), 'guarded OBS branding copy not implemented')
        spec = importlib.util.spec_from_file_location('obs_branding', ROOT / 'tools/obs_branding.py')
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.source = self.root/'donor'; self.source.mkdir()
        self.git('init', '-q'); self.git('config', 'user.name', 'Fixture'); self.git('config', 'user.email', 'fixture@example.invalid')
        (self.source/'frontend').mkdir(); (self.source/'frontend/main.cpp').write_text('Original identity\n')
        (self.source/'COPYING').write_text('Original license\n')
        (self.source/'run').write_text('#!/bin/sh\ntrue\n'); (self.source/'run').chmod(0o755)
        os.symlink('run', self.source/'run-link')
        self.git('add', '.'); self.git('commit', '-qm', 'donor fixture')
        self.pin = self.git('rev-parse','HEAD').strip()
        self.out = self.root/'branded'
        self.asset = self.root/'logo.png'; self.asset.write_bytes(b'fixed logo fixture')
        self.overlay = {'version': 1, 'donor_commit': self.pin, 'replacements': [{'path': 'frontend/main.cpp','input_sha256': self.m.sha256(b'Original identity\n'),'output_sha256':self.m.sha256(b'StreamStrike identity\n'),'edits':[{'before':'Original identity','after':'StreamStrike identity','count':1}]}], 'additions':[{'source':'logo.png','path':'frontend/logo.png','sha256':self.m.sha256(self.asset.read_bytes())}]}

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.source),*args],text=True,stderr=subprocess.DEVNULL)

    def prepare(self):
        return self.m.prepare_copy(self.source,self.out,self.overlay,self.root)

    def test_copy_preserves_donor_history_license_modes_and_applies_only_overlay(self):
        receipt=self.prepare()
        self.assertEqual((self.source/'frontend/main.cpp').read_text(),'Original identity\n')
        self.assertEqual(self.git('status','--porcelain'),'')
        self.assertEqual((self.out/'frontend/main.cpp').read_text(),'StreamStrike identity\n')
        self.assertEqual((self.out/'COPYING').read_text(),'Original license\n')
        self.assertTrue(os.access(self.out/'run',os.X_OK))
        self.assertEqual(os.readlink(self.out/'run-link'),'run')
        self.assertEqual(receipt['donor_commit'],self.pin)
        self.m.verify_copy(self.out,self.overlay,self.root)

    def eol_fixture(self, attributes='*.sln text eol=crlf\n'):
        self.git('config','core.autocrlf','false')
        (self.source/'.gitattributes').write_text(attributes)
        path=self.source/'project.sln'; path.write_bytes(b'first line\nsecond line\n')
        self.git('add','.');self.git('commit','-qm','EOL attributes fixture')
        self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        path.unlink();self.git('checkout','--','project.sln')
        return path

    def test_explicit_crlf_checkout_exports_exact_canonical_git_blob(self):
        path=self.eol_fixture()
        self.assertEqual(path.read_bytes(),b'first line\r\nsecond line\r\n')
        self.assertEqual(self.git('status','--porcelain'),'')
        receipt=self.prepare()
        self.assertEqual((self.out/'project.sln').read_bytes(),b'first line\nsecond line\n')
        self.assertEqual(receipt['files']['project.sln']['checkout_conversion'],'text-eol-crlf')
        self.assertEqual(receipt['files']['project.sln']['checkout_sha256'],self.m.sha256(path.read_bytes()))
        self.m.verify_copy(self.out,self.overlay,self.root)

    def test_crlf_attribute_does_not_hide_byte_tampering(self):
        path=self.eol_fixture();self.git('update-index','--assume-unchanged','project.sln')
        path.write_bytes(b'changed content\r\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()
        self.assertFalse(self.out.exists())

    def test_lf_attribute_does_not_authorize_crlf_worktree(self):
        path=self.eol_fixture('*.sln text eol=lf\n');self.git('update-index','--assume-unchanged','project.sln')
        path.write_bytes(b'first line\r\nsecond line\r\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()

    def test_unspecified_attribute_does_not_authorize_crlf_worktree(self):
        path=self.eol_fixture('');self.git('update-index','--assume-unchanged','project.sln')
        path.write_bytes(b'first line\r\nsecond line\r\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()

    def test_untracked_info_attributes_cannot_authorize_checkout_conversion(self):
        path=self.eol_fixture('');self.git('update-index','--assume-unchanged','project.sln')
        (self.source/'.git/info/attributes').write_text('*.sln text eol=crlf\n')
        path.write_bytes(b'first line\r\nsecond line\r\n')
        with self.assertRaisesRegex(ValueError,'attributes'):self.prepare()

    def test_filter_attribute_does_not_authorize_eol_conversion(self):
        self.eol_fixture('*.sln text eol=crlf filter=example\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()

    def test_missing_cr_is_not_an_authorized_checkout_conversion(self):
        path=self.eol_fixture();self.git('update-index','--assume-unchanged','project.sln')
        path.write_bytes(b'first line\r\nsecond line\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()

    def test_extra_cr_is_not_an_authorized_checkout_conversion(self):
        path=self.eol_fixture();self.git('update-index','--assume-unchanged','project.sln')
        path.write_bytes(b'first line\r\r\nsecond line\r\n')
        with self.assertRaisesRegex(ValueError,'identity'):self.prepare()

    def test_declared_lf_checkout_exports_exact_bytes(self):
        path=self.eol_fixture('*.sln text eol=lf\n');receipt=self.prepare()
        self.assertEqual((self.out/'project.sln').read_bytes(),path.read_bytes())
        self.assertNotIn('checkout_conversion',receipt['files']['project.sln'])

    def test_initialized_submodule_crlf_checkout_exports_canonical_blob(self):
        module=self.source/'module';module.mkdir()
        def git(*args):return subprocess.check_output(['git','-C',str(module),*args],text=True,stderr=subprocess.DEVNULL)
        git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
        (module/'.gitattributes').write_text('*.sln text eol=crlf\n')
        path=module/'project.sln';path.write_bytes(b'canonical\n')
        git('add','.');git('commit','-qm','nested EOL fixture');pin=git('rev-parse','HEAD').strip()
        path.unlink();git('checkout','--','project.sln')
        self.git('update-index','--add','--cacheinfo','160000,'+pin+',module');self.git('commit','-qm','pin nested fixture')
        self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        receipt=self.prepare()
        self.assertEqual((self.out/'module/project.sln').read_bytes(),b'canonical\n')
        self.assertEqual(receipt['submodules']['module'],pin)
        self.assertEqual(receipt['files']['module/project.sln']['checkout_conversion'],'text-eol-crlf')

    def test_existing_destination_is_not_overwritten(self):
        self.out.mkdir(); (self.out/'keep').write_text('keep')
        with self.assertRaises(FileExistsError): self.prepare()
        self.assertEqual((self.out/'keep').read_text(),'keep')

    def test_tracked_dirty_source_is_rejected_before_copy(self):
        (self.source/'COPYING').write_text('changed')
        with self.assertRaisesRegex(ValueError,'dirty'): self.prepare()
        self.assertFalse(self.out.exists())

    def test_wrong_input_hash_is_rejected(self):
        self.overlay['replacements'][0]['input_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'input'): self.prepare()

    def test_wrong_output_hash_is_rejected(self):
        self.overlay['replacements'][0]['output_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'output'): self.prepare()

    def test_ambiguous_edit_count_is_rejected(self):
        self.overlay['replacements'][0]['edits'][0]['count']=2
        with self.assertRaisesRegex(ValueError,'count'): self.prepare()

    def test_modified_overlay_file_rejected(self):
        self.prepare(); (self.out/'frontend/main.cpp').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'identity'): self.m.verify_copy(self.out,self.overlay,self.root)

    def test_modified_non_overlay_source_rejected(self):
        self.prepare(); (self.out/'COPYING').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'identity'): self.m.verify_copy(self.out,self.overlay,self.root)

    def test_unlisted_source_file_rejected(self):
        self.prepare(); (self.out/'frontend/extra.cpp').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'unlisted'): self.m.verify_copy(self.out,self.overlay,self.root)

    def test_untracked_build_output_allowed_but_not_source(self):
        self.prepare(); (self.out/'build_ubuntu').mkdir();(self.out/'build_ubuntu/test').write_text('build output')
        self.m.verify_copy(self.out,self.overlay,self.root)

    def test_build_directory_symlink_rejected_before_any_build_mutation(self):
        self.prepare(); outside = self.root/'outside'; outside.mkdir()
        marker = outside/'streamstrike-branding-build.json'; marker.write_text('unrelated')
        (self.out/'build_ubuntu').symlink_to(outside, target_is_directory=True)
        with mock.patch.object(self.m, 'checked', return_value=(self.source,self.overlay)), \
             mock.patch.object(self.m, 'COPY', self.out), mock.patch.object(self.m, 'ROOT', self.root):
            with self.assertRaisesRegex(ValueError, 'build.*symlink'): self.m.build()
        self.assertEqual(marker.read_text(), 'unrelated')

    def test_generated_tree_symlink_must_not_escape_build_directory(self):
        self.prepare(); build = self.out/'build_ubuntu'; build.mkdir()
        (build/'outside').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'build.*symlink'): self.m.verify_copy(self.out,self.overlay,self.root)

    def test_internal_generated_library_symlink_is_allowed(self):
        self.prepare(); build = self.out/'build_ubuntu'; build.mkdir()
        (build/'libobs.so.1').write_text('generated library')
        (build/'libobs.so').symlink_to('libobs.so.1')
        self.m.verify_copy(self.out,self.overlay,self.root)

    def test_configure_sets_deterministic_build_number_without_source_cache(self):
        self.prepare(); self.git('tag','33.0.0')
        # Recreate the version-bearing receipt after assigning the fixture tag.
        import shutil
        shutil.rmtree(self.out); self.prepare()
        cef = self.root/'cef'; cef.mkdir()
        (self.source/'build_ubuntu').mkdir()
        (self.source/'build_ubuntu/CMakeCache.txt').write_text('CEF_ROOT_DIR:PATH='+str(cef)+'\n')
        calls = []; real_run = subprocess.run
        def configure_boundary(args, **kwargs):
            if args[0] != 'cmake': return real_run(args, **kwargs)
            calls.append(args)
            if '--preset' in args:
                self.assertIn('-DOBS_BUILD_NUMBER=0', args)
                raise RuntimeError('stop before invoking unavailable CMake')
        with mock.patch.object(self.m, 'checked', return_value=(self.source,self.overlay)), \
             mock.patch.object(self.m, 'COPY', self.out), mock.patch.object(self.m, 'ROOT', self.root), \
             mock.patch.object(self.m.subprocess, 'run', side_effect=configure_boundary):
            with self.assertRaisesRegex(RuntimeError, 'stop before'): self.m.build()
        self.assertEqual(len(calls),1)
        self.assertFalse((self.out/'cmake/.CMakeBuildNumber').exists())

    def test_original_guard_status_does_not_pollute_machine_readable_stdout(self):
        lock = self.root/'lock.json'; lock.write_text(json.dumps({'commit':self.pin,'source_directory':'donor'}))
        manifest = self.root/'overlay.json'; manifest.write_text(json.dumps(self.overlay))
        stdout = io.StringIO(); stderr = io.StringIO()
        def guard(*args): print('Verified official OBS source pin')
        with mock.patch.object(self.m.obs_foundation, 'LOCK', lock), \
             mock.patch.object(self.m, 'MANIFEST', manifest), mock.patch.object(self.m, 'ROOT', self.root), \
             mock.patch.object(self.m.obs_foundation, 'verify', side_effect=guard), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.m.checked()
            print(json.dumps({'evidence':'only JSON'}))
        self.assertEqual(json.loads(stdout.getvalue()), {'evidence':'only JSON'})
        self.assertIn('Verified official OBS', stderr.getvalue())

    def test_asset_tamper_rejected(self):
        self.asset.write_bytes(b'changed logo')
        with self.assertRaisesRegex(ValueError,'asset'): self.prepare()

    def test_path_traversal_rejected(self):
        self.overlay['additions'][0]['path']='../escape'
        with self.assertRaisesRegex(ValueError,'path'): self.prepare()
        self.assertFalse((self.root/'escape').exists())

    def test_source_symlink_escape_rejected(self):
        (self.source/'run-link').unlink();os.symlink('../outside',self.source/'run-link')
        self.git('add','.');self.git('commit','-qm','bad symlink fixture');self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        with self.assertRaisesRegex(ValueError,'symlink'): self.prepare()

    def test_source_chained_symlink_escape_rejected(self):
        (self.source/'link').symlink_to('.')
        (self.source/'x').mkdir(); (self.source/'x/escape').symlink_to('../link/..')
        self.git('add','.');self.git('commit','-qm','chained escape fixture')
        self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        with self.assertRaisesRegex(ValueError,'symlink'): self.prepare()
        self.assertFalse(self.out.exists())

    def test_source_symlink_cycle_rejected(self):
        (self.source/'cycle').symlink_to('cycle')
        self.git('add','.');self.git('commit','-qm','cycle fixture')
        self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        with self.assertRaisesRegex(ValueError,'symlink'): self.prepare()

    def test_destination_symlink_ancestor_rejected(self):
        real = self.root/'real'; real.mkdir()
        link = self.root/'ancestor'; link.symlink_to(real, target_is_directory=True)
        self.out = link/'branded'
        with self.assertRaisesRegex(ValueError,'symlink'): self.prepare()
        self.assertFalse((real/'branded').exists())

    def test_missing_submodule_rejected(self):
        self.git('update-index','--add','--cacheinfo','160000,'+self.pin+',submodule')
        self.git('commit','-qm','missing gitlink fixture');self.overlay['donor_commit']=self.git('rev-parse','HEAD').strip()
        with self.assertRaisesRegex(ValueError,'submodule'): self.prepare()

    def test_directory_symlink_rejected_even_if_expected_bytes_exist(self):
        self.prepare()
        outside = self.root/'outside'; (self.out/'frontend').rename(outside)
        os.symlink(outside, self.out/'frontend')
        with self.assertRaises(ValueError): self.m.verify_copy(self.out,self.overlay,self.root)

    def test_missing_build_receipt_and_changed_binary_rejected(self):
        self.assertTrue(hasattr(self.m,'validate_build'),'branded binary receipt gate missing')
        receipt = self.prepare()
        binary = self.out/'build_ubuntu/install/RelWithDebInfo/bin/obs';binary.parent.mkdir(parents=True)
        binary.write_bytes(b'fixture executable');binary.chmod(0o755)
        with self.assertRaises(OSError): self.m.validate_build(self.out,receipt)
        stamp = {'donor_commit':self.pin,'overlay_sha256':receipt['overlay_sha256'],
                 'source_inventory_sha256':self.m.sha256(self.m.canonical(receipt['files'])),
                 'executable_sha256':self.m.sha256(b'fixture executable')}
        (self.out/'build_ubuntu/streamstrike-branding-build.json').write_text(json.dumps(stamp))
        self.m.validate_build(self.out,receipt)
        binary.write_bytes(b'changed executable')
        with self.assertRaisesRegex(ValueError,'build receipt'): self.m.validate_build(self.out,receipt)

    def test_forged_receipt_does_not_authorize_modified_file(self):
        self.prepare(); (self.out/'COPYING').write_text('forged')
        p=self.out/'.streamstrike-source.json'; r=json.loads(p.read_text());r['files']['COPYING']['sha256']=self.m.sha256(b'forged');p.write_text(json.dumps(r))
        with self.assertRaisesRegex(ValueError,'receipt'): self.m.verify_copy(self.out,self.overlay,self.root)

if __name__=='__main__':unittest.main()
