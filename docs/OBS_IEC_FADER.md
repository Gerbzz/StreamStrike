# Original OBS IEC fader conversion slice

This independent slice replaces `iec_def_to_db` and `iec_db_to_def` from pinned
OBS `72e86655715d9a25d69ce446aa4dd44ba58e10d2`, `libobs/obs-audio-controls.c`, with
Rust implementations. The original `OBS_FADER_IEC` constructor dispatch,
set/get public APIs, synchronization, callbacks and all Qt frontend code remain
in place. Only the two conversion bodies move; the rest remains transitional C/C++.
The separately held six settings-reader candidate is **not** included or published.

## Source and integration

- `evidence/upstream/libobs/obs-audio-controls.c` is verbatim upstream, including
  its copyright and GPL-2.0-or-later notice. Its full SHA-256 is checked by the C
  oracle. The companion CMake input is also an exact pinned fixture.
- `foundation/rust-fader/iec.rs` is allocation-free `no_std` Rust with the same
  binary32 arithmetic order, branch boundaries, infinities, signed zero and NaN
  fallthrough. No new dependency or approximation is added.
- The existing hash-locked source-copy overlay removes the two original C bodies,
  declares hidden Rust ABI functions and redirects the existing dispatch names.
  The pinned donor checkout is never edited. All added source and build-oracle files are hashed.
- `StreamStrikeFader.cmake` compiles a PIC Rust static library and links it into
  the actual `libobs` target. Source, CMake and the discovered compiler executable timestamp invalidate the
  custom-command output. Switching a rustup-managed active toolchain requires a
  clean build directory (or explicit removal of the old archive) and reconfigure;
  a stable rustup proxy path alone does not attest that change. Missing Rust or undefined references fail the build;
  there is no C fallback. This path supports GNU C native x86_64 Linux profiles only when the exact compiler
  oracle passes. It is not cross-build or Windows/macOS acceptance, and FMA-profile
  artifacts require the same supported CPU/OS capabilities at execution.

## Tests and acceptance boundary

1. The C ABI oracle extracts the original two source bodies verbatim, compiles
   them alongside the Rust archive and compares exact float bits for 200,000
   deterministic bit patterns plus branch boundaries and their float neighbors.
   A zero-returning Rust skeleton failed before the implementation was written.
   This is a real C/Rust call test, **not a complete libobs/native application test**.
2. Overlay tests replay exact source transformations and assert that original
   dispatch uses Rust, original C bodies are removed and native CMake links the
   added source. Existing source/ELF closure tests remain required.
3. Hosted `verify_obs_fader.py` loads the actual complete original and migrated
   libraries in separate processes and compares 1,000 public API cases. It checks
   exact loaded library identity and bytes, and proves the constructor-selected
   db-to-deflection callback address is the Rust symbol in migrated libobs.
   Identical libraries, missing rows, mismatches or non-Rust dispatch fail.
4. The existing real OBS/Qt build, loader closure, native branding/render and
   normal-shutdown tests still follow. A passing reduced C oracle does not waive
   them. No recording, streaming, hardware or release claim follows from this slice.

The first complete native oracle found 69/1,000 rounding differences: the actual
original library used fused arithmetic, while the initial Rust profile did not.
Both complete native builds passed, but the parity gate failed and native capture
was skipped. No acceptance or merge followed. Retained run 40338854446/artifact
12658329598 anchors the regression fixture. Independent reduced C reproduction
matched all original rows with FMA and all initial Rust rows without it.

The correction supports explicit separate and fused arithmetic profiles. The
build-only driver replays the exact `obs-audio-controls.c` compile-command argv,
changing only source/output/dependency-output arguments, to compile pinned original
helpers. It first tries separate Rust arithmetic; only a numerical mismatch permits
trying Rust x86_64 FMA intrinsics at the twelve original multiply-plus-offset sites.
The fused oracle checks AVX/FMA/OSXSAVE and XGETBV XMM/YMM state before executing it.
Either profile must pass 200,000 original-C bit patterns and boundary neighbors
before its archive may link into libobs; crashes/unsupported CPU or unknown math
behavior fail closed. This is native-build support, not portable binary distribution.
The C oracle is build-only and never linked into the shipped application. Rust
runtime conversion is still Rust; the rest of libobs remains transitional C/C++.

Compiler argv/macros/version, Rust/source hashes, failed attempts, selected profile
and archive digest are retained. Compile database, compiler, source, script and
CMake inputs invalidate the archive. A rustup proxy changing its selected toolchain
without changing its executable still requires clean reconfiguration, as noted above.
The workflow retains original audio compile invocation and compiler target defaults
as well. GCC-specific effective-option diagnostics currently reject other C
compilers explicitly. The complete original-vs-migrated public API gate remains bit-exact and
unchanged; original reference flags are never altered to fit Rust.

Local profile tests and all 69 observed mismatches pass the corrected reduced
regression. Corrected complete-libobs/CMake/native acceptance remains pending hosted
checks; source fixtures are not native acceptance. Publication/merge receipts are separate.

Commands (with an existing official Rust compiler in PATH):

```sh
cargo test --locked --all-targets
python3 -m unittest discover -s tests -p 'test_obs_*.py' -v
# After complete original and branded/native builds:
python3 tools/verify_obs_fader.py
```

First hosted run built original OBS and passed shared Qt contracts, but strict
migrated linking exposed existing direct GLib/GObject calls missing from OBS's
Gio link interface. The integration now declares those providers explicitly only
when Gio is enabled. `--no-undefined` remains required; a reduced C link reproduces
the missing-provider failure and passes with both providers. Full native acceptance
still requires the corrected hosted candidate to pass all gates.
