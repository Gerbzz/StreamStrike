use streamstrike::obs_scalar::{
    IntConversionError, NumberType, Read, ScalarItem, ScalarValue, Tier,
};

#[test]
fn native_numeric_getters_subtypes_and_unsets_match_defined_c_oracle() {
    let rows = include_str!("oracle/obs_numeric.tsv");
    assert_eq!(rows.lines().count(), 127);
    for row in rows.lines() {
        let c: Vec<_> = row.split('\t').collect();
        assert_eq!(c.len(), 17, "{row}");
        let mut item = ScalarItem::default();
        match c[0] {
            "tiers" => {
                for (tier, s) in [Tier::User, Tier::Default, Tier::Autoselect]
                    .into_iter()
                    .zip(&c[1..4])
                {
                    let value = match *s {
                        "0" => continue,
                        "1" => ScalarValue::Integer(-17),
                        "2" => ScalarValue::Double(3.75),
                        _ => panic!("invalid fixture {row}"),
                    };
                    item.set(tier, value).unwrap();
                }
                match c[4] {
                    "0" => {}
                    "1" => item.unset(Tier::User),
                    "2" => item.unset(Tier::Default),
                    "3" => item.unset(Tier::Autoselect),
                    _ => panic!("invalid fixture {row}"),
                }
            }
            "int" => item
                .set(Tier::User, ScalarValue::Integer(c[1].parse().unwrap()))
                .unwrap(),
            "double" => item
                .set(
                    Tier::User,
                    ScalarValue::Double(f64::from_bits(u64::from_str_radix(c[1], 16).unwrap())),
                )
                .unwrap(),
            _ => panic!("invalid fixture {row}"),
        }
        for (i, read) in [Read::Effective, Read::Default, Read::Autoselect]
            .into_iter()
            .enumerate()
        {
            assert_eq!(
                item.get_int(read),
                Ok(c[5 + i * 2].parse().unwrap()),
                "{row}"
            );
            assert_eq!(
                item.get_double(read).to_bits(),
                u64::from_str_radix(c[6 + i * 2], 16).unwrap(),
                "{row}"
            );
        }
        assert_eq!(
            item.number_type(),
            match c[11] {
                "0" => None,
                "1" => Some(NumberType::Integer),
                "2" => Some(NumberType::Double),
                _ => panic!("invalid subtype {row}"),
            },
            "{row}"
        );
        for (i, tier) in [Tier::User, Tier::Default, Tier::Autoselect]
            .into_iter()
            .enumerate()
        {
            assert_eq!(item.has(tier), c[12 + i] == "1", "{row}");
        }
        assert_eq!(item.get_bool(Read::Effective), c[15] == "1", "{row}");
        assert_eq!(
            item.get_string(Read::Effective).len(),
            c[16].parse::<usize>().unwrap(),
            "{row}"
        );
    }
}

#[test]
fn undefined_native_integer_conversions_are_explicit_errors_not_saturation() {
    for (value, error) in [
        (f64::NAN, IntConversionError::NonFinite),
        (f64::INFINITY, IntConversionError::NonFinite),
        (f64::NEG_INFINITY, IntConversionError::NonFinite),
        (9223372036854775808.0, IntConversionError::OutOfRange),
        (-9223372036854777856.0, IntConversionError::OutOfRange),
        (f64::MAX, IntConversionError::OutOfRange),
        (f64::MIN, IntConversionError::OutOfRange),
    ] {
        let mut item = ScalarItem::default();
        item.set(Tier::Default, ScalarValue::Double(value)).unwrap();
        assert_eq!(item.get_double(Read::Default).to_bits(), value.to_bits());
        assert_eq!(item.get_int(Read::Default), Err(error));
        // A defined user value masks the unsupported default conversion.
        item.set(Tier::User, ScalarValue::Integer(12)).unwrap();
        assert_eq!(item.get_int(Read::Effective), Ok(12));
        assert_eq!(item.get_int(Read::Default), Err(error));
        item.unset(Tier::User);
        assert_eq!(item.get_int(Read::Effective), Err(error));
    }
}

#[test]
fn numeric_wrong_type_getters_and_cross_family_rejection_preserve_existing_contract() {
    for value in [ScalarValue::Boolean(true), ScalarValue::String("42".into())] {
        let mut item = ScalarItem::default();
        item.set(Tier::User, value).unwrap();
        let before = item.clone();
        assert_eq!(item.get_int(Read::Effective), Ok(0));
        assert_eq!(item.get_double(Read::Effective), 0.0);
        assert_eq!(item.number_type(), None);
        assert!(item.set(Tier::Default, ScalarValue::Integer(42)).is_err());
        assert_eq!(item, before);
    }
    let mut item = ScalarItem::default();
    item.set(Tier::User, ScalarValue::Integer(0)).unwrap();
    item.set(Tier::User, ScalarValue::Double(-0.0)).unwrap();
    item.set(Tier::Default, ScalarValue::Integer(8)).unwrap();
    assert_eq!(
        item.get_double(Read::Effective).to_bits(),
        (-0.0_f64).to_bits()
    );
    assert_eq!(item.number_type(), Some(NumberType::Double));
    let before = item.clone();
    assert!(
        item.set(Tier::Autoselect, ScalarValue::Boolean(false))
            .is_err()
    );
    assert_eq!(item, before);
    item.unset(Tier::User);
    assert_eq!(item.get_int(Read::Effective), Ok(8));
    assert_eq!(item.number_type(), Some(NumberType::Integer));
}
