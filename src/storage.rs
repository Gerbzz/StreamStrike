//! Shared project persistence for the CLI and native editor.

use crate::{MAX_PROJECT_BYTES, Project};
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;

pub fn load(path: &Path) -> Result<Project, String> {
    reject_symlink(path)?;
    let size = fs::metadata(path)
        .map_err(|error| format!("cannot inspect project: {error}"))?
        .len();
    if size > MAX_PROJECT_BYTES {
        return Err("project exceeds 1 MiB limit".into());
    }
    let data = fs::read(path).map_err(|error| format!("cannot read project: {error}"))?;
    if data.len() as u64 > MAX_PROJECT_BYTES {
        return Err("project exceeds 1 MiB limit".into());
    }
    let project: Project =
        serde_json::from_slice(&data).map_err(|error| format!("invalid project JSON: {error}"))?;
    project.validate()?;
    Ok(project)
}

pub fn create(path: &Path, project: &Project) -> Result<(), String> {
    project.validate()?;
    let data = encode(project)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(|error| format!("cannot create new project: {error}"))?;
    file.write_all(&data)
        .map_err(|error| format!("project write failed; inspect {}: {error}", path.display()))?;
    file.sync_all()
        .map_err(|error| format!("project sync failed; inspect {}: {error}", path.display()))
}

pub fn save(path: &Path, project: &Project) -> Result<(), String> {
    project.validate()?;
    reject_symlink(path)?;
    let data = encode(project)?;
    let temp = path.with_extension("streamstrike.tmp");
    let backup = path.with_extension("streamstrike.bak");
    if temp.exists() || backup.exists() {
        return Err(format!(
            "recovery sidecar exists; inspect {} and {} before saving",
            temp.display(),
            backup.display()
        ));
    }
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temp)
        .map_err(|error| format!("cannot create staging file: {error}"))?;
    file.write_all(&data)
        .map_err(|error| format!("staging write failed; inspect {}: {error}", temp.display()))?;
    file.sync_all()
        .map_err(|error| format!("staging sync failed; inspect {}: {error}", temp.display()))?;
    fs::rename(path, &backup)
        .map_err(|error| format!("cannot preserve old project; staging file kept: {error}"))?;
    if let Err(error) = fs::rename(&temp, path) {
        let restore = fs::rename(&backup, path);
        return Err(format!(
            "cannot publish project: {error}; old-project restore: {restore:?}; staging file kept"
        ));
    }
    fs::remove_file(&backup).map_err(|error| {
        format!(
            "project saved, but backup cleanup failed at {}: {error}",
            backup.display()
        )
    })
}

fn reject_symlink(path: &Path) -> Result<(), String> {
    let metadata =
        fs::symlink_metadata(path).map_err(|error| format!("cannot inspect project: {error}"))?;
    if metadata.file_type().is_symlink() {
        return Err("project symlinks are unsupported".into());
    }
    if !metadata.is_file() {
        return Err("project path is not a regular file".into());
    }
    Ok(())
}

fn encode(project: &Project) -> Result<Vec<u8>, String> {
    let mut data = serde_json::to_vec_pretty(project).map_err(|error| error.to_string())?;
    data.push(b'\n');
    if data.len() as u64 > MAX_PROJECT_BYTES {
        return Err("project exceeds 1 MiB limit".into());
    }
    Ok(data)
}

