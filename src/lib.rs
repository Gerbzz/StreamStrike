//! Source-only project core. No screen, audio, encoder, or network device is opened here.

use serde::{Deserialize, Serialize};
use std::collections::HashSet;

pub mod editor;
pub mod storage;
pub mod obs_scalar;

pub const PROJECT_VERSION: u32 = 1;
pub const MAX_PROJECT_BYTES: u64 = 1024 * 1024;

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Project {
    pub version: u32,
    pub next_id: u64,
    pub active_scene_id: u64,
    pub scenes: Vec<Scene>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Scene {
    pub id: u64,
    pub name: String,
    pub sources: Vec<Source>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Source {
    pub id: u64,
    pub name: String,
    pub kind: SourceKind,
    /// An engine-resolved display, window, or audio device selector. No device is opened yet.
    pub selector: String,
    pub visible: bool,
    pub muted: bool,
    pub gain_db: f32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SourceKind {
    Display,
    Window,
    Microphone,
    DesktopAudio,
}

impl SourceKind {
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "display" => Some(Self::Display),
            "window" => Some(Self::Window),
            "microphone" => Some(Self::Microphone),
            "desktop_audio" => Some(Self::DesktopAudio),
            _ => None,
        }
    }
}

impl Project {
    pub fn new() -> Self {
        Self {
            version: PROJECT_VERSION,
            next_id: 2,
            active_scene_id: 1,
            scenes: vec![Scene {
                id: 1,
                name: "Scene 1".into(),
                sources: Vec::new(),
            }],
        }
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.version != PROJECT_VERSION {
            return Err(format!("unsupported project version: {}", self.version));
        }
        if self.scenes.is_empty() {
            return Err("project has no scenes".into());
        }
        let mut ids = HashSet::new();
        let mut scene_names = HashSet::new();
        let mut maximum = 0;
        for scene in &self.scenes {
            validate_name(&scene.name)?;
            if !scene_names.insert(scene.name.to_lowercase()) {
                return Err("duplicate scene name".into());
            }
            if scene.id == 0 || !ids.insert(scene.id) {
                return Err("invalid or duplicate scene ID".into());
            }
            maximum = maximum.max(scene.id);
            let mut source_names = HashSet::new();
            for source in &scene.sources {
                validate_name(&source.name)?;
                if !source_names.insert(source.name.to_lowercase()) {
                    return Err("duplicate source name in scene".into());
                }
                if source.id == 0 || !ids.insert(source.id) {
                    return Err("invalid or duplicate source ID".into());
                }
                maximum = maximum.max(source.id);
                if source.selector.trim().is_empty() || source.selector.len() > 512 {
                    return Err("source selector must contain 1 to 512 bytes".into());
                }
                if !source.gain_db.is_finite() || !(-96.0..=12.0).contains(&source.gain_db) {
                    return Err("source gain must be between -96 and +12 dB".into());
                }
            }
        }
        if !self
            .scenes
            .iter()
            .any(|scene| scene.id == self.active_scene_id)
        {
            return Err("active scene does not exist".into());
        }
        if self.next_id <= maximum {
            return Err("next ID must exceed existing IDs".into());
        }
        Ok(())
    }

    pub fn add_scene(&mut self, name: &str) -> Result<u64, String> {
        validate_name(name)?;
        if self
            .scenes
            .iter()
            .any(|scene| scene.name.eq_ignore_ascii_case(name))
        {
            return Err("scene name already exists".into());
        }
        let id = self.take_id()?;
        self.scenes.push(Scene {
            id,
            name: name.into(),
            sources: Vec::new(),
        });
        Ok(id)
    }

    pub fn select_scene(&mut self, scene_id: u64) -> Result<(), String> {
        if !self.scenes.iter().any(|scene| scene.id == scene_id) {
            return Err("scene ID not found".into());
        }
        self.active_scene_id = scene_id;
        Ok(())
    }

    pub fn rename_scene(&mut self, scene_id: u64, name: &str) -> Result<(), String> {
        validate_name(name)?;
        if self.scenes.iter().any(|scene| scene.id != scene_id && scene.name.eq_ignore_ascii_case(name)) {
            return Err("scene name already exists".into());
        }
        let scene = self.scenes.iter_mut().find(|scene| scene.id == scene_id).ok_or("scene ID not found")?;
        scene.name = name.into();
        Ok(())
    }

    pub fn remove_scene(&mut self, scene_id: u64) -> Result<(), String> {
        if self.scenes.len() == 1 {
            return Err("a project needs at least one scene".into());
        }
        let index = self.scenes.iter().position(|scene| scene.id == scene_id).ok_or("scene ID not found")?;
        self.scenes.remove(index);
        if self.active_scene_id == scene_id {
            self.active_scene_id = self.scenes[0].id;
        }
        Ok(())
    }

    pub fn add_source(
        &mut self,
        scene_id: u64,
        name: &str,
        kind: SourceKind,
        selector: &str,
    ) -> Result<u64, String> {
        validate_name(name)?;
        if selector.trim().is_empty() || selector.len() > 512 {
            return Err("source selector must contain 1 to 512 bytes".into());
        }
        let scene_index = self
            .scenes
            .iter()
            .position(|scene| scene.id == scene_id)
            .ok_or("scene ID not found")?;
        if self.scenes[scene_index]
            .sources
            .iter()
            .any(|source| source.name.eq_ignore_ascii_case(name))
        {
            return Err("source name already exists in scene".into());
        }
        let id = self.take_id()?;
        self.scenes[scene_index].sources.push(Source {
            id,
            name: name.into(),
            kind,
            selector: selector.into(),
            visible: true,
            muted: false,
            gain_db: 0.0,
        });
        Ok(id)
    }

    pub fn set_audio(&mut self, source_id: u64, muted: bool, gain_db: f32) -> Result<(), String> {
        if !gain_db.is_finite() || !(-96.0..=12.0).contains(&gain_db) {
            return Err("gain must be between -96 and +12 dB".into());
        }
        let source = self
            .scenes
            .iter_mut()
            .flat_map(|scene| &mut scene.sources)
            .find(|source| source.id == source_id)
            .ok_or("source ID not found")?;
        if !matches!(
            source.kind,
            SourceKind::Microphone | SourceKind::DesktopAudio
        ) {
            return Err("source is not an audio input".into());
        }
        source.muted = muted;
        source.gain_db = gain_db;
        Ok(())
    }

    pub fn edit_source(&mut self, source_id: u64, name: &str, selector: &str, visible: bool) -> Result<(), String> {
        validate_name(name)?;
        if selector.trim().is_empty() || selector.len() > 512 {
            return Err("source selector must contain 1 to 512 bytes".into());
        }
        let scene = self.scenes.iter_mut().find(|scene| scene.sources.iter().any(|source| source.id == source_id)).ok_or("source ID not found")?;
        if scene.sources.iter().any(|source| source.id != source_id && source.name.eq_ignore_ascii_case(name)) {
            return Err("source name already exists in scene".into());
        }
        let source = scene.sources.iter_mut().find(|source| source.id == source_id).expect("source located above");
        source.name = name.into();
        source.selector = selector.into();
        source.visible = visible;
        Ok(())
    }

    pub fn remove_source(&mut self, source_id: u64) -> Result<(), String> {
        let scene = self.scenes.iter_mut().find(|scene| scene.sources.iter().any(|source| source.id == source_id)).ok_or("source ID not found")?;
        scene.sources.retain(|source| source.id != source_id);
        Ok(())
    }

    fn take_id(&mut self) -> Result<u64, String> {
        let next = self
            .next_id
            .checked_add(1)
            .ok_or("project ID space exhausted")?;
        let id = self.next_id;
        self.next_id = next;
        Ok(id)
    }
}

fn validate_name(name: &str) -> Result<(), String> {
    if name.trim().is_empty() || name.len() > 128 || name.chars().any(char::is_control) {
        return Err("name must contain 1 to 128 bytes without control characters".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scene_source_and_audio_survive_json_round_trip() -> Result<(), Box<dyn std::error::Error>> {
        let mut project = Project::new();
        let scene = project.add_scene("Game")?;
        project.select_scene(scene)?;
        let microphone = project.add_source(scene, "Voice", SourceKind::Microphone, "default")?;
        project.set_audio(microphone, true, -6.0)?;
        let encoded = serde_json::to_vec(&project)?;
        let restored: Project = serde_json::from_slice(&encoded)?;
        restored.validate()?;
        assert_eq!(restored.active_scene_id, scene);
        assert_eq!(restored.scenes[1].sources[0].gain_db, -6.0);
        assert!(restored.scenes[1].sources[0].muted);
        Ok(())
    }

    #[test]
    fn invalid_ids_and_gain_are_rejected() {
        let mut project = Project::new();
        project.next_id = 1;
        assert!(project.validate().is_err());
        project.next_id = 2;
        assert!(project.set_audio(999, false, f32::NAN).is_err());
    }

    #[test]
    fn scene_and_source_edits_keep_project_valid() {
        let mut project = Project::new();
        let second = project.add_scene("Game").unwrap();
        let source = project.add_source(second, "Display", SourceKind::Display, "primary").unwrap();
        project.rename_scene(second, "Gameplay").unwrap();
        project.edit_source(source, "Main display", "monitor-1", false).unwrap();
        assert!(!project.scenes[1].sources[0].visible);
        assert!(project.edit_source(source, "", "monitor-1", false).is_err());
        assert_eq!(project.scenes[1].sources[0].name, "Main display");
        project.remove_source(source).unwrap();
        project.select_scene(second).unwrap();
        project.remove_scene(second).unwrap();
        assert_eq!(project.active_scene_id, 1);
        assert!(project.remove_scene(1).is_err());
        project.validate().unwrap();
    }
}

