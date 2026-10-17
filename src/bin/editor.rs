use eframe::egui::{self, Color32, RichText};
use std::path::PathBuf;
use streamstrike::{SourceKind, editor::EditorDocument};

#[derive(Clone)]
enum Pending {
    New,
    Open,
    Close,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum DeleteTarget {
    Scene { id: u64, name: String },
    Source { scene_id: u64, id: u64, name: String },
}

struct EditorApp {
    document: EditorDocument,
    selected_source: Option<u64>,
    scene_name: String,
    source_name: String,
    selector: String,
    source_kind: SourceKind,
    visible: bool,
    muted: bool,
    gain_db: f32,
    new_scene_name: String,
    new_source_name: String,
    new_selector: String,
    new_kind: SourceKind,
    message: Option<String>,
    pending: Option<Pending>,
    confirm_delete: Option<DeleteTarget>,
    about: bool,
    about_logo: Option<egui::TextureHandle>,
    capture: Option<PathBuf>,
    frames: u32,
    allow_close: bool,
}

impl EditorApp {
    fn new(document: EditorDocument, capture: Option<PathBuf>) -> Self {
        let mut app = Self {
            document,
            selected_source: None,
            scene_name: String::new(),
            source_name: String::new(),
            selector: String::new(),
            source_kind: SourceKind::Display,
            visible: true,
            muted: false,
            gain_db: 0.0,
            new_scene_name: String::new(),
            new_source_name: String::new(),
            new_selector: String::new(),
            new_kind: SourceKind::Display,
            message: None,
            pending: None,
            confirm_delete: None,
            about: false,
            about_logo: None,
            capture,
            frames: 0,
            allow_close: false,
        };
        app.sync_selection();
        app
    }

    fn active_scene(&self) -> Option<&streamstrike::Scene> {
        self.document.project.scenes.iter().find(|scene| scene.id == self.document.project.active_scene_id)
    }

    fn sync_selection(&mut self) {
        self.scene_name = self.active_scene().map(|scene| scene.name.clone()).unwrap_or_default();
        self.sync_source_selection();
    }

    fn sync_source_selection(&mut self) {
        let source = self.active_scene().and_then(|scene| scene.sources.iter().find(|source| Some(source.id) == self.selected_source)).cloned();
        if let Some(source) = source {
            self.source_name = source.name.clone();
            self.selector = source.selector.clone();
            self.source_kind = source.kind;
            self.visible = source.visible;
            self.muted = source.muted;
            self.gain_db = source.gain_db;
        } else {
            self.selected_source = None;
            self.source_name.clear();
            self.selector.clear();
        }
    }

    fn selected_delete_target(&self) -> Option<DeleteTarget> {
        let scene = self.active_scene()?;
        let source = scene.sources.iter().find(|source| Some(source.id) == self.selected_source)?;
        Some(DeleteTarget::Source { scene_id: scene.id, id: source.id, name: source.name.clone() })
    }

    fn delete_target(&mut self, target: &DeleteTarget) -> Result<(), String> {
        let active_before = self.document.project.active_scene_id;
        self.document.apply(|project| match target {
            DeleteTarget::Scene { id, name } => {
                let scene = project.scenes.iter().find(|scene| scene.id == *id).ok_or("scene no longer exists")?;
                if scene.name != *name { return Err("scene changed since confirmation opened".into()); }
                project.remove_scene(*id)
            }
            DeleteTarget::Source { scene_id, id, name } => {
                let scene = project.scenes.iter().find(|scene| scene.id == *scene_id).ok_or("scene no longer exists")?;
                let source = scene.sources.iter().find(|source| source.id == *id).ok_or("source no longer exists")?;
                if source.name != *name { return Err("source changed since confirmation opened".into()); }
                project.remove_source(*id)
            }
        })?;
        if self.document.project.active_scene_id != active_before {
            self.selected_source = None;
            self.sync_selection();
        } else if matches!(target, DeleteTarget::Source { id, .. } if self.selected_source == Some(*id)) {
            self.selected_source = None;
            self.sync_source_selection();
        }
        Ok(())
    }

