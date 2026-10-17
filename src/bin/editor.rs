use eframe::egui::{self, Color32, RichText};
use std::path::PathBuf;
use streamstrike::{SourceKind, editor::EditorDocument};

#[derive(Clone)]
enum Pending {
    New,
    Open,
    Close,
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
    confirm_delete: Option<bool>,
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

    fn report(&mut self, result: Result<(), String>, success: &str) {
        self.message = Some(match result { Ok(()) => success.into(), Err(error) => format!("Could not complete action: {error}") });
    }

    fn save_as(&mut self) -> bool {
        let Some(path) = rfd::FileDialog::new().add_filter("StreamStrike project", &["streamstrike"]).set_file_name("untitled.streamstrike").save_file() else { return false; };
        let path = path.with_extension("streamstrike");
        let result = self.document.save_as(&path);
        let ok = result.is_ok();
        self.report(result, "Project saved");
        ok
    }

    fn save(&mut self) -> bool {
        if self.document.path.is_none() { return self.save_as(); }
        let result = self.document.save();
        let ok = result.is_ok();
        self.report(result, "Project saved");
        ok
    }

    fn request(&mut self, action: Pending, ctx: &egui::Context) {
        if self.document.is_dirty() {
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
        if ui.add_enabled(self.document.project.scenes.len() > 1, egui::Button::new("Delete scene.")).clicked() { self.confirm_delete = Some(true); }
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
                let (name, selector, visible, muted, gain, kind) = (self.source_name.trim().to_owned(), self.selector.trim().to_owned(), self.visible, self.muted, self.gain_db, self.source_kind);
                let result = self.document.apply(|project| { project.edit_source(id, &name, &selector, visible)?; if matches!(kind, SourceKind::Microphone | SourceKind::DesktopAudio) { project.set_audio(id, muted, gain)?; } Ok(()) });
                self.report(result, "Source updated");
            }
            if ui.button("Delete source.").clicked() { self.confirm_delete = Some(false); }
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
        if let Some(scene) = self.confirm_delete {
            egui::Window::new(if scene { "Delete scene?" } else { "Delete source?" }).collapsible(false).resizable(false).show(ctx, |ui| {
                ui.label("This removes the item from the project. Save to keep the change.");
                ui.horizontal(|ui| {
                    if ui.button("Delete").clicked() {
                        let result = if scene {
                            let id = self.document.project.active_scene_id;
                            self.document.apply(|project| project.remove_scene(id))
                        } else {
                            self.document.apply(|project| project.remove_source(self.selected_source.expect("source selected")))
                        };
                        self.report(result, "Item deleted");
                        self.selected_source = None;
                        self.sync_selection();
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
                if self.document.is_dirty() { ui.label(RichText::new("? Unsaved").color(Color32::from_rgb(242, 176, 85))); }
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

