"""Fresh native source-function oracle must match the portable Rust fixture."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent

class ScalarOracle(unittest.TestCase):
    def test_pinned_c_getters_and_unsets_match_checked_in_fixture(self):
        result = subprocess.run([sys.executable, str(ROOT / 'oracle/obs_scalar_oracle.py')],
                                check=True, capture_output=True)
        self.assertEqual(result.stdout, (ROOT / 'oracle/obs_scalar.tsv').read_bytes())

if __name__ == '__main__':
    unittest.main()
