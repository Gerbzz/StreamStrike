# IEC fader runtime slice

Scope: exactly two original OBS IEC conversion bodies; native Linux libobs ABI.
Preserve original Qt UI and donor, all C storage/callback synchronization, held
settings candidate, existing regression/build/native gates and current source.

- [x] Reconcile main b8e2233d and held settings scope; isolate gerbzz work branch.
- [x] Fail real C/Rust oracle against stub; implement original arithmetic; pass.
- [x] Fail source-dispatch overlay check; add hashed Rust and CMake linkage; pass.
- [x] Fail native evidence rejection cases; implement complete-libobs verifier.
- [x] Independent final review, complete project Rust/Python checks.
- [ ] Draft publication, exact-head hosted full libobs/native checks.
- [ ] Gated merge only if accepted; no release or whole-port claim.
