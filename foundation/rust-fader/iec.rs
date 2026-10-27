// Derived from OBS libobs/obs-audio-controls.c (Leonhard Oelke, 2014).
// SPDX-License-Identifier: GPL-2.0-or-later
#![no_std]

#[panic_handler]
fn panic(_: &core::panic::PanicInfo<'_>) -> ! {
    loop {}
}

// The build-only original-C probe selects this profile; its full differential
// oracle must pass before linking libobs. No original converter C body remains; system libm FFI is disclosed below.
#[inline]
fn multiply_add(a: f32, b: f32, c: f32) -> f32 {
    #[cfg(streamstrike_fma)]
    {
        // SAFETY: native x86_64 configure probe requires hardware FMA support;
        // the selected compiler profile and exact oracle are build prerequisites.
        unsafe { fused(a, b, c) }
    }
    #[cfg(not(streamstrike_fma))]
    { a * b + c }
}

#[cfg(streamstrike_fma)]
#[target_feature(enable = "fma")]
unsafe fn fused(a: f32, b: f32, c: f32) -> f32 {
    use core::arch::x86_64::{_mm_cvtss_f32, _mm_fmadd_ss, _mm_set_ss};
    _mm_cvtss_f32(_mm_fmadd_ss(_mm_set_ss(a), _mm_set_ss(b), _mm_set_ss(c)))
}

// Preserve the original f32 expression order and comparisons, including NaN,
// infinities, signed zero, endpoints and the discontinuity below 0.001.
#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_iec_def_to_db(def: f32) -> f32 {
    if def == 1.0 {
        0.0
    } else if def <= 0.0 {
        f32::NEG_INFINITY
    } else if def >= 0.75 {
        (def - 1.0) / 0.25 * 9.0
    } else if def >= 0.5 {
        multiply_add((def - 0.75) / 0.25, 11.0, -9.0)
    } else if def >= 0.3 {
        multiply_add((def - 0.5) / 0.2, 10.0, -20.0)
    } else if def >= 0.15 {
        multiply_add((def - 0.3) / 0.15, 10.0, -30.0)
    } else if def >= 0.075 {
        multiply_add((def - 0.15) / 0.075, 10.0, -40.0)
    } else if def >= 0.025 {
        multiply_add((def - 0.075) / 0.05, 10.0, -50.0)
    } else if def >= 0.001 {
        multiply_add((def - 0.025) / 0.025, 90.0, -60.0)
    } else {
        f32::NEG_INFINITY
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_iec_db_to_def(db: f32) -> f32 {
    if db == 0.0 {
        1.0
    } else if db == f32::NEG_INFINITY {
        0.0
    } else if db >= -9.0 {
        multiply_add((db + 9.0) / 9.0, 0.25, 0.75)
    } else if db >= -20.0 {
        multiply_add((db + 20.0) / 11.0, 0.25, 0.5)
    } else if db >= -30.0 {
        multiply_add((db + 30.0) / 10.0, 0.2, 0.3)
    } else if db >= -40.0 {
        multiply_add((db + 40.0) / 10.0, 0.15, 0.15)
    } else if db >= -50.0 {
        multiply_add((db + 50.0) / 10.0, 0.075, 0.075)
    } else if db >= -60.0 {
        multiply_add((db + 60.0) / 10.0, 0.05, 0.025)
    } else if db >= -114.0 {
        (db + 150.0) / 90.0 * 0.025
    } else {
        0.0
    }
}

// Transitional system-math ABI, the same libm primitives called by original OBS.
// Branching, expression order and fader conversion runtime are Rust; these
// transcendental implementations are not claimed as a Rust math-library port.
#[link(name = "m")]
unsafe extern "C" {
    fn log10f(value: f32) -> f32;
    fn powf(base: f32, exponent: f32) -> f32;
    fn cbrtf(value: f32) -> f32;
}

#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_cubic_def_to_db(def: f32) -> f32 {
    if def == 1.0 {
        0.0
    } else if def <= 0.0 {
        f32::NEG_INFINITY
    } else {
        let mul = (def * def) * def;
        if mul == 0.0 { f32::NEG_INFINITY } else {
            // SAFETY: system libm accepts every binary32 value, including NaN.
            20.0 * unsafe { log10f(mul) }
        }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_cubic_db_to_def(db: f32) -> f32 {
    if db == 0.0 {
        1.0
    } else if db == f32::NEG_INFINITY {
        0.0
    } else {
        let mul = if db.is_finite() {
            // SAFETY: system libm scalar ABI has no pointer preconditions.
            unsafe { powf(10.0, db / 20.0) }
        } else { 0.0 };
        // SAFETY: same original system libm cbrtf operation.
        unsafe { cbrtf(mul) }
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_log_def_to_db(def: f32) -> f32 {
    if def >= 1.0 {
        0.0
    } else if def <= 0.0 {
        f32::NEG_INFINITY
    } else {
        // SAFETY: same original system libm powf operation.
        multiply_add(-102.0, unsafe { powf(17.0, -def) }, 6.0)
    }
}

#[unsafe(no_mangle)]
pub extern "C" fn streamstrike_log_db_to_def(db: f32) -> f32 {
    const LOG_OFFSET_VAL: f32 = -0.77815125038364363;
    const LOG_RANGE_VAL: f32 = -2.00860017176191756;
    if db >= 0.0 {
        1.0
    } else if db <= -96.0 {
        0.0
    } else {
        // SAFETY: same original system libm log10f operation.
        (-unsafe { log10f(-db + 6.0) } - LOG_RANGE_VAL)
            / (LOG_OFFSET_VAL - LOG_RANGE_VAL)
    }
}
