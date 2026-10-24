# Original OBS entrypoint cutover and preservation audit

## Intent and boundary

Following the verified original OBS build, retire the superseded custom GUI and
make the actual upstream frontend/engine the developer application starting point.
Do not redesign the old GUI, remove useful libraries, rewrite Git history, touch
user projects, or claim a Rust port or completed native runtime acceptance.

Baseline: StreamStrike main `573a11c130e2fd35c8126c238b2c05d6bd04041c` (PR #7).
Original OBS pin: `72e86655715d9a25d69ce446aa4dd44ba58e10d2`, OBS 33.0.0.
Hosted original build: run `40045870669`, job `120727339763`, successful.
Provenance artifact: `12541812274`; ZIP SHA-256
`d2a135c367920e3b74ceace85566846acc7ebe46bb99a1fd42676b8df5664703`.
Runner-recorded executable SHA-256:
`5408d94427592afdfc81ec7870a080963c29d404224e8e7f36a4a43c8b8bb815`.
The binary was not distributed in this provenance-only artifact.

## Approaches and implementation scope

Keeping the old GUI active would contradict the requested OBS starting point.
Deleting the whole Rust crate would lose useful JSON validation and safe storage.
The bounded choice is therefore to retire only the custom frontend, retain the
compatibility crate, and route the documented developer launch to original OBS.
Local tooling targets Ubuntu first, matching the verified donor platform;
Windows/macOS acceptance is not inferred from that build.

## Dependency and preservation map

| Component | Decision and evidence |
| --- | --- |
| `src/bin/editor.rs` | Remove superseded custom eframe frontend. Last full version remains in baseline Git history. |
| `eframe`, `rfd`, `image` | GUI/capture-only consumers removed; drop direct dependencies and prune unreachable lock entries without changing retained versions/checksums. |
| `tests/native_capture_gate.rs`, `.github/workflows/editor-preview.yml` | Remove old-GUI screenshot test and workflow, not a test of original OBS. Replace with compatibility CI rather than manufacture a new screenshot. |
| `src/lib.rs`, `src/editor.rs`, `src/storage.rs`, `src/main.rs` | Byte-preserved project model, validation, atomic document state, persistence and CLI. No OBS engine behavior claimed. |
| `foundation/obs-source.lock.json`, `evidence/upstream/**` | Byte-preserved reviewed donor pin, notices and source/build fixtures. No original-base work discarded. |
| `tools/obs_foundation.py` | Extend existing donor fetch/verification with original CMake build and checked original-binary launch. No substitute UI. |
| `tests/test_obs_foundation.py` | Existing source guardrail tests retained. Add separate entrypoint tests. |
| Existing artwork and screenshot/provenance files | Retain unchanged; annotate historical documentation instead of presenting old GUI images as current OBS. |
| User `.streamstrike` JSON and recovery sidecars | Never searched, rewritten, deleted or automatically imported. New integration tests work only with temporary copies of a committed synthetic fixture. |
| Git history | No rebase, force push or history rewriting. Removal is a normal reviewable tree change. |

## Build and launch behavior

See the root README for fetch/build/run commands. The no-argument Python command
is the default application entrypoint. Cargo remains a legacy compatibility CLI,
not an OBS launcher. No implicit download or build happens on launch.

The build helper verifies source, invokes the donor `ubuntu` CMake preset with
RelWithDebInfo, browser support and relocatable runtime paths enabled, builds and installs into the donor
checkout. It requires already-prepared upstream system/CEF dependencies; it does
not install packages or change global configuration. Configure/build/install
failure stops immediately without creating a new success receipt. Any previous
receipt is invalidated before configuring, so an interrupted rebuild cannot be
launched through this helper. The configure-time and install-time prefixes match;
relocatable runtime paths prevent dependence on a system-installed libobs. Hosted
CI rebuilds this developer configuration after the upstream dependency/build
entrypoint and checks the installed executable for unresolved shared libraries.

After a successful local build (or the existing hosted upstream build),
`record-build` records the checked source pin and executable hash. Launch verifies
source identity and receipt against the fixed original executable path, then
runs that file without shell interpolation. Missing or changed binaries fail;
there is no custom-editor or system-OBS fallback. This local receipt checks
consistency only. Because `record-build` can stamp an existing executable, it
does not prove that binary was compiled from the pinned source. Verified hosted
build execution and provenance remain authoritative, not this local receipt.
The helper honors `CMAKE_BUILD_PARALLEL_LEVEL`; when unset it leaves scheduling
to the native generator default instead of imposing an arbitrary fixed cap.
Developers can set the environment variable using measured CPU/memory capacity.

OBS itself uses normal OBS configuration/profile locations when launched. Back up
existing OBS settings before developer runtime testing. This change neither
rewrites legacy JSON into OBS collections nor asserts that the schemas match.
There is no implemented OBS importer to remove or preserve: a future explicit
converter must retain originals and report unsupported fields in new output.

## Review and validation plan

1. Freeze the diff against fresh merged main and constrain removals to the three
   old-GUI files above; verify byte preservation of compatibility core/donor data.
2. Run original source guardrails plus missing/unreceipted/changed-binary,
   no-fallback, fixed-path and build-failure entrypoint tests.
3. Run all locked Rust tests and the preserved CLI on the synthetic fixture;
   verify originals and recovery sidecars remain byte-identical.
4. Require hosted original OBS build and compatibility CI before merge. A
   successful helper unit test is not evidence of an interactive GUI launch.
5. Keep native display/microphone capture, preview, bounded recording,
   finalization/decode and device-loss/disk-full acceptance as separate gates.

All OBS license notices remain. No binary release, installer, upstream
relicensing, Rust parity slice or replacement UI is included.
