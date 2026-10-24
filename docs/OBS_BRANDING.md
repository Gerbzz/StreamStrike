# StreamStrike identity on the real OBS frontend

This source slice adds the existing published product mark to the actual original
OBS frontend, not a custom imitation UI. The original pin and license remain
`72e86655715d9a25d69ce446aa4dd44ba58e10d2` (GPL-2.0-or-later). The PNG is unchanged:
SHA-256 `86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926`.
Its prior creation/publication provenance remains in `assets/branding/`; this
change does not invent another visual approval or license grant.

## Source and runtime boundary

`tools/obs_branding.py prepare` verifies the clean original donor, all initialized
submodule pins, tracked Git object bytes and modes, then exports them into a new
`foundation/streamstrike-obs` directory. It refuses an existing destination. The
original checkout, Git history, notices, resources and original build remain.
`foundation/branding/overlay.json` pins the input/output hashes and exact edits
for six donor source files plus three new resource/helper files. Every later
verify/build/run rederives the expected copy from the clean donor and reviewed
overlay; an edited receipt cannot authorize different source. Unlisted source,
path escapes, dirty/missing submodules, changed assets or binaries fail closed.
The generated build directory may not be a symlink, and generated symlinks must
stay inside it.

The new developer build uses the original Ubuntu preset and prepared upstream
CEF dependency, retains browser support and relocatable paths, and records donor,
overlay, entire source inventory and executable hashes. Version text retains the
OBS donor version with a StreamStrike suffix. A deterministic developer build
number of zero avoids the donor CMake module writing a cache into guarded source. The original helper remains the
untouched reference path, not an automatic fallback.

Shared Qt presentation changes are the app/window icon, main title, tray tooltip
and idle/active/paused icons. The active badge and paused transparency bars are
functional state indicators around the unchanged S mark. The original output
state branches and media operations are preserved. No application settings or
profile path, desktop ID, plugin API, credentials, update policy or user project
is migrated. Ordinary launch has no capture behavior unless the explicit test
environment variable is set.

## Acceptance gates

The existing standard Ubuntu job first retains the unchanged original OBS build
and its provenance. It then compiles real Qt icon tests, prepares/verifies/builds
the branding copy, and runs `tools/obs_capture.sh` under Xvfb, Openbox and a real
stalonetray host. Actual WM and Qt tray readiness are required before launch. This is a separate isolated synthetic HOME/configuration with
`FirstRun=true`, an empty source collection and no account/device/media fixture.
Safe mode is used for capture only; ordinary branded launch does not force it.

The opt-in hook reads the actual app/window/tray icons and compiled PNG, switches
only tray presentation to prove active/paused glyphs, restores idle, and captures
the real native root-framebuffer region covering the decorated OBS window. It
never reconstructs the UI, composites a logo onto a screenshot or starts media
outputs. The app closes through normal OBS shutdown. Missing tray/display,
unexposed window, modal startup, wrong resource, output overwrite,
blank image, timeout or nonzero exit is a failed gate. Artifacts retain failures
rather than silently treating them as success. Visual review must reject an
obscured window, incomplete rendering, or any unexpected/non-OBS scene.

A screenshot is suitable for the README only after exact source/build/hash checks
and visual review. A per-launch nonce, actual executable readback and runtime
artifact hashes reject stale/swapped evidence. These consistency checks are not
cryptographic attestation of a genuine UI: fresh hosted-process provenance and
human inspection of the framebuffer remain mandatory. No current OBS screenshot is claimed by source tests alone.
The retained old WGPU project editor image is historical and must not be reused.

## Explicitly unfinished

This first native gate is Linux only. Windows ICO/PE resources, macOS app iconsets,
installer/desktop launcher branding and native OS-shell appearance are not changed
or accepted here. Shared Qt source edits are not Windows/macOS runtime proof.
Display/microphone acquisition, recording/finalization/decode, streaming and
failure-path acceptance remain separate. No release, installer, full Rust rewrite
or OBS Project affiliation is claimed. Original notices and upstream credits are
preserved.
