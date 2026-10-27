# Remaining original OBS fader conversions

> **For agentic workers:** Use superpowers:executing-plans with TDD and independent review.

**Goal:** Move the four remaining cubic/logarithmic fader conversion bodies into
Rust through original libobs dispatch, preserving original OBS frontend behavior.
**Architecture:** Extend the existing no_std Rust staticlib and exact compiler-profile
oracle. Retain system libm log10f/powf/cbrtf through explicitly disclosed transitional
FFI; no alternate UI or standalone-module delivery claim.
**Tech stack:** Original pinned OBS C/C++, Rust, GNU/native x86_64 Linux, Python.
**Authority:** Existing authorized OBS parity migration; Neil explicitly opted out
of optional questions. Choice of this bounded slice is the worker's, not a new
user scope approval. No settings-reader hold is changed.

## Constraints and review focus
- Preserve existing IEC 200,000-pattern/edge and native 1,000-case gates unchanged.
- Add original-source four-function numerical parity, including NaN payloads,
  infinities, signed zero, underflow, endpoints and branch neighbors.
- Preserve actual compiler argv; separate/fused profile must match all converters.
- Preserve all three native public constructors, clamps and callback dispatch.
- Source hashes, runtime library identity and native original Qt acceptance remain
  required; local reduced oracle alone is not native acceptance.
- System libm FFI is transitional; no claim of full fader/OBS rewrite or release.

## One coherent runtime slice
- [x] Fail original-C/Rust differential test before implementing four exports.
- [x] Implement original cubic/log formulas and exact f32 arithmetic in Rust.
- [x] Fail hashed original dispatch/source overlay tests; wire remaining callbacks.
- [x] Fail native coverage/callback rejection tests; extend without dropping IEC.
- [ ] Run full Rust/Python/build checks and independent immutable-diff review.
- [ ] Publish normal draft PR; monitor exact-head complete OBS/native gates.
- [ ] Merge expected reviewed head only after all gates pass; record handoff.
