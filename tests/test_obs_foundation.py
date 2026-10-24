import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("foundation", ROOT / "tools/obs_foundation.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class SourceIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name)
        self.lock = json.loads((ROOT / "foundation/obs-source.lock.json").read_text())
        # Fixtures are actual API-returned pinned official source, not invented OBS.
        for path in self.lock["sha256"]:
            dest = self.source / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes((ROOT / "evidence/upstream" / path).read_bytes())
        (self.source / "frontend").mkdir()
        (self.source / "frontend/CMakeLists.txt").write_text("# presence fixture\n")

    def check(self, head=None, origin=None, status="", version="32.1.0-10-g72e866557"):
        def fake_git(source, *args):
            if args[0] == "rev-parse": return head or self.lock["commit"]
            if args[0] == "describe": return version
            if args[0] == "remote": return origin or self.lock["repository"]
            return status
        with patch.object(m, "git", side_effect=fake_git):
            m.verify(self.source, self.lock)

    def test_pinned_source_hashes(self): self.check()
    def test_github_checkout_origin_without_git_suffix(self):
        self.check(origin="https://github.com/obsproject/obs-studio")
    def test_reject_missing_version_tags(self):
        with self.assertRaises(ValueError): self.check(version="72e866557")
    def test_reject_wrong_commit(self):
        with self.assertRaises(ValueError): self.check(head="0"*40)
    def test_reject_unofficial_origin(self):
        with self.assertRaises(ValueError): self.check(origin="https://example.com/obs.git")
    def test_reject_modified_source(self):
        with self.assertRaises(ValueError): self.check(status=" M CMakeLists.txt")
    def test_reject_custom_editor_substitution(self):
        (self.source / "CMakeLists.txt").write_text("cargo run --bin streamstrike-editor\n")
        with self.assertRaises(ValueError): self.check()
    def test_reject_missing_frontend(self):
        (self.source / "frontend/CMakeLists.txt").unlink()
        with self.assertRaises(ValueError): self.check()
    def test_fetch_does_not_overwrite_existing_directory(self):
        with self.assertRaises(FileExistsError): m.fetch(self.source, self.lock)

if __name__ == "__main__": unittest.main()
