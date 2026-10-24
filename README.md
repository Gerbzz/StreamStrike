<p align="center">
  <img src="assets/branding/StreamStrike-logo.png" alt="StreamStrike product logo" width="128" height="128">
</p>

<p align="center">
  <a href="https://prowebdevsolutions.com"><picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/branding/PWDS-logo-orange.svg">
    <img src="assets/branding/PWDS-logo.png" alt="PWDS company logo" width="120">
  </picture></a>
</p>
<p align="center"><strong>Published by PWDS</strong></p>

<h1 align="center">StreamStrike</h1>

StreamStrike now starts from **the original OBS Studio frontend and libobs engine**,
not the retired custom Rust project-editor UI. The pinned upstream source is
`obsproject/obs-studio` commit `72e86655715d9a25d69ce446aa4dd44ba58e10d2`
(OBS 33.0.0). Original C/C++ compilation passed in
[run 40045870669](https://github.com/Gerbzz/StreamStrike/actions/runs/40045870669).
This is a source-development baseline, **not a Rust rewrite, verified native
capture/recording acceptance, installer, or StreamStrike release**.

## Default developer application: actual OBS with StreamStrike identity

The supported helper path currently targets Ubuntu 26.04. Prepare the toolchain
and dependencies required by the pinned upstream source, including CMake, Ninja,
Qt (including Ubuntu's `qt6-svg-plugins` runtime package), FFmpeg and CEF. This helper does not install system dependencies, invoke sudo,
or silently reduce frontend/browser functionality. The exact fully provisioned
hosted build remains in [obs-foundation.yml](.github/workflows/obs-foundation.yml).

```sh
python3 tools/obs_foundation.py fetch
python3 tools/obs_foundation.py build --cef-root "$PWD/foundation/obs-studio/.deps/cef_binary_7871_linux_x86_64"
python3 tools/obs_branding.py prepare
python3 tools/obs_branding.py build
python3 tools/obs_branding.py
```

Before building, use the pinned upstream dependency preparation to retain both
`.deps/cef_binary_7871_linux_x86_64.tar.xz` and its extracted directory inside the
original donor. The branded helper requires this exact checksum-verified archive
and canonical prepared location; an arbitrary external CEF directory is not its
ownership-provenance contract. The hosted workflow demonstrates the full setup.

The branding helper builds a separate tracked-source copy with a hash-locked overlay; the original donor and its original build remain unchanged. It wires the existing mark into the actual Qt window and all idle/active/paused tray states, retaining the OBS frontend and media engine. Native verification is a required hosted gate, not established merely by these source changes. [Overlay, validation and platform limits](docs/OBS_BRANDING.md).

`fetch` refuses an existing directory. `build` verifies the donor identity,
uses its original `ubuntu` CMake preset with browser support and relocatable runtime paths enabled, and installs
to the checkout-local `build_ubuntu/install/RelWithDebInfo`. The original helper’s no-argument
command (or `run`) launches only that original `bin/obs`, checking its source pin
and recorded build hash. The default branding command above separately verifies the complete copied source/overlay and its own executable receipt; it never falls back to the donor or legacy editor. If source, binary, receipt, dependencies or runtime are
missing, it fails explicitly; it never launches the old editor or system OBS.
`record-build` can stamp a preexisting executable: its receipt is only a local
identity check, **not proof that the binary was compiled from the pinned source**.
The verified hosted build and its provenance remain authoritative build evidence.
An executable-only loader check does not prove plugin readiness. The branded
helper additionally verifies installed ELF dependency closure and a complete
installed-file inventory; [the Linux install correction](docs/OBS_BRANDING.md#linux-developer-runtime-dependency-closure) remains part of the source-matched native gate.
Build concurrency honors `CMAKE_BUILD_PARALLEL_LEVEL` if set; otherwise CMake
uses the native generator default. Set that environment variable to a job count
appropriate for measured available CPU and memory; the helper imposes no fixed cap.

Windows/macOS source work should follow the pinned upstream platform build
instructions; this helper does not claim those platforms have passed acceptance.
Running OBS uses normal OBS settings/profile locations and can change them;
back up existing OBS profiles before developer testing. No legacy `.streamstrike`
project is automatically opened, converted, migrated or overwritten.

## Preserved legacy project compatibility

The old GUI entrypoint, GUI-only dependencies and screenshot workflow are retired.
Their code and captures remain recoverable in Git history; existing evidence and
artwork remain in the tree, labeled historical rather than current application UI.
The Rust project model, validation, atomic storage, document state and CLI remain
intact for compatibility with existing JSON `.streamstrike` projects:

```sh
cargo test --locked --all-targets
cargo run --locked --bin streamstrike -- show PATH.streamstrike
```

The CLI is **not** the application launcher or media engine. Its create/edit/save
commands are still available; they do not open media devices. No automatic OBS
importer exists yet: preserve originals and map unsupported fields explicitly in
a separate future conversion, writing new files rather than replacing user data.
See [the preservation audit](docs/OBS_CUTOVER.md) and
[OBS foundation direction](docs/OBS_FOUNDATION.md).

## Acceptance and licenses

Next gates are original OBS on a real desktop: display/microphone capture,
preview, bounded recording, stop/finalize, independent decode, and failure paths.
Compilation and launch-helper unit tests do not establish those results.
OBS retains its upstream GPL-2.0-or-later notices; all supplied upstream fixtures
and approved artwork are preserved. Distribution requires corresponding source,
build scripts and dependency notices. No first-party license grant or OBS Project
affiliation is claimed by this source checkpoint.

### PWDS publisher artwork

The company mark in this masthead is the existing [official PWDS logo](https://github.com/Gerbzz/PWDS-Website/blob/main/public/prowebdevsolutions-logo.png), with the [official orange display asset](https://prowebdevsolutions.com/images/prowebdevsolutions-logo-orange.svg) for dark backgrounds. This is PWDS publisher artwork, not a StreamStrike app logo.

## Product artwork

The StreamStrike product mark above has an original [SVG master](assets/branding/StreamStrike-logo.svg) and matching PNG. [Asset provenance](assets/branding/StreamStrike-logo.provenance.json) records how it was created and the exact file hashes. The PWDS publisher artwork and inherited software credits are unchanged. Historical screenshots retain the artwork visible in their original captured builds. The current native OBS screenshot is not substituted with the retired custom GUI; a new image is published only after exact-source hosted capture and visual review.
