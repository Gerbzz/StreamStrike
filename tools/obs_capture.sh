#!/usr/bin/env bash
# Only synthetic hosted X11 data; never run against a developer's OBS profiles.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
evidence="$root/obs-branding-evidence"
mkdir "$evidence"
fixture=$(mktemp -d)
cleanup() { rm -rf -- "$fixture"; }
trap cleanup EXIT
mkdir -p "$fixture/home" "$fixture/config/obs-studio" "$fixture/runtime" "$evidence/capture"
chmod 700 "$fixture/runtime"
cat > "$fixture/config/obs-studio/user.ini" <<'EOF'
[General]
FirstRun=true
ConfirmOnExit=false

[Basic]
Profile=StreamStrike fixture
SceneCollection=StreamStrike fixture
SceneCollectionFile=StreamStrike fixture

[BasicWindow]
SysTrayEnabled=true
SysTrayWhenStarted=false
PreviewEnabled=true
EOF
# FirstRun=true causes upstream CreateDefaultScene(false): no first-run device sources.
# No old project, account token, stream key or external media enters this profile.
python3 "$root/tools/obs_branding.py" evidence > "$evidence/build.json"
# Bind this fresh capture to the guarded build receipt; do not accept stale artifacts.
read -r nonce identity < <(python3 - "$evidence/build.json" <<'PYTHON'
import hashlib, json, secrets, sys
from pathlib import Path
path=Path(sys.argv[1]); build=json.loads(path.read_text())
identity=hashlib.sha256(json.dumps(build,sort_keys=True,separators=(",",":")).encode()).hexdigest()
nonce=secrets.token_hex(16); build["capture_nonce"]=nonce
path.write_text(json.dumps(build,indent=2)+"\n")
print(nonce,identity)
PYTHON
)
git -C "$root" rev-parse HEAD > "$evidence/streamstrike-checkout.txt"
cp "$root/foundation/branding/overlay.json" "$evidence/overlay.json"
cp "$root/foundation/obs-source.lock.json" "$evidence/obs-source.lock.json"
set +e
env -i PATH="$PATH" HOME="$fixture/home" XDG_CONFIG_HOME="$fixture/config" \
  XDG_RUNTIME_DIR="$fixture/runtime" LANG=C.UTF-8 LC_ALL=C.UTF-8 \
  QT_QPA_PLATFORM=xcb LIBGL_ALWAYS_SOFTWARE=1 \
  STREAMSTRIKE_CAPTURE_NONCE="$nonce" STREAMSTRIKE_BUILD_IDENTITY="$identity" \
  STREAMSTRIKE_CAPTURE_DIR="$evidence/capture" STREAMSTRIKE_ROOT="$root" \
  xvfb-run -a -s '-screen 0 1920x1080x24 +extension GLX +render -noreset' \
  bash -c '
    set -euo pipefail
    openbox > "$STREAMSTRIKE_ROOT/obs-branding-evidence/window-manager.log" 2>&1 & wm=$!
    stalonetray --geometry 1x1-0+0 --icon-size 32 > "$STREAMSTRIKE_ROOT/obs-branding-evidence/tray.log" 2>&1 & tray=$!
    trap "kill $tray $wm 2>/dev/null || true" EXIT
    # Wait for actual WM ownership instead of assuming a fixed startup delay.
    ready=false
    for ((n=0;n<100;n++)); do
      if xprop -root _NET_SUPPORTING_WM_CHECK | grep -q "window id"; then ready=true; break; fi
      sleep .1
    done
    "$ready"
    "$STREAMSTRIKE_ROOT/build-branding-test/streamstrike-icon-contract" --wait-for-native-tray
    timeout --signal=TERM --kill-after=15s 120s python3 "$STREAMSTRIKE_ROOT/tools/obs_branding.py" capture
  ' > "$evidence/runtime.log" 2>&1
result=$?
set -e
printf '%s\n' "$result" > "$evidence/process-exit.txt"
# Keep only logs from the isolated synthetic profile, never a real home directory.
if test -d "$fixture/config/obs-studio/logs"; then cp -R "$fixture/config/obs-studio/logs" "$evidence/obs-logs"; fi
if ((result != 0)); then echo 'Actual branded OBS did not close successfully' >&2; exit "$result"; fi
python3 "$root/tools/obs_branding.py" verify
python3 "$root/tools/verify_obs_capture.py" "$evidence/capture" --build-evidence "$evidence/build.json"
