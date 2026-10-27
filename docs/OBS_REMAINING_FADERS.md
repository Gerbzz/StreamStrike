# Original cubic and logarithmic fader conversion runtime

## Bounded migration, not the completed OBS rewrite

This candidate replaces the remaining four conversion bodies from official OBS
`72e86655715d9a25d69ce446aa4dd44ba58e10d2`, `libobs/obs-audio-controls.c`:
`cubic_def_to_db`, `cubic_db_to_def`, `log_def_to_db`, `log_db_to_def`.
The previous IEC pair remains in Rust. Hash-locked source-copy transformations
route all three **original libobs constructors** to those Rust functions; original
Qt frontend/layout, C fader state, locks, source signals, clamp policy, lifetime
and all other audio runtime are unchanged. No alternate app entrypoint is added.
The separate held settings-reader candidate is not included or cleared.

The formulas, branch/NaN/nonfinite behavior and binary32 expression order execute
in Rust. **Transitional FFI remains:** original system `libm` implementations of
`log10f`, `powf` and `cbrtf` are called through their native scalar ABI. This is not
a claim that those mathematical libraries, all fader state or all OBS are Rust.
There are no new downloaded dependencies. Supported build scope remains native
GNU x86_64 Linux, not a portable release or another platform's acceptance.

## Source and exact numerical gates

Verbatim GPL-2.0-or-later controls and audio-math fixtures preserve the original
Leonhard Oelke and Lain Bailey notices and are hash-pinned. Cubic conversion keeps
left-associated multiplication, zero-underflow behavior, and `db_to_mul`'s rule
that *every nonfinite db* returns zero before `cbrtf`. Log conversion keeps its
-96 dB clamp and original rounded binary32 constants.

The existing compiler-replay driver now tests all six conversion bodies using the
**actual** libobs compile argv. Original compiler flags are not changed. Separate
and fused Rust arithmetic profiles must match original C bit-for-bit; logarithmic
multiply-plus-offset uses the same selected profile. The original 200,000-pattern
LCG and IEC edge-neighbor coverage remain, with additional -96 dB, explicit cubic
underflow/overflow, and signed/signaling NaN payload cases. Unsupported math still
fails closed before the Rust archive may link. This is build-only original C,
not shipped converter C bodies. Complete native parity is still independently
required; the reduced driver is not an application acceptance test.

## Native evidence contract

`tools/verify_obs_fader.py` preserves the exact previous 1,000 IEC input sequence
and adds 1,000 cases for each original cubic/logarithmic public constructor.
It requires distinct original/migrated complete libobs identities and digests,
all six expected Rust symbols, actual Rust db-to-deflection callback addresses
for each constructor, complete expected typed input sequences, public acceptance
flags and exact get-db/get-deflection output bits. Missing/duplicated/wrong-type
traces, a non-Rust callback, a single mismatch or changing library fails.
Separate processes prevent original/migrated SONAME cross-contamination.

All existing original/migrated OBS builds, strict linking, loader-closure audits,
shared Qt contracts, real native frontend capture and normal shutdown remain
required, followed by independent review and exact-head hosted verification.
No recording, streaming, hardware, full migration or release claim follows.

## Evidence status

Local source/ABI tests are not hosted or native acceptance. Publication, exact-head
CI, native result, merge receipt and any release are recorded separately in the
run handoff. This document specifies the gates; it does not predeclare them passed.

Commands with the existing official Rust compiler and cached dependencies:

```sh
cargo test --locked
cargo build --locked --bin streamstrike
python3 -m unittest discover -s tests -p 'test_obs_*.py' -v
# Only after complete original and migrated OBS installations:
python3 tools/verify_obs_fader.py
```
