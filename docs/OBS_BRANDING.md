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
for eight donor source files plus three new resource/helper files. Every later
verify/build/run rederives the expected copy from the clean donor and reviewed
overlay; an edited receipt cannot authorize different source. Unlisted source,
path escapes, dirty/missing submodules, changed assets or binaries fail closed.
For explicit pinned `text eol=crlf` files, the donor checkout must equal the
canonical Git blob with exactly LF→CRLF conversion. The copy uses the exact
canonical blob and records the raw checkout hash/conversion separately. Unknown
filters, encodings, attribute overrides or other byte changes cannot authorize
this conversion.
Attribute reads use the immutable pin (requiring Git with `check-attr --source`
support), with system/global/info overrides excluded. The canonical conversion
path itself never invokes clean/smudge filters; ordinary Git status checks still
have their normal Git semantics.
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

## Linux developer-runtime dependency closure

The first actual native launch exposed an upstream relocatable-install gap:
`frontend-tools.so` lives under `lib/.../obs-modules/core/`, while its required
`libobs-scripting.so.30` is two directories above. The pinned Linux defaults only
searched the module directory and its immediate parent. An executable-only `ldd`
pass did not establish plugin runtime readiness; that original reference build
is retained unchanged and is not claimed to have passed native acceptance.

Two additional hash-locked CMake edits in the build copy append the existing
package library directory, `$ORIGIN/../..`, to module install paths and to
obs-browser's separate install path. Existing entries remain in order; browser's
adjacent CEF `$ORIGIN/` stays first. Browser BUILD_RPATH, browser-page helper,
scripting bindings, plugin features and the clean original donor are unchanged.
No global loader configuration or library-path environment override is used.

`tools/obs_runtime.py` inventories every installed regular file and symlink,
stream-hashing large CEF assets. It inspects every installed real ELF with
`readelf`/`ldd` in a clean inspection environment, handles static ELF explicitly,
and rejects unresolved dependencies or non-private shipped SONAMEs resolving to
another installation. The first all-ELF audit incorrectly treated the bundled
CEF graphics libraries as globally owned: hosted diagnostic run `40114902835`
identified `obs-ffmpeg.so` reaching system `libplacebo.so.360`, whose own
`DT_NEEDED` correctly resolved system Vulkan rather than CEF's adjacent copy.

`tools/obs_components.py` now revalidates the retained, pinned CEF archive and
streams its six explicitly copied ELF members without extracting anything.
Archive, prepared input and installed bytes must agree; exact source contracts,
cache paths, explicit browser consumers and member hashes form the ownership
context. Other modules share the same core directory and are not CEF members.
For those proven private payloads only, a different external target is allowed
when the complete closure has a nonempty, unambiguous set of matching declared
`DT_NEEDED` requesters entirely outside the install prefix. Installed, mixed,
unknown or aliased requesters fail closed; CEF consumers and all non-private
shipped libraries retain exact-target requirements. There is no Vulkan-name
exception, loader override or changed search path. Without a source-derived
context, the auditor retains its original strict behavior.

The full report records the context and each private/system overlap rationale;
both are freshly rederived before launch. Standalone `ldd` is not a simulation of
same-process `dlopen` load order or namespace reuse. Fresh real frontend startup
and capture remain required, and do not establish optional hardware drivers or
media/device acceptance. Build and launch require this closure; the receipt additionally
binds the entire installed inventory and canonical closure-report digest, not
only the main executable. A fresh audit must match both before launch. The capture
artifact retains the matching dependency report and inventory hashes.

## Acceptance gates

The existing standard Ubuntu job first retains the unchanged original OBS build
and its provenance. It explicitly installs `qt6-svg-plugins` alongside the standard
ephemeral X11 tools before Qt tests and branded build/runtime inventory. Ubuntu
26.04 separates QIcon's SVG engine and SVG image handler from the linked SVG
library; `qt6-svg-dev` alone did not install these recommended runtime plugins.
The first mechanically passing native capture (`40118442822`) was rejected in
visual review because original toolbar SVG icons rendered as ellipses. That image
is diagnostic evidence, not an accepted README screenshot. No replacement icons,
theme changes or plugin-path overrides are used to conceal the missing dependency.
See the [official Ubuntu package file list](https://packages.ubuntu.com/resolute/all/qt6-svg-plugins/filelist)
and [Qt icon-engine documentation](https://doc.qt.io/qt-6/qicon.html#icon-engines).

The job then compiles real Qt icon tests, prepares/verifies/builds
the branding copy, and runs `tools/obs_capture.sh` under Xvfb, Openbox and a real
stalonetray host. Actual WM and Qt tray readiness are required before launch. This is a separate isolated synthetic HOME/configuration with
`FirstRun=true`, an empty source collection and no account/device/media fixture.
Safe mode is used for capture only; ordinary branded launch does not force it.

The opt-in hook reads the actual app/window/tray icons and compiled PNG, switches
only tray presentation to prove active/paused glyphs, restores idle, and captures
the real native root-framebuffer region covering the decorated OBS window. It
never reconstructs the UI, composites a logo onto a screenshot or starts media
outputs. It also requires the SVG image handler, renders the hash-checked original
OBS plus resource through `QIcon`, and reads the actual visible/enabled scene and
source add-toolbar button icons. Their nonempty 16×16 alpha silhouettes must match
the original plus; theme colors are preserved, not replaced. These readbacks and
their pixel hashes are recorded in the fresh runtime receipt. The app closes
through normal OBS shutdown. Missing SVG/icon rendering, tray/display,
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

### Verified Linux capture

[Run 40121353686](https://github.com/Gerbzz/StreamStrike/actions/runs/40121353686)
passed the original/branded builds, real Qt SVG/icon tests, archive-bound ownership
and 39-ELF closure checks, fresh native identity capture, and normal close with
exit 0. Root and independent visual review accepted the complete original OBS
frame with the StreamStrike mark and correctly rendered original toolbar icons.
The [unchanged PNG and source sidecar](../assets/screenshots/streamstrike-obs-linux-20261024.provenance.json)
remain bound to source head `aa18f3bcb9cf696933e08e0116debc07bd15c18b`, tested
checkout `9549373dfd24aec4603f7991d402be230c38278b`, and tree
`3d604075c9595cb6f979e3c469c3dad49541bff9`. A later documentation commit is not
represented as the source of that capture. The fixture was safe mode with an empty
scene; active/paused tray checks changed presentation only, not media state.
Nonfatal DBus/device/profile/shutdown warnings remain documented in the sidecar;
this is not a clean-device or full-feature acceptance claim.

## Explicitly unfinished

This first native gate is Linux only. Windows ICO/PE resources, macOS app iconsets,
installer/desktop launcher branding and native OS-shell appearance are not changed
or accepted here. Shared Qt source edits are not Windows/macOS runtime proof.
Display/microphone acquisition, recording/finalization/decode, streaming and
failure-path acceptance remain separate. No release, installer, full Rust rewrite
or OBS Project affiliation is claimed. Original notices and upstream credits are
preserved.