    fn report(&mut self, result: Result<(), String>, success: &str) {
        self.message = Some(match result { Ok(()) => success.into(), Err(error) => format!("Could not complete action: {error}") });
    }

    fn form_dirty(&self) -> bool {
        let Some(scene) = self.active_scene() else { return false; };
        if self.scene_name != scene.name { return true; }
        scene.sources.iter().find(|source| Some(source.id) == self.selected_source).is_some_and(|source| {
            self.source_name != source.name || self.selector != source.selector || self.visible != source.visible
                || self.muted != source.muted || self.gain_db != source.gain_db
        })
    }

    fn has_pending_changes(&self) -> bool {
        self.document.is_dirty() || self.form_dirty()
    }

    fn commit_details(&mut self) -> Result<(), String> {
        if !self.form_dirty() { return Ok(()); }
        let (scene_id, scene_name) = (self.document.project.active_scene_id, self.scene_name.trim().to_owned());
        let source = self.selected_source.map(|id| (id, self.source_name.trim().to_owned(), self.selector.trim().to_owned(), self.visible, self.muted, self.gain_db, self.source_kind));
        self.document.apply(|project| {
            project.rename_scene(scene_id, &scene_name)?;
            if let Some((id, name, selector, visible, muted, gain, kind)) = source {
                project.edit_source(id, &name, &selector, visible)?;
                if matches!(kind, SourceKind::Microphone | SourceKind::DesktopAudio) { project.set_audio(id, muted, gain)?; }
            }
            Ok(())
        })?;
        self.sync_selection();
        Ok(())
    }

    fn save_as(&mut self) -> bool {
        if let Err(error) = self.commit_details() { self.message = Some(format!("Could not save: {error}")); return false; }
        let Some(path) = rfd::FileDialog::new().add_filter("StreamStrike project", &["streamstrike"]).set_file_name("untitled.streamstrike").save_file() else { return false; };
        let path = path.with_extension("streamstrike");
        let result = self.document.save_as(&path);
        let ok = result.is_ok();
        self.report(result, "Project saved");
        ok
    }

    fn save(&mut self) -> bool {
        if let Err(error) = self.commit_details() { self.message = Some(format!("Could not save: {error}")); return false; }
        if self.document.path.is_none() { return self.save_as(); }
        let result = self.document.save();
        let ok = result.is_ok();
        self.report(result, "Project saved");
        ok
    }

    fn request(&mut self, action: Pending, ctx: &egui::Context) {
        if self.has_pending_changes() {
            self.pending = Some(action);
        } else {
            self.run_action(action, ctx);
        }
    }

    fn run_action(&mut self, action: Pending, ctx: &egui::Context) {
        match action {
            Pending::New => { self.document = EditorDocument::new(); self.selected_source = None; self.sync_selection(); self.message = Some("New project".into()); }
            Pending::Open => {
                if let Some(path) = rfd::FileDialog::new().add_filter("StreamStrike project", &["streamstrike"]).pick_file() {
                    match EditorDocument::open(&path) {
                        Ok(document) => { self.document = document; self.selected_source = None; self.sync_selection(); self.message = Some("Project opened".into()); }
                        Err(error) => self.message = Some(format!("Could not open project: {error}")),
                    }
                }
            }
            Pending::Close => { self.allow_close = true; ctx.send_viewport_cmd(egui::ViewportCommand::Close); }
        }
    }

    fn shortcut(&mut self, ctx: &egui::Context) {
        let command = egui::Modifiers::COMMAND;
        if ctx.input_mut(|input| input.consume_key(command, egui::Key::N)) { self.request(Pending::New, ctx); }
        if ctx.input_mut(|input| input.consume_key(command, egui::Key::O)) { self.request(Pending::Open, ctx); }
        if ctx.input_mut(|input| input.consume_key(command, egui::Key::S)) { self.save(); }
    }

