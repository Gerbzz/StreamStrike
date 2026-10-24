# OBS Runtime Branding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the existing StreamStrike mark into the actual OBS Linux frontend and verify a genuine native capture.
**Architecture:** Preserve the clean pinned donor; export tracked source and initialized submodules to a separate immutable-inventory build copy, then apply hash-locked source/resource changes. A disabled-by-default runtime proof hook reads actual Qt icons and grabs the native window; the existing hosted job builds and validates both original and branded sources.
**Tech Stack:** Python standard library, Git, original OBS C++/Qt6/CMake, existing Ubuntu GitHub Actions.
**Spec:** `docs/superpowers/specs/2026-10-24-obs-runtime-branding-design.md`

## Global Constraints
- Original donor pin `72e86655715d9a25d69ce446aa4dd44ba58e10d2` and current original guard remain unchanged.
- Existing product PNG SHA-256 `86acca5004fbe90a471230159b452d3eb4a3663db30dac5d26523f43f470d926` is the master.
- No user machines, paid runners, credentials, new artwork, settings/desktop-ID migration or release.
- Root owns merge; Linux native proof does not establish Windows/macOS packaging.

## Review Focus
- Dirty/uninitialized submodules, tracked source tampering and altered overlay receipts must fail closed.
- Existing output directories and symlink/path escapes must never overwrite unrelated files.
- Paused/active/idle tray states remain distinct and cannot silently revert to OBS theme icons.
- A blank framebuffer, missing actual tray object, stale binary or partial capture must fail structural gates. No mock image is accepted without genuine hosted-process provenance and visual review.
- Capture opt-in is inert during ordinary launches; test settings are isolated and contain no real accounts/devices.

### Task 1: Deterministic source copy and build provenance
**Files:** `tools/obs_branding.py`, `foundation/branding/overlay.json`, `tests/test_obs_branding.py`.
**Interfaces:** prepare/verify/build/run uses fixed donor and separate copy; inventory describes modes, hashes, submodule pins and overlay inputs/outputs.
- [x] Write failing executable tests using temporary real Git repositories: clean copy, existing destination, input tamper, output tamper, symlink escape, missing submodule and stale build receipt.
- [x] Run new tests and observe expected failure before implementation.
- [x] Implement source export, exact replacements, verification and original-preset branded build/receipt, no fallback.
- [x] Run all Python and locked Rust tests; record limits.

### Task 2: Runtime identity and native capture probe
**Files:** `foundation/branding/StreamStrikeBranding.hpp`, `foundation/branding/StreamStrikeCapture.hpp`, `tests/branding/icon_test.cpp`, overlay substitutions.
**Interfaces:** `StreamStrikeBranding::icon(State)` supplies Qt icon states; capture hook receives actual OBSBasic QWidget and tray object, only on explicit environment opt-in.
- [x] Define failing Qt tests for original master resource identity and distinct state pixels/title/icon logic.
- [x] Implement shared Qt icon helper, actual app/window/tray use and opt-in readback/native capture/normal close.
- [x] Validate exact donor anchors and compile/test in hosted original dependencies (run `40121353686`; no local native inference).

### Task 3: Existing hosted acceptance and documentation
**Files:** `.github/workflows/obs-foundation.yml`, `tools/verify_obs_capture.py`, `tests/test_obs_capture.py`, README/docs/evidence.
**Interfaces:** capture output carries native PNG, raw Qt icon/resource exports and JSON; verifier binds source/overlay/binary/resource and validates image data/state distinctions.
- [x] Write failing acceptance tests for missing/stale/mismatched artifacts and degenerate PNG.
- [x] Add bounded isolated Xvfb capture after unchanged original build, keep provenance/diagnostics on failure, no binary release.
- [x] Run full local suite and independent review; publish draft using reviewed exact files only.
- [x] Inspect actual hosted artifacts and image; add the unchanged capture and truthful safe-mode/empty-scene caption after run `40121353686` and independent/root visual approval.
- [ ] Root merges only reviewed exact-head hosted proof. Report remaining OS packaging limitations.
