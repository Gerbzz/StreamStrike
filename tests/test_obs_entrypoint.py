import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('foundation', ROOT / 'tools/obs_foundation.py')
foundation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(foundation)

class OriginalEntry(unittest.TestCase):
    def test_missing_binary_fails_without_fallback(self):
        self.assertTrue(hasattr(foundation, 'launch'), 'original OBS launcher missing')
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'Build original OBS'):
                foundation.launch(Path(temp), {})
            run.assert_not_called()

    def test_only_fixed_original_binary_is_launched(self):
        self.assertTrue(hasattr(foundation, 'launch'), 'original OBS launcher missing')
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.subprocess, 'run') as run:
            source = Path(temp)
            binary = source / 'build_ubuntu/install/RelWithDebInfo/bin/obs'
            binary.parent.mkdir(parents=True)
            binary.write_text('test fixture, not OBS')
            binary.chmod(0o755)
            foundation.record_build(source, {"commit": "test-pin"})
            foundation.launch(source, {"commit": "test-pin"})
            self.assertEqual(run.call_args.args[0], [str(binary)])
            self.assertEqual(run.call_args.kwargs['cwd'], binary.parent)

    def test_source_failure_prevents_launch(self):
        self.assertTrue(hasattr(foundation, 'launch'), 'original OBS launcher missing')
        with patch.object(foundation, 'verify', side_effect=ValueError('bad source')), patch.object(foundation.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'bad source'):
                foundation.launch(ROOT, {})
            run.assert_not_called()

    def test_changed_binary_is_not_launched(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.subprocess, 'run') as run:
            source = Path(temp)
            binary = foundation.executable(source)
            binary.parent.mkdir(parents=True)
            binary.write_text('test fixture')
            binary.chmod(0o755)
            foundation.record_build(source, {"commit": "pin"})
            binary.write_text('changed fixture')
            with self.assertRaisesRegex(ValueError, 'receipt differs'):
                foundation.launch(source, {"commit": "pin"})
            run.assert_not_called()

    def test_unreceipted_binary_is_not_launched(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.subprocess, 'run') as run:
            source = Path(temp)
            binary = foundation.executable(source)
            binary.parent.mkdir(parents=True)
            binary.write_text('unverified fixture')
            binary.chmod(0o755)
            with self.assertRaisesRegex(ValueError, 'receipt missing'):
                foundation.launch(source, {"commit": "pin"})
            run.assert_not_called()

    def test_build_uses_original_preset_and_stops_on_failed_configure(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.platform, 'system', return_value='Linux'), patch.object(foundation.subprocess, 'run', side_effect=foundation.subprocess.CalledProcessError(1, 'cmake')) as run, patch.object(foundation, 'record_build') as record:
            with self.assertRaises(foundation.subprocess.CalledProcessError):
                foundation.build(Path(temp), {"commit": "pin"})
            self.assertEqual(run.call_args.args[0], ['cmake', '--preset', 'ubuntu', '-DCMAKE_BUILD_TYPE=RelWithDebInfo', '-DENABLE_BROWSER=ON', '-DENABLE_RELOCATABLE=ON', '-DCMAKE_INSTALL_PREFIX:PATH=' + str(Path(temp) / 'build_ubuntu/install/RelWithDebInfo')])
            self.assertEqual(run.call_count, 1)
            record.assert_not_called()

    def test_failed_rebuild_invalidates_old_receipt(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.platform, 'system', return_value='Linux'), patch.object(foundation.subprocess, 'run', side_effect=foundation.subprocess.CalledProcessError(1, 'cmake')):
            source = Path(temp)
            receipt = source / 'build_ubuntu/streamstrike-build.json'
            receipt.parent.mkdir()
            receipt.write_text('{"commit":"old"}')
            with self.assertRaises(foundation.subprocess.CalledProcessError):
                foundation.build(source, {"commit": "pin"})
            self.assertFalse(receipt.exists())

    def test_build_does_not_override_environment_parallelism(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(foundation, 'verify'), patch.object(foundation.platform, 'system', return_value='Linux'), patch.object(foundation.subprocess, 'run') as run, patch.object(foundation, 'record_build'), patch.dict(foundation.os.environ, {'CMAKE_BUILD_PARALLEL_LEVEL': '7'}):
            foundation.build(Path(temp), {"commit": "pin"})
            self.assertEqual(run.call_args_list[1].args[0], ['cmake', '--build', 'build_ubuntu'])
            self.assertNotIn('env', run.call_args_list[1].kwargs)
            self.assertEqual(foundation.os.environ['CMAKE_BUILD_PARALLEL_LEVEL'], '7')

    def test_old_custom_gui_is_not_active(self):
        self.assertFalse((ROOT / 'src/bin/editor.rs').exists())
        self.assertNotIn('streamstrike-editor', (ROOT / 'Cargo.toml').read_text())
        self.assertFalse((ROOT / '.github/workflows/editor-preview.yml').exists())

if __name__ == '__main__':
    unittest.main()