    fn scene_panel(&mut self, ctx: &egui::Context) {
        egui::SidePanel::left("scenes").resizable(true).default_width(230.0).min_width(175.0).show(ctx, |ui| {
            ui.heading("Scenes");
            ui.label(RichText::new("Choose the scene whose sources you want to edit.").weak().small());
            ui.add_space(12.0);
            let scenes: Vec<_> = self.document.project.scenes.iter().map(|scene| (scene.id, scene.name.clone(), scene.sources.len())).collect();
            for (id, name, count) in scenes {
                if ui.selectable_label(self.document.project.active_scene_id == id, format!("{name}  �  {count}")).clicked() {
                    if let Err(error) = self.commit_details() { self.message = Some(format!("Finish scene or source edits: {error}")); continue; }
                    let result = self.document.apply(|project| project.select_scene(id));
                    self.report(result, "Scene selected");
                    self.selected_source = None;
                    self.sync_selection();
                }
            }
            ui.separator();
            ui.label("New scene");
            ui.text_edit_singleline(&mut self.new_scene_name);
            if ui.button("Add scene").clicked() {
                if let Err(error) = self.commit_details() { self.message = Some(format!("Finish current edits: {error}")); return; }
                let name = self.new_scene_name.trim().to_owned();
                let result = self.document.apply(|project| project.add_scene(&name));
                match result {
                    Ok(id) => { self.new_scene_name.clear(); let result = self.document.apply(|project| project.select_scene(id)); self.report(result, "Scene added"); self.selected_source = None; self.sync_selection(); }
                    Err(error) => self.message = Some(format!("Could not add scene: {error}")),
                }
            }
        });
    }

    fn source_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("Sources");
        ui.label(RichText::new("Selectors are stored in the project. No device is opened.").weak().small());
        ui.add_space(12.0);
        let sources: Vec<_> = self.active_scene().map(|scene| scene.sources.iter().map(|source| (source.id, source.name.clone(), source.kind, source.visible)).collect()).unwrap_or_default();
        if sources.is_empty() { ui.label(RichText::new("No sources in this scene yet.").weak()); }
        for (id, name, kind, visible) in sources {
            let label = format!("{}  {}  �  {}", if visible { "?" } else { "	" }, name, kind_label(kind));
            if ui.selectable_label(self.selected_source == Some(id), label).clicked() {
                if let Err(error) = self.commit_details() { self.message = Some(format!("Finish source edits: {error}")); continue; }
                self.selected_source = Some(id);
                self.sync_selection();
            }
        }
        ui.separator();
        ui.strong("Add source");
        ui.label("Name");
        ui.text_edit_singleline(&mut self.new_source_name);
        ui.label("Type");
        kind_picker(ui, "new_kind", &mut self.new_kind);
        ui.label("Selector");
        ui.text_edit_singleline(&mut self.new_selector);
        ui.label(RichText::new("Enter the intended display, window, or audio device selector.").weak().small());
        if ui.button("Add source").clicked() {
            if let Err(error) = self.commit_details() { self.message = Some(format!("Finish current edits: {error}")); return; }
            let (scene, name, kind, selector) = (self.document.project.active_scene_id, self.new_source_name.trim().to_owned(), self.new_kind, self.new_selector.trim().to_owned());
            match self.document.apply(|project| project.add_source(scene, &name, kind, &selector)) {
                Ok(id) => { self.selected_source = Some(id); self.sync_selection(); self.new_source_name.clear(); self.new_selector.clear(); self.message = Some("Source added".into()); }
                Err(error) => self.message = Some(format!("Could not add source: {error}")),
            }
        }
    }

