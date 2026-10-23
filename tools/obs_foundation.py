"""Fetch/verify the actual pinned OBS source; never substitute the legacy editor."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "foundation/obs-source.lock.json"


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def verify(source, lock):
    if git(source, "rev-parse", "HEAD") != lock["commit"]:
        raise ValueError("OBS HEAD differs from reviewed pin")
    if git(source, "remote", "get-url", "origin").removesuffix(".git") != lock["repository"].removesuffix(".git"):
        raise ValueError("OBS origin is not the official repository")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("OBS tracked source was modified")
    for name, expected in lock["sha256"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("OBS source identity mismatch: " + name)
    if "project(obs-studio " not in (source / "CMakeLists.txt").read_text():
        raise ValueError("Not the original OBS CMake project")
    if not (source / "frontend/CMakeLists.txt").is_file():
        raise ValueError("Original OBS frontend is missing")
    print("Verified official OBS source pin, notices, build script and original frontend")


def fetch(source, lock):
    # Refuse to overwrite any existing checkout, even an empty-looking one.
    source.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "init", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin", lock["repository"]], check=True)
    subprocess.run(["git", "-C", str(source), "fetch", "--depth=1", "origin", lock["commit"]], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], check=True)
    subprocess.run(["git", "-C", str(source), "submodule", "update", "--init", "--recursive", "--depth=1"], check=True)
    verify(source, lock)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "verify"])
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text())
    source = ROOT / lock["source_directory"]
    (fetch if args.action == "fetch" else verify)(source, lock)
