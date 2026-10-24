# StreamStrike runtime identity on the actual OBS foundation

## Intent and authority
Use the existing requested, published StreamStrike geometric SVG/PNG identity in the actual pinned OBS frontend. Do not replace the frontend, manufacture screenshots, or claim additional aesthetic sign-off. The original OBS source pin is `72e86655715d9a25d69ce446aa4dd44ba58e10d2`; StreamStrike baseline is `24f2111dcae836edca7a19149f598eb5432c19bd`.

## Approach
README-only artwork is already delivered and insufficient. Editing the clean donor in place breaks the existing source guard. Instead, keep that donor and its build unchanged, export an isolated complete tracked source/submodule build copy, and apply a deterministic hash-locked branding overlay. Record all original file identities, overlay inputs/outputs, source version and resulting executable. Verify the clean donor before and after. Refuse existing destinations, symlink/path escapes, missing or dirty submodules, unexpected input hashes, and modified overlay copies.

## Runtime surfaces
Use the existing PNG unchanged as the master Qt resource. Window icon/title and tray identity must agree. Idle/active/paused tray transitions retain distinct functional state indicators around that same mark; no animal, new logo, OBS-mark substitution, UI redesign or media logic change. Keep upstream copyright/about/license notices, application settings/profile paths, desktop IDs, executable names, plugin APIs and upstream provenance intact.

## Native proof
Add an opt-in verification hook, off by default, to the real OBS frontend. In the existing standard Ubuntu hosted job only, launch the branded native X11 frontend with isolated synthetic settings and no accounts, device sources, streaming or recording. Capture its actual rendered native framebuffer, not a recreated layout. Read back the compiled resource and application/window/tray icon values and record all hashes and the title. Exercise idle/active/paused icon presentation without starting media outputs. Close normally. Failure, timeout or unavailable display is not acceptance. Retain diagnostic artifacts even on failure and do not place an unverified image in the README.

## Scope and gates
Local Python guardrail/tamper tests and original Rust/C oracle suite must pass; shared Qt icon tests run on hosted Qt. Require independent source review, unchanged original OBS build, successful branded build, source/inventory/resource/runtime checks, and visually inspected source-matched screenshot. Publish only a draft until these pass; root owns merge. No paid capacity, credentials, security changes, release or installer. Windows PE/ICO and macOS bundle/iconset/native acceptance remain unfinished and explicitly excluded from this Linux slice. Shared Qt source coverage is not cross-platform acceptance.

## Evidence-driven Linux install correction
Actual branded compilation succeeded, but the first native launch failed before the capture hook because the upstream relocatable module path was one directory too shallow for `libobs-scripting.so.30`. The refined bounded scope adds two hash-locked application-local CMake INSTALL_RPATH edits (Linux module default and browser's separate install path), retaining existing order/CEF adjacency, all features and the original donor. This supersedes the initial one-file repair proposal. Installed-file inventory and standalone ELF dependency closure are required before launch; no global environment workaround or suppressed fatal dialog is permitted. Original executable-only build evidence is not native runtime acceptance.
