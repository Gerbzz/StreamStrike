//! Document state shared by the native editor's controls.

use crate::{Project, storage};
use std::path::{Path, PathBuf};

pub struct EditorDocument {
    pub project: Project,
    saved: Project,
    pub path: Option<PathBuf>,
}

impl Default for EditorDocument {
    fn default() -> Self {
        Self::new()
    }
}

impl EditorDocument {
    pub fn new() -> Self {
        let project = Project::new();
        Self {
            saved: project.clone(),
            project,
            path: None,
        }
    }

    pub fn open(path: &Path) -> Result<Self, String> {
        let project = storage::load(path)?;
        Ok(Self {
            saved: project.clone(),
            project,
            path: Some(path.to_path_buf()),
        })
    }

    pub fn is_dirty(&self) -> bool {
        self.project != self.saved
    }

    /// Apply one operation atomically, so a rejected edit cannot damage the open document.
    pub fn apply<T>(&mut self, edit: impl FnOnce(&mut Project) -> Result<T, String>) -> Result<T, String> {
        let mut candidate = self.project.clone();
        let result = edit(&mut candidate)?;
        candidate.validate()?;
        self.project = candidate;
        Ok(result)
    }

    pub fn save(&mut self) -> Result<(), String> {
        let path = self.path.as_ref().ok_or("Choose a project path with Save as")?;
        storage::save(path, &self.project)?;
        self.saved = self.project.clone();
        Ok(())
    }

    pub fn save_as(&mut self, path: &Path) -> Result<(), String> {
        if path.extension().and_then(|ext| ext.to_str()) != Some("streamstrike") {
            return Err("project files must end in .streamstrike".into());
        }
        if self.path.as_deref() == Some(path) {
            return self.save();
        }
        if path.exists() {
            return Err("that project already exists; choose a new name".into());
        }
        storage::create(path, &self.project)?;
        self.path = Some(path.to_path_buf());
        self.saved = self.project.clone();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::SourceKind;

    #[test]
    fn rejected_edits_are_atomic_and_successful_edits_mark_dirty() {
        let mut doc = EditorDocument::new();
        assert!(!doc.is_dirty());
        let before = doc.project.clone();
        assert!(doc.apply(|project| project.rename_scene(1, "")).is_err());
        assert_eq!(doc.project, before);
        assert!(!doc.is_dirty());
        doc.apply(|project| project.add_scene("Game")).unwrap();
        assert!(doc.is_dirty());
    }

    #[test]
    fn create_edit_save_and_reopen_real_project() {
        let mut doc = EditorDocument::new();
        let scene = doc.apply(|project| project.add_scene("Game")).unwrap();
        let microphone = doc.apply(|project| project.add_source(scene, "Voice", SourceKind::Microphone, "default")).unwrap();
        doc.apply(|project| project.set_audio(microphone, true, -6.0)).unwrap();
        let path = std::env::temp_dir().join(format!(
            "streamstrike-editor-{}-{}.streamstrike",
            std::process::id(),
            std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()
        ));
        doc.save_as(&path).unwrap();
        assert!(!doc.is_dirty());
        doc.apply(|project| project.rename_scene(scene, "Gameplay")).unwrap();
        assert!(doc.is_dirty());
        doc.save().unwrap();
        let reopened = EditorDocument::open(&path).unwrap();
        assert!(!reopened.is_dirty());
        assert_eq!(reopened.project.scenes[1].name, "Gameplay");
        assert!(reopened.project.scenes[1].sources[0].muted);
    }
}

