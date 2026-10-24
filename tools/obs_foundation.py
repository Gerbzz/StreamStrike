"""Build and launch the actual pinned OBS source; never substitute the legacy editor."""
import argparse
import hashlib
import json
import os
import platform
import sys
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "foundation/obs-source.lock.json"


def git(source, *args):
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()


def verify(source, lock):
    if not source.is_dir():
        raise ValueError("Original OBS source missing; run python3 tools/obs_foundation.py fetch")
    if git(source, "rev-parse", "HEAD") != lock["commit"]:
        raise ValueError("OBS HEAD differs from reviewed pin")
    if git(source, "remote", "get-url", "origin").removesuffix(".git") != lock["repository"].removesuffix(".git"):
        raise ValueError("OBS origin is not the official repository")
    version = git(source, "describe", "--always", "--tags", "--dirty=-modified")
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-|$)", version):
        raise ValueError("OBS version tags/history missing; fetch full upstream history before build")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("OBS tracked source was modified")
    for name, expected in lock["sha256"].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError("OBS source identity mismatch: " + name)
    if "project(obs-studio " not in (source / "CMakeLists.txt").read_text():
        raise ValueError("Not the original OBS CMake project")
    if not (source / "frontend/CMakeLists.txt").is_file():
        raise ValueError("Original OBS frontend is missing")
    print("Verified official OBS source pin, notices, build script and original frontend; version=" + version)


def fetch(source, lock):
    # Refuse to overwrite any existing checkout, even an empty-looking one.
    source.mkdir(parents=True, exist_ok=False)
    subprocess.run(["git", "init", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "remote", "add", "origin", lock["repository"]], check=True)
    subprocess.run(["git", "-C", str(source), "fetch", "--tags", "origin", lock["commit"]], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD"], check=True)
    subprocess.run(["git", "-C", str(source), "submodule", "update", "--init", "--recursive", "--depth=1"], check=True)
    verify(source, lock)


def executable(source):
    return source / "build_ubuntu/install/RelWithDebInfo/bin/obs"


def record_build(source, lock):
    # Local identity record only: this can stamp an existing binary and is NOT
    # proof that the binary was compiled from the verified source.
    verify(source, lock)
    binary = executable(source)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError("Build original OBS first: python3 tools/obs_foundation.py build")
    receipt = {"commit": lock["commit"], "sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
    (source / "build_ubuntu/streamstrike-build.json").write_text(json.dumps(receipt) + "\n")


def build(source, lock, cef_root=None):
    # Local developer build; dependencies must already be provisioned. No sudo/installers.
    verify(source, lock)
    if platform.system() != "Linux":
        raise ValueError("This developer build path supports Ubuntu only; use pinned upstream platform instructions")
    # An interrupted rebuild must not leave an old success receipt usable.
    (source / "build_ubuntu/streamstrike-build.json").unlink(missing_ok=True)
    prefix = source / "build_ubuntu/install/RelWithDebInfo"
    args = ["cmake", "--preset", "ubuntu", "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
            "-DENABLE_BROWSER=ON", "-DENABLE_RELOCATABLE=ON",
            "-DCMAKE_INSTALL_PREFIX:PATH=" + str(prefix)]
    if cef_root:
        args.append("-DCEF_ROOT_DIR:PATH=" + str(Path(cef_root).resolve()))
    subprocess.run(args, cwd=source, check=True)
    # CMake honors CMAKE_BUILD_PARALLEL_LEVEL; when unset, the native generator
    # chooses its own default. Do not override the developer/runner resource budget.
    subprocess.run(["cmake", "--build", "build_ubuntu"], cwd=source, check=True)
    subprocess.run(["cmake", "--install", "build_ubuntu", "--prefix", str(source / "build_ubuntu/install/RelWithDebInfo")], cwd=source, check=True)
    record_build(source, lock)


def launch(source, lock):
    verify(source, lock)
    binary = executable(source)
    receipt_path = source / "build_ubuntu/streamstrike-build.json"
    if not binary.is_file() or not os.access(binary, os.X_OK) or not receipt_path.is_file():
        raise ValueError("Build original OBS first: python3 tools/obs_foundation.py build (binary or build receipt missing)")
    receipt = json.loads(receipt_path.read_text())
    if not isinstance(receipt, dict) or receipt.get("commit") != lock["commit"] or receipt.get("sha256") != hashlib.sha256(binary.read_bytes()).hexdigest():
        raise ValueError("OBS build receipt differs from source pin or executable; rebuild original OBS")
    subprocess.run([str(binary)], cwd=binary.parent, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch", "verify", "build", "record-build", "run"], nargs="?", default="run")
    parser.add_argument("--cef-root", help="Prepared upstream CEF directory (build only)")
    args = parser.parse_args()
    if args.cef_root and args.action != "build":
        parser.error("--cef-root applies only to build")
    lock = json.loads(LOCK.read_text())
    source = ROOT / lock["source_directory"]
    try:
        if args.action == "build":
            build(source, lock, args.cef_root)
        else:
            {"fetch": fetch, "verify": verify, "record-build": record_build, "run": launch}[args.action](source, lock)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print("StreamStrike OBS foundation: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
