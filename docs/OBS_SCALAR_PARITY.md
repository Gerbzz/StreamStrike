# Bounded OBS scalar settings Rust port

`src/obs_scalar.rs` ports the **boolean, UTF-8 string and numeric item** portion of
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

A future OBS settings consumer can map each known scalar key to a
`ScalarItem`, set defaults and user values separately, and use `Read::Effective`
for the same resolution contract. The module's doctest exercises that boundary.
**There is no caller in original OBS yet.** This module is not a wrapper around
libobs, and no alternative frontend is introduced. Original Qt/libobs remain
the actual application; the legacy JSON utilities and user files are unchanged.

The supported domain is intentionally smaller than native obs_data: no object, array, serialization, key enumeration, reference-count/ABI, arbitrary
non-UTF-8 bytes, or cross-family setter semantics. Interior NUL and cross-family
writes are rejected without mutation; these are explicit Rust boundary
restrictions, not claims that native OBS rejects them. Native uses one type tag
for the item while holding multiple tier byte buffers. Reproducing unsafe
cross-type reinterpretation is not an acceptable implicit migration behavior.
After all values are unset, a new type may be written safely.

## Proof and its limits

`tests/oracle/obs_scalar_oracle.py` verifies the existing upstream source SHA-256,
extracts the original getter, presence and unset function bodies verbatim, and
compiles/runs them with the system C compiler. A small harness supplies only the
fields read by these functions and primitive payloads. Numeric payloads are aligned
for the verbatim upstream number struct; static assertions enforce 64-bit integer
and binary64 support. The three
release callbacks are no-ops, equivalent only within primitive scalar types.
The harness is **not the original struct ABI or a complete libobs build**.

The original Boolean/String executable still emits the same 216 rows: two scalar types × 27 absent/false-or-empty/
true-or-Unicode tier combinations × unchanged/unset-user/unset-default/
unset-autoselect. Both matching and mismatching typed reads and all presence
flags are recorded. The checked-in TSV is generated output, not hand-authored
expected values. Rust tests consume it on any platform; the existing Python
Linux CI guardrail command recompiles the C source functions and requires an
exact byte match. No network, OBS rebuild, extra Rust dependency or large cache
is required. C setters/allocation behavior are **not** exercised by this oracle.

Additional regression tests cover repeated replacement/unset, atomic rejection
of unsupported input, and the consumer doctest. The initial API skeleton failed
all three initial Boolean/String tests before implementation (presence, fallback, and rejection
assertions); the implemented module passed them.

```sh
cargo test --locked
python3 -m unittest discover -s tests -p 'test_obs_*.py' -v
```

The Python suite requires Python 3 and `cc` (C11); the Rust suite itself does not.
This establishes source-function parity only for the declared subset. It does
not establish a completed OBS rewrite, frontend integration, binary ABI/lifetime
parity, display/microphone capture, recording acceptance, or a releasable build.

## Numeric extension: one shared scalar core

`ScalarValue::Integer(i64)` and `Double(f64)` share the native `OBS_DATA_NUMBER`
family. Unlike a Boolean/String family change, replacing an integer with a double
or mixing numeric subtypes across tiers is supported. Each tier retains its own
subtype; `number_type()` follows the effective user/default/autoselect value,
matching `obs_data_item_numtype`. All existing Boolean/String APIs and the
original 216-row fixture are preserved.

The native correspondence is `obs_set_int/double` (lines 1080–1100),
`item_int`, `data_item_get_int`, `item_double`, `data_item_get_double`
(lines 1675–1710), and `obs_data_item_numtype` (line 1550) in the pinned file.
Missing or wrong-family numeric reads yield zero. Explicit default/autoselect
reads do not fall through. Signed zero and double storage are retained.

`get_int(Read)` returns `Result<i64, IntConversionError>`: finite doubles in
`[-2^63, 2^63)` truncate toward zero. NaN/infinity produce `NonFinite`; doubles
outside that interval produce `OutOfRange`. These errors define the Rust
boundary where the original C cast has no defined result; **native OBS is not
claimed to return an error**. Storage and `get_double` still accept these values.
The upper boundary is exclusive: converting `i64::MAX` to binary64 rounds to
`2^63`, so using `i64::MAX as f64` as an inclusive bound would be incorrect.

`tests/oracle/obs_numeric_oracle.py` reuses the source hash check, exact function
extractor and compiler runner. It adds verbatim numeric getters/subtype lookup,
mixed integer/double tier and unset cases, i64 extrema, values around `2^53`,
positive/negative fractions, signed zero, and subnormal doubles. Double results
are compared by bits rather than rounded display strings. A harness guard
refuses nonfinite/out-of-range doubles **before** invoking the native integer
cast. Unsupported conversions are independently tested only against the safe
Rust boundary, never executed as C casts.

Integer-to-double rounding beyond binary64's exact-integer range is verified
against the current host C compiler (Linux x86-64, 64-bit `long long`, binary64,
default floating-point environment). This is observed target parity, not a claim
that the C standard mandates identical rounding on every compiler/architecture
or nondefault rounding mode. The checked-in oracle output is a host-generated
fixture; Python CI regenerates and compares it. C allocation/setter behavior,
serialization and full libobs ABI remain outside the proof.

The numeric API skeleton first failed three tests for missing numeric values,
rejected mixed numeric subtype replacement, and lost nonfinite double storage.
After implementation, those tests and the unchanged Boolean/String suite pass.
