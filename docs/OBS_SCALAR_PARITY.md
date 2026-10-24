# First bounded OBS settings Rust port

`src/obs_scalar.rs` ports the **boolean and UTF-8 string item** portion of
`libobs/obs-data.c` at the existing source pin
`72e86655715d9a25d69ce446aa4dd44ba58e10d2` (OBS 33.0.0).
The source fixture remains byte-for-byte unchanged, including its copyright;
the derived Rust module is GPL-2.0-or-later, with upstream attribution.

## Implemented contract and consumption boundary

- Three independently present tiers: user, default, autoselect.
- Ordinary reads resolve **user, then default, then autoselect**. Autoselect is
  not an override. Explicit default/autoselect reads never fall through.
- False and empty strings are present values. Wrong-type getters return false
  or an empty string, matching native `data_item_get_bool/string`.
- Replacing/unsetting one tier preserves the others. Repeated unsets do nothing.
- Rust owns values rather than exposing native pointers or allocation layout.

A future OBS settings consumer can map each known boolean/string key to a
`ScalarItem`, set defaults and user values separately, and use `Read::Effective`
for the same resolution contract. The module's doctest exercises that boundary.
**There is no caller in original OBS yet.** This module is not a wrapper around
libobs, and no alternative frontend is introduced. Original Qt/libobs remain
the actual application; the legacy JSON utilities and user files are unchanged.

The supported domain is intentionally smaller than native obs_data: no numeric,
object, array, serialization, key enumeration, reference-count/ABI, arbitrary
non-UTF-8 bytes, or cross-type setter semantics. Interior NUL and mixed-type
writes are rejected without mutation; these are explicit Rust boundary
restrictions, not claims that native OBS rejects them. Native uses one type tag
for the item while holding multiple tier byte buffers. Reproducing unsafe
cross-type reinterpretation is not an acceptable implicit migration behavior.
After all values are unset, a new type may be written safely.

## Proof and its limits

`tests/oracle/obs_scalar_oracle.py` verifies the existing upstream source SHA-256,
extracts the original getter, presence and unset function bodies verbatim, and
compiles/runs them with the system C compiler. A small harness supplies only the
fields read by these functions and packed boolean/string payloads. The three
release callbacks are no-ops, equivalent only within these two primitive types.
The harness is **not the original struct ABI or a complete libobs build**.

The executable emits 216 rows: two scalar types × 27 absent/false-or-empty/
true-or-Unicode tier combinations × unchanged/unset-user/unset-default/
unset-autoselect. Both matching and mismatching typed reads and all presence
flags are recorded. The checked-in TSV is generated output, not hand-authored
expected values. Rust tests consume it on any platform; the existing Python
Linux CI guardrail command recompiles the C source functions and requires an
exact byte match. No network, OBS rebuild, extra Rust dependency or large cache
is required. C setters/allocation behavior are **not** exercised by this oracle.

Additional regression tests cover repeated replacement/unset, atomic rejection
of unsupported input, and the consumer doctest. The initial API skeleton failed
all three added tests before implementation (presence, fallback, and rejection
assertions); the implemented module passed them.

```sh
cargo test --locked
python3 -m unittest discover -s tests -p 'test_obs_*.py' -v
```

The Python suite requires Python 3 and `cc` (C11); the Rust suite itself does not.
This establishes source-function parity only for the declared subset. It does
not establish a completed OBS rewrite, frontend integration, binary ABI/lifetime
parity, display/microphone capture, recording acceptance, or a releasable build.
