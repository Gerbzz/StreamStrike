// SPDX-License-Identifier: GPL-2.0-or-later
// Derived from OBS Studio libobs/obs-data.c:
// Copyright (C) 2023 by Lain Bailey <lain@obsproject.com>
// See evidence/upstream/COPYING for the license and docs/OBS_SCALAR_PARITY.md
// for exact upstream provenance and the intentionally bounded port domain.

//! Owned Rust port of OBS scalar settings-item resolution.
//!
//! A future settings consumer can hold one item per OBS key, apply a source's
//! defaults, and then apply the user's overrides. This module does not read or
//! rewrite profiles and is not yet called by the original OBS frontend/libobs.
//!
//! ```
//! use streamstrike::obs_scalar::{Read, ScalarItem, ScalarValue, Tier};
//! let mut enabled = ScalarItem::default();
//! enabled.set(Tier::Default, ScalarValue::Boolean(true))?;
//! enabled.set(Tier::User, ScalarValue::Boolean(false))?;
//! assert!(!enabled.get_bool(Read::Effective)); // explicit false wins
//! enabled.unset(Tier::User);
//! assert!(enabled.get_bool(Read::Effective)); // native default restored
//! # Ok::<(), &'static str>(())
//! ```

//! Numeric subtypes may differ across tiers without changing the item family:
//! ```
//! use streamstrike::obs_scalar::{NumberType, Read, ScalarItem, ScalarValue, Tier};
//! let mut rate = ScalarItem::default();
//! rate.set(Tier::Default, ScalarValue::Integer(60))?;
//! rate.set(Tier::User, ScalarValue::Double(59.94))?;
//! assert_eq!(rate.get_int(Read::Effective), Ok(59));
//! assert_eq!(rate.number_type(), Some(NumberType::Double));
//! rate.unset(Tier::User);
//! assert_eq!(rate.get_int(Read::Effective), Ok(60));
//! assert_eq!(rate.number_type(), Some(NumberType::Integer));
//! # Ok::<(), &'static str>(())
//! ```

/// The three separately present values in an OBS data item.
#[derive(Clone, Copy, Debug)]
pub enum Tier {
    User,
    Default,
    Autoselect,
}

/// OBS normal getters resolve all tiers; explicit default/autoselect getters do not.
#[derive(Clone, Copy, Debug)]
pub enum Read {
    Effective,
    Default,
    Autoselect,
}

/// Primitive values in this port's domain. Integer and Double share the native
/// OBS_DATA_NUMBER family, but each tier retains its own numeric subtype.
#[derive(Clone, Debug, PartialEq)]
pub enum ScalarValue {
    Integer(i64),
    Double(f64),
    Boolean(bool),
    String(String),
}

/// Owned, type-consistent scalar values; no native pointer or ABI layout is exposed.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct ScalarItem {
    user: Option<ScalarValue>,
    default: Option<ScalarValue>,
    autoselect: Option<ScalarValue>,
}

/// Subtype tag carried separately by each native OBS numeric tier.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum NumberType {
    Integer,
    Double,
}
/// A double-to-integer conversion that native C does not define.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum IntConversionError {
    NonFinite,
    OutOfRange,
}

impl ScalarItem {
    /// Native integer read on the defined conversion domain. Missing/wrong-type
    /// values return zero. Doubles truncate toward zero, but NaN/infinity and
    /// out-of-range values return an error instead of reproducing C undefined
    /// behavior or silently using Rust's saturating float-to-integer cast.
    pub fn get_int(&self, read: Read) -> Result<i64, IntConversionError> {
        match self.resolve(read) {
            Some(ScalarValue::Integer(value)) => Ok(*value),
            Some(ScalarValue::Double(value)) => {
                if !value.is_finite() {
                    return Err(IntConversionError::NonFinite);
                }
                // 2^63 is exactly representable; i64::MAX as f64 rounds UP to
                // this excluded endpoint. The lower endpoint -2^63 is valid.
                if !(-9223372036854775808.0..9223372036854775808.0).contains(value) {
                    return Err(IntConversionError::OutOfRange);
                }
                Ok(*value as i64)
            }
            _ => Ok(0),
        }
    }

    /// Native double read. Integer rounding is checked against the host C
    /// oracle; stored double bits (including signed zero) are retained.
    pub fn get_double(&self, read: Read) -> f64 {
        match self.resolve(read) {
            Some(ScalarValue::Integer(value)) => *value as f64,
            Some(ScalarValue::Double(value)) => *value,
            _ => 0.0,
        }
    }

    /// Like obs_data_item_numtype, inspect the effective value, not necessarily
    /// the user tier. An absent or nonnumeric value has no numeric subtype.
    pub fn number_type(&self) -> Option<NumberType> {
        match self.resolve(Read::Effective) {
            Some(ScalarValue::Integer(_)) => Some(NumberType::Integer),
            Some(ScalarValue::Double(_)) => Some(NumberType::Double),
            _ => None,
        }
    }

    /// Replace one tier, retaining the others. Reject unsupported cross-family types and
    /// interior NUL atomically. Native OBS uses one type tag for all tier storage;
    /// this safe subset does not reproduce cross-type byte reinterpretation.
    pub fn set(&mut self, tier: Tier, value: ScalarValue) -> Result<(), &'static str> {
        if let ScalarValue::String(text) = &value {
            if text.contains('\0') {
                return Err("interior NUL is outside the supported OBS string domain");
            }
        }
        if let Some(existing) = self.resolve(Read::Effective) {
            let both_numeric = matches!(existing, ScalarValue::Integer(_) | ScalarValue::Double(_))
                && matches!(&value, ScalarValue::Integer(_) | ScalarValue::Double(_));
            if !both_numeric && std::mem::discriminant(existing) != std::mem::discriminant(&value) {
                return Err("mixed scalar types are outside the supported OBS item domain");
            }
        }
        *self.slot_mut(tier) = Some(value);
        Ok(())
    }

    /// Remove only the requested tier. Repeated unsets are harmless.
    pub fn unset(&mut self, tier: Tier) {
        *self.slot_mut(tier) = None;
    }

    /// False and the empty string are present values, not missing values.
    pub fn has(&self, tier: Tier) -> bool {
        match tier {
            Tier::User => self.user.is_some(),
            Tier::Default => self.default.is_some(),
            Tier::Autoselect => self.autoselect.is_some(),
        }
    }

    /// As in data_item_get_bool, missing values or the wrong type return false.
    pub fn get_bool(&self, read: Read) -> bool {
        match self.resolve(read) {
            Some(ScalarValue::Boolean(value)) => *value,
            _ => false,
        }
    }

    /// As in data_item_get_string, missing values or the wrong type return "".
    pub fn get_string(&self, read: Read) -> &str {
        match self.resolve(read) {
            Some(ScalarValue::String(value)) => value,
            _ => "",
        }
    }

    fn resolve(&self, read: Read) -> Option<&ScalarValue> {
        match read {
            Read::Effective => self
                .user
                .as_ref()
                .or(self.default.as_ref())
                .or(self.autoselect.as_ref()),
            Read::Default => self.default.as_ref(),
            Read::Autoselect => self.autoselect.as_ref(),
        }
    }

    fn slot_mut(&mut self, tier: Tier) -> &mut Option<ScalarValue> {
        match tier {
            Tier::User => &mut self.user,
            Tier::Default => &mut self.default,
            Tier::Autoselect => &mut self.autoselect,
        }
    }
}