    fn details_panel(&mut self, ui: &mut egui::Ui) {
        ui.heading("Details");
        ui.add_space(12.0);
        ui.strong("Scene name");
        ui.text_edit_singleline(&mut self.scene_name);
        if ui.button("Rename scene").clicked() {
            let (id, name) = (self.document.project.active_scene_id, self.scene_name.trim().to_owned());
            let result = self.document.apply(|project| project.rename_scene(id, &name));
            self.report(result, "Scene renamed");
        }
        if ui.add_enabled(self.document.project.scenes.len() > 1, egui::Button::new("Delete scene.")).clicked() {
            self.confirm_delete = self.active_scene().map(|scene| DeleteTarget::Scene { id: scene.id, name: scene.name.clone() });
        }
        ui.separator();
        if let Some(id) = self.selected_source {
            ui.strong("Selected source");
            ui.label("Name");
            ui.text_edit_singleline(&mut self.source_name);
            ui.label(format!("Type: {}", kind_label(self.source_kind)));
            ui.label("Selector");
            ui.text_edit_singleline(&mut self.selector);
            ui.checkbox(&mut self.visible, "Visible");
            if matches!(self.source_kind, SourceKind::Microphone | SourceKind::DesktopAudio) {
                ui.checkbox(&mut self.muted, "Muted");
                ui.add(egui::Slider::new(&mut self.gain_db, -96.0..=12.0).text("Gain dB"));
            }
            if ui.button("Apply source changes").clicked() {
                let result = self.commit_details();
                self.report(result, "Source updated");
            }
            if ui.button("Delete source.").clicked() { self.confirm_delete = self.selected_delete_target(); }
        } else {
            ui.label(RichText::new("Select a source to edit its settings.").weak());
        }
    }

    fn dialogs(&mut self, ctx: &egui::Context) {
        if self.pending.is_some() {
            egui::Window::new("Unsaved changes").collapsible(false).resizable(false).show(ctx, |ui| {
                ui.label("Save your project before continuing?");
                ui.horizontal(|ui| {
                    if ui.button("Save").clicked() && self.save() { if let Some(action) = self.pending.take() { self.run_action(action, ctx); } }
                    if ui.button("Discard").clicked() { if let Some(action) = self.pending.take() { self.run_action(action, ctx); } }
                    if ui.button("Cancel").clicked() { self.pending = None; }
                });
            });
        }
        if let Some(target) = self.confirm_delete.clone() {
            let (title, name) = match &target {
                DeleteTarget::Scene { name, .. } => ("Delete scene?", name),
                DeleteTarget::Source { name, .. } => ("Delete source?", name),
            };
            egui::Window::new(title).collapsible(false).resizable(false).show(ctx, |ui| {
                ui.label(format!("Remove "{name}" from this project? Save to keep the change."));
                ui.horizontal(|ui| {
                    if ui.button("Delete").clicked() {
                        let result = self.delete_target(&target);
                        self.report(result, "Item deleted");
                        self.confirm_delete = None;
                    }
                    if ui.button("Cancel").clicked() { self.confirm_delete = None; }
                });
            });
        }
        if self.about {
            if self.about_logo.is_none() {
                if let Ok(bitmap) = image::load_from_memory(include_bytes!("../../assets/branding/PWDS-logo.png")) {
                    let rgba = bitmap.to_rgba8();
                    let size = [rgba.width() as usize, rgba.height() as usize];
                    self.about_logo = Some(ctx.load_texture("pwds-about", egui::ColorImage::from_rgba_unmultiplied(size, rgba.as_raw()), Default::default()));
                }
            }
            egui::Window::new("About StreamStrike").open(&mut self.about).resizable(false).show(ctx, |ui| {
                ui.heading("StreamStrike");
                if let Some(logo) = &self.about_logo { ui.image((logo.id(), egui::vec2(180.0, 77.0))); }
                ui.label("Project and source editor by PWDS");
                ui.label("Scene and source settings are saved locally.");
                ui.label("Capture, recording, and streaming are not available yet.");
            });
        }
    }

