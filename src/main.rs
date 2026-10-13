use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::Path;
use streamstrike::{MAX_PROJECT_BYTES, Project, SourceKind};

fn main() {
    match run(std::env::args().skip(1).collect()) {
        Ok(message) => println!("{message}"),
        Err(message) => {
            eprintln!("StreamStrike: {message}");
            std::process::exit(1);
        }
    }
}

fn run(args: Vec<String>) -> Result<String, String> {
    let Some(command) = args.first().map(String::as_str) else {
        return Err(usage());
    };
    match (command, args.len()) {
        ("new", 2) => {
            let path = Path::new(&args[1]);
            create(path, &Project::new())?;
            Ok(format!("created {} with Scene 1 (ID 1)", path.display()))
        }
        ("show", 2) => {
            let project = load(Path::new(&args[1]))?;
            serde_json::to_string_pretty(&project).map_err(|error| error.to_string())
        }
        ("add-scene", 3) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let id = project.add_scene(&args[2])?;
            save(path, &project)?;
            Ok(format!("added scene ID {id}"))
        }
        ("select-scene", 3) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            project.select_scene(parse_id(&args[2])?)?;
            save(path, &project)?;
            Ok(format!("active scene ID {}", project.active_scene_id))
        }
        ("add-source", 6) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let scene_id = parse_id(&args[2])?;
            let kind = SourceKind::parse(&args[4])
                .ok_or("kind must be display, window, microphone, or desktop_audio")?;
            let id = project.add_source(scene_id, &args[3], kind, &args[5])?;
            save(path, &project)?;
            Ok(format!(
                "added source ID {id}; selector is stored but not opened"
            ))
        }
        ("set-audio", 5) => {
            let path = Path::new(&args[1]);
            let mut project = load(path)?;
            let id = parse_id(&args[2])?;
            let muted = args[3]
                .parse::<bool>()
                .map_err(|_| "mute must be true or false")?;
            let gain_db = args[4]
                .parse::<f32>()
                .map_err(|_| "gain must be a number in dB")?;
            project.set_audio(id, muted, gain_db)?;
            save(path, &project)?;
            Ok(format!(
                "stored audio settings for source ID {id}; no audio device is opened"
            ))
        }
        _ => Err(usage()),
    }
}

fn parse_id(text: &str) -> Result<u64, String> {
    let id = text
        .parse::<u64>()
        .map_err(|_| "ID must be a positive integer")?;
    if id == 0 {
        return Err("ID must be a positive integer".into());
    }
    Ok(id)
}

fn load(path: &Path) -> Result<Project, String> {
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

fn create(path: &Path, project: &Project) -> Result<(), String> {
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

fn save(path: &Path, project: &Project) -> Result<(), String> {
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

fn usage() -> String {
    "StreamStrike (source-only project CLI)\nby PWDS\nusage:\n  streamstrike new PATH.streamstrike\n  streamstrike show PATH.streamstrike\n  streamstrike add-scene PATH.streamstrike NAME\n  streamstrike select-scene PATH.streamstrike SCENE_ID\n  streamstrike add-source PATH.streamstrike SCENE_ID NAME KIND SELECTOR\n  streamstrike set-audio PATH.streamstrike SOURCE_ID true|false GAIN_DB\nKIND: display | window | microphone | desktop_audio".into()
}
