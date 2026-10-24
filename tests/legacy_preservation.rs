use streamstrike::{editor::EditorDocument, storage};
use std::{fs, path::PathBuf, time::{SystemTime, UNIX_EPOCH}};

fn workspace() -> PathBuf {
    let path = std::env::temp_dir().join(format!("streamstrike-preservation-{}-{}", std::process::id(), SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()));
    fs::create_dir(&path).unwrap();
    path
}

#[test]
fn legacy_json_opens_without_rewriting_and_converts_only_to_new_path() {
    let root = workspace();
    let old = root.join("original.streamstrike");
    let bytes = include_bytes!("../docs/evidence/demo.streamstrike");
    fs::write(&old, bytes).unwrap();
    let mut document = EditorDocument::open(&old).unwrap();
    assert_eq!(fs::read(&old).unwrap(), bytes);
    assert!(storage::create(&old, &document.project).is_err());
    let copy = root.join("separate.streamstrike");
    document.save_as(&copy).unwrap();
    assert_eq!(storage::load(&old).unwrap(), storage::load(&copy).unwrap());
    assert_eq!(fs::read(&old).unwrap(), bytes);
    fs::remove_dir_all(root).unwrap();
}

#[test]
fn recovery_sidecars_prevent_overwriting_existing_user_project() {
    let root = workspace();
    let old = root.join("original.streamstrike");
    let bytes = include_bytes!("../docs/evidence/demo.streamstrike");
    fs::write(&old, bytes).unwrap();
    let project = storage::load(&old).unwrap();
    for extension in ["streamstrike.tmp", "streamstrike.bak"] {
        let sidecar = old.with_extension(extension);
        fs::write(&sidecar, b"preserve recovery data").unwrap();
        assert!(storage::save(&old, &project).unwrap_err().contains("recovery sidecar"));
        assert_eq!(fs::read(&old).unwrap(), bytes);
        assert_eq!(fs::read(&sidecar).unwrap(), b"preserve recovery data");
        fs::remove_file(sidecar).unwrap();
    }
    fs::remove_dir_all(root).unwrap();
}