    fn screenshot(&mut self, ctx: &egui::Context) {
        let Some(path) = self.capture.clone() else { return; };
        for event in ctx.input(|input| input.events.clone()) {
            if let egui::Event::Screenshot { image, .. } = event {
                let mut pixels = Vec::with_capacity(image.pixels.len() * 4);
                for color in &image.pixels { pixels.extend_from_slice(&color.to_array()); }
                if let Err(error) = image::save_buffer(&path, &pixels, image.size[0] as u32, image.size[1] as u32, image::ColorType::Rgba8) {
                    self.message = Some(format!("Screenshot failed: {error}"));
                } else {
                    self.capture = None;
                    self.allow_close = true;
                    ctx.send_viewport_cmd(egui::ViewportCommand::Close);
                }
            }
        }
        self.frames += 1;
        if self.frames == 12 { ctx.send_viewport_cmd(egui::ViewportCommand::Screenshot(egui::UserData::default())); }
        if self.capture.is_some() { ctx.request_repaint(); }
    }
}

impl eframe::App for EditorApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        if !self.allow_close && ctx.input(|input| input.viewport().close_requested()) {
            ctx.send_viewport_cmd(egui::ViewportCommand::CancelClose);
            if self.pending.is_none() { self.request(Pending::Close, ctx); }
        }
        self.shortcut(ctx);
        egui::TopBottomPanel::top("toolbar").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.heading("StreamStrike");
                ui.separator();
                if ui.button("New").clicked() { self.request(Pending::New, ctx); }
                if ui.button("Open.").clicked() { self.request(Pending::Open, ctx); }
                if ui.button("Save").clicked() { self.save(); }
                if ui.button("Save as.").clicked() { self.save_as(); }
                if ui.button("About").clicked() { self.about = true; }
                if self.has_pending_changes() { ui.label(RichText::new("? Unsaved").color(Color32::from_rgb(242, 176, 85))); }
            });
            ui.label(RichText::new(self.document.path.as_ref().map(|path| path.display().to_string()).unwrap_or_else(|| "Untitled project".into())).weak().small());
        });
        egui::TopBottomPanel::bottom("status").show(ctx, |ui| {
            ui.label(RichText::new("Project setup only  �  Capture, recording, and streaming unavailable").color(Color32::from_rgb(242, 176, 85)));
            if let Some(message) = &self.message { ui.label(message); }
        });
        self.scene_panel(ctx);
        egui::CentralPanel::default().show(ctx, |ui| {
            ui.columns(2, |columns| { self.source_panel(&mut columns[0]); self.details_panel(&mut columns[1]); });
        });
        self.dialogs(ctx);
        self.screenshot(ctx);
    }
}

fn kind_label(kind: SourceKind) -> &'static str {
    match kind { SourceKind::Display => "Display", SourceKind::Window => "Window", SourceKind::Microphone => "Microphone", SourceKind::DesktopAudio => "Desktop audio" }
}

fn kind_picker(ui: &mut egui::Ui, id: &str, kind: &mut SourceKind) {
    egui::ComboBox::from_id_salt(id).selected_text(kind_label(*kind)).show_ui(ui, |ui| {
        for option in [SourceKind::Display, SourceKind::Window, SourceKind::Microphone, SourceKind::DesktopAudio] {
            ui.selectable_value(kind, option, kind_label(option));
        }
    });
}

