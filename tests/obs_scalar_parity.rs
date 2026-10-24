use streamstrike::obs_scalar::{Read, ScalarItem, ScalarValue, Tier};

// C oracle catches reversed precedence, false/empty treated as absent,
// wrong getter type accepted, and unsetting one tier corrupting another.
#[test]
fn matches_pinned_obs_scalar_getters_and_unsets() {
    // Checked-in output keeps Rust tests portable (including Windows).
    // Python guardrail tests recompile the pinned C and require an exact match.
    let rows = include_str!("oracle/obs_scalar.tsv");
    assert_eq!(rows.lines().count(), 216);
    for row in rows.lines() {
        let cols: Vec<_> = row.split('\t').collect();
        assert_eq!(cols.len(), 14);
        let mut item = ScalarItem::default();
        for (tier, col) in [Tier::User, Tier::Default, Tier::Autoselect]
            .into_iter()
            .zip(&cols[1..4])
        {
            let value = match (cols[0], *col) {
                (_, "0") => continue,
                ("0", s) => ScalarValue::Boolean(s == "2"),
                (_, s) => ScalarValue::String(if s == "1" { "" } else { "選択" }.into()),
            };
            item.set(tier, value).unwrap();
        }
        match cols[4] {
            "1" => item.unset(Tier::User),
            "2" => item.unset(Tier::Default),
            "3" => item.unset(Tier::Autoselect),
            _ => {}
        }
        for (index, tier) in [Read::Effective, Read::Default, Read::Autoselect]
            .into_iter()
            .enumerate()
        {
            assert_eq!(item.get_bool(tier), cols[5 + index] == "1", "{row}");
            assert_eq!(item.get_string(tier), cols[8 + index], "{row}");
        }
        for (index, tier) in [Tier::User, Tier::Default, Tier::Autoselect]
            .into_iter()
            .enumerate()
        {
            assert_eq!(item.has(tier), cols[11 + index] == "1", "{row}");
        }
    }
}

#[test]
fn rejected_type_change_or_nul_does_not_mutate_settings() {
    let mut item = ScalarItem::default();
    item.set(Tier::Default, ScalarValue::Boolean(true)).unwrap();
    let before = item.clone();
    assert!(
        item.set(Tier::User, ScalarValue::String("x".into()))
            .is_err()
    );
    assert_eq!(item, before);
    let mut text = ScalarItem::default();
    assert!(
        text.set(Tier::User, ScalarValue::String("x\0y".into()))
            .is_err()
    );
    assert_eq!(text, ScalarItem::default());
}

#[test]
fn repeated_set_unset_and_clear_preserve_native_fallback() {
    let mut item = ScalarItem::default();
    item.set(Tier::Autoselect, ScalarValue::Boolean(true))
        .unwrap();
    item.set(Tier::Default, ScalarValue::Boolean(false))
        .unwrap();
    item.set(Tier::User, ScalarValue::Boolean(true)).unwrap();
    item.set(Tier::User, ScalarValue::Boolean(false)).unwrap();
    assert!(!item.get_bool(Read::Effective));
    item.unset(Tier::User);
    item.unset(Tier::User);
    assert!(!item.get_bool(Read::Effective));
    item.unset(Tier::Default);
    assert!(item.get_bool(Read::Effective));
    item.unset(Tier::Autoselect);
    assert!(!item.get_bool(Read::Effective));
    assert!(!item.has(Tier::User));
}
