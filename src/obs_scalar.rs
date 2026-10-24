// SPDX-License-Identifier: GPL-2.0-or-later
// Derived from OBS Studio libobs/obs-data.c:
// Copyright (C) 2023 by Lain Bailey <lain@obsproject.com>
// See evidence/upstream/COPYING for the license and docs/OBS_SCALAR_PARITY.md
// for exact upstream provenance and the intentionally bounded port domain.

//! Owned Rust port of OBS boolean/string settings-item resolution.
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

/// Only boolean and UTF-8 string items are in this port's current domain.
#[derive(Clone, Debug, PartialEq)]
pub enum ScalarValue {
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

impl ScalarItem {
    /// Replace one tier, retaining the others. Reject unsupported mixed types and
    /// interior NUL atomically. Native OBS uses one type tag for all tier storage;
    /// this safe subset does not reproduce cross-type byte reinterpretation.
    pub fn set(&mut self, tier: Tier, value: ScalarValue) -> Result<(), &'static str> {
        if let ScalarValue::String(text) = &value {
            if text.contains('\0') {
                return Err("interior NUL is outside the supported OBS string domain");
            }
        }
        if let Some(existing) = self.resolve(Read::Effective) {
            if std::mem::discriminant(existing) != std::mem::discriminant(&value) {
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