fn main() -> eframe::Result {
    let mut args = std::env::args().skip(1);
    let mut open = None;
    let mut capture = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--open" => open = args.next().map(PathBuf::from),
            "--capture" => capture = args.next().map(PathBuf::from),
            _ => { eprintln!("usage: streamstrike-editor [--open PROJECT.streamstrike] [--capture OUTPUT.png]"); std::process::exit(2); }
        }
    }
    let document = match open { Some(path) => EditorDocument::open(&path).unwrap_or_else(|error| { eprintln!("cannot open {}: {error}", path.display()); std::process::exit(1); }), None => EditorDocument::new() };
    let options = eframe::NativeOptions { viewport: egui::ViewportBuilder::default().with_inner_size([1160.0, 740.0]).with_min_inner_size([900.0, 560.0]), renderer: eframe::Renderer::Wgpu, ..Default::default() };
    eframe::run_native("StreamStrike", options, Box::new(move |_cc| Ok(Box::new(EditorApp::new(document, capture)))))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn staged_details_are_dirty_and_rejected_atomically() {
        let mut app = EditorApp::new(EditorDocument::new(), None);
        app.scene_name = "Gameplay".into();
        assert!(app.has_pending_changes());
        app.commit_details().unwrap();
        assert_eq!(app.active_scene().unwrap().name, "Gameplay");
        let id = app.document.apply(|project| project.add_source(1, "Display", SourceKind::Display, "primary")).unwrap();
        app.selected_source = Some(id);
        app.sync_selection();
        app.source_name.clear();
        assert!(app.has_pending_changes());
        assert!(app.commit_details().is_err());
        assert_eq!(app.active_scene().unwrap().sources[0].name, "Display");
    }

    #[test]
    fn deletion_uses_original_source_after_scene_or_selection_changes() {
        let mut app = EditorApp::new(EditorDocument::new(), None);
        let first = app.document.apply(|project| project.add_source(1, "First", SourceKind::Display, "primary")).unwrap();
        let second = app.document.apply(|project| project.add_source(1, "Second", SourceKind::Window, "game")).unwrap();
        app.selected_source = Some(first);
        app.sync_selection();
        let target = app.selected_delete_target().unwrap();

        app.selected_source = Some(second);
        app.sync_selection();
        app.delete_target(&target).unwrap();
        assert_eq!(app.selected_source, Some(second));
        assert_eq!(app.active_scene().unwrap().sources.iter().map(|source| source.id).collect::<Vec<_>>(), vec![second]);

        let target = app.selected_delete_target().unwrap();
        let other_scene = app.document.apply(|project| project.add_scene("Other")).unwrap();
        app.document.apply(|project| project.select_scene(other_scene)).unwrap();
        app.selected_source = None;
        app.sync_selection();
        app.scene_name = "Unapplied other scene name".into();
        app.delete_target(&target).unwrap();
        assert_eq!(app.document.project.active_scene_id, other_scene);
        assert_eq!(app.scene_name, "Unapplied other scene name");
        assert!(app.document.project.scenes[0].sources.is_empty());
    }

    #[test]
    fn deletion_preserves_unrelated_staged_scene_name() {
        let mut app = EditorApp::new(EditorDocument::new(), None);
        let id = app.document.apply(|project| project.add_source(1, "Display", SourceKind::Display, "primary")).unwrap();
        app.selected_source = Some(id);
        app.sync_selection();
        let target = app.selected_delete_target().unwrap();
        app.scene_name = "Unapplied scene name".into();
        app.delete_target(&target).unwrap();
        assert_eq!(app.scene_name, "Unapplied scene name");
        assert!(app.form_dirty());
        assert_eq!(app.selected_source, None);
    }

    #[test]
    fn missing_or_changed_target_does_not_delete_another_item() {
        let mut app = EditorApp::new(EditorDocument::new(), None);
        let id = app.document.apply(|project| project.add_source(1, "Display", SourceKind::Display, "primary")).unwrap();
        app.selected_source = Some(id);
        app.sync_selection();
        let target = app.selected_delete_target().unwrap();
        app.document.apply(|project| project.rename_scene(1, "Renamed scene")).unwrap();
        app.document.apply(|project| project.remove_source(id)).unwrap();
        let before = app.document.project.clone();
        assert!(app.delete_target(&target).is_err());
        assert_eq!(app.document.project, before);
        assert!(app.document.is_dirty());
    }

    #[test]
    fn scene_deletion_uses_original_scene_after_switch() {
        let mut app = EditorApp::new(EditorDocument::new(), None);
        let original = app.active_scene().unwrap();
        let target = DeleteTarget::Scene { id: original.id, name: original.name.clone() };
        let second = app.document.apply(|project| project.add_scene("Second")).unwrap();
        app.document.apply(|project| project.select_scene(second)).unwrap();
        app.sync_selection();
        app.scene_name = "Unapplied second name".into();
        app.delete_target(&target).unwrap();
        assert_eq!(app.document.project.active_scene_id, second);
        assert_eq!(app.scene_name, "Unapplied second name");
        assert_eq!(app.document.project.scenes.len(), 1);
    }
}

